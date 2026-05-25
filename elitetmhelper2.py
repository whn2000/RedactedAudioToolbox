import requests
import time
import sys
import json
from pathlib import Path
import re
import random
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font as tkfont, filedialog
import threading
from types import SimpleNamespace
from i18n import _

# ==========================================
# 站点配置
# ==========================================

SITE_CONFIGS = {
    "RED": {
        "name": "RED (Redacted)",
        "api_url": "https://redacted.sh/ajax.php",
        "base_url": "https://redacted.sh",
        "tracker_url": "https://flacsfor.me/announce",
        "source": "RED",
        "max_pages": 5,
    },
    "OPS": {
        "name": "OPS (Orpheus)",
        "api_url": "https://orpheus.network/ajax.php",
        "base_url": "https://orpheus.network",
        "tracker_url": "https://home.opsfet.ch/announce",
        "source": "OPS",
        "max_pages": 5,
    }
}

# ==========================================
# 核心业务逻辑 (基于原脚本优化)
# ==========================================

class Color:
    # GUI 中其实用不到颜色代码，但为了兼容原脚本的打印逻辑予以保留
    PURPLE = ''
    CYAN = ''
    DARKCYAN = ''
    BLUE = ''
    GREEN = ''
    YELLOW = ''
    RED = ''
    GREY = ''
    BOLD = ''
    UNDERLINE = ''
    END = ''

class RedactedAPIError(Exception):
    pass

class RedactedSession(requests.Session):
    def __init__(self, options):
        super().__init__()
        self.last_request_time = 0
        self.options = options
        self.timeout = 15 # 优化：增加超时限制，防止死等

    def wait(self):
        now = time.monotonic()
        elapsed = now - self.last_request_time
        if self.options.show_api_times:
            print(f" {round(elapsed, 2)} ", end="")
        interval = getattr(self.options, 'request_interval', 3.0)
        if elapsed < interval: # 严格遵守 API 的速率限制
            time.sleep(interval - elapsed)
        self.last_request_time = time.monotonic()

    def get(self, *args, **kwargs):
        self.wait()
        kwargs.setdefault('timeout', self.timeout)
        return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        self.wait()
        kwargs.setdefault('timeout', self.timeout)
        return super().post(*args, **kwargs)

    def get_api(self, params):
        api_url = getattr(self.options, 'site_config', SITE_CONFIGS["RED"])["api_url"]
        retries = 5
        for attempt in range(retries):
            res = self.get(api_url, params=params)
            try:
                data = res.json()
            except Exception:
                return res
            
            if data.get("status") != "success" and data.get("error") == "Rate limit exceeded":
                print(_("log_api_rate_limit").format(attempt=attempt + 1, retries=retries))
                time.sleep(10)
                continue
                
            return res
        return res

class Cache:
    def __init__(self, options):
        self.options = options
        self.json_file = Path(self.options.cache)
        if Path(self.json_file).exists():
            with self.json_file.open() as json_file_open:
                try:
                    self.data = json.load(json_file_open)
                except json.JSONDecodeError:
                    self.data = {'0': "nope"}
        else:
            self.data = {'0': "nope"}
            self.json_file.write_text(json.dumps(self.data))

    def write(self):
        self.json_file.write_text(json.dumps(self.data))

    def check(self, torrent_id):
        return str(torrent_id) in self.data

def get_edition(torrent):
    return {
        x: torrent.get(x) for x in [
            "remastered",
            "remasterYear",
            "remasterTitle",
            "remasterRecordLabel",
            "remasterCatalogueNumber",
            "media"
        ]
    }

class FoundTorrent:
    def __init__(self, torrent_id, group_info):
        self.torrent_id = torrent_id
        self.group_info = group_info
        self.torrents = self.group_info["response"]["torrents"]
        self.bbBody = self.group_info["response"]["group"].get("bbBody", self.group_info["response"]["group"].get("wikiBody", ""))
        self.lossy_status = False
        self.trump_status = False
        self.edition = []
        self.seeders = 0

    def is_24_bit(self):
        current_torrent = None
        for torrent in self.torrents:
            if torrent.get("id") == self.torrent_id or torrent.get("torrentId") == self.torrent_id:
                self.edition = get_edition(torrent)
                if torrent.get('lossyWebApproved') or torrent.get('lossyMasterApproved'):
                    self.lossy_status = True
                if torrent.get('trumpable'):
                    self.trump_status = True
                self.seeders = torrent.get('seeders', 0)
                self.snatched = torrent.get('snatched', torrent.get('snatches', 0))
                current_torrent = torrent
                break
                
        if not current_torrent:
            return False
            
        if current_torrent.get("format") != "FLAC" or current_torrent.get("encoding") != "24bit Lossless":
            return False

        for torrent in self.torrents:
            if get_edition(torrent) == self.edition:
                if torrent.get("encoding") == "Lossless":
                    return False
        return True

    def bandcamp(self):
        if "bandcamp" in self.bbBody:
            link_regex = re.compile(r'((https?):(//|\\\\)+([\w:#@%/;$()~_?+-=\\.&]*(#!)?))', re.DOTALL)
            links = re.findall(link_regex, self.bbBody)
            for link in links:
                if 'bandcamp' in link[0]:
                    try:
                        bc_page = requests.get(link[0], timeout=10).text
                        if "name your price" in bc_page.lower():
                            return True
                    except requests.exceptions.RequestException:
                        return False
        return False

    def uns(self):
        result = False
        for torrent in self.torrents:
            if torrent.get('remastered') is True and torrent.get('remasterYear') in (0, None) and torrent.get('encoding') == "Lossless":
                result = True
            if torrent.get('remastered') is False and torrent.get('remasterYear') in (0, None) and torrent.get('encoding') == "Lossless":
                result = True
        return result

    def any_16_bit(self):
        for torrent in self.torrents:
            if torrent.get("encoding") == "Lossless":
                return True
        return False

def search_result_iterator(session, options, found, abort_flag):
    year = int(options.year_latest)
    
    seen_groups = set()
    site_config = getattr(options, 'site_config', SITE_CONFIGS["RED"])
    max_pages = site_config.get("max_pages", 5)

    while year > int(options.year_earliest) - 1:
        if abort_flag(): # 优化：检查是否需要中断
            print(_("log_search_aborted"))
            return

        if options.order_by == "random":
            if found >= options.find_number:
                print(_("log_requested_torrents_found").format(found=found))
                return # 优化：将 quit() 换成 return
            year = random.choice(list(range(int(options.year_earliest), int(options.year_latest+1))))
        
        search_queue = [{}]
        
        while search_queue:
            if abort_flag(): return
            extra_params = search_queue.pop(0)
            
            exceded_max_size = False
            params = {
                "action": "browse",
                "encoding": "24bit Lossless",
                "media": options.media,
                "order_by": options.order_by,
                "order_way": options.order_way,
                "scene": 0,
                "year": year,
                "taglist": options.tags,
                "tags_type": options.tags_type
            }
            if options.release_type != "":
                params["releasetype"] = options.release_type

            params.update(extra_params)
            
            search_label_parts = []
            if "releasetype" in extra_params: search_label_parts.append(f"RT:{extra_params['releasetype']}")
            if "media" in extra_params: search_label_parts.append(f"Media:{extra_params['media']}")
            if "order_way" in extra_params: search_label_parts.append(f"Order:{extra_params['order_way']}")
            search_label = f"[{','.join(search_label_parts)}] " if search_label_parts else ""
            
            print(_("log_req_page_1").format(year=year, label=search_label))
            try:
                first_page = session.get_api(params).json()
            except requests.exceptions.RequestException as e:
                raise RedactedAPIError(_("log_req_fail").format(e=str(e)))
            except json.decoder.JSONDecodeError:
                raise RedactedAPIError(_("log_invalid_cred"))

            if first_page.get("status") != "success":
                print(_("log_api_err_skip").format(err=first_page.get("error", first_page)))
                break
                
            if not first_page["response"]["results"]:
                print(_("log_no_results").format(year=year, label=search_label))
                continue
            else:
                number_of_pages = first_page["response"]["pages"]

            print(_("log_found_pages").format(pages=number_of_pages))
            
            if number_of_pages > max_pages:
                if "releasetype" not in extra_params and options.release_type == "":
                    print(_("log_gt_20_pages_rt").format(year=year, label=search_label, max_pages=max_pages))
                    release_types = [1, 3, 5, 6, 7, 9, 11, 13, 14, 15, 16, 21, 22, 23]
                    for rt in release_types:
                        new_params = extra_params.copy()
                        new_params["releasetype"] = rt
                        search_queue.append(new_params)
                    continue
                elif "media" not in extra_params and options.media == "":
                    print(_("log_gt_20_pages_media").format(year=year, label=search_label, max_pages=max_pages))
                    medias = ['CD', 'WEB', 'Vinyl', 'SACD', 'Cassette', 'Blu-Ray', 'DVD', 'Soundboard']
                    for m in medias:
                        new_params = extra_params.copy()
                        new_params["media"] = m
                        search_queue.append(new_params)
                    continue
                elif "order_way" not in extra_params:
                    print(_("log_gt_20_pages_order").format(year=year, label=search_label, max_pages=max_pages))
                    new_params_desc = extra_params.copy()
                    new_params_desc["order_way"] = "desc"
                    search_queue.append(new_params_desc)
                    
                    new_params_asc = extra_params.copy()
                    new_params_asc["order_way"] = "asc"
                    search_queue.append(new_params_asc)
                    continue
                else:
                    print(_("log_exhausted_split").format(year=year, label=search_label, max_pages=max_pages))
                    
            actual_pages = min(number_of_pages, max_pages)

            for group in first_page["response"]["results"]:
                if abort_flag(): return
                
                group_id = group["groupId"]
                if group_id in seen_groups:
                    continue
                seen_groups.add(group_id)
                
                rt = group.get("releaseType")
                if isinstance(rt, str) and not rt.isdigit():
                    # Handle cases where releaseType might be a string like 'Anthology'
                    rt = 1 # Fallback or map it to a default/corresponding value, though typically API should return ID.
                else:
                    rt = int(rt or 1)
                
                if not options.release_type_allowed.get(rt, False): continue
                
                if options.order_by == "size" and options.order_way == "asc":
                    if any(map(lambda x: x.get("size", 0) > options.max_size, group.get("torrents", []))):
                        exceded_max_size = True
                        print(_("log_exceed_max_size"))
                        break
                yield group
                    
            if exceded_max_size:
                continue

            for i in range(2, actual_pages + 1):
                if abort_flag(): return
                params["page"] = i
                print(_("log_req_page_i").format(year=year, label=search_label, i=i, pages=number_of_pages))
                try:
                    page = session.get_api(params).json()
                except Exception as e:
                    print(_("log_fetch_page_fail").format(i=i, e=str(e)))
                    break

                if page.get("status") != "success":
                    print(_("log_api_err_abort_kw").format(err=page.get("error", page)))
                    break

                if not page["response"]["results"]:
                    print(_("log_api_limit_next_kw"))
                    break

                for group in page["response"]["results"]:
                    if abort_flag(): return
                    
                    group_id = group["groupId"]
                    if group_id in seen_groups:
                        continue
                    seen_groups.add(group_id)
                    
                    rt = group.get("releaseType")
                    if isinstance(rt, str) and not rt.isdigit():
                        rt = 1
                    else:
                        rt = int(rt or 1)
                        
                    if not options.release_type_allowed.get(rt, False): continue
                    
                    if options.order_by == "size" and options.order_way == "asc":
                        if any(map(lambda x: x.get("size", 0) > options.max_size, group.get("torrents", []))):
                            exceded_max_size = True
                            print(_("log_exceed_max_size"))
                            break
                    yield group
                if exceded_max_size:
                    break

        if options.order_by != 'random':
            year -= 1

def perform_search(options, abort_flag):
    found = 0
    site_config = getattr(options, 'site_config', SITE_CONFIGS["RED"])
    base_url = site_config["base_url"]
    api_url = site_config["api_url"]
    if not options.api_key:
        print(_("log_need_api_key"))
        return

    session = RedactedSession(options)
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'User-Agent': 'EliteTMHelper_GUI',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip,deflate,sdch',
        'Accept-Language': 'en-US,en;q=0.8'
    }
    
    auth_key = options.api_key
    if site_config.get("source") == "OPS" and not auth_key.startswith("token "):
        auth_key = f"token {auth_key}"
        
    headers['Authorization'] = auth_key
    session.headers.update(headers)

    # 获取用户状态以计算 Buffer
    current_buffer_gb = float('inf')
    try:
        index_data = session.get_api({"action": "index"}).json()
        if index_data.get("status") == "success":
            user_stats = index_data["response"]["userstats"]
            uploaded = user_stats.get("uploaded", 0)
            downloaded = user_stats.get("downloaded", 0)
            req_ratio = user_stats.get("requiredRatio", 0)
            
            formula = options.buffer_formula.strip()
            safe_dict = {'U': uploaded, 'D': downloaded, 'R': req_ratio}
            try:
                # 仅限基本数学运算
                current_buffer = eval(formula, {"__builtins__": None}, safe_dict)
            except Exception as e:
                print(_("log_buffer_formula_fail").format(f=formula, e=e))
                current_buffer = (uploaded / 0.65) - downloaded
                
            current_buffer_gb = current_buffer / (1024**3)
            print(_("log_buffer_info").format(buf=current_buffer_gb, limit=options.buffer_limit))
    except Exception as e:
        print(_("log_skip_buffer_check").format(e=e))

    cache = Cache(options) if options.cache != 'Disabled' else False
    search_results = search_result_iterator(session, options, found, abort_flag)

    for group in search_results:
        if abort_flag(): break
        
        if cache:
            cached = False
            for torrent in group["torrents"]:
                cached = cache.check(torrent["torrentId"])
            if cached: continue

        group_search_params = {"action": "torrentgroup", "id": group["groupId"]}
        try:
            group_info = session.get_api(group_search_params).json()
            if group_info.get("status") != "success" or not isinstance(group_info.get("response"), dict):
                print(_("log_group_info_format_err").format(id=group["groupId"]))
                continue
        except Exception as e:
            print(_("log_group_info_fail").format(id=group["groupId"], e=str(e)))
            continue

        for torrent in group["torrents"]:
            if abort_flag(): break
            
            this_torrent = FoundTorrent(torrent["torrentId"], group_info)
            if this_torrent.is_24_bit():
                nope = [""]
                if options.any16bit and this_torrent.any_16_bit(): nope.append(" 16")
                if options.bandcamp and not this_torrent.bandcamp(): nope.append(" bc")
                if options.trumpable and this_torrent.trump_status: nope.append(" tr")
                if options.lossy and this_torrent.lossy_status: nope.append(" lo")
                if options.uns and this_torrent.uns(): nope.append(" un")
                if options.min_seeders and this_torrent.seeders < options.min_seeders: nope.append(" sd")
                if options.exclude_zero_snatches and this_torrent.snatched == 0: nope.append(" 0snatches")
                if options.max_size and torrent.get("size", 0) > options.max_size: nope.append(" >max_size")

                if nope == [""]:
                    found += 1
                    with Path(options.output).open(mode='a+', encoding='utf-8') as myfile:
                        html_start = html_mid = html_end = html_found = ""
                        if options.html:
                            html_start = '<a href="'
                            html_mid = f'">{base_url}/torrents.php?id={group["groupId"]}&torrentid={torrent["torrentId"]}</a>'
                            html_end = '</br>'
                            html_found = str(found) + " "
                        myfile.write(f"{html_found}{html_start}{base_url}/torrents.php?id={group['groupId']}&torrentid={torrent['torrentId']}{html_mid}")
                        if options.show_size:
                            myfile.write(f" {round(torrent['size']/1048576, 2)}MB")
                        myfile.write(f"{html_end}\n")
                        
                    print(_("log_found_target").format(id=torrent["torrentId"], url=f"{base_url}/torrents.php?id={group['groupId']}&torrentid={torrent['torrentId']}"), end="")
                    if options.show_size: print(f" {round(torrent['size']/1048576, 2)}MB", end="")
                    
                    if options.auto_download:
                        size_mb = torrent['size'] / 1048576
                        
                        # 检查 Buffer 是否够用
                        if not options.use_fl_token or size_mb < options.fl_token_threshold:
                            if current_buffer_gb - (size_mb / 1024) < options.buffer_limit:
                                print(_("log_buffer_below_safe").format(limit=options.buffer_limit))
                                return
                            current_buffer_gb -= (size_mb / 1024) # 扣除预计下载量

                        try:
                            dl_url = f"{api_url}?action=download&id={torrent['torrentId']}"
                            used_token = False
                            if options.use_fl_token and size_mb >= options.fl_token_threshold:
                                dl_url += "&usetoken=1"
                                used_token = True
                                
                            dl_res = session.get(dl_url)
                            if dl_res.status_code == 200:
                                fname = f"{torrent['torrentId']}.torrent"
                                cd = dl_res.headers.get("content-disposition", "")
                                if 'filename="' in cd:
                                    fname = cd.split('filename="')[1].split('"')[0]
                                fname = "".join(c for c in fname if c not in r'\/:*?"<>|')
                                
                                save_dir = Path(options.save_path) if hasattr(options, 'save_path') and options.save_path else Path(".")
                                save_dir.mkdir(parents=True, exist_ok=True)
                                save_path = save_dir / fname
                                
                                save_path.write_bytes(dl_res.content)
                                token_str = " (使用了 Token)" if used_token else ""
                                print(_("log_dl_success").format(token=token_str, path=save_path), end="")
                                
                                # 将 metadata 保存为 json 供 PipelineManager 读取
                                meta_path = save_path.with_suffix('.json')
                                with open(meta_path, 'w', encoding='utf-8') as f:
                                    json.dump({
                                        'group_info': group_info,
                                        'torrent_info': torrent,
                                        'tracker_url': site_config['tracker_url']
                                    }, f)
                                
                                # 推送到 qBittorrent
                                if hasattr(options, 'pipeline') and options.pipeline:
                                    options.pipeline.add_to_pipeline(str(save_path), group_info, torrent, None)
                                    
                            else:
                                print(_("log_dl_fail_code").format(code=dl_res.status_code), end="")
                        except Exception as e:
                            print(_("log_dl_exception").format(e=e), end="")
                    
                    print("")
                    
                    if cache and not options.dont_cache_yays:
                        cache.data[str(torrent['torrentId'])] = "yay"
                        cache.write()
                else:
                    print(_("log_ignore_reason").format(id=torrent["torrentId"], nope="".join(nope)))
                    if cache:
                        cache.data[str(torrent['torrentId'])] = "nope"
                        cache.write()
            else:
                print(_("log_ignore_not_24bit").format(id=torrent["torrentId"]))
                if cache:
                    cache.data[str(torrent['torrentId'])] = "nope"
                    cache.write()
                    
            if found >= options.find_number:
                print(_("log_target_reached").format(found=found))
                return

    print(_("log_search_done").format(found=found))


# ==========================================
# 桌面图形界面 GUI 逻辑
# ==========================================

import customtkinter as ctk
from i18n import _

class RedirectText:
    """拦截 print 输出并重定向到 Tkinter 文本框"""
    def __init__(self, text_ctrl):
        self.output = text_ctrl

    def write(self, string):
        try:
            # Check if scrollbar is at the bottom before inserting
            yview = self.output.yview()
            is_at_bottom = yview[1] >= 0.99
            
            self.output.insert(tk.END, string)
            
            if is_at_bottom:
                self.output.see(tk.END)
        except Exception:
            pass

    def flush(self):
        pass

class AppGUI:
    def __init__(self, parent):
        self.parent = parent
        self.is_running = False
        self.pipeline = None
        
        self.site_configs_data = {"RED": {}, "OPS": {}}
        self._is_switching_site = False
        
        self.site_var = tk.StringVar(value="RED")
        self.api_key_var = tk.StringVar()
        
        self.site_var.trace_add("write", self.on_site_changed)
        self.save_path_var = tk.StringVar()
        self.media_var = tk.StringVar(value="CD")
        self.year_latest_var = tk.StringVar(value="2023")
        self.year_earliest_var = tk.StringVar(value="1970")
        self.number_var = tk.StringVar(value="50")
        self.max_size_var = tk.StringVar(value="2048")
        self.order_by_var = tk.StringVar(value="time")
        
        self.bandcamp_var = tk.BooleanVar(value=False)
        self.ignore_lossy_var = tk.BooleanVar(value=False)
        self.ignore_16bit_var = tk.BooleanVar(value=False)
        self.ignore_trumpable_var = tk.BooleanVar(value=False)
        self.album_var = tk.BooleanVar(value=True)
        self.soundtrack_var = tk.BooleanVar(value=True)
        self.ep_var = tk.BooleanVar(value=True)
        self.anthology_var = tk.BooleanVar(value=True)
        self.compilation_var = tk.BooleanVar(value=True)
        self.single_var = tk.BooleanVar(value=True)
        self.live_album_var = tk.BooleanVar(value=True)
        self.remix_var = tk.BooleanVar(value=True)
        self.bootleg_var = tk.BooleanVar(value=True)
        self.interview_var = tk.BooleanVar(value=True)
        self.mixtape_var = tk.BooleanVar(value=True)
        self.demo_var = tk.BooleanVar(value=True)
        self.unknown_var = tk.BooleanVar(value=True)
        self.concert_recording_var = tk.BooleanVar(value=True)
        self.dj_mix_var = tk.BooleanVar(value=True)
        self.exclude_zero_snatches_var = tk.BooleanVar(value=False)
        self.auto_download_var = tk.BooleanVar(value=False)
        self.min_seeders_var = tk.StringVar(value="0")
        
        self.buffer_limit_var = tk.StringVar(value="10.0")
        self.buffer_formula_var = tk.StringVar(value="(U / 0.65) - D")
        self.use_fl_token_var = tk.BooleanVar(value=False)
        self.fl_token_threshold_var = tk.StringVar(value="500")
        
        self.qb_host_var = tk.StringVar(value="http://127.0.0.1")
        self.qb_port_var = tk.StringVar(value="8080")
        self.qb_user_var = tk.StringVar(value="admin")
        self.qb_pass_var = tk.StringVar(value="adminadmin")
        self.enable_pipeline_var = tk.BooleanVar(value=False)

        self.request_interval_var = tk.StringVar(value="3.0")

        self.config_file = "config.json"
        self.last_site = self.site_var.get()
        self.load_config()

        self.build_ui()

    def on_site_changed(self, *args):
        if self._is_switching_site: return
        self._is_switching_site = True
        
        new_site = self.site_var.get()
        if self.last_site != new_site:
            self.site_configs_data[self.last_site] = self.get_current_site_settings()
            self.apply_site_settings(self.site_configs_data.get(new_site, {}))
            self.last_site = new_site
            
        self._is_switching_site = False

    def get_current_site_settings(self):
        return {
            'api_key': self.api_key_var.get(),
            'save_path': self.save_path_var.get(),
            'buffer_formula': self.buffer_formula_var.get(),
            'media': self.media_var.get(),
            'year_latest': self.year_latest_var.get(),
            'year_earliest': self.year_earliest_var.get(),
            'number': self.number_var.get(),
            'max_size': self.max_size_var.get(),
            'order_by': self.order_by_var.get(),
            'bandcamp': self.bandcamp_var.get(),
            'ignore_lossy': self.ignore_lossy_var.get(),
            'ignore_16bit': self.ignore_16bit_var.get(),
            'ignore_trumpable': self.ignore_trumpable_var.get(),
            'album': self.album_var.get(),
            'soundtrack': self.soundtrack_var.get(),
            'ep': self.ep_var.get(),
            'anthology': self.anthology_var.get(),
            'compilation': self.compilation_var.get(),
            'single': self.single_var.get(),
            'live_album': self.live_album_var.get(),
            'remix': self.remix_var.get(),
            'bootleg': self.bootleg_var.get(),
            'interview': self.interview_var.get(),
            'mixtape': self.mixtape_var.get(),
            'demo': self.demo_var.get(),
            'unknown': self.unknown_var.get(),
            'concert_recording': self.concert_recording_var.get(),
            'dj_mix': self.dj_mix_var.get(),
            'exclude_zero_snatches': self.exclude_zero_snatches_var.get(),
            'auto_download': self.auto_download_var.get(),
            'min_seeders': self.min_seeders_var.get(),
            'buffer_limit': self.buffer_limit_var.get(),
            'use_fl_token': self.use_fl_token_var.get(),
            'fl_token_threshold': self.fl_token_threshold_var.get(),
            'request_interval': self.request_interval_var.get(),
        }

    def apply_site_settings(self, config):
        if not config: return
        
        if 'api_key' in config: self.api_key_var.set(config['api_key'])
        if 'save_path' in config: self.save_path_var.set(config['save_path'])
        if 'buffer_formula' in config: self.buffer_formula_var.set(config['buffer_formula'])
        if 'media' in config: self.media_var.set(config['media'])
        if 'year_latest' in config: self.year_latest_var.set(config['year_latest'])
        if 'year_earliest' in config: self.year_earliest_var.set(config['year_earliest'])
        if 'number' in config: self.number_var.set(config['number'])
        if 'max_size' in config: self.max_size_var.set(config['max_size'])
        if 'order_by' in config: self.order_by_var.set(config['order_by'])
        if 'bandcamp' in config: self.bandcamp_var.set(config['bandcamp'])
        if 'ignore_lossy' in config: self.ignore_lossy_var.set(config['ignore_lossy'])
        if 'ignore_16bit' in config: self.ignore_16bit_var.set(config['ignore_16bit'])
        if 'ignore_trumpable' in config: self.ignore_trumpable_var.set(config['ignore_trumpable'])
        if 'album' in config: self.album_var.set(config['album'])
        if 'soundtrack' in config: self.soundtrack_var.set(config['soundtrack'])
        if 'ep' in config: self.ep_var.set(config['ep'])
        if 'anthology' in config: self.anthology_var.set(config['anthology'])
        if 'compilation' in config: self.compilation_var.set(config['compilation'])
        if 'single' in config: self.single_var.set(config['single'])
        if 'live_album' in config: self.live_album_var.set(config['live_album'])
        if 'remix' in config: self.remix_var.set(config['remix'])
        if 'bootleg' in config: self.bootleg_var.set(config['bootleg'])
        if 'interview' in config: self.interview_var.set(config['interview'])
        if 'mixtape' in config: self.mixtape_var.set(config['mixtape'])
        if 'demo' in config: self.demo_var.set(config['demo'])
        if 'unknown' in config: self.unknown_var.set(config['unknown'])
        if 'concert_recording' in config: self.concert_recording_var.set(config['concert_recording'])
        if 'dj_mix' in config: self.dj_mix_var.set(config['dj_mix'])
        if 'exclude_zero_snatches' in config: self.exclude_zero_snatches_var.set(config['exclude_zero_snatches'])
        if 'auto_download' in config: self.auto_download_var.set(config['auto_download'])
        if 'min_seeders' in config: self.min_seeders_var.set(str(config['min_seeders']))
        if 'buffer_limit' in config: self.buffer_limit_var.set(config['buffer_limit'])
        if 'use_fl_token' in config: self.use_fl_token_var.set(config['use_fl_token'])
        if 'fl_token_threshold' in config: self.fl_token_threshold_var.set(config['fl_token_threshold'])
        if 'request_interval' in config: self.request_interval_var.set(config['request_interval'])

    def load_config(self):
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    if "sites" in config:
                        # 新版配置
                        self.site_configs_data = config.get("sites", {"RED": {}, "OPS": {}})
                        
                        if 'site' in config: 
                            self.site_var.set(config['site'])
                        self.last_site = self.site_var.get()
                        
                        global_config = config.get("global", {})
                        if 'qb_host' in global_config: self.qb_host_var.set(global_config['qb_host'])
                        if 'qb_port' in global_config: self.qb_port_var.set(global_config['qb_port'])
                        if 'qb_user' in global_config: self.qb_user_var.set(global_config['qb_user'])
                        if 'qb_pass' in global_config: self.qb_pass_var.set(global_config['qb_pass'])
                        if 'enable_pipeline' in global_config: self.enable_pipeline_var.set(global_config['enable_pipeline'])
                        
                        self.apply_site_settings(self.site_configs_data.get(self.last_site, {}))
                        
                    else:
                        # 兼容旧版本：将现有的扁平配置分别克隆到两个站点中
                        print(_("log_migrate_config"))
                        if 'site' in config: self.site_var.set(config['site'])
                        self.last_site = self.site_var.get()
                        
                        if 'qb_host' in config: self.qb_host_var.set(config['qb_host'])
                        if 'qb_port' in config: self.qb_port_var.set(config['qb_port'])
                        if 'qb_user' in config: self.qb_user_var.set(config['qb_user'])
                        if 'qb_pass' in config: self.qb_pass_var.set(config['qb_pass'])
                        if 'enable_pipeline' in config: self.enable_pipeline_var.set(config['enable_pipeline'])
                        
                        migrated_site_config = config.copy()
                        # 旧版的 API key
                        old_api_keys = config.get('api_keys', {})
                        if not old_api_keys and 'api_key' in config:
                            old_api_keys = {"RED": config['api_key'], "OPS": config['api_key']}
                            
                        self.apply_site_settings(migrated_site_config)
                        self.site_configs_data["RED"] = self.get_current_site_settings()
                        self.site_configs_data["OPS"] = self.get_current_site_settings()
                        
                        # 恢复各自的 API KEY
                        self.site_configs_data["RED"]["api_key"] = old_api_keys.get("RED", "")
                        self.site_configs_data["OPS"]["api_key"] = old_api_keys.get("OPS", "")
                        
                        # 最后重新应用当前选择站点的配置
                        self.apply_site_settings(self.site_configs_data.get(self.last_site, {}))
                        
        except Exception as e:
            print(_("log_config_load_fail").format(e=e))

    def save_config(self):
        try:
            current_site = self.site_var.get()
            self.site_configs_data[current_site] = self.get_current_site_settings()
            
            config = {
                'site': current_site,
                'global': {
                    'qb_host': self.qb_host_var.get(),
                    'qb_port': self.qb_port_var.get(),
                    'qb_user': self.qb_user_var.get(),
                    'qb_pass': self.qb_pass_var.get(),
                    'enable_pipeline': self.enable_pipeline_var.get(),
                },
                'sites': self.site_configs_data
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(_("log_config_save_fail").format(e=e))

    def build_ui(self):
        self.scrollable_frame = ctk.CTkScrollableFrame(self.parent)
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        config_frame = ctk.CTkFrame(self.scrollable_frame)
        config_frame.pack(fill=tk.X, padx=5, pady=5)
        ctk.CTkLabel(config_frame, text=_("core_config"), font=("", 16, "bold")).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=5, padx=5)

        ctk.CTkLabel(config_frame, text=_("site")).grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkComboBox(config_frame, variable=self.site_var, values=['RED', 'OPS'], width=100).grid(row=1, column=1, sticky=tk.W, padx=5)
        ctk.CTkLabel(config_frame, text=_("api_key")).grid(row=1, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.api_key_var, width=200, show="*").grid(row=1, column=3, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("media")).grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkComboBox(config_frame, variable=self.media_var, values=['', 'CD', 'WEB', 'Vinyl', 'SACD', 'Cassette', 'Blu-Ray'], width=120).grid(row=2, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("order_by")).grid(row=2, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkComboBox(config_frame, variable=self.order_by_var, values=['time', 'size', 'snatched', 'seeders', 'random'], width=120).grid(row=2, column=3, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("start_year")).grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.year_earliest_var, width=120).grid(row=3, column=1, sticky=tk.W, padx=5)
        
        ctk.CTkLabel(config_frame, text=_("end_year")).grid(row=3, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.year_latest_var, width=120).grid(row=3, column=3, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("target_count")).grid(row=4, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.number_var, width=120).grid(row=4, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("max_size_mb")).grid(row=4, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.max_size_var, width=120).grid(row=4, column=3, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("req_interval")).grid(row=5, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.request_interval_var, width=120).grid(row=5, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("save_path")).grid(row=6, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.save_path_var, width=300).grid(row=6, column=1, columnspan=2, sticky=tk.W, padx=5)
        ctk.CTkButton(config_frame, text=_("browse"), command=self.browse_save_path, width=80).grid(row=6, column=3, sticky=tk.W, padx=5)

        filter_frame = ctk.CTkFrame(self.scrollable_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        ctk.CTkLabel(filter_frame, text=_("advanced_filters"), font=("", 16, "bold")).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=5, padx=5)
        
        ctk.CTkCheckBox(filter_frame, text=_("nyp_only"), variable=self.bandcamp_var).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text=_("ignore_lossy"), variable=self.ignore_lossy_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text=_("ignore_16bit"), variable=self.ignore_16bit_var).grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text=_("ignore_trumpable"), variable=self.ignore_trumpable_var).grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text=_("excl_0_snatches"), variable=self.exclude_zero_snatches_var).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text=_("auto_dl_torrent"), variable=self.auto_download_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        min_seeders_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        min_seeders_frame.grid(row=2, column=2, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ctk.CTkLabel(min_seeders_frame, text=_("min_seeders")).pack(side=tk.LEFT, padx=(0, 5))
        ctk.CTkEntry(min_seeders_frame, textvariable=self.min_seeders_var, width=60).pack(side=tk.LEFT)

        ctk.CTkLabel(filter_frame, text=_("buffer_limit_gb")).grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        buf_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        buf_frame.grid(row=3, column=0, columnspan=2, sticky=tk.E, padx=5)
        ctk.CTkEntry(buf_frame, textvariable=self.buffer_limit_var, width=60).pack(side=tk.LEFT)
        ctk.CTkLabel(buf_frame, text=_("formula")).pack(side=tk.LEFT, padx=(10,5))
        ctk.CTkEntry(buf_frame, textvariable=self.buffer_formula_var, width=120).pack(side=tk.LEFT)

        ctk.CTkCheckBox(filter_frame, text=_("auto_use_fl_token"), variable=self.use_fl_token_var).grid(row=3, column=2, sticky=tk.W, padx=5)
        token_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        token_frame.grid(row=3, column=3, sticky=tk.W, padx=5)
        ctk.CTkLabel(token_frame, text=_("token_threshold_mb")).pack(side=tk.LEFT, padx=(0,5))
        ctk.CTkEntry(token_frame, textvariable=self.fl_token_threshold_var, width=80).pack(side=tk.LEFT)

        type_frame = ctk.CTkFrame(self.scrollable_frame)
        type_frame.pack(fill=tk.X, padx=5, pady=5)
        ctk.CTkLabel(type_frame, text=_("release_type"), font=("", 16, "bold")).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5, padx=5)
        types_list = [
            (self.album_var, "Album"), (self.soundtrack_var, "Soundtrack"), (self.ep_var, "EP"), 
            (self.anthology_var, "Anthology"), (self.compilation_var, "Compilation"), (self.single_var, "Single"), 
            (self.live_album_var, "Live album"), (self.remix_var, "Remix"), (self.bootleg_var, "Bootleg"), 
            (self.interview_var, "Interview"), (self.mixtape_var, "Mixtape"), (self.demo_var, "Demo"), 
            (self.concert_recording_var, "Concert Recording"), (self.dj_mix_var, "DJ Mix"), (self.unknown_var, "Unknown")
        ]
        
        for idx, (var, text) in enumerate(types_list):
            row = 1 + idx // 3
            col = idx % 3
            ctk.CTkCheckBox(type_frame, text=text, variable=var).grid(row=row, column=col, sticky=tk.W, padx=15, pady=5)

        pipeline_frame = ctk.CTkFrame(self.scrollable_frame)
        pipeline_frame.pack(fill=tk.X, padx=5, pady=5)
        ctk.CTkLabel(pipeline_frame, text=_("auto_pipeline"), font=("", 16, "bold")).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=5, padx=5)
        
        ctk.CTkCheckBox(pipeline_frame, text=_("enable_pipeline"), variable=self.enable_pipeline_var).grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=5, padx=5)
        
        ctk.CTkLabel(pipeline_frame, text=_("qb_host")).grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(pipeline_frame, textvariable=self.qb_host_var, width=200).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        ctk.CTkLabel(pipeline_frame, text=_("qb_port")).grid(row=2, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(pipeline_frame, textvariable=self.qb_port_var, width=100).grid(row=2, column=3, sticky=tk.W, padx=5)
        
        ctk.CTkLabel(pipeline_frame, text=_("qb_user")).grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(pipeline_frame, textvariable=self.qb_user_var, width=200).grid(row=3, column=1, sticky=tk.W, padx=5)
        
        ctk.CTkLabel(pipeline_frame, text=_("qb_pass")).grid(row=3, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(pipeline_frame, textvariable=self.qb_pass_var, width=200, show="*").grid(row=3, column=3, sticky=tk.W, padx=5)

        btn_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.start_btn = ctk.CTkButton(btn_frame, text=_("start_search"), command=self.start_search, fg_color="#28a745", hover_color="#218838")
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ctk.CTkButton(btn_frame, text=_("stop_search"), command=self.stop_search, fg_color="#dc3545", hover_color="#c82333", state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        log_frame = ctk.CTkFrame(self.parent)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        ctk.CTkLabel(log_frame, text=_("run_logs"), font=("", 16, "bold")).pack(anchor=tk.W, padx=5, pady=5)
        
        self.log_tabs = ctk.CTkTabview(log_frame)
        self.log_tabs.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_tabs.add(_("log_tab_main"))
        self.log_tabs.add(_("log_tab_process"))
        self.log_tabs.add(_("log_tab_check"))
        
        self.log_text_main = ctk.CTkTextbox(self.log_tabs.tab(_("log_tab_main")), wrap=tk.WORD)
        self.log_text_main.pack(fill=tk.BOTH, expand=True)
        
        self.log_text_process = ctk.CTkTextbox(self.log_tabs.tab(_("log_tab_process")), wrap=tk.WORD)
        self.log_text_process.pack(fill=tk.BOTH, expand=True)
        
        self.log_text_check = ctk.CTkTextbox(self.log_tabs.tab(_("log_tab_check")), wrap=tk.WORD)
        self.log_text_check.pack(fill=tk.BOTH, expand=True)

        sys.stdout = RedirectText(self.log_text_main)
        self.log_main = RedirectText(self.log_text_main)
        self.log_process = RedirectText(self.log_text_process)
        self.log_check = RedirectText(self.log_text_check)

    def browse_save_path(self):
        directory = filedialog.askdirectory()
        if directory:
            self.save_path_var.set(directory)

    def _safe_int(self, var, default=0):
        try: return int(var.get())
        except ValueError: return default

    def _safe_float(self, var, default=0.0):
        try: return float(var.get())
        except ValueError: return default

    def get_options(self):
        return SimpleNamespace(
            api_key=self.api_key_var.get().strip(),
            site_config=SITE_CONFIGS.get(self.site_var.get(), SITE_CONFIGS["RED"]),
            bandcamp=self.bandcamp_var.get(),
            cache=f'EliteTMHelper2_{self.site_var.get()}.cache',
            dont_cache_yays=False,
            ignore_20_pages_limit=False,
            any16bit=self.ignore_16bit_var.get(),
            lossy=self.ignore_lossy_var.get(),
            trumpable=self.ignore_trumpable_var.get(),
            uns=False,
            max_size=self._safe_int(self.max_size_var, 2048) * 1048576,
            media=self.media_var.get() if self.media_var.get() else "",
            min_seeders=self._safe_int(self.min_seeders_var, 0),
            order_by=self.order_by_var.get(),
            order_way="desc",
            output=f'EliteTMHelper2_{self.site_var.get()}_Found.txt',
            output_args=False,
            html=False,
            find_number=self._safe_int(self.number_var, 50),
            release_type="",
            exclude_zero_snatches=self.exclude_zero_snatches_var.get(),
            auto_download=self.auto_download_var.get(),
            release_type_allowed={
                1: self.album_var.get(),
                3: self.soundtrack_var.get(),
                5: self.ep_var.get(),
                6: self.anthology_var.get(),
                7: self.compilation_var.get(),
                9: self.single_var.get(),
                11: self.live_album_var.get(),
                13: self.remix_var.get(),
                14: self.bootleg_var.get(),
                15: self.interview_var.get(),
                16: self.mixtape_var.get(),
                17: self.demo_var.get(),
                21: self.unknown_var.get(),
                22: self.concert_recording_var.get(),
                23: self.dj_mix_var.get()
            },
            buffer_limit=self._safe_float(self.buffer_limit_var, 10.0),
            buffer_formula=self.buffer_formula_var.get(),
            use_fl_token=self.use_fl_token_var.get(),
            fl_token_threshold=self._safe_int(self.fl_token_threshold_var, 500),
            show_api_times=False,
            show_size=True,
            tags=None,
            tags_type=0,
            year_earliest=self._safe_int(self.year_earliest_var, 1970),
            year_latest=self._safe_int(self.year_latest_var, 2023),
            request_interval=self._safe_float(self.request_interval_var, 3.0),
            save_path=self.save_path_var.get(),
            qb_host=self.qb_host_var.get(),
            qb_port=self.qb_port_var.get(),
            qb_user=self.qb_user_var.get(),
            qb_pass=self.qb_pass_var.get(),
            enable_pipeline=self.enable_pipeline_var.get()
        )

    def start_search(self):
        if not self.api_key_var.get().strip():
            messagebox.showwarning(_("msg_tip_title"), _("msg_need_api_key_box"))
            return

        self.save_config()

        self.is_running = True
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.log_text_main.delete(1.0, tk.END)
        self.log_text_process.delete(1.0, tk.END)
        self.log_text_check.delete(1.0, tk.END)
        print(_("log_starting_bg_search"))

        threading.Thread(target=self.run_thread, daemon=True).start()

    def ask_manual_check(self, album_name):
        result_event = threading.Event()
        result_var = [False]

        def show_prompt():
            res = messagebox.askyesno(_("msg_manual_confirm_title"), _("msg_manual_confirm_prompt").format(album=album_name), parent=self.parent)
            result_var[0] = res
            result_event.set()

        self.parent.after(0, show_prompt)
        result_event.wait()
        return result_var[0]

    def stop_search(self):
        self.is_running = False
        print(_("log_sending_stop"))
        self.stop_btn.configure(state=tk.DISABLED)

    def run_thread(self):
        try:
            options = self.get_options()
            
            if hasattr(self, 'pipeline') and self.pipeline:
                self.pipeline.stop()
                self.pipeline = None
            
            pipeline = None
            if options.enable_pipeline:
                try:
                    import time as _time
                    from pipeline_manager import PipelineManager
                    pipeline = PipelineManager(
                        options.qb_host, options.qb_port, options.qb_user, options.qb_pass,
                        None, options, 
                        log_main=lambda s: self.log_main.write(f"[{_time.strftime('%H:%M:%S')}] {s}\n"),
                        log_process=lambda s: self.log_process.write(f"[{_time.strftime('%H:%M:%S')}] {s}\n"),
                        log_check=lambda s: self.log_check.write(f"[{_time.strftime('%H:%M:%S')}] {s}\n"),
                        ask_manual_check=self.ask_manual_check
                    )
                    pipeline.start()
                    self.pipeline = pipeline
                    options.pipeline = pipeline
                except Exception as e:
                    print(_("log_init_pipeline_fail").format(e=e))
            
            perform_search(options, abort_flag=lambda: not self.is_running)
            
            if pipeline:
                print(_("log_search_done_pipeline_bg"))
        except RedactedAPIError as e:
            print(_("log_api_error_final").format(e=str(e)))
        except Exception as e:
            import traceback
            print(_("log_sys_error_final").format(e=str(e), tb=traceback.format_exc()))
            self.stop_search()
        finally:
            self.is_running = False
            try:
                self.parent.after(0, self._reset_buttons)
            except:
                pass

    def _reset_buttons(self):
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)

if __name__ == "__main__":
    pass