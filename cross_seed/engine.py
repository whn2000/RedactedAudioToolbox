import time
import threading
import json
from pathlib import Path
from typing import List, Dict, Any, Callable
from core.clients.factory import create_client
from cross_seed.red_checker import RedChecker
from cross_seed.metadata import MetadataFetcher
import traceback
import subprocess
import requests

class CrossSeedEngine:
    def __init__(self, app_context, pipeline_manager, qb_host, qb_port, qb_user, qb_pass, save_path, client_type="qBittorrent", rclone_remote=None, rclone_config=None):
        self.app_context = app_context
        self.pipeline_manager = pipeline_manager
        self.client_type = client_type
        self.rclone_remote = rclone_remote
        self.rclone_config = rclone_config
        self.save_path = save_path
        
        from core.clients.factory import create_client
        self.client = create_client(client_type, qb_host, qb_port, qb_user, qb_pass)
        self.metadata_fetcher = MetadataFetcher()
        self.is_running = False
        self.thread = None
        
        self.sessions = {}
        config = self.app_context.gateway.get_config("global") or {} if self.app_context and self.app_context.gateway else {}
        self.checker = RedChecker(self.sessions, config)
        self.reload_sessions()
        
    def reload_sessions(self):
        self.sessions.clear()
        config = {}
        if self.app_context and self.app_context.gateway:
            config = self.app_context.gateway.get_config("global") or {}
            sites_config = self.app_context.gateway.get_config("sites") or {}
            
            try:
                from elitetmhelper2 import RedactedSession, SITE_CONFIGS
                from types import SimpleNamespace
                for site in ["RED", "OPS", "JPS", "DIC"]:
                    if site in sites_config and sites_config[site].get("api_key"):
                        merged_site_config = SITE_CONFIGS.get(site, {}).copy()
                        merged_site_config.update(sites_config[site])
                        
                        options = SimpleNamespace(
                            api_key=sites_config[site]["api_key"],
                            site_config=merged_site_config,
                            request_interval=3.0,
                            show_api_times=False
                        )
                        sess = RedactedSession(options)
                        sess.headers.update({
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.8'
                        })
                        auth_type = merged_site_config.get("auth_type", "api_key")
                        if auth_type == "cookie":
                            auth_key = options.api_key
                            if "=" not in auth_key:
                                if site in ["JPS", "DIC"]:
                                    auth_key = f"PHPSESSID={auth_key}"
                                else:
                                    auth_key = f"session={auth_key}"
                            sess.headers.update({'Cookie': auth_key})
                        else:
                            auth_key = options.api_key
                            if site == "OPS" and not auth_key.startswith("token "):
                                auth_key = f"token {auth_key}"
                            sess.headers.update({'Authorization': auth_key})
                        self.sessions[site] = sess
            except ImportError as e:
                self.log(f"Failed to import RedactedSession: {e}")

    def start(self, source_site: str, target_sites: List[str]):
        if self.is_running: return
        self.reload_sessions()
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, args=(source_site, target_sites), daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        
    def log(self, msg):
        print(f"[CrossSeed] {msg}")

    def _run_loop(self, source_site: str, target_sites: List[str]):
        self.log(f"Starting cross-seed check from {source_site} to {', '.join(target_sites)}")
        try:
            # 1. Fetch seeding torrents from qBittorrent matching the source site tracker
            source_session = self.sessions.get(source_site)
            if not source_session:
                self.log(f"No session configured for source site {source_site}")
                return
                
            tracker_url = source_session.options.site_config.get("tracker_url", "")
            tracker_domain = tracker_url.split('/')[2] if tracker_url else ""
            
            if tracker_domain:
                self.log(f"Fetching torrents matching tracker {tracker_domain}...")
                qb_torrents = self.client.get_torrents()
                if qb_torrents is None:
                    qb_torrents = []
                
                source_torrents = [t for t in qb_torrents if tracker_domain in t.get("tracker", "")]
                self.log(f"Found {len(source_torrents)} seeding torrents for {source_site}.")
                
                for t in source_torrents:
                    if not self.is_running: break
                    self._process_torrent(t, source_site, target_sites, source_session)
                    time.sleep(2) # rate limit
            
            # 2. Could also fetch newly uploaded torrents from the source site via API
            # For MVP, we stick to checking qB seeded torrents which covers the user's main requirement (1).
            
        except Exception as e:
            self.log(f"Error in cross-seed loop: {e}")
            traceback.print_exc()
        finally:
            self.is_running = False
            self.log("Cross-seed loop finished.")

    def _process_torrent(self, torrent_dict: dict, source_site: str, target_sites: List[str], source_session):
        name = torrent_dict.get("name", "")
        hash_str = torrent_dict.get("hash", "")
        save_path = torrent_dict.get("save_path", "")
        
        self.log(f"Checking {name}...")
        
        # We need to parse artist and album from name or query API.
        # It's better to find the group ID from the tracker using hash, but RED/OPS API doesn't support search by infohash.
        # We will extract artist/album from the folder name heuristically, or search the source tracker.
        
        # Heuristic extraction: "Artist - Album (Year) [Format]"
        import re
        match = re.match(r'^(.*?) - (.*?) \(\d{4}\)', name)
        if not match:
            match = re.match(r'^(.*?) - (.*?)$', name)
            
        if not match:
            self.log(f"Could not parse Artist/Album from name: {name}")
            return
            
        artist = match.group(1).strip()
        album = match.group(2).strip()
        
        # Check targets
        existence = self.checker.check_album(artist, album, target_sites=target_sites)
        
        missing_on = []
        for site in target_sites:
            site_exists = getattr(existence, f"{site.lower()}_exists", False)
            if not site_exists:
                missing_on.append(site)
                
        if not missing_on:
            self.log(f"Already exists on all targets.")
            return
            
        self.log(f"Missing on: {', '.join(missing_on)}. Starting upload process.")
        
        # We need metadata. Search source site for exact details.
        group_info = None
        try:
            res = source_session.get_api({"action": "browse", "searchstr": f"{artist} {album}"}).json()
            if res.get("status") == "success" and res["response"]["results"]:
                # Pick first
                group_id = res["response"]["results"][0]["groupId"]
                group_info_res = source_session.get_api({"action": "torrentgroup", "id": group_id}).json()
                if group_info_res.get("status") == "success":
                    group_info = group_info_res["response"]["group"]
        except Exception as e:
            self.log(f"Failed to fetch metadata from source site: {e}")
            
        # Supplement missing data
        mb_data = self.metadata_fetcher.fetch_release_info(artist, album)
        
        final_year = group_info.get("year") if group_info and group_info.get("year") else mb_data.get("year", "2024")
        final_desc = group_info.get("wikiBody") if group_info and group_info.get("wikiBody") else f"Cross-seeded release: {artist} - {album}"
        final_tags = "pop" # default
        if group_info and group_info.get("tags"):
            final_tags = ",".join(group_info["tags"])
            
        # Create torrent using mktorrent
        data_path = Path(save_path) / name
        if not data_path.exists():
            self.log(f"Data path does not exist: {data_path}")
            return
            
        for site in missing_on:
            if not self.is_running: break
            
            site_session = self.sessions.get(site)
            if not site_session: continue
            
            tracker_url = site_session.options.site_config.get("tracker_url")
            if not tracker_url: continue
            
            # Generate torrent
            out_torrent_path = Path(self.save_path) / f"{name}_{site}.torrent"
            out_torrent_path.parent.mkdir(parents=True, exist_ok=True)
            
            cmd = ['mktorrent', '-p', '-a', tracker_url, '-o', str(out_torrent_path), str(data_path)]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if not out_torrent_path.exists():
                self.log(f"Failed to generate torrent for {site}.")
                continue
                
            # Upload
            upload_url = f"{site_session.options.site_config.get('api_url', '')}?action=upload"
            headers = site_session.headers.copy()
            
            upload_data = {
                'submit': 'true',
                'type': '0',
                'artists[]': artist,
                'importance[]': '1',
                'title': album,
                'year': str(final_year),
                'releasetype': '1',
                'format': 'FLAC',
                'bitrate': 'Lossless',
                'media': 'WEB', # default guess if we don't know
                'tags': final_tags,
                'release_desc': final_desc
            }
            
            self.log(f"Uploading to {site}...")
            try:
                with open(out_torrent_path, 'rb') as f:
                    files = {'file_input': (out_torrent_path.name, f, 'application/x-bittorrent')}
                    resp = requests.post(upload_url, headers=headers, data=upload_data, files=files, timeout=30)
                
                if resp.status_code == 200:
                    resp_json = resp.json()
                    if resp_json.get('status') == 'success':
                        self.log(f"Successfully cross-seeded to {site}!")
                        
                        # 使用 SeedingManager 集中管理远程/本地挂载和上传
                        from core.seeding.seeding_manager import SeedingManager
                        seeding_mgr = SeedingManager(self.app_context.gateway if self.app_context else None)
                        
                        use_remote = bool(self.rclone_remote)
                        seeding_mgr.seed_torrent(
                            local_path=str(data_path),
                            torrent_path=str(out_torrent_path),
                            use_remote=use_remote,
                            remote_save_path=save_path,
                            on_progress=self.log
                        )
                    else:
                        self.log(f"Upload API failed on {site}: {resp_json}")
                else:
                    self.log(f"Upload HTTP failed on {site}: {resp.status_code}")
            except Exception as e:
                self.log(f"Exception during upload to {site}: {e}")
                
            time.sleep(4) # delay between uploads
