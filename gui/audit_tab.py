import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from pathlib import Path

class AuditTabGUI:
    """独立的风险审核仪表盘，异步调用 Quality Engine 分析选定目录"""
    
    def __init__(self, parent_frame: ctk.CTkFrame) -> None:
        self.parent = parent_frame
        
        # 顶部操作区
        self.top_frame = ctk.CTkFrame(self.parent)
        self.top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.dir_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Select Album Directory...")
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.btn_select = ctk.CTkButton(self.top_frame, text="Browse", width=80, command=self.browse_dir)
        self.btn_select.pack(side=tk.LEFT, padx=(0, 10))
        
        self.btn_run = ctk.CTkButton(self.top_frame, text="Run Audit", width=100, command=self.run_audit)
        self.btn_run.pack(side=tk.LEFT)
        
        # 中间大字核心数据展示 (Score + Level)
        self.dash_frame = ctk.CTkFrame(self.parent)
        self.dash_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.score_label = ctk.CTkLabel(self.dash_frame, text="Score: --", font=ctk.CTkFont(size=20))
        self.score_label.pack(pady=(15, 5))
        
        self.level_label = ctk.CTkLabel(self.dash_frame, text="READY", font=ctk.CTkFont(size=36, weight="bold"))
        self.level_label.pack(pady=(0, 15))
        
        # 底部规则触发详情滚动窗
        self.scroll_frame = ctk.CTkScrollableFrame(self.parent, label_text="Rule Breakdown")
        self.scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def browse_dir(self) -> None:
        directory = filedialog.askdirectory()
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)

    def run_audit(self) -> None:
        album_dir = self.dir_entry.get()
        if not album_dir or not Path(album_dir).exists():
            messagebox.showerror("Error", "Invalid directory selected.")
            return
            
        # 防止重复点击并清理旧记录
        self.btn_run.configure(state="disabled", text="Running...")
        self.level_label.configure(text="ANALYZING...", text_color="gray")
        
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        # 启动守护线程跑重量级的扫描
        threading.Thread(target=self._audit_thread, args=(album_dir,), daemon=True).start()

    def _audit_thread(self, album_dir: str) -> None:
        """后台线程，严禁在此方法中直接操作 GUI 组件"""
        try:
            from quality.features.extractor import FeatureExtractor
            from quality.risk.engine import RiskEngine
            from quality.models import AudioContext
            
            ctx = AudioContext(
                album_dir=Path(album_dir), 
                format="FLAC", 
                source="WEB", 
                bitrate="Lossless"
            )
            extractor = FeatureExtractor()
            ctx.features = extractor.extract_album(Path(album_dir))
            
            engine = RiskEngine()
            report = engine.evaluate(ctx)
            
            # 使用 after() 将结果安全回传给主线程渲染
            self.parent.after(0, self._update_gui, report)
        except Exception as e:
            self.parent.after(0, self._on_error, str(e))

    def _update_gui(self, report) -> None:
        """主线程渲染结果"""
        self.btn_run.configure(state="normal", text="Run Audit")
        self.score_label.configure(text=f"Total Score: {report.score}")
        
        # 色彩映射要求
        colors = {
            "SAFE": "#28a745",          # 绿色
            "LOW_RISK": "#ffc107",      # 黄色
            "SUSPICIOUS": "#fd7e14",    # 橙色
            "HIGH_RISK": "#dc3545",     # 红色
            "LIKELY_TRANSCODE": "#dc3545"
        }
        color = colors.get(report.level, "white")
        self.level_label.configure(text=report.level, text_color=color)
        
        # 渲染扣分项详细规则 Breakdown
        for rule in report.rule_results:
            if rule.score_delta > 0:
                text = f"[+{rule.score_delta}] {rule.reason}"
                lbl = ctk.CTkLabel(self.scroll_frame, text=text, anchor="w", justify="left", font=ctk.CTkFont(size=13))
                lbl.pack(fill=tk.X, padx=10, pady=4)

    def _on_error(self, error_msg: str) -> None:
        """异常安全处理机制"""
        self.btn_run.configure(state="normal", text="Run Audit")
        self.level_label.configure(text="ERROR", text_color="red")
        messagebox.showerror("Audit Error", f"An error occurred during audit:\n{error_msg}")
