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

    def _process_downloaded_torrent(self, save_path, name, qb_torrent_info):
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
            hash_str_lower = qb_torrent_info.get("hash", "").lower()
            
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
            upload_url = f"{api_url}?action=upload"
            auth_key = self.red_options.api_key
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
                    resp = requests.post(upload_url, headers=headers, data=upload_data, files=files, timeout=30)
                    
                if resp.status_code == 200:
                    try:
                        resp_json = resp.json()
                        if resp_json.get('status') == 'success':
                            new_torrent_id = resp_json['response'].get('torrentid') or resp_json['response'].get('torrentId')
                            new_link = f"{base_url}/torrents.php?id={group_id}&torrentid={new_torrent_id}"
                            self.log_main(_("log_upload_success"))
                            self.log_main(_("log_new_torrent_link").format(link=new_link))
                            
                            self.log_main(_("log_dl_official_torrent").format(source=site_config.get("source", "RED")))
                            dl_url = f"{api_url}?action=download&id={new_torrent_id}"
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
            self._change_category(hash_str_lower, "red_processed")

        except Exception as e:
            self.log_main(_("log_pipeline_exception").format(e=e))
            traceback.print_exc()
            self._mark_failed(qb_torrent_info)

    def _mark_failed(self, qb_torrent_info):
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

