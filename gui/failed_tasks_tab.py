import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

class FailedTasksGUI:
    """界面用于管理和重试处于 red_failed 状态的种子任务"""
    
    def __init__(self, parent_frame: ctk.CTkFrame, pipeline) -> None:
        self.parent = parent_frame
        self.pipeline = pipeline
        self.checkboxes = {}
        self.task_widgets = []
        
        self.top_frame = ctk.CTkFrame(self.parent)
        self.top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.btn_refresh = ctk.CTkButton(self.top_frame, text="Refresh Failed Tasks", command=self.refresh_tasks)
        self.btn_refresh.pack(side=tk.LEFT, padx=5)
        
        self.btn_retry = ctk.CTkButton(self.top_frame, text="Retry Selected", command=self.retry_selected, fg_color="#28a745", hover_color="#218838")
        self.btn_retry.pack(side=tk.LEFT, padx=5)

        self.btn_remove = ctk.CTkButton(self.top_frame, text="Remove from Tracker", command=self.remove_selected, fg_color="#dc3545", hover_color="#c82333")
        self.btn_remove.pack(side=tk.LEFT, padx=5)
        
        self.scroll_frame = ctk.CTkScrollableFrame(self.parent, label_text="Failed Torrents (red_failed)")
        self.scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.status_label = ctk.CTkLabel(self.top_frame, text="Ready", text_color="gray")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # Auto-refresh on startup
        self.parent.after(1000, self.refresh_tasks)

    def refresh_tasks(self) -> None:
        if not self.pipeline:
            self.status_label.configure(text="Pipeline not loaded")
            return
            
        self.btn_refresh.configure(state="disabled")
        self.status_label.configure(text="Refreshing...")
        
        # Clear existing checkboxes and labels
        for widget in self.task_widgets:
            widget.destroy()
        self.task_widgets.clear()
        self.checkboxes.clear()
        
        threading.Thread(target=self._fetch_failed_thread, daemon=True).start()

    def _fetch_failed_thread(self) -> None:
        try:
            torrents = self.pipeline.qb.get_torrents(category="red_failed")
            self.parent.after(0, self._update_list, torrents)
        except Exception as e:
            self.parent.after(0, self._on_error, str(e))

    def _update_list(self, torrents) -> None:
        self.btn_refresh.configure(state="normal")
        self.status_label.configure(text=f"Found {len(torrents)} failed task(s)")
        
        if not torrents:
            lbl = ctk.CTkLabel(self.scroll_frame, text="No failed tasks found.", text_color="gray")
            lbl.pack(pady=20)
            self.task_widgets.append(lbl)
            return
            
        for t in torrents:
            name = t.get("name", "Unknown")
            hash_str = t.get("hash")
            
            var = tk.BooleanVar(value=True)
            self.checkboxes[hash_str] = var
            
            chk = ctk.CTkCheckBox(self.scroll_frame, text=name, variable=var)
            chk.pack(anchor="w", padx=10, pady=5)
            self.task_widgets.append(chk)

    def _on_error(self, error_msg: str) -> None:
        self.btn_refresh.configure(state="normal")
        self.status_label.configure(text="Error", text_color="red")
        messagebox.showerror("Error", f"Failed to fetch tasks:\n{error_msg}")

    def retry_selected(self) -> None:
        if not self.pipeline: return
        selected_hashes = [h for h, var in self.checkboxes.items() if var.get()]
        if not selected_hashes:
            messagebox.showinfo("Info", "No tasks selected.")
            return
            
        self.status_label.configure(text=f"Retrying {len(selected_hashes)} task(s)...")
        threading.Thread(target=self._retry_thread, args=(selected_hashes,), daemon=True).start()

    def _retry_thread(self, hashes: list) -> None:
        try:
            for hash_str in hashes:
                # Change category back to red_auto
                self.pipeline._change_category(hash_str, "red_auto")
            
            self.parent.after(0, self.refresh_tasks)
        except Exception as e:
            self.parent.after(0, self._on_error, str(e))

    def remove_selected(self) -> None:
        if not self.pipeline: return
        selected_hashes = [h for h, var in self.checkboxes.items() if var.get()]
        if not selected_hashes:
            messagebox.showinfo("Info", "No tasks selected.")
            return
            
        if messagebox.askyesno("Confirm", "Are you sure you want to change category to red_processed to stop tracking?"):
            self.status_label.configure(text=f"Removing {len(selected_hashes)} task(s)...")
            threading.Thread(target=self._remove_thread, args=(selected_hashes,), daemon=True).start()

    def _remove_thread(self, hashes: list) -> None:
        try:
            for hash_str in hashes:
                self.pipeline._change_category(hash_str, "red_processed")
            
            self.parent.after(0, self.refresh_tasks)
        except Exception as e:
            self.parent.after(0, self._on_error, str(e))
