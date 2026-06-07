import time
import threading
from pathlib import Path
import json
import requests
from torf import Torrent
from qbittorrent_client import QbittorrentClient
from flac_downsampler import process_album as flac_downsample_album, get_16bit_dir_name, process_mp3_album, get_mp3_dir_name
from lossless_checker import process_album as check_lossless_album
from i18n import _
import traceback

_DEFAULT_SITE_CONFIG = {
    "api_url": "https://redacted.sh/ajax.php",
    "base_url": "https://redacted.sh",
    "tracker_url": "https://flacsfor.me/announce",
    "source": "RED",
}

class PipelineManager:
    def __init__(self, qb_host, qb_port, qb_user, qb_pass, red_session, red_options, log_main=print, log_process=print, log_check=print, ask_manual_check=None):
        self.qb = QbittorrentClient(qb_host, qb_port, qb_user, qb_pass)
        self.red_session = red_session
        self.red_options = red_options
        if not self.red_session and self.red_options:
            from redacted_session import RedactedSession
            self.red_session = RedactedSession.from_options(self.red_options)
        self.log_main = log_main
        self.log_process = log_process
        self.log_check = log_check
        self.ask_manual_check = ask_manual_check
        self.is_running = False
        self.monitor_thread = None
        self.tracked_torrents = {} # hash -> dict(group_info, torrent_info)
        self.processed_hashes = set()
        
        import core.globals
        self.db = core.globals.app_context.db if core.globals.app_context else None
        
        if self.db:
            rows = self.db.fetch_all("SELECT hash FROM pipeline_processed")
            for r in rows:
                self.processed_hashes.add(r['hash'])
                
        self.cache_file = Path("pipeline_cache.json")
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding='utf-8') as f:
                    old_hashes = json.load(f)
                for h in old_hashes:
                    self.processed_hashes.add(h)
                    if self.db:
                        self.db.execute("INSERT OR IGNORE INTO pipeline_processed (hash) VALUES (?)", (h,))
                self.cache_file.unlink(missing_ok=True)
            except Exception:
                pass

    def start(self):
        if self.is_running: return
        self.is_running = True
        self.log_main(_("log_pipeline_started"))
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        self.is_running = False
        self.log_main(_("log_pipeline_stopped"))

    def add_to_pipeline(self, torrent_path, group_info, torrent_info, save_path):
        """将种子添加到 qB 并加入追踪列表"""
        success = self.qb.add_torrent(torrent_path, save_path=save_path, category="red_auto")
        if success:
            self.log_main(_("log_push_qb_success").format(name=Path(torrent_path).name))
        else:
            self.log_main(_("log_push_qb_fail").format(name=Path(torrent_path).name))

    def _monitor_loop(self):
        while self.is_running:
            try:
                torrents = self.qb.get_torrents(category="red_auto")
                for t in torrents:
                    hash_str = t.get("hash")
                    progress = t.get("progress", 0)
                    state = t.get("state", "")
                    name = t.get("name", "Unknown")
                    save_path = t.get("save_path", "")
                    
                    # 当进度 100% 且不处于错误状态时触发后处理
                    if progress == 1 and state in ["uploading", "stalledUP", "pausedUP"]:
                        if hash_str in self.processed_hashes:
                            continue
                            
                        self.processed_hashes.add(hash_str)
                        if self.db:
                            self.db.execute("INSERT OR IGNORE INTO pipeline_processed (hash) VALUES (?)", (hash_str,))
                        self.log_main(_("log_dl_complete_ready").format(name=name))
                        
                        # 启动异步任务处理，避免阻塞轮询
                        threading.Thread(target=self._process_downloaded_torrent, args=(save_path, name, t), daemon=True).start()

            except Exception as e:
                self.log_main(_("log_monitor_exception").format(e=e))
                
            time.sleep(10) # 每 10 秒轮询一次

    def _change_category(self, torrent_hash, new_category):
        return self.qb.set_category(torrent_hash, new_category)

    # ------------------------------------------------------------------
    # 手动入队接口（供 Pipeline 标签页调用）
    # ------------------------------------------------------------------

    def queue_folder_for_processing(self, folder_path: str, on_status_change=None, json_path: str = None):
        """
        将一个本地已下载完成的音乐目录手动加入流水线处理。
        不经过 qBittorrent，直接执行：降频 → 无损检查 → 上传。

        Parameters
        ----------
        folder_path : str
            音乐目录的完整路径（例如 /data/Artist - Album [24bit]）
        on_status_change : callable(status: str) | None
            状态变更回调，参数为字符串：'processing' / 'done' / 'failed'
        json_path : str | None
            可选的 .json 元数据文件路径，用于自动上传
        """
        album_dir = Path(folder_path)
        if not album_dir.exists() or not album_dir.is_dir():
            self.log_process(_("log_album_dir_not_found").format(album_dir=album_dir))
            if on_status_change:
                on_status_change("failed")
            return

        self.log_main(f">>> [手动入队] 开始处理本地目录: {album_dir.name}")
        if on_status_change:
            on_status_change("processing")

        def _run():
            try:
                self._process_downloaded_torrent(album_dir.parent, album_dir.name, None, manual_json_path=json_path)
                if on_status_change:
                    on_status_change("done")
            except Exception as e:
                self.log_process(f"[手动入队] 处理异常: {e}")
                if on_status_change:
                    on_status_change("failed")

        threading.Thread(target=_run, daemon=True).start()

    def push_torrent_to_qb(self, torrent_path: str, save_path: str, on_status_change=None):
        """
        将一个 .torrent 文件推送到 qBittorrent（分类 red_auto），
        下载完成后 monitor loop 会自动触发后处理流程。

        若同目录下存在同名 .json 元数据文件，会自动被 pipeline 找到并用于上传。

        Parameters
        ----------
        torrent_path : str
            .torrent 文件路径
        save_path : str
            qBittorrent 下载保存路径
        on_status_change : callable(status: str) | None
            状态变更回调
        """
        path = Path(torrent_path)
        if not path.exists():
            self.log_main(f"[手动入队] 种子文件不存在: {torrent_path}")
            if on_status_change:
                on_status_change("failed")
            return

        if on_status_change:
            on_status_change("queued_in_qb")

        success = self.qb.add_torrent(torrent_path, save_path=save_path, category="red_auto")
        if success:
            self.log_main(f"[手动入队] 已推送到 qBittorrent，等待下载完成: {path.name}")
            if on_status_change:
                on_status_change("downloading")
        else:
            self.log_main(f"[手动入队] 推送 qBittorrent 失败: {path.name}")
            if on_status_change:
                on_status_change("failed")

    def process_local_directory(self, dir_path: str):
        """外部触发的直接处理本地目录入口 (用于发现模块下载后的处理) — 兼容旧接口"""
        album_dir = Path(dir_path)
        if not album_dir.exists() or not album_dir.is_dir():
            self.log_process(_("log_album_dir_not_found").format(album_dir=album_dir))
            return
            
        self.log_main(f">>> 开始处理本地目录: {album_dir.name}")
        # 内部复用 _process_downloaded_torrent，传入 None 作为 qb_torrent_info 标识为本地处理
        threading.Thread(target=self._process_downloaded_torrent, args=(album_dir.parent, album_dir.name, None), daemon=True).start()

    def _process_downloaded_torrent(self, save_path, name, qb_torrent_info, manual_json_path=None):
        try:
            site_config = getattr(self.red_options, 'site_config', _DEFAULT_SITE_CONFIG)
            base_url = site_config["base_url"]
            api_url = site_config["api_url"]
            album_dir = Path(save_path) / name
            if not album_dir.exists() or not album_dir.is_dir():
                self.log_process(_("log_album_dir_not_found").format(album_dir=album_dir))
                return

            output_dir_name = get_16bit_dir_name(album_dir.name)
            output_dir = album_dir.parent / output_dir_name
            generated_torrent = album_dir.parent / f"{output_dir.name}.torrent"
            
            # 如果降频目录和种子文件都已经存在，则跳过降频和检测阶段
            if output_dir.exists() and generated_torrent.exists():
                self.log_process(_("log_skip_downsample_check"))
            else:
                self.log_process(_("log_start_downsample").format(name=name))
                tracker_url = site_config.get("tracker_url", "https://flacsfor.me/announce")
                source_flag = site_config.get("source", "RED")
                # 实际的 process_album 会搜索 flac，并生成 16bit 目录
                flac_downsample_album(album_dir, tracker_url, source_flag) 
                
                # 找到生成的 16bit 目录
                if not output_dir.exists():
                    self.log_process(_("log_downsample_no_16bit").format(name=name))
                    raise Exception(_("err_downsample_no_16bit"))

                self.log_check(_("log_start_lossless_check").format(name=output_dir.name))
                # 2. 检查无损 (Fast Mode)，此步骤现由 AAFS 接管

                is_lossless = check_lossless_album(output_dir, fast_mode=True)
                if not is_lossless:
                    self.log_check(_("log_lossless_fail").format(name=output_dir.name))
                    if self.ask_manual_check:
                        self.log_check(_("log_wait_manual_confirm").format(name=output_dir.name))
                        user_confirmed = self.ask_manual_check(output_dir.name)
                        if not user_confirmed:
                            self.log_check(_("log_manual_confirm_fail").format(name=output_dir.name))
                            if qb_torrent_info:
                                self._mark_failed(qb_torrent_info)
                            return
                        self.log_check(_("log_manual_confirm_pass").format(name=output_dir.name))
                    else:
                        self.log_check(_("log_no_manual_confirm_configured").format(name=output_dir.name))
                        self._mark_failed(qb_torrent_info)
                        return
                
            self.log_check(_("log_lossless_pass_uploading").format(name=output_dir.name))
            
            ignore_mp3_exists = getattr(self.red_options, 'ignore_mp3_exists', False)
            if ignore_mp3_exists:
                self.log_process(f"    [Pipeline] 正在进行 MP3 (320k/V0) 转码...")
                process_mp3_album(album_dir, tracker_url, source_flag)

            # 3. 自动上传 (从本地 .json 恢复 Context)
            json_meta_path = None
            if manual_json_path and Path(manual_json_path).exists():
                json_meta_path = Path(manual_json_path)
            else:
                hash_str_lower = qb_torrent_info.get("hash", "").lower() if qb_torrent_info else ""
                
                # 必须去 elitetmhelper 原本设定的下载目录里找，而不是 qb 的保存目录
                original_save_dir = Path(self.red_options.save_path) if self.red_options.save_path else Path(".")
                
                for tf in original_save_dir.glob('*.torrent'):
                    try:
                        t_obj = Torrent.read(str(tf))
                        if t_obj.infohash.lower() == hash_str_lower:
                            candidate_json = tf.with_suffix('.json')
                            if candidate_json.exists():
                                json_meta_path = candidate_json
                                break
                    except Exception:
                        pass
            
            if not json_meta_path:
                self.log_main(_("log_no_meta_file").format(hash=hash_str_lower))
                self._mark_failed(qb_torrent_info)
                return
                
            with open(json_meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                
            group_info = meta['group_info']
            torrent_info = meta['torrent_info']
            
            group_id = group_info['response']['group']['id']
            torrent_id = torrent_info.get('torrentId', torrent_info.get('id'))
            
            # 构造多个上传任务 (FLAC 16-bit, MP3 320, MP3 V0)
            source_link = f"{base_url}/torrents.php?id={group_id}&torrentid={torrent_id}"
            uploads = []
            
            generated_torrent = album_dir.parent / f"{output_dir.name}.torrent"
            if generated_torrent.exists():
                uploads.append({
                    'format': 'FLAC',
                    'bitrate': 'Lossless',
                    'desc_prefix': "16-bit downsample created from the 24-bit source.",
                    'torrent_path': generated_torrent,
                    'dir_name': output_dir.name
                })
            else:
                self.log_main(_("log_no_generated_torrent").format(name=generated_torrent.name))
                self._mark_failed(qb_torrent_info)
                return
                
            if ignore_mp3_exists:
                for fmt, bitrate in [("320", "320"), ("V0", "V0 (VBR)")]:
                    mp3_dir_name = get_mp3_dir_name(album_dir.name, fmt)
                    mp3_torrent = album_dir.parent / f"{mp3_dir_name}.torrent"
                    if mp3_torrent.exists():
                        uploads.append({
                            'format': 'MP3',
                            'bitrate': bitrate,
                            'desc_prefix': f"MP3 {fmt} created from the 24-bit source.",
                            'torrent_path': mp3_torrent,
                            'dir_name': mp3_dir_name
                        })

            # 携带 Remaster 信息以保持与原种子同一 Edition
            # 由于 search API 的 torrent_info 可能缺少 record label 等信息，我们需要从 group_info 里面找出对应的完整的 torrent 字典
            full_torrent_info = torrent_info
            for t in group_info['response']['torrents']:
                if t['id'] == torrent_id:
                    full_torrent_info = t
                    break

            is_remastered = (
                full_torrent_info.get('remastered') is True or 
                (full_torrent_info.get('remasterYear') not in (None, 0, '')) or
                bool(full_torrent_info.get('remasterTitle')) or 
                bool(full_torrent_info.get('remasterRecordLabel')) or 
                bool(full_torrent_info.get('remasterCatalogueNumber'))
            )
            
            remaster_data = {}
            if is_remastered:
                remaster_data['remaster'] = 'true'
                r_year = full_torrent_info.get('remasterYear')
                if not r_year:
                    r_year = group_info['response']['group'].get('year', '')
                remaster_data['remaster_year'] = str(r_year)
                remaster_data['remaster_title'] = str(full_torrent_info.get('remasterTitle') or '')
                r_label = full_torrent_info.get('remasterRecordLabel') or group_info['response']['group'].get('recordLabel', '')
                r_cat = full_torrent_info.get('remasterCatalogueNumber') or group_info['response']['group'].get('catalogueNumber', '')
                remaster_data['remaster_record_label'] = str(r_label)
                remaster_data['remaster_catalogue_number'] = str(r_cat)

            # 执行循环上传
            site_source = site_config.get("source", "RED")
            if site_source in ["JPS", "DIC"]:
                upload_url = f"{base_url}/upload.php"
            else:
                upload_url = f"{api_url}?action=upload"

            auth_key = self.red_options.api_key
            auth_type = site_config.get("auth_type", "api_key")
            if auth_type == "cookie":
                if "=" not in auth_key:
                    if site_config.get("source") in ["JPS", "DIC"]:
                        auth_key = f"PHPSESSID={auth_key}"
                    else:
                        auth_key = f"session={auth_key}"
                headers = {
                    'Cookie': auth_key,
                    'User-Agent': 'EliteTMHelper_AutoUpload'
                }
            else:
                if site_config.get("source") == "OPS" and not auth_key.startswith("token "):
                    auth_key = f"token {auth_key}"
                headers = {
                    'Authorization': auth_key,
                    'User-Agent': 'EliteTMHelper_AutoUpload'
                }
            
            for idx, up in enumerate(uploads):
                if idx > 0:
                    self.log_main("    [Pipeline] 等待 4 秒以防触发 API 频率限制...")
                    time.sleep(4)
                    
                upload_data = {
                    'submit': 'true',
                    'type': '0', # Music
                    'groupid': str(group_id),
                    'format': up['format'],
                    'bitrate': up['bitrate'],
                    'media': torrent_info.get('media', 'WEB'),
                    'release_desc': f"{up['desc_prefix']}\n\n[url={source_link}]24-bit source[/url]"
                }
                upload_data.update(remaster_data)

                self.log_main(f"    [Pipeline] 正在发布: {up['dir_name']} ({up['format']} / {up['bitrate']})")
                with open(up['torrent_path'], 'rb') as f:
                    files = {'file_input': (up['torrent_path'].name, f, 'application/x-bittorrent')}
                    if self.red_session:
                        resp = self.red_session.post(upload_url, data=upload_data, files=files, timeout=30)
                    else:
                        resp = requests.post(upload_url, headers=headers, data=upload_data, files=files, timeout=30)
                    
                if resp.status_code == 200:
                    if site_source in ["JPS", "DIC"]:
                        import re
                        match = re.search(r'torrentid=(\d+)', resp.url)
                        if match:
                            new_torrent_id = match.group(1)
                            group_match = re.search(r'id=(\d+)', resp.url)
                            if group_match:
                                group_id = group_match.group(1)
                            new_link = f"{base_url}/torrents.php?id={group_id}&torrentid={new_torrent_id}"
                            self.log_main(_("log_upload_success"))
                            self.log_main(_("log_new_torrent_link").format(link=new_link))
                            
                            self.log_main(_("log_dl_official_torrent").format(source=site_config.get("source", "RED")))
                            base_url = site_config.get("base_url", api_url.replace("/ajax.php", ""))
                            dl_url = f"{base_url}/torrents.php?action=download&id={new_torrent_id}"
                            
                            if self.red_session:
                                dl_resp = self.red_session.get(dl_url, timeout=30)
                            else:
                                dl_resp = requests.get(dl_url, headers=headers, timeout=30)
                            
                            if dl_resp.status_code == 200 and b'd8:announce' in dl_resp.content[:50]:
                                official_torrent = album_dir.parent / f"{up['dir_name']}_official.torrent"
                                official_torrent.write_bytes(dl_resp.content)
                                
                                self.log_process(_("log_add_official_to_qb"))
                                self.qb.add_torrent(str(official_torrent), save_path=str(album_dir.parent), category="red_seeding")
                            else:
                                self.log_main(_("log_dl_official_fail"))
                        else:
                            self.log_main(f"    [Pipeline] ❌ 上传失败，未成功跳转到种子页面。当前页面: {resp.url}")
                            error_match = re.search(r'<p[^>]*class="warning"[^>]*>(.*?)</p>', resp.text, re.DOTALL)
                            if not error_match:
                                error_match = re.search(r'<p[^>]*style="color:\s*red;?"[^>]*>(.*?)</p>', resp.text, re.DOTALL)
                            if error_match:
                                err_text = re.sub('<[^<]+?>', '', error_match.group(1)).strip()
                                self.log_main(f"    [Pipeline] 错误提示: {err_text}")
                            else:
                                self.log_main(f"    [Pipeline] 响应前 500 字符: {resp.text[:500]}")
                            if idx == 0: self._mark_failed(qb_torrent_info)
                            break
                    else:
                        try:
                            resp_json = resp.json()
                            if resp_json.get('status') == 'success':
                                new_torrent_id = resp_json['response'].get('torrentid') or resp_json['response'].get('torrentId')
                                new_link = f"{base_url}/torrents.php?id={group_id}&torrentid={new_torrent_id}"
                                self.log_main(_("log_upload_success"))
                                self.log_main(_("log_new_torrent_link").format(link=new_link))
                                
                                self.log_main(_("log_dl_official_torrent").format(source=site_config.get("source", "RED")))
                                if site_config.get("source") in ["DIC", "JPS"]:
                                    base_url = site_config.get("base_url", api_url.replace("/ajax.php", ""))
                                    dl_url = f"{base_url}/torrents.php?action=download&id={new_torrent_id}"
                                else:
                                    dl_url = f"{api_url}?action=download&id={new_torrent_id}"
                                
                                if self.red_session:
                                    dl_resp = self.red_session.get(dl_url, timeout=30)
                                else:
                                    dl_resp = requests.get(dl_url, headers=headers, timeout=30)
                                
                                if dl_resp.status_code == 200 and b'd8:announce' in dl_resp.content[:50]:
                                    official_torrent = album_dir.parent / f"{up['dir_name']}_official.torrent"
                                    official_torrent.write_bytes(dl_resp.content)
                                    
                                    self.log_process(_("log_add_official_to_qb"))
                                    self.qb.add_torrent(str(official_torrent), save_path=str(album_dir.parent), category="red_seeding")
                                else:
                                    self.log_main(_("log_dl_official_fail"))
                                    
                            else:
                                self.log_main(_("log_upload_api_fail").format(resp=resp_json))
                                if idx == 0: self._mark_failed(qb_torrent_info)
                                break
                        except Exception as e:
                            self.log_main(_("log_upload_json_parse_fail").format(e=e, text=resp.text[:200]))
                            if idx == 0: self._mark_failed(qb_torrent_info)
                            break
                else:
                    self.log_main(_("log_upload_http_fail").format(code=resp.status_code))
                    self.log_main(f"    [Pipeline] {resp.text[:500]}")
                    if idx == 0: self._mark_failed(qb_torrent_info)
                    break
                    
            # 全部上传循环结束后，无论后面 MP3 成功与否，只要处理完毕就标记为已处理。
            if qb_torrent_info:
                self._change_category(qb_torrent_info.get("hash"), "red_processed")
            
        except Exception as e:
            self.log_process(_("log_pipeline_exception").format(e=e))
            self.log_main(_("log_pipeline_exception").format(e=e))
            traceback.print_exc()
            if qb_torrent_info:
                self._mark_failed(qb_torrent_info)

    def process_discovery_upload(self, folder_path, meta_info):
        """
        处理 Discovery 模块下载的本地目录，
        跳过 qBittorrent 交互，直接执行全新上传流程。

        注意: 与 process_local_directory() 不同，
        此方法用于从未发布过的全新专辑，需要提供完整的元数据。
        """
        if not isinstance(folder_path, Path):
            folder_path = Path(folder_path)
            
        self.log_main(f">>> 开始处理 Discovery 下载目录: {folder_path.name}")
        threading.Thread(target=self._process_discovery_upload, args=(folder_path, meta_info), daemon=True).start()

    def _process_discovery_upload(self, album_dir, meta_info):
        try:
            res_id = meta_info.get("discovery_result_id")
            target_sites = meta_info.get("target_sites", ["RED"])
            
            # 从数据库获取信息
            artist = "Unknown Artist"
            album = "Unknown Album"
            year = 2024
            if self.db and res_id:
                row = self.db.fetch_one("SELECT * FROM discovery_results WHERE id = ?", (res_id,))
                if row:
                    artist = row['artist']
                    album = row['album']
                    year = row['year'] or 2024
            
            # 生成种子
            self.log_process(f"    [Pipeline] 正在为 {album_dir.name} 生成种子...")
            import subprocess
            tracker_url = getattr(self.red_options, 'site_config', {}).get("tracker_url", "https://flacsfor.me/announce")
            torrent_path = album_dir.parent / f"{album_dir.name}.torrent"
            
            # 使用 mktorrent 生成
            cmd = ['mktorrent', '-p', '-a', tracker_url, '-o', str(torrent_path), str(album_dir)]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if not torrent_path.exists():
                self.log_main(f"生成种子失败: {torrent_path}")
                if self.db and res_id:
                    self.db.execute("UPDATE discovery_results SET status = 'failed' WHERE id = ?", (res_id,))
                return
                
            # 执行全新上传
            for site in target_sites:
                from core.site_config import SITE_CONFIGS
                site_config = SITE_CONFIGS.get(site, getattr(self.red_options, 'site_config', {}))
                base_url = site_config.get("base_url", "https://redacted.sh")
                api_url = site_config.get("api_url", "https://redacted.sh/ajax.php")
                auth_key = self.red_options.api_key
                
                if site in ["JPS", "DIC"]:
                    upload_url = f"{base_url}/upload.php"
                else:
                    upload_url = f"{api_url}?action=upload"
                headers = {
                    'Authorization': auth_key,
                    'User-Agent': 'EliteTMHelper_AutoUpload'
                }
                
                # 全新上传所需的字段
                upload_data = {
                    'submit': 'true',
                    'type': '0',
                    'artists[]': artist,
                    'importance[]': '1', # Main
                    'title': album,
                    'year': str(year),
                    'releasetype': '1', # Album
                    'format': 'FLAC',
                    'bitrate': 'Lossless',
                    'media': 'WEB',
                    'tags': 'pop', # Default tag, RED requires at least one
                    'release_desc': f"Automated upload by Discovery Module from EliteTMHelper2."
                }
                
                self.log_main(f"    [Pipeline] 正在向 {site} 全新发布: {album_dir.name}")
                with open(torrent_path, 'rb') as f:
                    files = {'file_input': (torrent_path.name, f, 'application/x-bittorrent')}
                    if self.red_session:
                        resp = self.red_session.post(upload_url, data=upload_data, files=files, timeout=30)
                    else:
                        resp = requests.post(upload_url, headers=headers, data=upload_data, files=files, timeout=30)
                
                if resp.status_code == 200:
                    if site in ["JPS", "DIC"]:
                        import re
                        match = re.search(r'torrentid=(\d+)', resp.url)
                        if match:
                            self.log_main(f"    [Pipeline] {site} 上传成功！")
                            if self.db and res_id:
                                self.db.execute("UPDATE discovery_results SET status = 'uploaded' WHERE id = ?", (res_id,))
                        else:
                            self.log_main(f"    [Pipeline] {site} 上传失败，跳转 URL 未包含 torrentid")
                            if self.db and res_id:
                                self.db.execute("UPDATE discovery_results SET status = 'failed' WHERE id = ?", (res_id,))
                    else:
                        try:
                            resp_json = resp.json()
                            if resp_json.get('status') == 'success':
                                self.log_main(f"    [Pipeline] {site} 上传成功！")
                                if self.db and res_id:
                                    self.db.execute("UPDATE discovery_results SET status = 'uploaded' WHERE id = ?", (res_id,))
                            else:
                                self.log_main(f"    [Pipeline] {site} API 返回错误: {resp_json}")
                                if self.db and res_id:
                                    self.db.execute("UPDATE discovery_results SET status = 'failed' WHERE id = ?", (res_id,))
                        except Exception as e:
                            self.log_main(f"    [Pipeline] 解析 {site} 响应失败: {e}")
                            if self.db and res_id:
                                self.db.execute("UPDATE discovery_results SET status = 'failed' WHERE id = ?", (res_id,))
                else:
                    self.log_main(f"    [Pipeline] {site} HTTP 错误: {resp.status_code}")
                    if self.db and res_id:
                        self.db.execute("UPDATE discovery_results SET status = 'failed' WHERE id = ?", (res_id,))
                        
            # 将种子添加到 qBittorrent 做种
            self.log_process("    [Pipeline] 正在将种子添加到 qBittorrent 做种...")
            self.qb.add_torrent(str(torrent_path), save_path=str(album_dir.parent), category="red_seeding")
            
        except Exception as e:
            self.log_process(f"全新上传处理异常: {e}")
            import traceback
            traceback.print_exc()
            res_id = meta_info.get("discovery_result_id")
            if self.db and res_id:
                self.db.execute("UPDATE discovery_results SET status = 'failed' WHERE id = ?", (res_id,))

    def _mark_failed(self, qb_torrent_info):
        """将失败任务移至 red_failed 类别，停止不断重试"""
        if not qb_torrent_info: return
        hash_str = qb_torrent_info.get("hash")
        
        # 将类别改为 red_failed，防止自动轮询陷入死循环。
        success = self._change_category(hash_str, "red_failed")
        
        # 只有在类别成功改变，确保它不再被 red_auto 捕获的情况下，才从 processed_hashes 中移除
        # 如果分类修改失败，我们决不能将其移除，否则会导致无限死循环
        if success:
            if hash_str and hash_str in self.processed_hashes:
                self.processed_hashes.remove(hash_str)
                if self.db:
                    self.db.execute("DELETE FROM pipeline_processed WHERE hash = ?", (hash_str,))
            self.log_process(_("log_task_failed_red_failed"))
        else:
            self.log_process(_("log_task_failed_cant_change_cat"))

