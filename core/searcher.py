"""
搜索核心逻辑

从 elitetmhelper2.py 提取：Cache、get_edition、FoundTorrent、
search_result_iterator、perform_search 等搜索业务逻辑。
"""

import time
import json
import re
import random
from pathlib import Path
from types import SimpleNamespace
import requests
import core.globals
from i18n import _
from errors import APIError as RedactedAPIError
from core.site_config import SITE_CONFIGS, GENRE_TAGS, ORDER_COMBOS, MEDIA_TYPES
from redacted_session import RedactedSession

class Cache:
    def __init__(self, options):
        self.options = options
        self.json_file = Path(self.options.cache)
        self.cache_key = self.options.cache
        
        if core.globals.app_context and core.globals.app_context.gateway:
            gateway = core.globals.app_context.gateway
            cached_str = gateway.read_cache("elitetm", self.cache_key, None)
            if cached_str:
                try:
                    self.data = json.loads(cached_str)
                except json.JSONDecodeError:
                    self.data = {'0': "nope"}
            else:
                self.data = {'0': "nope"}
                gateway.write_cache("elitetm", self.cache_key, json.dumps(self.data), 86400 * 30)
        else:
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
        if core.globals.app_context and core.globals.app_context.gateway:
            gateway = core.globals.app_context.gateway
            gateway.write_cache("elitetm", self.cache_key, json.dumps(self.data), 86400 * 30)
        else:
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

    def missing_mp3(self):
        for torrent in self.torrents:
            if get_edition(torrent) == self.edition:
                enc = torrent.get("encoding", "")
                if enc == "320" or enc == "V0 (VBR)":
                    return False
        return True

def search_result_iterator(session, options, found, abort_flag):
    year = int(options.year_latest)
    
    seen_groups = set()
    site_config = getattr(options, 'site_config', SITE_CONFIGS["RED"])
    max_pages = site_config.get("max_pages", 20)
    enable_tag_split = site_config.get("enable_tag_split", True)

    while year > int(options.year_earliest) - 1:
        if abort_flag(): # 优化：检查是否需要中断
            print(_("log_search_aborted"))
            return

        if options.order_by == "random":
            if found >= options.find_number:
                print(_("log_requested_torrents_found").format(found=found))
                return # 优化：将 quit() 换成 return
            year = random.choice(list(range(int(options.year_earliest), int(options.year_latest+1))))
        
        # 每个 queue item 携带拆分历史，便于决定下一步拆分方向
        # {"params": {额外搜索参数}, "splits": [已使用的拆分维度列表]}
        search_queue = [{"params": {}, "splits": []}]
        
        while search_queue:
            if abort_flag(): return
            item = search_queue.pop(0)
            extra_params = item["params"]
            splits_done = item["splits"]
            
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
            if "taglist" in extra_params: search_label_parts.append(f"Tag:{extra_params['taglist']}")
            if "order_by" in extra_params or "order_way" in extra_params:
                ob = extra_params.get('order_by', options.order_by)
                ow = extra_params.get('order_way', options.order_way)
                search_label_parts.append(f"Sort:{ob}/{ow}")
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
            
            # 仅当 API 返回超过 max_pages (20) 页时才需要拆分
            if number_of_pages > max_pages:
                # Layer 1: 按 Release Type 拆分
                if "releasetype" not in splits_done and "releasetype" not in extra_params and options.release_type == "":
                    print(_("log_gt_20_pages_rt").format(year=year, label=search_label, max_pages=max_pages))
                    release_types = [1, 3, 5, 6, 7, 9, 11, 13, 14, 15, 16, 21, 22, 23]
                    for rt in release_types:
                        new_params = extra_params.copy()
                        new_params["releasetype"] = rt
                        search_queue.append({"params": new_params, "splits": splits_done + ["releasetype"]})
                    continue
                # Layer 2: 按 Media 拆分
                elif "media" not in splits_done and "media" not in extra_params and options.media == "":
                    print(_("log_gt_20_pages_media").format(year=year, label=search_label, max_pages=max_pages))
                    for m in MEDIA_TYPES:
                        new_params = extra_params.copy()
                        new_params["media"] = m
                        search_queue.append({"params": new_params, "splits": splits_done + ["media"]})
                    continue
                # Layer 3: 按流派 Tag 拆分 (仅 RED 启用)
                elif enable_tag_split and "taglist" not in splits_done and "taglist" not in extra_params:
                    print(_("log_gt_20_pages_tag").format(year=year, label=search_label, max_pages=max_pages))
                    for tag in GENRE_TAGS:
                        new_params = extra_params.copy()
                        new_params["taglist"] = tag
                        new_params["tags_type"] = 1  # 精确匹配
                        search_queue.append({"params": new_params, "splits": splits_done + ["taglist"]})
                    continue
                # Layer 4: 多排序组合拆分
                elif "order_combo" not in splits_done:
                    print(_("log_gt_20_pages_order").format(year=year, label=search_label, max_pages=max_pages))
                    for ob, ow in ORDER_COMBOS:
                        new_params = extra_params.copy()
                        new_params["order_by"] = ob
                        new_params["order_way"] = ow
                        search_queue.append({"params": new_params, "splits": splits_done + ["order_combo"]})
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

    session = RedactedSession.from_options(options)
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip,deflate,sdch',
        'Accept-Language': 'en-US,en;q=0.8'
    }
    
    auth_key = options.api_key
    auth_type = site_config.get("auth_type", "api_key")
    if auth_type == "cookie":
        if "=" not in auth_key:
            if site_config.get("source") in ["JPS", "DIC"]:
                auth_key = f"PHPSESSID={auth_key}"
            else:
                auth_key = f"session={auth_key}"
        headers['Cookie'] = auth_key
    else:
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
                if getattr(options, 'ignore_mp3_exists', False) and not this_torrent.missing_mp3(): nope.append(" mp3_exists")
                if options.bandcamp and not this_torrent.bandcamp(): nope.append(" bc")
                if options.trumpable and this_torrent.trump_status: nope.append(" tr")
                if options.lossy and this_torrent.lossy_status: nope.append(" lo")
                if options.uns and this_torrent.uns(): nope.append(" un")
                if options.min_seeders and this_torrent.seeders < options.min_seeders: nope.append(" sd")
                if options.exclude_zero_snatches and this_torrent.snatched == 0: nope.append(" 0snatches")
                if options.max_size and torrent.get("size", 0) > options.max_size: nope.append(" >max_size")
                if getattr(options, 'min_size', 0) > 0 and torrent.get("size", 0) < options.min_size: nope.append(" <min_size")

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
                            if site_config.get("source") in ["DIC", "JPS"]:
                                base_url = site_config.get("base_url", api_url.replace("/ajax.php", ""))
                                dl_url = f"{base_url}/torrents.php?action=download&id={torrent['torrentId']}"
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

