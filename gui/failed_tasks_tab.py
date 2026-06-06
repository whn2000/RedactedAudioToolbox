import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk


class FailedTasksGUI:
    """界面用于管理和重试处于 red_failed 状态的种子任务"""

    def __init__(self, parent_frame: ctk.CTkFrame, app_ref) -> None:
        """
        Parameters
        ----------
        parent_frame : ctk.CTkFrame
            父容器帧
        app_ref : AppGUI 实例（来自 elitetmhelper2）
            持有 .pipeline 属性；每次操作时动态读取，解决初始化时
            pipeline 尚未创建（为 None）导致功能完全失效的问题。
        """
        self.parent = parent_frame
        self._app_ref = app_ref   # 保存 app 引用，每次操作动态取 pipeline
        self.checkboxes = {}
        self.task_widgets = []

        self.top_frame = ctk.CTkFrame(self.parent)
        self.top_frame.pack(fill=tk.X, padx=10, pady=10)

        self.btn_refresh = ctk.CTkButton(
            self.top_frame, text="刷新失败任务 / Refresh Failed Tasks",
            command=self.refresh_tasks
        )
        self.btn_refresh.pack(side=tk.LEFT, padx=5)

        self.btn_retry = ctk.CTkButton(
            self.top_frame, text="重试选中 / Retry Selected",
            command=self.retry_selected,
            fg_color="#28a745", hover_color="#218838"
        )
        self.btn_retry.pack(side=tk.LEFT, padx=5)

        self.btn_remove = ctk.CTkButton(
            self.top_frame, text="停止追踪 / Remove from Tracker",
            command=self.remove_selected,
            fg_color="#dc3545", hover_color="#c82333"
        )
        self.btn_remove.pack(side=tk.LEFT, padx=5)

        self.scroll_frame = ctk.CTkScrollableFrame(
            self.parent, label_text="Failed Torrents (red_failed)"
        )
        self.scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.status_label = ctk.CTkLabel(self.top_frame, text="就绪 / Ready", text_color="gray")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # 启动后延迟刷新（此时 pipeline 可能还未初始化，refresh_tasks 内会重试）
        self.parent.after(2000, self.refresh_tasks)

    # ------------------------------------------------------------------
    # 动态获取当前 pipeline（解决初始化时永远为 None 的根本问题）
    # ------------------------------------------------------------------
    @property
    def pipeline(self):
        if self._app_ref is None:
            return None
        # 兼容直接传入 pipeline 对象或 app 对象两种情况
        if hasattr(self._app_ref, 'pipeline'):
            return self._app_ref.pipeline
        return self._app_ref   # 如果传入的本身就是 pipeline 对象

    # ------------------------------------------------------------------
    # 刷新列表
    # ------------------------------------------------------------------
    def refresh_tasks(self) -> None:
        pl = self.pipeline
        if not pl:
            self.status_label.configure(text="Pipeline 未启动，请先在搜索标签页开启流水线并运行一次搜索")
            # 5 秒后自动重试，等待 pipeline 被初始化
            self.parent.after(5000, self.refresh_tasks)
            return

        self.btn_refresh.configure(state="disabled")
        self.status_label.configure(text="刷新中...")

        for widget in self.task_widgets:
            widget.destroy()
        self.task_widgets.clear()
        self.checkboxes.clear()

        threading.Thread(target=self._fetch_failed_thread, daemon=True).start()

    def _fetch_failed_thread(self) -> None:
        try:
            pl = self.pipeline
            if not pl:
                self.parent.after(0, lambda: self.status_label.configure(text="Pipeline 不可用"))
                self.parent.after(0, lambda: self.btn_refresh.configure(state="normal"))
                return
            torrents = pl.qb.get_torrents(category="red_failed")
            self.parent.after(0, self._update_list, torrents)
        except Exception as e:
            self.parent.after(0, self._on_error, str(e))

    def _update_list(self, torrents) -> None:
        self.btn_refresh.configure(state="normal")
        count = len(torrents)
        self.status_label.configure(
            text=f"找到 {count} 个失败任务 / Found {count} failed task(s)",
            text_color=("red" if count > 0 else "gray")
        )

        if not torrents:
            lbl = ctk.CTkLabel(self.scroll_frame, text="没有失败任务。/ No failed tasks found.", text_color="gray")
            lbl.pack(pady=20)
            self.task_widgets.append(lbl)
            return

        for t in torrents:
            name = t.get("name", "Unknown")
            hash_str = t.get("hash", "")
            size_bytes = t.get("size", 0)
            size_str = f"{size_bytes / 1024**3:.2f} GB" if size_bytes else "?"
            state = t.get("state", "unknown")

            row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            row_frame.pack(fill=tk.X, padx=5, pady=3)

            var = tk.BooleanVar(value=True)
            self.checkboxes[hash_str] = var

            chk = ctk.CTkCheckBox(row_frame, text="", variable=var, width=30)
            chk.pack(side=tk.LEFT)

            info_frame = ctk.CTkFrame(row_frame, fg_color="#2b2b2b", corner_radius=6)
            info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

            ctk.CTkLabel(info_frame, text=name, anchor="w", font=("", 12, "bold")).pack(
                anchor="w", padx=8, pady=(4, 0)
            )
            ctk.CTkLabel(
                info_frame,
                text=f"Hash: {hash_str[:12]}...  |  大小: {size_str}  |  状态: {state}",
                anchor="w", text_color="gray", font=("", 10)
            ).pack(anchor="w", padx=8, pady=(0, 4))

            self.task_widgets.append(row_frame)

    def _on_error(self, error_msg: str) -> None:
        self.btn_refresh.configure(state="normal")
        self.status_label.configure(text="错误 / Error", text_color="red")
        messagebox.showerror("错误 / Error", f"获取失败任务时出错：\n{error_msg}")

    # ------------------------------------------------------------------
    # 重试
    # ------------------------------------------------------------------
    def retry_selected(self) -> None:
        pl = self.pipeline
        if not pl:
            messagebox.showwarning("提示", "Pipeline 未启动，无法重试。")
            return
        selected_hashes = [h for h, var in self.checkboxes.items() if var.get()]
        if not selected_hashes:
            messagebox.showinfo("提示 / Info", "请先勾选要重试的任务。/ No tasks selected.")
            return

        self.status_label.configure(text=f"正在重试 {len(selected_hashes)} 个任务...")
        threading.Thread(target=self._retry_thread, args=(selected_hashes,), daemon=True).start()

    def _retry_thread(self, hashes: list) -> None:
        try:
            pl = self.pipeline
            if not pl:
                return
            for hash_str in hashes:
                # 1. 改回 red_auto，让监控循环能重新捡到它
                pl._change_category(hash_str, "red_auto")
                # 2. 关键：同时从 processed_hashes 中移除，否则轮询会直接 continue 跳过
                if hash_str in pl.processed_hashes:
                    pl.processed_hashes.discard(hash_str)
                    if pl.db:
                        pl.db.execute(
                            "DELETE FROM pipeline_processed WHERE hash = ?",
                            (hash_str,)
                        )

            self.parent.after(0, self.refresh_tasks)
        except Exception as e:
            self.parent.after(0, self._on_error, str(e))

    # ------------------------------------------------------------------
    # 停止追踪（标记为 processed，不再重试）
    # ------------------------------------------------------------------
    def remove_selected(self) -> None:
        pl = self.pipeline
        if not pl:
            messagebox.showwarning("提示", "Pipeline 未启动。")
            return
        selected_hashes = [h for h, var in self.checkboxes.items() if var.get()]
        if not selected_hashes:
            messagebox.showinfo("提示 / Info", "请先勾选任务。/ No tasks selected.")
            return

        if messagebox.askyesno(
            "确认 / Confirm",
            "确定要将选中任务标记为 red_processed（停止追踪，不再重试）吗？\n"
            "Are you sure you want to mark selected as red_processed?"
        ):
            self.status_label.configure(text=f"正在移除 {len(selected_hashes)} 个任务...")
            threading.Thread(target=self._remove_thread, args=(selected_hashes,), daemon=True).start()

    def _remove_thread(self, hashes: list) -> None:
        try:
            pl = self.pipeline
            if not pl:
                return
            for hash_str in hashes:
                pl._change_category(hash_str, "red_processed")

            self.parent.after(0, self.refresh_tasks)
        except Exception as e:
            self.parent.after(0, self._on_error, str(e))
