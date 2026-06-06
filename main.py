import sys
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from dependency_manager import check_and_install_dependencies
from gui.search_tab import AppGUI as RedactedFinderGUI
from flac_downsampler import FlacDownsamplerGUI
from lossless_checker import LosslessCheckerGUI
from gui.failed_tasks_tab import FailedTasksGUI
from gui.discovery_tab import DiscoveryTabGUI
from gui.pipeline_tab import PipelineTabGUI

from i18n import _, set_language, CURRENT_LANG, subscribe_lang_change
from core.context import AppContext
from core.consolidation import WriteGuardMode, default_guard
import core.globals

ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title(_("title"))
        
        subscribe_lang_change(self.update_ui_text)
        
        self.build_menu()
        
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.tabview = None
        self.build_tabs()
        
        self.change_window_size(1024, 768)

    def build_tabs(self):
        if hasattr(self, 'app1') and self.app1 and hasattr(self.app1, 'pipeline') and self.app1.pipeline:
            self.app1.pipeline.stop()
            
        if self.tabview:
            self.tabview.destroy()
            
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.pack(fill=tk.BOTH, expand=True)
        
        self.tab_name_search = _("tab_search")
        self.tab_name_downsample = _("tab_downsample")
        self.tab_name_check = _("tab_check")
        self.tab_name_pipeline = "⚙️ Pipeline"
        self.tab_name_failed = "❌ Failed Tasks"
        self.tab_name_discovery = "🌐 " + _("tab_discovery") if _("tab_discovery") != "tab_discovery" else "🌐 Discovery"
        
        self.tabview.add(self.tab_name_search)
        self.tabview.add(self.tab_name_downsample)
        self.tabview.add(self.tab_name_check)
        self.tabview.add(self.tab_name_pipeline)
        self.tabview.add(self.tab_name_failed)
        self.tabview.add(self.tab_name_discovery)
        
        self.app1 = RedactedFinderGUI(self.tabview.tab(self.tab_name_search))
        self.app2 = FlacDownsamplerGUI(self.tabview.tab(self.tab_name_downsample))
        self.app3 = LosslessCheckerGUI(self.tabview.tab(self.tab_name_check))
        # 传入 self.app1 引用，让各标签页动态获取 pipeline（解决初始化时永远 None 的问题）
        self.app_pipeline = PipelineTabGUI(self.tabview.tab(self.tab_name_pipeline), self.app1)
        self.app5 = FailedTasksGUI(self.tabview.tab(self.tab_name_failed), self.app1)
        self.app_discovery = DiscoveryTabGUI(self.tabview.tab(self.tab_name_discovery), core.globals.app_context, getattr(self.app1, 'pipeline', None))

    def update_ui_text(self):
        self.root.title(_("title"))
        self.build_menu()
        self.build_tabs()

    def build_menu(self):
        menubar = tk.Menu(self.root)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label=_("small_window"), command=lambda: self.change_window_size(800, 600))
        view_menu.add_command(label=_("medium_window"), command=lambda: self.change_window_size(1024, 768))
        view_menu.add_command(label=_("large_window"), command=lambda: self.change_window_size(1280, 900))
        view_menu.add_command(label=_("huge_window"), command=lambda: self.change_window_size(1600, 1200))
        view_menu.add_separator()
        view_menu.add_command(label=_("fit_screen"), command=self.auto_fit_screen)
        
        lang_menu = tk.Menu(menubar, tearoff=0)
        lang_menu.add_command(label="中文 (zh_CN)", command=lambda: set_language("zh_CN"))
        lang_menu.add_command(label="English (en_US)", command=lambda: set_language("en_US"))
        
        menubar.add_cascade(label=_("view"), menu=view_menu)
        menubar.add_cascade(label=_("language"), menu=lang_menu)
        self.root.config(menu=menubar)

    def change_window_size(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        x = int((screen_width - width) / 2)
        y = int((screen_height - height) / 2)
        
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def auto_fit_screen(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        target_width = int(screen_width * 0.8)
        target_height = int(screen_height * 0.8)
        
        self.change_window_size(target_width, target_height)

if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    root = ctk.CTk()
    
    if not check_and_install_dependencies(root):
        messagebox.showerror("错误/Error", "缺少必要的环境依赖 (ffmpeg, sox) / Missing dependencies (ffmpeg, sox).")
        sys.exit(1)
        
    core.globals.app_context = AppContext()
    core.globals.app_context.startup()
    
    # Configure WriteGuard to strictly block legacy writes going forward
    default_guard.mode = WriteGuardMode.STRICT
    default_guard.set_gateway(core.globals.app_context.gateway)
    
    app = MainApp(root)
    
    try:
        root.mainloop()
    finally:
        core.globals.app_context.shutdown()
