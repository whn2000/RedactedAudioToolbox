import os
import sys
import time
import tkinter as tk
import customtkinter as ctk
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from core.seeding.seeding_manager import SeedingManager

class SeedingTabGUI:
    def __init__(self, parent_frame: ctk.CTkFrame, app_context, app_ref=None):
        self.parent = parent_frame
        self.app_context = app_context
        self._app_ref = app_ref
        
        # Variables
        self.client_type_var = tk.StringVar(value="qBittorrent")
        self.qb_host_var = tk.StringVar(value="http://127.0.0.1")
        self.qb_port_var = tk.StringVar(value="8080")
        self.qb_user_var = tk.StringVar(value="admin")
        self.qb_pass_var = tk.StringVar(value="adminadmin")
        
        self.rclone_remote_var = tk.StringVar(value="")
        self.rclone_config_var = tk.StringVar(value="")
        
        self.local_data_var = tk.StringVar(value="")
        self.torrent_path_var = tk.StringVar(value="")
        self.remote_save_var = tk.StringVar(value="")
        
        self.load_config()
        self.build_ui()

    def load_config(self):
        if self.app_context and self.app_context.gateway:
            gateway = self.app_context.gateway
            # 优先读取独立的做种客户端配置，如果没有则从全局 qb 连接配置继承
            self.qb_host_var.set(gateway.get_config("seeding.host", gateway.get_config("global.qb_host", "http://127.0.0.1")))
            self.qb_port_var.set(str(gateway.get_config("seeding.port", gateway.get_config("global.qb_port", "8080"))))
            self.qb_user_var.set(gateway.get_config("seeding.user", gateway.get_config("global.qb_user", "admin")))
            self.qb_pass_var.set(gateway.get_config("seeding.pass", gateway.get_config("global.qb_pass", "adminadmin")))
            
            # Seeding config
            self.client_type_var.set(gateway.get_config("seeding.client_type", "qBittorrent"))
            self.rclone_remote_var.set(gateway.get_config("seeding.rclone_remote", ""))
            self.rclone_config_var.set(gateway.get_config("seeding.rclone_config", ""))
            
            # Manual seeding config
            self.local_data_var.set(gateway.get_config("seeding.manual_local_path", ""))
            self.torrent_path_var.set(gateway.get_config("seeding.manual_torrent_path", ""))
            self.remote_save_var.set(gateway.get_config("seeding.manual_remote_save_path", ""))

    def save_config(self):
        if self.app_context and self.app_context.gateway:
            gateway = self.app_context.gateway
            # 保存独立的做种客户端配置
            gateway.set_config("seeding.host", self.qb_host_var.get().strip())
            gateway.set_config("seeding.port", self.qb_port_var.get().strip())
            gateway.set_config("seeding.user", self.qb_user_var.get().strip())
            gateway.set_config("seeding.pass", self.qb_pass_var.get().strip())
            
            # Seeding config
            gateway.set_config("seeding.client_type", self.client_type_var.get())
            gateway.set_config("seeding.rclone_remote", self.rclone_remote_var.get().strip())
            gateway.set_config("seeding.rclone_config", self.rclone_config_var.get().strip())
            
            # Manual seeding config
            gateway.set_config("seeding.manual_local_path", self.local_data_var.get().strip())
            gateway.set_config("seeding.manual_torrent_path", self.torrent_path_var.get().strip())
            gateway.set_config("seeding.manual_remote_save_path", self.remote_save_var.get().strip())

    def build_ui(self):
        # UI utilizes a PanedWindow split vertically
        self.paned_window = tk.PanedWindow(self.parent, orient=tk.VERTICAL, sashwidth=5, bg="#333333")
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 1. Top Section: Frame container in PanedWindow
        top_container = ctk.CTkFrame(self.paned_window, fg_color="transparent")
        self.paned_window.add(top_container, minsize=320, stretch="always")
        
        # 2. Scrollable configuration frame inside container
        top_scroll = ctk.CTkScrollableFrame(top_container)
        top_scroll.pack(fill=tk.BOTH, expand=True)
        
        # --- CARD 1: CONNECTIONS & REMOTE CONFIG ---
        conn_frame = ctk.CTkFrame(top_scroll)
        conn_frame.pack(fill=tk.X, padx=10, pady=8)
        
        ctk.CTkLabel(conn_frame, text="⚙️ 远程配置与客户端设置 (Remote Settings)", font=("", 14, "bold")).pack(anchor=tk.W, padx=12, pady=(10, 4))
        
        conn_grid = ctk.CTkFrame(conn_frame, fg_color="transparent")
        conn_grid.pack(fill=tk.X, padx=12, pady=6)
        
        # Row 1: Client and connection host/port
        ctk.CTkLabel(conn_grid, text="做种客户端:").grid(row=0, column=0, sticky=tk.W, pady=4, padx=5)
        ctk.CTkOptionMenu(conn_grid, variable=self.client_type_var, values=["qBittorrent", "Transmission"], width=130).grid(row=0, column=1, sticky=tk.W, pady=4, padx=5)
        
        ctk.CTkLabel(conn_grid, text="做种地址(Host):").grid(row=0, column=2, sticky=tk.W, pady=4, padx=5)
        ctk.CTkEntry(conn_grid, textvariable=self.qb_host_var, width=150, placeholder_text="e.g. http://127.0.0.1").grid(row=0, column=3, sticky=tk.W, pady=4, padx=5)
        
        ctk.CTkLabel(conn_grid, text="做种端口(Port):").grid(row=0, column=4, sticky=tk.W, pady=4, padx=5)
        ctk.CTkEntry(conn_grid, textvariable=self.qb_port_var, width=70, placeholder_text="8080").grid(row=0, column=5, sticky=tk.W, pady=4, padx=5)
        
        # Row 2: Username and password
        ctk.CTkLabel(conn_grid, text="做种账户(User):").grid(row=1, column=0, sticky=tk.W, pady=4, padx=5)
        ctk.CTkEntry(conn_grid, textvariable=self.qb_user_var, width=130).grid(row=1, column=1, sticky=tk.W, pady=4, padx=5)
        
        ctk.CTkLabel(conn_grid, text="做种密码(Pass):").grid(row=1, column=2, sticky=tk.W, pady=4, padx=5)
        ctk.CTkEntry(conn_grid, textvariable=self.qb_pass_var, width=150, show="*").grid(row=1, column=3, sticky=tk.W, pady=4, padx=5)
        
        # Row 3: rclone Remote and configuration path
        ctk.CTkLabel(conn_grid, text="rclone 路径:").grid(row=2, column=0, sticky=tk.W, pady=4, padx=5)
        ctk.CTkEntry(conn_grid, textvariable=self.rclone_remote_var, width=220, placeholder_text="e.g. seedbox:downloads/music").grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=4, padx=5)
        
        ctk.CTkLabel(conn_grid, text="rclone 配置:").grid(row=2, column=3, sticky=tk.W, pady=4, padx=5)
        ctk.CTkEntry(conn_grid, textvariable=self.rclone_config_var, width=180, placeholder_text="rclone.conf (可选)").grid(row=2, column=4, sticky=tk.W, pady=4, padx=5)
        ctk.CTkButton(conn_grid, text="浏览", width=50, command=self.browse_rclone_conf).grid(row=2, column=5, sticky=tk.W, pady=4, padx=5)
        
        # --- CARD 2: MANUAL REMOTE SEEDING FORM ---
        form_frame = ctk.CTkFrame(top_scroll)
        form_frame.pack(fill=tk.X, padx=10, pady=8)
        
        ctk.CTkLabel(form_frame, text="🚀 手动远程做种任务 (Manual Seeding)", font=("", 14, "bold")).pack(anchor=tk.W, padx=12, pady=(10, 4))
        
        form_grid = ctk.CTkFrame(form_frame, fg_color="transparent")
        form_grid.pack(fill=tk.X, padx=12, pady=6)
        
        # Local path
        ctk.CTkLabel(form_grid, text="本地数据路径:").grid(row=0, column=0, sticky=tk.W, pady=4, padx=5)
        ctk.CTkEntry(form_grid, textvariable=self.local_data_var, width=320, placeholder_text="选择要上传的文件或目录...").grid(row=0, column=1, columnspan=2, sticky=tk.W, pady=4, padx=5)
        
        btn_path_frame = ctk.CTkFrame(form_grid, fg_color="transparent")
        btn_path_frame.grid(row=0, column=3, columnspan=2, sticky=tk.W)
        ctk.CTkButton(btn_path_frame, text="选择目录", width=70, command=self.browse_local_dir).pack(side=tk.LEFT, padx=2)
        ctk.CTkButton(btn_path_frame, text="选择文件", width=70, command=self.browse_local_file).pack(side=tk.LEFT, padx=2)
        
        # Torrent path
        ctk.CTkLabel(form_grid, text="种子文件路径:").grid(row=1, column=0, sticky=tk.W, pady=4, padx=5)
        ctk.CTkEntry(form_grid, textvariable=self.torrent_path_var, width=320, placeholder_text="选择 .torrent 文件...").grid(row=1, column=1, columnspan=2, sticky=tk.W, pady=4, padx=5)
        ctk.CTkButton(form_grid, text="选择种子", width=80, command=self.browse_torrent).grid(row=1, column=3, sticky=tk.W, pady=4, padx=5)
        
        # Remote directory save path
        ctk.CTkLabel(form_grid, text="远程做种目录:").grid(row=2, column=0, sticky=tk.W, pady=4, padx=5)
        ctk.CTkEntry(form_grid, textvariable=self.remote_save_var, width=320, placeholder_text="e.g. /home/user/downloads/music").grid(row=2, column=1, columnspan=2, sticky=tk.W, pady=4, padx=5)
        
        # Action buttons
        btn_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_row.pack(fill=tk.X, padx=12, pady=15)
        
        self.btn_save_config = ctk.CTkButton(btn_row, text="💾 保存配置", font=("", 13, "bold"), fg_color="#17a2b8", hover_color="#138496", height=36, command=self.save_config_with_msg)
        self.btn_save_config.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.btn_start = ctk.CTkButton(btn_row, text="🚀 开始远程同步与做种", font=("", 13, "bold"), fg_color="#28a745", hover_color="#218838", height=36, command=self.start_seeding)
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # 2. Bottom Section: Console log
        bottom_frame = ctk.CTkFrame(self.paned_window)
        self.paned_window.add(bottom_frame, minsize=180, stretch="always")
        
        ctk.CTkLabel(bottom_frame, text="📋 做种日志控制台", font=("", 12, "bold")).pack(anchor=tk.W, padx=10, pady=(6, 2))
        
        self.log_text = tk.Text(bottom_frame, bg="#1a1a1a", fg="#cccccc", font=("Consolas", 10), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def browse_rclone_conf(self):
        f = filedialog.askopenfilename(title="选择 rclone 配置文件", filetypes=[("Conf files", "*.conf"), ("All files", "*.*")])
        if f:
            self.rclone_config_var.set(f)

    def browse_local_dir(self):
        d = filedialog.askdirectory(title="选择本地做种数据目录")
        if d:
            self.local_data_var.set(d)

    def browse_local_file(self):
        f = filedialog.askopenfilename(title="选择本地做种数据文件")
        if f:
            self.local_data_var.set(f)

    def browse_torrent(self):
        f = filedialog.askopenfilename(title="选择种子文件", filetypes=[("Torrent files", "*.torrent"), ("All files", "*.*")])
        if f:
            self.torrent_path_var.set(f)

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        def _write():
            try:
                self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
                self.log_text.see(tk.END)
            except Exception:
                pass
        self.parent.after(0, _write)

    def start_seeding(self):
        local_path = self.local_data_var.get().strip()
        torrent_path = self.torrent_path_var.get().strip()
        remote_save_path = self.remote_save_var.get().strip()
        
        if not local_path:
            messagebox.showwarning("提示", "请选择本地做种数据目录或文件！")
            return
        if not os.path.exists(local_path):
            messagebox.showerror("错误", f"本地路径不存在：\n{local_path}")
            return
            
        if not torrent_path:
            messagebox.showwarning("提示", "请选择种子文件！")
            return
        if not os.path.exists(torrent_path):
            messagebox.showerror("错误", f"种子文件不存在：\n{torrent_path}")
            return
            
        if not remote_save_path:
            messagebox.showwarning("提示", "请填写远程做种客户端中的保存目录！")
            return
            
        self.save_config()
        self.btn_start.configure(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        
        threading.Thread(target=self._run_seeding_thread, args=(local_path, torrent_path, remote_save_path), daemon=True).start()

    def _run_seeding_thread(self, local_path, torrent_path, remote_save_path):
        self.log("🚀 启动手动同步与做种流程...")
        try:
            # 高内聚重构：直接实例化 SeedingManager 调度整个任务，免去 GUI 的 rclone_copy 及 Client 依赖
            manager = SeedingManager(self.app_context.gateway)
            
            rclone_remote = self.rclone_remote_var.get().strip()
            use_remote = bool(rclone_remote)
            
            success = manager.seed_torrent(
                local_path=local_path,
                torrent_path=torrent_path,
                use_remote=use_remote,
                remote_save_path=remote_save_path,
                on_progress=self.log
            )
            
            if success:
                self.log("🎉 任务顺利完成！")
            else:
                self.log("❌ 任务执行失败，请检查上面日志。")
        except Exception as e:
            self.log(f"❌ 流程执行异常: {e}")
            
        self.parent.after(0, lambda: self.btn_start.configure(state=tk.NORMAL))

    def save_config_with_msg(self):
        try:
            self.save_config()
            messagebox.showinfo("提示", "做种配置已成功保存！")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败：\n{e}")
