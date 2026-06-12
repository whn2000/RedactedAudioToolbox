"""
搜索标签页 (Search Tab)

从 elitetmhelper2.py 提取，原 AppGUI 类。
提供 24bit Lossless 搜索的 GUI 界面。
"""

import sys
import json
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from types import SimpleNamespace
import customtkinter as ctk
from i18n import _
import core.globals
from core.site_config import SITE_CONFIGS
from core.searcher import perform_search, Cache
from errors import APIError as RedactedAPIError
from gui.widgets import RedirectText

class AppGUI:
    def __init__(self, parent):
        self.parent = parent
        self.is_running = False
        self.pipeline = None
        
        self.site_configs_data = {"RED": {}, "OPS": {}, "JPS": {}, "DIC": {}}
        self._is_switching_site = False
        
        self.site_var = tk.StringVar(value="RED")
        self.api_key_var = tk.StringVar()
        
        self.site_var.trace_add("write", self.on_site_changed)
        self.passkey_var = tk.StringVar()
        self.save_path_var = tk.StringVar()
        self.media_var = tk.StringVar(value="CD")
        self.year_latest_var = tk.StringVar(value="2023")
        self.year_earliest_var = tk.StringVar(value="1970")
        self.number_var = tk.StringVar(value="50")
        self.max_size_var = tk.StringVar(value="2048")
        self.min_size_var = tk.StringVar(value="0")
        self.order_by_var = tk.StringVar(value="time")
        
        self.bandcamp_var = tk.BooleanVar(value=False)
        self.ignore_lossy_var = tk.BooleanVar(value=False)
        self.ignore_16bit_var = tk.BooleanVar(value=False)
        self.ignore_mp3_exists_var = tk.BooleanVar(value=False)
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
        self.pipeline_use_remote_var = tk.BooleanVar(value=False)
        self.ignore_warnings_var = tk.BooleanVar(value=False)

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
            'passkey': self.passkey_var.get(),
            'save_path': self.save_path_var.get(),
            'buffer_formula': self.buffer_formula_var.get(),
            'media': self.media_var.get(),
            'year_latest': self.year_latest_var.get(),
            'year_earliest': self.year_earliest_var.get(),
            'number': self.number_var.get(),
            'max_size': self.max_size_var.get(),
            'min_size': self.min_size_var.get(),
            'order_by': self.order_by_var.get(),
            'bandcamp': self.bandcamp_var.get(),
            'ignore_lossy': self.ignore_lossy_var.get(),
            'ignore_16bit': self.ignore_16bit_var.get(),
            'ignore_mp3_exists': self.ignore_mp3_exists_var.get(),
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
            'ignore_warnings': self.ignore_warnings_var.get(),
        }

    def apply_site_settings(self, config):
        if not config: return
        
        if 'api_key' in config: self.api_key_var.set(config['api_key'])
        if 'passkey' in config: self.passkey_var.set(config['passkey'])
        if 'save_path' in config: self.save_path_var.set(config['save_path'])
        if 'buffer_formula' in config: self.buffer_formula_var.set(config['buffer_formula'])
        if 'media' in config: self.media_var.set(config['media'])
        if 'year_latest' in config: self.year_latest_var.set(config['year_latest'])
        if 'year_earliest' in config: self.year_earliest_var.set(config['year_earliest'])
        if 'number' in config: self.number_var.set(config['number'])
        if 'max_size' in config: self.max_size_var.set(config['max_size'])
        if 'min_size' in config: self.min_size_var.set(config['min_size'])
        if 'order_by' in config: self.order_by_var.set(config['order_by'])
        if 'bandcamp' in config: self.bandcamp_var.set(config['bandcamp'])
        if 'ignore_lossy' in config: self.ignore_lossy_var.set(config['ignore_lossy'])
        if 'ignore_16bit' in config: self.ignore_16bit_var.set(config['ignore_16bit'])
        if 'ignore_mp3_exists' in config: self.ignore_mp3_exists_var.set(config['ignore_mp3_exists'])
        if 'ignore_warnings' in config: self.ignore_warnings_var.set(config['ignore_warnings'])
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
            if core.globals.app_context and core.globals.app_context.gateway:
                gateway = core.globals.app_context.gateway
                # We retrieve the entire flat structure that auto_migration_runner migrated.
                # Actually, the migration runner writes it using flat key paths but also dict structure.
                # Just fetching it via get_config("") or getting the dict structure directly might be tricky if it was saved flat.
                # BUT wait, the migration runner wrote it by unrolling the dict.
                # We can just fetch the whole config from gateway.config.config_data or get individual keys.
                # Wait, getting individual keys is safer:
                
                # Check if it was migrated
                has_site = gateway.get_config("site")
                if has_site is not None:
                    # New Gateway-based config load
                    config = gateway.config.config_data
                    
                    if "sites" in config:
                        self.site_configs_data = config.get("sites", {"RED": {}, "OPS": {}, "JPS": {}, "DIC": {}})
                        
                        if 'site' in config: 
                            self.site_var.set(config['site'])
                        self.last_site = self.site_var.get()
                        
                        global_config = config.get("global", {})
                        if 'qb_host' in global_config: self.qb_host_var.set(global_config['qb_host'])
                        if 'qb_port' in global_config: self.qb_port_var.set(global_config['qb_port'])
                        if 'qb_user' in global_config: self.qb_user_var.set(global_config['qb_user'])
                        if 'qb_pass' in global_config: self.qb_pass_var.set(global_config['qb_pass'])
                        if 'enable_pipeline' in global_config: self.enable_pipeline_var.set(global_config['enable_pipeline'])
                        if 'pipeline_use_remote' in global_config: self.pipeline_use_remote_var.set(global_config['pipeline_use_remote'])
                        
                        self.apply_site_settings(self.site_configs_data.get(self.last_site, {}))
                        
                    else:
                        print(_("log_migrate_config"))
                        if 'site' in config: self.site_var.set(config['site'])
                        self.last_site = self.site_var.get()
                        
                        if 'qb_host' in config: self.qb_host_var.set(config['qb_host'])
                        if 'qb_port' in config: self.qb_port_var.set(config['qb_port'])
                        if 'qb_user' in config: self.qb_user_var.set(config['qb_user'])
                        if 'qb_pass' in config: self.qb_pass_var.set(config['qb_pass'])
                        if 'enable_pipeline' in config: self.enable_pipeline_var.set(config['enable_pipeline'])
                        if 'pipeline_use_remote' in config: self.pipeline_use_remote_var.set(config['pipeline_use_remote'])
                        
                        migrated_site_config = config.copy()
                        old_api_keys = config.get('api_keys', {})
                        if not old_api_keys and 'api_key' in config:
                            old_api_keys = {"RED": config['api_key'], "OPS": config['api_key']}
                            
                        self.apply_site_settings(migrated_site_config)
                        self.site_configs_data["RED"] = self.get_current_site_settings()
                        self.site_configs_data["OPS"] = self.get_current_site_settings()
                        self.site_configs_data["JPS"] = self.get_current_site_settings()
                        self.site_configs_data["DIC"] = self.get_current_site_settings()
                        
                        self.site_configs_data["RED"]["api_key"] = old_api_keys.get("RED", "")
                        self.site_configs_data["OPS"]["api_key"] = old_api_keys.get("OPS", "")
                        self.site_configs_data["JPS"]["api_key"] = ""
                        self.site_configs_data["DIC"]["api_key"] = ""
                        
                        self.apply_site_settings(self.site_configs_data.get(self.last_site, {}))
                return
            
            # Fallback for testing standalone
            if Path(self.config_file).exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    if "sites" in config:
                        # 新版配置
                        self.site_configs_data = config.get("sites", {"RED": {}, "OPS": {}, "JPS": {}, "DIC": {}})
                        
                        if 'site' in config: 
                            self.site_var.set(config['site'])
                        self.last_site = self.site_var.get()
                        
                        global_config = config.get("global", {})
                        if 'qb_host' in global_config: self.qb_host_var.set(global_config['qb_host'])
                        if 'qb_port' in global_config: self.qb_port_var.set(global_config['qb_port'])
                        if 'qb_user' in global_config: self.qb_user_var.set(global_config['qb_user'])
                        if 'qb_pass' in global_config: self.qb_pass_var.set(global_config['qb_pass'])
                        if 'enable_pipeline' in global_config: self.enable_pipeline_var.set(global_config['enable_pipeline'])
                        if 'pipeline_use_remote' in global_config: self.pipeline_use_remote_var.set(global_config['pipeline_use_remote'])
                        
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
                        if 'pipeline_use_remote' in config: self.pipeline_use_remote_var.set(config['pipeline_use_remote'])
                        
                        migrated_site_config = config.copy()
                        # 旧版的 API key
                        old_api_keys = config.get('api_keys', {})
                        if not old_api_keys and 'api_key' in config:
                            old_api_keys = {"RED": config['api_key'], "OPS": config['api_key']}
                            
                        self.apply_site_settings(migrated_site_config)
                        self.site_configs_data["RED"] = self.get_current_site_settings()
                        self.site_configs_data["OPS"] = self.get_current_site_settings()
                        self.site_configs_data["JPS"] = self.get_current_site_settings()
                        self.site_configs_data["DIC"] = self.get_current_site_settings()
                        
                        # 恢复各自的 API KEY
                        self.site_configs_data["RED"]["api_key"] = old_api_keys.get("RED", "")
                        self.site_configs_data["OPS"]["api_key"] = old_api_keys.get("OPS", "")
                        self.site_configs_data["JPS"]["api_key"] = ""
                        self.site_configs_data["DIC"]["api_key"] = ""
                        
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
                    'pipeline_use_remote': self.pipeline_use_remote_var.get(),
                },
                'sites': self.site_configs_data
            }
            
            if core.globals.app_context and core.globals.app_context.gateway:
                gateway = core.globals.app_context.gateway
                gateway.set_config("site", config["site"])
                gateway.set_config("global", config["global"])
                gateway.set_config("sites", config["sites"])
                # We can also sync api_keys to keyring, but since elitetmhelper2 currently mixes them in config,
                # letting YAML store it temporarily during UI transition is fine, or we can explicitly migrate them here.
            else:
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
        ctk.CTkComboBox(config_frame, variable=self.site_var, values=['RED', 'OPS', 'JPS', 'DIC'], width=150).grid(row=1, column=1, sticky=tk.W, padx=5)
        ctk.CTkLabel(config_frame, text=_("api_key") + " / Cookie").grid(row=1, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.api_key_var, width=200, show="*").grid(row=1, column=3, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text="Passkey").grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.passkey_var, width=200, show="*").grid(row=2, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("media")).grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkComboBox(config_frame, variable=self.media_var, values=['', 'CD', 'WEB', 'Vinyl', 'SACD', 'Cassette', 'Blu-Ray'], width=120).grid(row=3, column=1, sticky=tk.W, padx=5)
        ctk.CTkLabel(config_frame, text=_("order_by")).grid(row=3, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkComboBox(config_frame, variable=self.order_by_var, values=['time', 'size', 'snatched', 'seeders', 'random'], width=120).grid(row=3, column=3, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("start_year")).grid(row=4, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.year_earliest_var, width=120).grid(row=4, column=1, sticky=tk.W, padx=5)
        
        ctk.CTkLabel(config_frame, text=_("end_year")).grid(row=4, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.year_latest_var, width=120).grid(row=4, column=3, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("target_count")).grid(row=5, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.number_var, width=120).grid(row=5, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("max_size_mb")).grid(row=5, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.max_size_var, width=120).grid(row=5, column=3, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text="最小体积 (MB)").grid(row=6, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.min_size_var, width=120).grid(row=6, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("req_interval")).grid(row=7, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.request_interval_var, width=120).grid(row=7, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("save_path")).grid(row=8, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.save_path_var, width=300).grid(row=8, column=1, columnspan=2, sticky=tk.W, padx=5)
        ctk.CTkButton(config_frame, text=_("browse"), command=self.browse_save_path, width=80).grid(row=8, column=3, sticky=tk.W, padx=5)

        filter_frame = ctk.CTkFrame(self.scrollable_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        ctk.CTkLabel(filter_frame, text=_("advanced_filters"), font=("", 16, "bold")).grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=5, padx=5)
        
        ctk.CTkCheckBox(filter_frame, text=_("nyp_only"), variable=self.bandcamp_var).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text=_("ignore_lossy"), variable=self.ignore_lossy_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text=_("ignore_16bit"), variable=self.ignore_16bit_var).grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text="忽略已有 MP3", variable=self.ignore_mp3_exists_var).grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text=_("ignore_trumpable"), variable=self.ignore_trumpable_var).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text=_("excl_0_snatches"), variable=self.exclude_zero_snatches_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        ctk.CTkCheckBox(filter_frame, text=_("auto_dl_torrent"), variable=self.auto_download_var).grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)

        min_seeders_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        min_seeders_frame.grid(row=2, column=3, sticky=tk.W, padx=5, pady=5)
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
        
        ctk.CTkCheckBox(pipeline_frame, text=_("enable_pipeline"), variable=self.enable_pipeline_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkCheckBox(pipeline_frame, text=_("pipeline_use_remote"), variable=self.pipeline_use_remote_var).grid(row=1, column=2, columnspan=2, sticky=tk.W, pady=5, padx=5)
        
        ctk.CTkCheckBox(pipeline_frame, text="无视警告直接上传 (无视无损检测结果)", variable=self.ignore_warnings_var).grid(row=2, column=0, columnspan=4, sticky=tk.W, pady=5, padx=5)
        
        ctk.CTkLabel(pipeline_frame, text=_("qb_host")).grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(pipeline_frame, textvariable=self.qb_host_var, width=200).grid(row=3, column=1, sticky=tk.W, padx=5)
        
        ctk.CTkLabel(pipeline_frame, text=_("qb_port")).grid(row=3, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(pipeline_frame, textvariable=self.qb_port_var, width=100).grid(row=3, column=3, sticky=tk.W, padx=5)
        
        ctk.CTkLabel(pipeline_frame, text=_("qb_user")).grid(row=4, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(pipeline_frame, textvariable=self.qb_user_var, width=200).grid(row=4, column=1, sticky=tk.W, padx=5)
        
        ctk.CTkLabel(pipeline_frame, text=_("qb_pass")).grid(row=4, column=2, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(pipeline_frame, textvariable=self.qb_pass_var, width=200, show="*").grid(row=4, column=3, sticky=tk.W, padx=5)

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
            passkey=self.passkey_var.get().strip(),
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
            min_size=self._safe_int(self.min_size_var, 0) * 1048576,
            ignore_mp3_exists=self.ignore_mp3_exists_var.get(),
            media=self.media_var.get() if self.media_var.get() else "",
            min_seeders=self._safe_int(self.min_seeders_var, 0),
            order_by=self.order_by_var.get(),
            order_way="desc",
            output=str(core.globals.app_context.paths.output_dir / f'EliteTMHelper2_{self.site_var.get()}_Found.txt') if core.globals.app_context else f'EliteTMHelper2_{self.site_var.get()}_Found.txt',
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
            enable_pipeline=self.enable_pipeline_var.get(),
            pipeline_use_remote=self.pipeline_use_remote_var.get(),
            ignore_warnings=self.ignore_warnings_var.get()
        )

    def start_search(self):
        if not self.api_key_var.get().strip():
            site_config = SITE_CONFIGS.get(self.site_var.get(), SITE_CONFIGS["RED"])
            auth_label = "Cookie" if site_config.get("auth_type") == "cookie" else _("api_key")
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