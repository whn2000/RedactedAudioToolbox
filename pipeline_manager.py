import time
import threading
from pathlib import Path
import json
import requests
from torf import Torrent
from qbittorrent_client import QbittorrentClient
from flac_downsampler import process_album as flac_downsample_album
from lossless_checker import process_album as check_lossless_album
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
        self.cache_file = Path("pipeline_cache.json")
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding='utf-8') as f:
                    self.processed_hashes = set(json.load(f))
            except Exception:
                pass

    def start(self):
        if self.is_running: return
        self.is_running = True
        self.log_main(">>> 自动处理流水线监控已启动...")
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        self.is_running = False
        self.log_main(">>> 自动处理流水线监控已停止。")

    def add_to_pipeline(self, torrent_path, group_info, torrent_info, save_path):
        """将种子添加到 qB 并加入追踪列表"""
        success = self.qb.add_torrent(torrent_path, save_path=save_path, category="red_auto")
        if success:
            self.log_main(f"    [Pipeline] 已成功推送到 qBittorrent: {Path(torrent_path).name}")
        else:
            self.log_main(f"    [Pipeline] ❌ 推送 qBittorrent 失败: {Path(torrent_path).name}")

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
                        try:
                            with open(self.cache_file, "w", encoding='utf-8') as f:
                                json.dump(list(self.processed_hashes), f)
                        except Exception:
                            pass
                        self.log_main(f"    [Pipeline] 📥 下载完成，准备处理: {name}")
                        
                        # 改变类别防止重复触发 (备用)
                        self._change_category(hash_str, "red_processed")
                        
                        # 启动异步任务处理，避免阻塞轮询
                        threading.Thread(target=self._process_downloaded_torrent, args=(save_path, name, t), daemon=True).start()

            except Exception as e:
                self.log_main(f"    [Pipeline] 监控出现异常: {e}")
                
            time.sleep(10) # 每 10 秒轮询一次

    def _change_category(self, torrent_hash, new_category):
        url = f"{self.qb.base_url}/api/v2/torrents/setCategory"
        try:
            self.qb.session.post(url, data={'hashes': torrent_hash, 'category': new_category})
        except:
            pass

    def _process_downloaded_torrent(self, save_path, name, qb_torrent_info):
        try:
            site_config = getattr(self.red_options, 'site_config', _DEFAULT_SITE_CONFIG)
            base_url = site_config["base_url"]
            api_url = site_config["api_url"]
            album_dir = Path(save_path) / name
            if not album_dir.exists() or not album_dir.is_dir():
                self.log_process(f"    [Pipeline] ❌ 找不到下载的文件夹: {album_dir}")
                return

            output_dir = album_dir.parent / f"{album_dir.name} (16bit)"
            official_torrent = album_dir.parent / f"{output_dir.name}_official.torrent"
            
            if official_torrent.exists():
                self.log_process(f"    [Pipeline] ⏭️ 发现本地已存在官方种子 ({official_torrent.name})，说明此前已成功上传，跳过重复处理。")
                return

            self.log_process(f"    [Pipeline] 💿 开始降频制种: {name}")
            # 1. 降频
            # flac_downsampler 的 process_album 其实处理的是单张专辑目录
            # 我们需要获取 group_info, 这个目前没有传给 qb，我们可以通过解析目录里的 metadata 或直接盲转
            tracker_url = site_config.get("tracker_url", "https://flacsfor.me/announce")
            source_flag = site_config.get("source", "RED")
            # 实际的 process_album 会搜索 flac，并生成 16bit 目录
            flac_downsample_album(album_dir, tracker_url, source_flag) 
            
            # 找到生成的 16bit 目录
            output_dir = album_dir.parent / f"{album_dir.name} (16bit)"
            if not output_dir.exists():
                self.log_process(f"    [Pipeline] ⚠️ 降频未生成 16bit 文件夹（可能原本就是 16bit）: {name}")
                return

            self.log_check(f"    [Pipeline] 🎵 开始进行无损检查: {output_dir.name}")
            # 2. 检查无损 (Fast Mode)
            is_lossless = check_lossless_album(output_dir, fast_mode=True)
            if not is_lossless:
                self.log_check(f"    [Pipeline] 🚨 警告: 假无损检测未通过: {output_dir.name}")
                if self.ask_manual_check:
                    self.log_check(f"    [Pipeline] ⏳ 正在等待人工确认: {output_dir.name}")
                    user_confirmed = self.ask_manual_check(output_dir.name)
                    if not user_confirmed:
                        self.log_check(f"    [Pipeline] 🛑 人工确认未通过，已中止自动上传: {output_dir.name}")
                        return
                    self.log_check(f"    [Pipeline] 👍 人工确认通过，继续发布流程: {output_dir.name}")
                else:
                    self.log_check(f"    [Pipeline] 🛑 且未配置人工确认，已中止自动上传: {output_dir.name}")
                    return
                
            self.log_check(f"    [Pipeline] ✅ 无损检测通过 (或人工放行)，准备上传: {output_dir.name}")
            
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
                self.log_main(f"    [Pipeline] ❌ 找不到元数据辅助文件 (按 Hash {hash_str_lower} 匹配失败)，无法执行自动上传。")
                return
                
            with open(json_meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                
            group_info = meta['group_info']
            torrent_info = meta['torrent_info']
            
            group_id = group_info['response']['group']['id']
            torrent_id = torrent_info.get('torrentId', torrent_info.get('id'))
            
            # 构造原始 24bit 的链接
            source_link = f"{base_url}/torrents.php?id={group_id}&torrentid={torrent_id}"
            release_desc = f"16-bit downsample created from the 24-bit source.\n\n[url={source_link}]24-bit source[/url]"
            
            upload_data = {
                'submit': 'true',
                'type': '0', # Music
                'groupid': str(group_id),
                'format': 'FLAC',
                'bitrate': 'Lossless',
                'media': torrent_info.get('media', 'WEB'),
                'release_desc': release_desc
            }
            
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

            if is_remastered:
                upload_data['remaster'] = 'true'
                
                r_year = full_torrent_info.get('remasterYear')
                if not r_year:
                    r_year = group_info['response']['group'].get('year', '')
                upload_data['remaster_year'] = str(r_year)
                
                upload_data['remaster_title'] = str(full_torrent_info.get('remasterTitle') or '')
                
                r_label = full_torrent_info.get('remasterRecordLabel') or group_info['response']['group'].get('recordLabel', '')
                r_cat = full_torrent_info.get('remasterCatalogueNumber') or group_info['response']['group'].get('catalogueNumber', '')
                
                upload_data['remaster_record_label'] = str(r_label)
                upload_data['remaster_catalogue_number'] = str(r_cat)
                
            # 寻找生成的 torrent 文件
            generated_torrent = album_dir.parent / f"{output_dir.name}.torrent"
            if not generated_torrent.exists():
                self.log_main(f"    [Pipeline] ❌ 找不到生成的种子文件: {generated_torrent.name}")
                return
                
            # 执行上传
            upload_url = f"{api_url}?action=upload"
            auth_key = self.red_options.api_key
            if site_config.get("source") == "OPS" and not auth_key.startswith("token "):
                auth_key = f"token {auth_key}"
                
            headers = {
                'Authorization': auth_key,
                'User-Agent': 'EliteTMHelper_AutoUpload'
            }
            
            self.log_main(f"    [Pipeline] 🚀 正在向 {site_config.get('source', 'RED')} 提交 POST 请求...")
            with open(generated_torrent, 'rb') as f:
                files = {'file_input': (generated_torrent.name, f, 'application/x-bittorrent')}
                # 注意：requests 在传递 dict 到 data 时，不要将 headers 设为 multipart/form-data，requests 会自动处理 boundary
                resp = requests.post(upload_url, headers=headers, data=upload_data, files=files, timeout=30)
                
            if resp.status_code == 200:
                try:
                    resp_json = resp.json()
                    if resp_json.get('status') == 'success':
                        new_torrent_id = resp_json['response'].get('torrentid') or resp_json['response'].get('torrentId')
                        new_link = f"{base_url}/torrents.php?id={group_id}&torrentid={new_torrent_id}"
                        self.log_main(f"    [Pipeline] 🎉 自动上传成功！")
                        self.log_main(f"    [Pipeline] 🔗 新种子链接: {new_link}")
                        
                        # 成功上传后，必须从 RED 下载打上了官方 tracker passkey 和 source 标记的新种子
                        self.log_main(f"    [Pipeline] 📥 正在从 {site_config.get('source', 'RED')} 下载官方种子文件以进行做种...")
                        dl_url = f"{api_url}?action=download&id={new_torrent_id}"
                        dl_resp = requests.get(dl_url, headers=headers, timeout=30)
                        
                        if dl_resp.status_code == 200:
                            official_torrent = album_dir.parent / f"{output_dir.name}_official.torrent"
                            official_torrent.write_bytes(dl_resp.content)
                            
                            self.log_process(f"    [Pipeline] 🔄 正在将官方 16bit 新种子加入 qBittorrent 做种...")
                            self.qb.add_torrent(str(official_torrent), save_path=str(album_dir.parent), category="red_seeding")
                        else:
                            self.log_main(f"    [Pipeline] ❌ 下载官方种子失败 (状态码: {dl_resp.status_code})，请手动前往网站下载并做种。")
                            
                    else:
                        self.log_main(f"    [Pipeline] ❌ 上传 API 返回失败状态: {resp_json}")
                except Exception as e:
                    self.log_main(f"    [Pipeline] ❌ 上传成功但解析返回 JSON 失败: {e} | Resp: {resp.text[:200]}")
            else:
                self.log_main(f"    [Pipeline] ❌ 上传 HTTP 请求失败, 状态码: {resp.status_code}")
                self.log_main(f"    [Pipeline] {resp.text[:500]}")

        except Exception as e:
            self.log_main(f"    [Pipeline] ❌ 处理流水线异常: {e}")
            traceback.print_exc()

