"""
pipeline_tab.py — 手动流水线标签页

功能：
  1. 添加本地音乐目录 → 直接走降频/无损检查/上传流程
  2. 添加 .torrent 文件 → 推入 qBittorrent red_auto 分类等待下载后自动处理
  3. 队列列表展示：等待/处理中/下载中/完成/失败
  4. 内嵌日志输出
"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from pathlib import Path
import time


# ──────────────────────────────────────────────
# 状态配置
# ──────────────────────────────────────────────
_STATUS_CFG = {
    "queued":      {"icon": "⏳", "text": "等待中",    "color": "#888888"},
    "processing":  {"icon": "⚙️", "text": "处理中",    "color": "#4a9eff"},
    "downloading": {"icon": "⬇️", "text": "下载中(qB)","color": "#f0a500"},
    "queued_in_qb":{"icon": "📤", "text": "已推送qB",  "color": "#aaaaff"},
    "done":        {"icon": "✅", "text": "已完成",    "color": "#28a745"},
    "failed":      {"icon": "❌", "text": "失败",      "color": "#dc3545"},
}


class _QueueItem:
    """代表队列中的一个任务条目"""
    _id_counter = 0

    def __init__(self, label: str, kind: str):
        _QueueItem._id_counter += 1
        self.id = _QueueItem._id_counter
        self.label = label          # 显示名称（目录名 or 种子名）
        self.kind = kind            # "folder" or "torrent"
        self.status = "queued"
        self.added_at = time.strftime("%H:%M:%S")

    def set_status(self, s: str):
        if s in _STATUS_CFG:
            self.status = s


class PipelineTabGUI:
    """手动流水线标签页"""

    def __init__(self, parent_frame: ctk.CTkFrame, app_ref):
        """
        Parameters
        ----------
        parent_frame : ctk.CTkFrame
        app_ref      : elitetmhelper2.AppGUI 实例，持有 .pipeline 属性
        """
        self.parent = parent_frame
        self._app_ref = app_ref
        self._queue: list[_QueueItem] = []
        self._queue_lock = threading.Lock()
        self._item_widgets: dict[int, dict] = {}   # item.id -> {frame, status_lbl, ...}

        self._build_ui()

    # ------------------------------------------------------------------
    # 动态获取 pipeline（和 FailedTasksGUI 同样的技巧）
    # ------------------------------------------------------------------
    @property
    def pipeline(self):
        if self._app_ref is None:
            return None
        if hasattr(self._app_ref, "pipeline"):
            return self._app_ref.pipeline
        return self._app_ref

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        # 顶部说明
        header = ctk.CTkFrame(self.parent, fg_color="transparent")
        header.pack(fill=tk.X, padx=12, pady=(10, 4))
        ctk.CTkLabel(
            header,
            text="🔧  手动流水线  /  Manual Pipeline",
            font=("", 15, "bold"),
        ).pack(side=tk.LEFT)

        self._pipeline_status_lbl = ctk.CTkLabel(
            header, text="● Pipeline 未启动", text_color="#888888", font=("", 11)
        )
        self._pipeline_status_lbl.pack(side=tk.RIGHT, padx=6)

        # 主体分为上下两区：输入区 / (队列 + 日志)
        paned = tk.PanedWindow(self.parent, orient=tk.VERTICAL, sashwidth=5, bg="#333333")
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # ── 上区：输入控件 ──────────────────────────────────────────
        top = ctk.CTkFrame(paned)
        paned.add(top, minsize=180, stretch="never")

        # 两栏并排：左=添加文件夹，右=添加种子
        cols = ctk.CTkFrame(top, fg_color="transparent")
        cols.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)

        self._build_folder_panel(cols)
        self._build_torrent_panel(cols)

        # ── 下区：队列列表 + 日志 ───────────────────────────────────
        bottom = ctk.CTkFrame(paned)
        paned.add(bottom, minsize=300, stretch="always")

        bottom_paned = tk.PanedWindow(bottom, orient=tk.VERTICAL, sashwidth=4, bg="#333333")
        bottom_paned.pack(fill=tk.BOTH, expand=True)

        # 队列列表
        queue_frame = ctk.CTkFrame(bottom_paned)
        bottom_paned.add(queue_frame, minsize=150, stretch="always")

        queue_header = ctk.CTkFrame(queue_frame, fg_color="transparent")
        queue_header.pack(fill=tk.X, padx=8, pady=(6, 2))
        ctk.CTkLabel(queue_header, text="📋 任务队列", font=("", 13, "bold")).pack(side=tk.LEFT)
        ctk.CTkButton(
            queue_header, text="清除已完成", width=90, height=26,
            command=self._clear_done
        ).pack(side=tk.RIGHT, padx=4)

        self._queue_scroll = ctk.CTkScrollableFrame(queue_frame)
        self._queue_scroll.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        self._empty_lbl = ctk.CTkLabel(
            self._queue_scroll, text="队列为空，请在上方添加任务。", text_color="gray"
        )
        self._empty_lbl.pack(pady=20)

        # 日志
        log_frame = ctk.CTkFrame(bottom_paned)
        bottom_paned.add(log_frame, minsize=120, stretch="always")

        ctk.CTkLabel(log_frame, text="📄 日志输出", font=("", 12, "bold")).pack(
            anchor=tk.W, padx=8, pady=(6, 2)
        )
        self._log_box = tk.Text(
            log_frame, bg="#1a1a1a", fg="#cccccc",
            font=("Consolas", 10), wrap=tk.WORD, state=tk.DISABLED
        )
        self._log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        # 轮询 pipeline 状态
        self.parent.after(2000, self._poll_pipeline_status)

    # ── 添加文件夹面板 ──────────────────────────────────────────────
    def _build_folder_panel(self, parent_grid):
        box = ctk.CTkFrame(parent_grid, border_width=1)
        box.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)

        ctk.CTkLabel(box, text="📁 添加本地音乐目录", font=("", 12, "bold")).pack(
            anchor=tk.W, padx=10, pady=(8, 4)
        )
        ctk.CTkLabel(
            box,
            text="选择一个已下载完成的 24-bit 音乐目录，\n直接进入降频→无损检查→上传流程。",
            text_color="gray", font=("", 10), justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=10, pady=(0, 6))

        path_row = ctk.CTkFrame(box, fg_color="transparent")
        path_row.pack(fill=tk.X, padx=10, pady=2)
        self._folder_var = tk.StringVar()
        ctk.CTkEntry(path_row, textvariable=self._folder_var, placeholder_text="目录路径…").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        ctk.CTkButton(path_row, text="浏览", width=60, command=self._browse_folder).pack(side=tk.LEFT)

        json_row = ctk.CTkFrame(box, fg_color="transparent")
        json_row.pack(fill=tk.X, padx=10, pady=2)
        self._json_var = tk.StringVar()
        ctk.CTkEntry(json_row, textvariable=self._json_var, placeholder_text="可选: .json 元数据文件，用于自动上传…").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        ctk.CTkButton(json_row, text="浏览", width=60, command=self._browse_json).pack(side=tk.LEFT)

        ctk.CTkButton(
            box, text="➕ 加入流水线处理",
            fg_color="#28a745", hover_color="#218838",
            command=self._enqueue_folder
        ).pack(padx=10, pady=(8, 10), fill=tk.X)

    # ── 添加种子面板 ────────────────────────────────────────────────
    def _build_torrent_panel(self, parent_grid):
        box = ctk.CTkFrame(parent_grid, border_width=1)
        box.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=0)

        ctk.CTkLabel(box, text="🌱 添加种子文件", font=("", 12, "bold")).pack(
            anchor=tk.W, padx=10, pady=(8, 4)
        )
        ctk.CTkLabel(
            box,
            text="推送 .torrent 到 qBittorrent (red_auto)，\n下载完成后自动触发后处理。",
            text_color="gray", font=("", 10), justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=10, pady=(0, 6))

        # 种子路径
        r1 = ctk.CTkFrame(box, fg_color="transparent")
        r1.pack(fill=tk.X, padx=10, pady=2)
        ctk.CTkLabel(r1, text=".torrent 文件:", width=90, anchor=tk.W).pack(side=tk.LEFT)
        self._torrent_var = tk.StringVar()
        ctk.CTkEntry(r1, textvariable=self._torrent_var, placeholder_text="种子文件路径…").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        ctk.CTkButton(r1, text="浏览", width=60, command=self._browse_torrent).pack(side=tk.LEFT)

        # 保存路径
        r2 = ctk.CTkFrame(box, fg_color="transparent")
        r2.pack(fill=tk.X, padx=10, pady=2)
        ctk.CTkLabel(r2, text="下载保存路径:", width=90, anchor=tk.W).pack(side=tk.LEFT)
        self._save_path_var = tk.StringVar()
        ctk.CTkEntry(r2, textvariable=self._save_path_var, placeholder_text="qB 保存目录…").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        ctk.CTkButton(r2, text="浏览", width=60, command=self._browse_save_path).pack(side=tk.LEFT)

        ctk.CTkButton(
            box, text="📤 推送到 qBittorrent",
            fg_color="#4a9eff", hover_color="#2d7dd2",
            command=self._enqueue_torrent
        ).pack(padx=10, pady=(8, 10), fill=tk.X)

    # ------------------------------------------------------------------
    # 浏览对话框
    # ------------------------------------------------------------------
    def _browse_folder(self):
        d = filedialog.askdirectory(title="选择音乐目录")
        if d:
            self._folder_var.set(d)

    def _browse_json(self):
        f = filedialog.askopenfilename(
            title="选择 JSON 元数据文件",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if f:
            self._json_var.set(f)

    def _browse_torrent(self):
        f = filedialog.askopenfilename(
            title="选择种子文件",
            filetypes=[("Torrent files", "*.torrent"), ("All files", "*.*")]
        )
        if f:
            self._torrent_var.set(f)

    def _browse_save_path(self):
        d = filedialog.askdirectory(title="选择 qBittorrent 下载保存目录")
        if d:
            self._save_path_var.set(d)

    # ------------------------------------------------------------------
    # 入队：本地目录
    # ------------------------------------------------------------------
    def _enqueue_folder(self):
        pl = self.pipeline
        if not pl:
            messagebox.showwarning("提示", "Pipeline 未启动。\n请先在「搜索」标签页启用流水线并运行一次搜索。")
            return

        folder = self._folder_var.get().strip()
        json_path = self._json_var.get().strip() or None
        
        if not folder:
            messagebox.showwarning("提示", "请先选择一个音乐目录。")
            return
        if not Path(folder).is_dir():
            messagebox.showerror("错误", f"目录不存在：\n{folder}")
            return
        if json_path and not Path(json_path).is_file():
            messagebox.showerror("错误", f"JSON 文件不存在：\n{json_path}")
            return

        item = _QueueItem(Path(folder).name, "folder")
        self._add_item_to_queue(item)
        log_msg = f"[{item.added_at}] 入队（本地目录）: {item.label}"
        if json_path:
            log_msg += " [附带 JSON]"
        self._log(log_msg)
        self._folder_var.set("")
        self._json_var.set("")

        def _cb(status):
            self.parent.after(0, self._update_item_status, item.id, status)
            self._log(f"[{time.strftime('%H:%M:%S')}] {item.label} → {_STATUS_CFG.get(status, {}).get('text', status)}")

        threading.Thread(
            target=pl.queue_folder_for_processing,
            args=(folder, _cb, json_path),
            daemon=True
        ).start()

    # ------------------------------------------------------------------
    # 入队：种子文件
    # ------------------------------------------------------------------
    def _enqueue_torrent(self):
        pl = self.pipeline
        if not pl:
            messagebox.showwarning("提示", "Pipeline 未启动。\n请先在「搜索」标签页启用流水线并运行一次搜索。")
            return

        torrent = self._torrent_var.get().strip()
        save_path = self._save_path_var.get().strip()

        if not torrent:
            messagebox.showwarning("提示", "请先选择 .torrent 文件。")
            return
        if not Path(torrent).is_file():
            messagebox.showerror("错误", f"种子文件不存在：\n{torrent}")
            return
        if not save_path:
            messagebox.showwarning("提示", "请先指定 qBittorrent 下载保存路径。")
            return

        item = _QueueItem(Path(torrent).name, "torrent")
        self._add_item_to_queue(item)
        self._log(f"[{item.added_at}] 入队（种子）: {item.label}  →  保存至: {save_path}")
        self._torrent_var.set("")

        def _cb(status):
            self.parent.after(0, self._update_item_status, item.id, status)
            self._log(f"[{time.strftime('%H:%M:%S')}] {item.label} → {_STATUS_CFG.get(status, {}).get('text', status)}")

        threading.Thread(
            target=pl.push_torrent_to_qb,
            args=(torrent, save_path, _cb),
            daemon=True
        ).start()

    # ------------------------------------------------------------------
    # 队列 UI 管理
    # ------------------------------------------------------------------
    def _add_item_to_queue(self, item: _QueueItem):
        with self._queue_lock:
            self._queue.append(item)

        # 移除空提示
        if self._empty_lbl.winfo_ismapped():
            self._empty_lbl.pack_forget()

        cfg = _STATUS_CFG[item.status]

        row = ctk.CTkFrame(self._queue_scroll, fg_color="#2a2a2a", corner_radius=6)
        row.pack(fill=tk.X, padx=4, pady=3)

        # 图标
        icon_lbl = ctk.CTkLabel(row, text=cfg["icon"], width=28, font=("", 16))
        icon_lbl.pack(side=tk.LEFT, padx=(8, 4), pady=6)

        # 文字主体
        body = ctk.CTkFrame(row, fg_color="transparent")
        body.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)

        name_lbl = ctk.CTkLabel(body, text=item.label, anchor=tk.W, font=("", 11, "bold"))
        name_lbl.pack(anchor=tk.W, padx=4)

        kind_str = "📁 本地目录" if item.kind == "folder" else "🌱 种子"
        meta_lbl = ctk.CTkLabel(
            body,
            text=f"{kind_str}  ·  添加于 {item.added_at}",
            text_color="gray", font=("", 9), anchor=tk.W
        )
        meta_lbl.pack(anchor=tk.W, padx=4)

        # 状态标签
        status_lbl = ctk.CTkLabel(
            row,
            text=f"{cfg['icon']} {cfg['text']}",
            text_color=cfg["color"],
            font=("", 11, "bold"),
            width=110
        )
        status_lbl.pack(side=tk.RIGHT, padx=10)

        self._item_widgets[item.id] = {
            "frame": row,
            "icon_lbl": icon_lbl,
            "status_lbl": status_lbl,
            "item": item,
        }

    def _update_item_status(self, item_id: int, status: str):
        widgets = self._item_widgets.get(item_id)
        if not widgets:
            return
        item = widgets["item"]
        item.set_status(status)
        cfg = _STATUS_CFG.get(status, {"icon": "?", "text": status, "color": "gray"})
        widgets["status_lbl"].configure(
            text=f"{cfg['icon']} {cfg['text']}",
            text_color=cfg["color"]
        )
        widgets["icon_lbl"].configure(text=cfg["icon"])

        # 完成/失败时改变行背景色
        if status == "done":
            widgets["frame"].configure(fg_color="#1a2e1a")
        elif status == "failed":
            widgets["frame"].configure(fg_color="#2e1a1a")

    def _clear_done(self):
        to_remove = [
            iid for iid, w in list(self._item_widgets.items())
            if w["item"].status in ("done", "failed")
        ]
        for iid in to_remove:
            w = self._item_widgets.pop(iid)
            w["frame"].destroy()
        with self._queue_lock:
            self._queue = [it for it in self._queue if it.id not in to_remove]

        if not self._item_widgets:
            self._empty_lbl.pack(pady=20)

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------
    def _log(self, msg: str):
        def _write():
            try:
                self._log_box.configure(state=tk.NORMAL)
                self._log_box.insert(tk.END, msg + "\n")
                self._log_box.see(tk.END)
                self._log_box.configure(state=tk.DISABLED)
            except Exception:
                pass
        self.parent.after(0, _write)

    # ------------------------------------------------------------------
    # 轮询 pipeline 状态（显示在右上角）
    # ------------------------------------------------------------------
    def _poll_pipeline_status(self):
        pl = self.pipeline
        if pl and pl.is_running:
            self._pipeline_status_lbl.configure(
                text="● Pipeline 运行中", text_color="#28a745"
            )
        elif pl:
            self._pipeline_status_lbl.configure(
                text="● Pipeline 已就绪（未运行）", text_color="#f0a500"
            )
        else:
            self._pipeline_status_lbl.configure(
                text="● Pipeline 未启动", text_color="#888888"
            )
        self.parent.after(5000, self._poll_pipeline_status)
