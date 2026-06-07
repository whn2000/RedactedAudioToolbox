import tkinter as tk
import customtkinter as ctk
import threading
from typing import Callable, List
from i18n import _

from cross_seed.engine import CrossSeedEngine
from gui.widgets import RedirectText

class DiscoveryTabGUI:
    def __init__(self, parent_frame: ctk.CTkFrame, app_context, app_ref=None):
        self.parent = parent_frame
        self.app_context = app_context
        self._app_ref = app_ref

        # Variables
        self.source_site_var = tk.StringVar(value="OPS")
        
        self.target_red = tk.BooleanVar(value=True)
        self.target_ops = tk.BooleanVar(value=False)
        self.target_jps = tk.BooleanVar(value=False)
        self.target_dic = tk.BooleanVar(value=False)
        
        self.qb_host_var = tk.StringVar(value="http://127.0.0.1")
        self.qb_port_var = tk.StringVar(value="8080")
        self.qb_user_var = tk.StringVar(value="admin")
        self.qb_pass_var = tk.StringVar(value="adminadmin")
        self.save_path_var = tk.StringVar(value="./cross_seed_torrents")
        
        self.client_type_var = tk.StringVar(value="qBittorrent")
        self.rclone_remote_var = tk.StringVar(value="")
        self.rclone_config_var = tk.StringVar(value="")
        
        self.engine = None
        
        self.load_config()
        self.build_ui()

    @property
    def pipeline_manager(self):
        if self._app_ref and hasattr(self._app_ref, 'pipeline'):
            return self._app_ref.pipeline
        return None

    def load_config(self):
        if self.app_context and self.app_context.gateway:
            gateway = self.app_context.gateway
            # Global config for client
            self.qb_host_var.set(gateway.get_config("global.qb_host", "http://127.0.0.1"))
            self.qb_port_var.set(str(gateway.get_config("global.qb_port", "8080")))
            self.qb_user_var.set(gateway.get_config("global.qb_user", "admin"))
            self.qb_pass_var.set(gateway.get_config("global.qb_pass", "adminadmin"))
            
            # Seeding specific config
            self.client_type_var.set(gateway.get_config("seeding.client_type", "qBittorrent"))
            self.rclone_remote_var.set(gateway.get_config("seeding.rclone_remote", ""))
            self.rclone_config_var.set(gateway.get_config("seeding.rclone_config", ""))
            self.save_path_var.set(gateway.get_config("seeding.save_path", "./cross_seed_torrents"))
            self.source_site_var.set(gateway.get_config("seeding.source_site", "OPS"))
            self.target_red.set(gateway.get_config("seeding.target_red", True))
            self.target_ops.set(gateway.get_config("seeding.target_ops", False))
            self.target_jps.set(gateway.get_config("seeding.target_jps", False))
            self.target_dic.set(gateway.get_config("seeding.target_dic", False))

    def save_config(self):
        if self.app_context and self.app_context.gateway:
            gateway = self.app_context.gateway
            # Global client config
            gateway.set_config("global.qb_host", self.qb_host_var.get())
            gateway.set_config("global.qb_port", self.qb_port_var.get())
            gateway.set_config("global.qb_user", self.qb_user_var.get())
            gateway.set_config("global.qb_pass", self.qb_pass_var.get())
            
            # Seeding specific config
            gateway.set_config("seeding.client_type", self.client_type_var.get())
            gateway.set_config("seeding.rclone_remote", self.rclone_remote_var.get())
            gateway.set_config("seeding.rclone_config", self.rclone_config_var.get())
            gateway.set_config("seeding.save_path", self.save_path_var.get())
            gateway.set_config("seeding.source_site", self.source_site_var.get())
            gateway.set_config("seeding.target_red", self.target_red.get())
            gateway.set_config("seeding.target_ops", self.target_ops.get())
            gateway.set_config("seeding.target_jps", self.target_jps.get())
            gateway.set_config("seeding.target_dic", self.target_dic.get())
        
    def build_ui(self):
        self.paned_window = tk.PanedWindow(self.parent, orient=tk.VERTICAL, sashwidth=5, bg="#333333")
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 1. Top Section: Controls
        top_frame = ctk.CTkFrame(self.paned_window)
        self.paned_window.add(top_frame, minsize=250, stretch="always")
        
        ctk.CTkLabel(top_frame, text="跨站自动转种 (Cross-Seeding)", font=("", 14, "bold")).pack(anchor=tk.W, padx=10, pady=5)
        
        settings_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Site Selection
        site_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        site_frame.pack(fill=tk.X, pady=2)
        ctk.CTkLabel(site_frame, text="源站点:").pack(side=tk.LEFT, padx=5)
        ctk.CTkOptionMenu(site_frame, variable=self.source_site_var, values=["RED", "OPS", "JPS", "DIC"], width=100).pack(side=tk.LEFT, padx=5)
        
        ctk.CTkLabel(site_frame, text="目标站点 (可多选):").pack(side=tk.LEFT, padx=(20, 5))
        ctk.CTkCheckBox(site_frame, text="RED", variable=self.target_red, width=50).pack(side=tk.LEFT, padx=2)
        ctk.CTkCheckBox(site_frame, text="OPS", variable=self.target_ops, width=50).pack(side=tk.LEFT, padx=2)
        ctk.CTkCheckBox(site_frame, text="JPS", variable=self.target_jps, width=50).pack(side=tk.LEFT, padx=2)
        ctk.CTkCheckBox(site_frame, text="DIC", variable=self.target_dic, width=50).pack(side=tk.LEFT, padx=2)
        
        # Client Type & Connection Settings
        qb_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        qb_frame.pack(fill=tk.X, pady=5)
        
        ctk.CTkLabel(qb_frame, text="客户端 (Client):").pack(side=tk.LEFT, padx=5)
        ctk.CTkOptionMenu(qb_frame, variable=self.client_type_var, values=["qBittorrent", "Transmission"], width=130).pack(side=tk.LEFT, padx=2)
        
        ctk.CTkLabel(qb_frame, text=" 连接配置:").pack(side=tk.LEFT, padx=(15, 2))
        ctk.CTkEntry(qb_frame, textvariable=self.qb_host_var, width=120, placeholder_text="Host").pack(side=tk.LEFT, padx=2)
        ctk.CTkEntry(qb_frame, textvariable=self.qb_port_var, width=60, placeholder_text="Port").pack(side=tk.LEFT, padx=2)
        ctk.CTkEntry(qb_frame, textvariable=self.qb_user_var, width=80, placeholder_text="User").pack(side=tk.LEFT, padx=2)
        ctk.CTkEntry(qb_frame, textvariable=self.qb_pass_var, width=80, placeholder_text="Pass", show="*").pack(side=tk.LEFT, padx=2)
        
        # rclone Settings
        rclone_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        rclone_frame.pack(fill=tk.X, pady=5)
        ctk.CTkLabel(rclone_frame, text="rclone 远程路径 (如 remote:dir):").pack(side=tk.LEFT, padx=5)
        ctk.CTkEntry(rclone_frame, textvariable=self.rclone_remote_var, width=220).pack(side=tk.LEFT, padx=2)
        ctk.CTkLabel(rclone_frame, text=" 配置文件路径 (可选):").pack(side=tk.LEFT, padx=(10, 2))
        ctk.CTkEntry(rclone_frame, textvariable=self.rclone_config_var, width=180, placeholder_text="rclone.conf 路径").pack(side=tk.LEFT, padx=2)

        # Save path
        path_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        path_frame.pack(fill=tk.X, pady=5)
        ctk.CTkLabel(path_frame, text="种子文件保存路径:").pack(side=tk.LEFT, padx=5)
        ctk.CTkEntry(path_frame, textvariable=self.save_path_var, width=300).pack(side=tk.LEFT, padx=2)
        
        btn_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=10)
        self.btn_start = ctk.CTkButton(btn_frame, text="开始扫描与转种", command=self.start_scan, width=120)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_stop = ctk.CTkButton(btn_frame, text="停止", command=self.stop_scan, width=80, fg_color="#dc3545", hover_color="#c82333")
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        self.btn_stop.configure(state="disabled")
        
        # 2. Bottom Section: Log
        bottom_frame = ctk.CTkFrame(self.paned_window)
        self.paned_window.add(bottom_frame, minsize=200, stretch="always")
        
        ctk.CTkLabel(bottom_frame, text="日志输出", font=("", 12, "bold")).pack(anchor=tk.W, padx=10, pady=5)
        
        self.log_text = tk.Text(bottom_frame, bg="#1e1e1e", fg="#cccccc", font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
    def start_scan(self):
        targets = []
        if self.target_red.get(): targets.append("RED")
        if self.target_ops.get(): targets.append("OPS")
        if self.target_jps.get(): targets.append("JPS")
        if self.target_dic.get(): targets.append("DIC")
        
        if not targets:
            self.log("Error: 请至少选择一个目标站点。")
            return
            
        self.save_config()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.log_text.delete(1.0, tk.END)
        
        self.engine = CrossSeedEngine(
            self.app_context, 
            self.pipeline_manager, 
            self.qb_host_var.get(), 
            self.qb_port_var.get(), 
            self.qb_user_var.get(), 
            self.qb_pass_var.get(),
            self.save_path_var.get(),
            client_type=self.client_type_var.get(),
            rclone_remote=self.rclone_remote_var.get() if self.rclone_remote_var.get() else None,
            rclone_config=self.rclone_config_var.get() if self.rclone_config_var.get() else None
        )
        
        # Wrap engine log to output to GUI
        self.engine.log = self.log
        
        self.engine.start(self.source_site_var.get(), targets)
        
        # Monitor thread to reset buttons
        threading.Thread(target=self._monitor_engine, daemon=True).start()

    def _monitor_engine(self):
        import time
        while self.engine and self.engine.is_running:
            time.sleep(1)
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def stop_scan(self):
        if self.engine:
            self.engine.stop()
        self.log("Stopping...")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def log(self, msg):
        def _write():
            try:
                self.log_text.insert(tk.END, f"{msg}\n")
                self.log_text.see(tk.END)
            except Exception:
                pass
        self.log_text.after(0, _write)
