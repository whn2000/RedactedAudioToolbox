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
        return self.get("https://redacted.sh/ajax.php", params=params)

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
        x: torrent[x] for x in [
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
        self.bbBody = self.group_info["response"]["group"]["bbBody"]
        self.lossy_status = False
        self.trump_status = False
        self.edition = []
        self.seeders = 0

    def is_24_bit(self):
        for torrent in self.torrents:
            if torrent["id"] == self.torrent_id:
                self.edition = get_edition(torrent)
                if torrent['lossyWebApproved'] or torrent['lossyMasterApproved']:
                    self.lossy_status = True
                if torrent['trumpable']:
                    self.trump_status = True
                self.seeders = torrent['seeders']
                self.snatched = torrent.get('snatched', torrent.get('snatches', 0))
                break

        for torrent in self.torrents:
            if get_edition(torrent) == self.edition:
                if torrent["encoding"] == "Lossless":
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
            if torrent['remastered'] is True and torrent['remasterYear'] == 0 and torrent['encoding'] == "Lossless":
                result = True
            if torrent['remastered'] is False and torrent['remasterYear'] == 0 and torrent['encoding'] == "Lossless":
                result = True
        return result

    def any_16_bit(self):
        for torrent in self.torrents:
            if torrent["encoding"] == "Lossless":
                return True
        return False

def search_result_iterator(session, options, found, abort_flag):
    year = int(options.year_latest)
    
    seen_groups = set()

    while year > int(options.year_earliest) - 1:
        if abort_flag(): # 优化：检查是否需要中断
            print("\n[!] 搜索被用户手动终止。")
            return

        if options.order_by == "random":
            if found >= options.find_number:
                print(f"{found} requested torrents found")
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
            
            print(f"请求 {year} 年 {search_label}第 1 页...")
            try:
                first_page = session.get_api(params).json()
            except requests.exceptions.RequestException as e:
                raise RedactedAPIError(f"网络请求失败: {str(e)}")
            except json.decoder.JSONDecodeError:
                raise RedactedAPIError("无效的登录凭证或 Cookie 过期")

            if first_page.get("status") != "success":
                # API 返回状态不成功
                break
                
            if not first_page["response"]["results"]:
                print(f"{year} 年 {search_label}没有找到结果")
                continue
            else:
                number_of_pages = first_page["response"]["pages"]

            print(f"找到 {number_of_pages} 页结果")
            
            if number_of_pages > 20:
                if "releasetype" not in extra_params and options.release_type == "":
                    print(f"⚠️ {year} 年 {search_label}结果超过 20 页。正在按 发行类型(Release Type) 细分搜索...")
                    release_types = [1, 3, 5, 6, 7, 9, 11, 13, 14, 15, 16, 21, 22, 23]
                    for rt in release_types:
                        new_params = extra_params.copy()
                        new_params["releasetype"] = rt
                        search_queue.append(new_params)
                    continue
                elif "media" not in extra_params and options.media == "":
                    print(f"⚠️ {year} 年 {search_label}结果依然超过 20 页。正在按 介质(Media) 细分搜索...")
                    medias = ['CD', 'WEB', 'Vinyl', 'SACD', 'Cassette', 'Blu-Ray', 'DVD', 'Soundboard']
                    for m in medias:
                        new_params = extra_params.copy()
                        new_params["media"] = m
                        search_queue.append(new_params)
                    continue
                elif "order_way" not in extra_params:
                    print(f"⚠️ {year} 年 {search_label}细分后依然超过 20 页。将分别获取最新和最旧的 1000 个种子...")
                    new_params_desc = extra_params.copy()
                    new_params_desc["order_way"] = "desc"
                    search_queue.append(new_params_desc)
                    
                    new_params_asc = extra_params.copy()
                    new_params_asc["order_way"] = "asc"
                    search_queue.append(new_params_asc)
                    continue
                else:
                    print(f"⚠️ {year} 年 {search_label}已穷尽细分策略，只能获取部分数据 (前 20 页)。")
                    
            actual_pages = min(number_of_pages, 20)

            for group in first_page["response"]["results"]:
                if abort_flag(): return
                
                group_id = group["groupId"]
                if group_id in seen_groups:
                    continue
                seen_groups.add(group_id)
                
                rt = group.get("releaseType", 1)
                if rt == 1 and not options.allow_album: continue
                if rt == 5 and not options.allow_ep: continue
                if rt == 9 and not options.allow_single: continue
                
                if any(map(lambda x: x["size"] > options.max_size, group["torrents"])):
                    if options.order_by == "size" and options.order_way == "asc":
                        exceded_max_size = True
                        print("文件超出最大体积限制，跳过...")
                        break
                else:
                    yield group
                    
            if exceded_max_size:
                continue

            for i in range(2, actual_pages + 1):
                if abort_flag(): return
                params["page"] = i
                print(f"请求 {year} 年 {search_label}第 {i}/{number_of_pages} 页...")
                try:
                    page = session.get_api(params).json()
                except Exception as e:
                    print(f"获取第 {i} 页失败，跳过。原因: {str(e)}")
                    break

                if page.get("status") != "success":
                    print("API 返回异常，终止当前关键词搜索。")
                    break

                if not page["response"]["results"]:
                    print(f"达到 API 限制，转到下一个关键词...")
                    break

                for group in page["response"]["results"]:
                    if abort_flag(): return
                    
                    group_id = group["groupId"]
                    if group_id in seen_groups:
                        continue
                    seen_groups.add(group_id)
                    
                    rt = group.get("releaseType", 1)
                    if rt == 1 and not options.allow_album: continue
                    if rt == 5 and not options.allow_ep: continue
                    if rt == 9 and not options.allow_single: continue
                    
                    if any(map(lambda x: x["size"] > options.max_size, group["torrents"])):
                        if options.order_by == "size" and options.order_way == "asc":
                            exceded_max_size = True
                            print("文件超出最大体积限制，跳过...")
                            break
                    else:
                        yield group
                if exceded_max_size:
                    break

        if options.order_by != 'random':
            year -= 1

def perform_search(options, abort_flag):
    found = 0
    if not options.api_key:
        print("请提供 API key!")
        return

    session = RedactedSession(options)
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'User-Agent': 'EliteTMHelper_GUI',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip,deflate,sdch',
        'Accept-Language': 'en-US,en;q=0.8',
        'Authorization': f'{options.api_key}'}
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
                print(f"⚠️ Buffer 公式 '{formula}' 解析失败 ({e})，降级使用默认公式: (U / 0.65) - D")
                current_buffer = (uploaded / 0.65) - downloaded
                
            current_buffer_gb = current_buffer / (1024**3)
            print(f">>> 当前账号 Buffer 约为: {current_buffer_gb:.2f} GB (保护线: {options.buffer_limit} GB)")
    except Exception as e:
        print(f"获取用户账号信息失败，将跳过 Buffer 检查: {e}")

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
        except Exception as e:
            print(f"获取组信息失败 groupId={group['groupId']}: {str(e)}")
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

                if nope == [""]:
                    found += 1
                    with Path(options.output).open(mode='a+', encoding='utf-8') as myfile:
                        html_start = html_mid = html_end = html_found = ""
                        if options.html:
                            html_start = '<a href="'
                            html_mid = '">https://redacted.sh/torrents.php?id=' + str(group['groupId']) + '&torrentid=' + str(torrent['torrentId']) + '</a>'
                            html_end = '</br>'
                            html_found = str(found) + " "
                        myfile.write(f"{html_found}{html_start}https://redacted.sh/torrents.php?id={group['groupId']}&torrentid={torrent['torrentId']}{html_mid}")
                        if options.show_size:
                            myfile.write(f" {round(torrent['size']/1048576, 2)}MB")
                        myfile.write(f"{html_end}\n")
                        
                    print(f"torrent<{torrent['torrentId']: >7}> : 发现目标! https://redacted.sh/torrents.php?id={group['groupId']}&torrentid={torrent['torrentId']}", end="")
                    if options.show_size: print(f" {round(torrent['size']/1048576, 2)}MB", end="")
                    
                    if options.auto_download:
                        size_mb = torrent['size'] / 1048576
                        
                        # 检查 Buffer 是否够用
                        if not options.use_fl_token or size_mb < options.fl_token_threshold:
                            if current_buffer_gb - (size_mb / 1024) < options.buffer_limit:
                                print(f" ⚠️ Buffer 将低于安全线 ({options.buffer_limit} GB)，停止下载当前及后续种子！")
                                return
                            current_buffer_gb -= (size_mb / 1024) # 扣除预计下载量

                        try:
                            dl_url = f"https://redacted.sh/ajax.php?action=download&id={torrent['torrentId']}"
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
                                print(f" [已下载{token_str}: {save_path}]", end="")
                                
                                # 将 metadata 保存为 json 供 PipelineManager 读取
                                meta_path = save_path.with_suffix('.json')
                                with open(meta_path, 'w', encoding='utf-8') as f:
                                    json.dump({
                                        'group_info': group_info,
                                        'torrent_info': torrent,
                                        'tracker_url': 'https://flacsfor.me/announce'
                                    }, f)
                                
                                # 推送到 qBittorrent
                                if hasattr(options, 'pipeline') and options.pipeline:
                                    options.pipeline.add_to_pipeline(str(save_path), group_info, torrent, str(save_path.parent))
                                    
                            else:
                                print(f" [下载失败 {dl_res.status_code}]", end="")
                        except Exception as e:
                            print(f" [下载异常: {e}]", end="")
                    
                    print("")
                    
                    if cache and not options.dont_cache_yays:
                        cache.data[str(torrent['torrentId'])] = "yay"
                        cache.write()
                else:
                    print(f"torrent<{torrent['torrentId']: >7}> : 忽略{''.join(nope)}")
                    if cache:
                        cache.data[str(torrent['torrentId'])] = "nope"
                        cache.write()
            else:
                print(f"torrent<{torrent['torrentId']: >7}> : 忽略 (非独立24bit)")
                if cache:
                    cache.data[str(torrent['torrentId'])] = "nope"
                    cache.write()
                    
            if found >= options.find_number:
                print(f"\n✅ 已达到设定的目标数量: {found} 个")
                return

    print(f"\n🏁 搜索完成，共找到 {found} 个结果")


# ==========================================
# 桌面图形界面 GUI 逻辑
# ==========================================

class RedirectText:
    """拦截 print 输出并重定向到 Tkinter 文本框"""
    def __init__(self, text_ctrl):
        self.output = text_ctrl

    def write(self, string):
        self.output.insert(tk.END, string)
        self.output.see(tk.END)

    def flush(self):
        pass

class AppGUI:
    def __init__(self, parent):
        self.parent = parent
        self.is_running = False
        
        # 定义界面绑定的变量
        self.api_key_var = tk.StringVar()
        self.save_path_var = tk.StringVar()
        self.media_var = tk.StringVar(value="CD")
        self.year_latest_var = tk.IntVar(value=2023)
        self.year_earliest_var = tk.IntVar(value=1970)
        self.number_var = tk.IntVar(value=50)
        self.max_size_var = tk.IntVar(value=2048)
        self.order_by_var = tk.StringVar(value="time")
        
        # 布尔开关
        self.bandcamp_var = tk.BooleanVar(value=False)
        self.ignore_lossy_var = tk.BooleanVar(value=False)
        self.ignore_16bit_var = tk.BooleanVar(value=False)
        self.ignore_trumpable_var = tk.BooleanVar(value=False)
        
        self.album_var = tk.BooleanVar(value=True)
        self.ep_var = tk.BooleanVar(value=True)
        self.single_var = tk.BooleanVar(value=True)
        self.exclude_zero_snatches_var = tk.BooleanVar(value=False)
        self.auto_download_var = tk.BooleanVar(value=False)
        
        self.buffer_limit_var = tk.DoubleVar(value=10.0) # GB
        self.buffer_formula_var = tk.StringVar(value="(U / 0.65) - D")
        self.use_fl_token_var = tk.BooleanVar(value=False)
        self.fl_token_threshold_var = tk.IntVar(value=500) # MB
        
        self.qb_host_var = tk.StringVar(value="http://127.0.0.1")
        self.qb_port_var = tk.StringVar(value="8080")
        self.qb_user_var = tk.StringVar(value="admin")
        self.qb_pass_var = tk.StringVar(value="adminadmin")
        self.enable_pipeline_var = tk.BooleanVar(value=False)

        self.request_interval_var = tk.DoubleVar(value=3.0)

        self.config_file = "config.json"
        self.load_config()

        # 构建界面元素
        self.build_ui()

    def load_config(self):
        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'api_key' in config:
                        self.api_key_var.set(config['api_key'])
                    if 'save_path' in config:
                        self.save_path_var.set(config['save_path'])
                    if 'buffer_formula' in config:
                        self.buffer_formula_var.set(config['buffer_formula'])
                    if 'qb_host' in config: self.qb_host_var.set(config['qb_host'])
                    if 'qb_port' in config: self.qb_port_var.set(config['qb_port'])
                    if 'qb_user' in config: self.qb_user_var.set(config['qb_user'])
                    if 'qb_pass' in config: self.qb_pass_var.set(config['qb_pass'])
                    if 'enable_pipeline' in config: self.enable_pipeline_var.set(config['enable_pipeline'])
        except Exception as e:
            print(f"Failed to load config: {e}")

    def save_config(self):
        try:
            config = {
                'api_key': self.api_key_var.get(),
                'save_path': self.save_path_var.get(),
                'buffer_formula': self.buffer_formula_var.get(),
                'qb_host': self.qb_host_var.get(),
                'qb_port': self.qb_port_var.get(),
                'qb_user': self.qb_user_var.get(),
                'qb_pass': self.qb_pass_var.get(),
                'enable_pipeline': self.enable_pipeline_var.get()
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def build_ui(self):
        # --- 1. 配置区 ---
        config_frame = ttk.LabelFrame(self.parent, text="核心配置 (Core Config)", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(config_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.api_key_var, width=50, show="*").grid(row=0, column=1, columnspan=3, sticky=tk.W, padx=5)

        ttk.Label(config_frame, text="媒介 (Media):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(config_frame, textvariable=self.media_var, values=['', 'CD', 'WEB', 'Vinyl', 'SACD', 'Cassette', 'Blu-Ray'], width=12).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(config_frame, text="排序方式 (Order By):").grid(row=1, column=2, sticky=tk.W, pady=2)
        ttk.Combobox(config_frame, textvariable=self.order_by_var, values=['time', 'size', 'snatched', 'seeders', 'random'], width=12).grid(row=1, column=3, sticky=tk.W, padx=5)

        ttk.Label(config_frame, text="起始年份 (Start Year):").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.year_earliest_var, width=14).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(config_frame, text="截止年份 (End Year):").grid(row=2, column=2, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.year_latest_var, width=14).grid(row=2, column=3, sticky=tk.W, padx=5)

        ttk.Label(config_frame, text="目标数量 (Target Count):").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.number_var, width=14).grid(row=3, column=1, sticky=tk.W, padx=5)

        ttk.Label(config_frame, text="最大体积 (Max Size MB):").grid(row=3, column=2, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.max_size_var, width=14).grid(row=3, column=3, sticky=tk.W, padx=5)

        ttk.Label(config_frame, text="请求间隔(s) (Req Interval):").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.request_interval_var, width=14).grid(row=4, column=1, sticky=tk.W, padx=5)

        ttk.Label(config_frame, text="保存路径 (Save Path):").grid(row=5, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.save_path_var, width=50).grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=5)
        ttk.Button(config_frame, text="浏览 (Browse)", command=self.browse_save_path).grid(row=5, column=3, sticky=tk.W, padx=5)

        # --- 2. 过滤选项区 ---
        filter_frame = ttk.LabelFrame(self.parent, text="高级过滤选项 (Advanced Filters)", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Checkbutton(filter_frame, text="仅限 Bandcamp (NYP Only)", variable=self.bandcamp_var).grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Checkbutton(filter_frame, text="忽略 Lossy 批准 (Ignore Lossy)", variable=self.ignore_lossy_var).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Checkbutton(filter_frame, text="忽略包含 16bit 的组 (Ignore 16bit)", variable=self.ignore_16bit_var).grid(row=0, column=2, sticky=tk.W, padx=5)
        ttk.Checkbutton(filter_frame, text="忽略 Trumpable (Ignore Trumpable)", variable=self.ignore_trumpable_var).grid(row=0, column=3, sticky=tk.W, padx=5)
        ttk.Checkbutton(filter_frame, text="排除 0 完成数(Snatched) (Excl 0 Snatches)", variable=self.exclude_zero_snatches_var).grid(row=1, column=0, sticky=tk.W, padx=5)
        ttk.Checkbutton(filter_frame, text="自动下载种子 (Auto DL Torrent)", variable=self.auto_download_var).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(filter_frame, text="保护 Buffer(GB):").grid(row=2, column=0, sticky=tk.W, pady=2)
        buf_frame = ttk.Frame(filter_frame)
        buf_frame.grid(row=2, column=0, sticky=tk.E, padx=5)
        ttk.Entry(buf_frame, textvariable=self.buffer_limit_var, width=6).pack(side=tk.LEFT)
        ttk.Label(buf_frame, text="公式:").pack(side=tk.LEFT, padx=(5,0))
        ttk.Entry(buf_frame, textvariable=self.buffer_formula_var, width=12).pack(side=tk.LEFT)

        ttk.Checkbutton(filter_frame, text="自动使用 FL Token", variable=self.use_fl_token_var).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(filter_frame, text="Token 大小阈值(MB):").grid(row=2, column=2, sticky=tk.W, pady=2)
        ttk.Entry(filter_frame, textvariable=self.fl_token_threshold_var, width=10).grid(row=2, column=2, sticky=tk.E, padx=5)

        # 新增发行类型区
        type_frame = ttk.LabelFrame(self.parent, text="发行类型筛选 (Release Type)", padding=10)
        type_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Checkbutton(type_frame, text="Album (专辑)", variable=self.album_var).grid(row=0, column=0, sticky=tk.W, padx=15)
        ttk.Checkbutton(type_frame, text="EP", variable=self.ep_var).grid(row=0, column=1, sticky=tk.W, padx=15)
        ttk.Checkbutton(type_frame, text="Single (单曲)", variable=self.single_var).grid(row=0, column=2, sticky=tk.W, padx=15)

        # --- 2.5 自动化工作流与 qBittorrent ---
        pipeline_frame = ttk.LabelFrame(self.parent, text="自动化工作流 (Auto Pipeline & qBittorrent)", padding=10)
        pipeline_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Checkbutton(pipeline_frame, text="启用完整流水线 (下载->降频->检查->尝试上传)", variable=self.enable_pipeline_var).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=5)
        
        ttk.Label(pipeline_frame, text="qB Host:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(pipeline_frame, textvariable=self.qb_host_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(pipeline_frame, text="qB Port:").grid(row=1, column=2, sticky=tk.W, pady=2)
        ttk.Entry(pipeline_frame, textvariable=self.qb_port_var, width=10).grid(row=1, column=3, sticky=tk.W, padx=5)
        
        ttk.Label(pipeline_frame, text="qB User:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(pipeline_frame, textvariable=self.qb_user_var, width=20).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(pipeline_frame, text="qB Pass:").grid(row=2, column=2, sticky=tk.W, pady=2)
        ttk.Entry(pipeline_frame, textvariable=self.qb_pass_var, width=20, show="*").grid(row=2, column=3, sticky=tk.W, padx=5)

        # --- 3. 按钮区 ---
        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_btn = ttk.Button(btn_frame, text="▶ 开始搜索 (Start Search)", command=self.start_search)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止搜索 (Stop Search)", command=self.stop_search, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # --- 4. 日志区 ---
        log_frame = ttk.LabelFrame(self.parent, text="运行日志 (Run Logs)", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.NORMAL, bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        sys.stdout = RedirectText(self.log_text)

    def browse_save_path(self):
        directory = filedialog.askdirectory()
        if directory:
            self.save_path_var.set(directory)

    def get_options(self):
        return SimpleNamespace(
            api_key=self.api_key_var.get().strip(),
            bandcamp=self.bandcamp_var.get(),
            cache='EliteTMHelper2_GUI.cache',
            dont_cache_yays=False,
            ignore_20_pages_limit=False,
            any16bit=self.ignore_16bit_var.get(),
            lossy=self.ignore_lossy_var.get(),
            trumpable=self.ignore_trumpable_var.get(),
            uns=False,
            max_size=self.max_size_var.get() * 1048576,
            media=self.media_var.get() if self.media_var.get() else "",
            min_seeders=1,
            order_by=self.order_by_var.get(),
            order_way="desc",
            output="EliteTMHelper2_Found.txt",
            output_args=False,
            html=False,
            find_number=self.number_var.get(),
            release_type="",
            exclude_zero_snatches=self.exclude_zero_snatches_var.get(),
            auto_download=self.auto_download_var.get(),
            allow_album=self.album_var.get(),
            allow_ep=self.ep_var.get(),
            allow_single=self.single_var.get(),
            buffer_limit=self.buffer_limit_var.get(),
            buffer_formula=self.buffer_formula_var.get(),
            use_fl_token=self.use_fl_token_var.get(),
            fl_token_threshold=self.fl_token_threshold_var.get(),
            show_api_times=False,
            show_size=True,
            tags=None,
            tags_type=0,
            year_earliest=self.year_earliest_var.get(),
            year_latest=self.year_latest_var.get(),
            request_interval=self.request_interval_var.get(),
            save_path=self.save_path_var.get(),
            qb_host=self.qb_host_var.get(),
            qb_port=self.qb_port_var.get(),
            qb_user=self.qb_user_var.get(),
            qb_pass=self.qb_pass_var.get(),
            enable_pipeline=self.enable_pipeline_var.get()
        )

    def start_search(self):
        if not self.api_key_var.get().strip():
            messagebox.showwarning("提示", "执行前请先填入有效的 API Key！")
            return

        self.save_config()

        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        print(">>> 正在启动后台搜索线程，请稍候...\n")

        threading.Thread(target=self.run_thread, daemon=True).start()

    def stop_search(self):
        self.is_running = False
        print("\n>>> 正在发送停止信号，等待当前请求完成...\n")
        self.stop_btn.config(state=tk.DISABLED)

    def run_thread(self):
        try:
            options = self.get_options()
            
            # 初始化 PipelineManager
            pipeline = None
            if options.enable_pipeline:
                try:
                    from pipeline_manager import PipelineManager
                    pipeline = PipelineManager(
                        options.qb_host, options.qb_port, options.qb_user, options.qb_pass,
                        None, options, log_callback=print
                    )
                    pipeline.start()
                    # 挂载到 options 上供 perform_search 使用
                    options.pipeline = pipeline
                except Exception as e:
                    print(f"初始化流水线失败: {e}")
            
            perform_search(options, abort_flag=lambda: not self.is_running)
            
            if pipeline:
                print(">>> 搜索完成，流水线监控将继续在后台运行，直至您关闭程序。")
        except RedactedAPIError as e:
            print(f"\n❌ [API 错误]: {str(e)}")
        except Exception as e:
            print(f"\n❌ [系统错误]: 发生未捕获的异常 - {str(e)}")
        finally:
            self.is_running = False
            self.parent.after(0, self._reset_buttons)

    def _reset_buttons(self):
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    
    # 启用高 DPI 支持，让字体在 4K 屏幕上不模糊
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    app = AppGUI(root)
    root.mainloop()