import sys
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont

from dependency_manager import check_and_install_dependencies
from elitetmhelper2 import AppGUI as RedactedFinderGUI
from flac_downsampler import FlacDownsamplerGUI
from lossless_checker import LosslessCheckerGUI

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Redacted Audio Toolbox - 三合一音乐工具箱 (3-in-1 Audio Toolbox)")
        
        self.build_menu()
        
        # 美化整体风格
        style = ttk.Style()
        if 'clam' in style.theme_names():
            style.theme_use('clam')
            
        # 设置 Notebook 容器
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: Redacted Finder
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text=" 🔍 Redacted 种子搜索与下载 (Search & DL) ")
        self.app1 = RedactedFinderGUI(self.tab1)
        
        # Tab 2: FLAC Downsampler
        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text=" 💽 FLAC 降频与制种 (24bit->16bit Downsampler) ")
        self.app2 = FlacDownsamplerGUI(self.tab2)
        
        # Tab 3: Lossless Checker
        self.tab3 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab3, text=" 🎵 频谱检测与真假无损验证 (Lossless Check) ")
        self.app3 = LosslessCheckerGUI(self.tab3)
        
        # 初始化窗口尺寸与字体适配
        self.change_window_size(1024, 768)

    def build_menu(self):
        menubar = tk.Menu(self.root)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="小窗口 (800x600)", command=lambda: self.change_window_size(800, 600))
        view_menu.add_command(label="中窗口 (1024x768)", command=lambda: self.change_window_size(1024, 768))
        view_menu.add_command(label="大窗口 (1280x900)", command=lambda: self.change_window_size(1280, 900))
        view_menu.add_command(label="超大窗口 (1600x1200)", command=lambda: self.change_window_size(1600, 1200))
        view_menu.add_separator()
        view_menu.add_command(label="自适应屏幕 (占全屏80%)", command=self.auto_fit_screen)
        
        menubar.add_cascade(label="视图 (View)", menu=view_menu)
        self.root.config(menu=menubar)

    def update_font_size(self, target_width):
        """根据窗口宽度动态计算并应用全局字体大小"""
        scale = target_width / 1024.0
        scale = max(0.8, min(scale, 2.0))
        
        ui_font_size = int(10 * scale)
        log_font_size = int(10 * scale)
        title_font_size = int(11 * scale)
        
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Microsoft YaHei", size=ui_font_size)
        
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family="Consolas", size=log_font_size)
        
        fixed_font = tkfont.nametofont("TkFixedFont")
        fixed_font.configure(family="Consolas", size=log_font_size)
        
        style = ttk.Style()
        style.configure(".", font=default_font)
        style.configure("TLabelframe.Label", font=("Microsoft YaHei", title_font_size, "bold"))
        style.configure("TNotebook.Tab", font=("Microsoft YaHei", ui_font_size, "bold"), padding=[10, 5])
        
        # 更新各子界面的日志框字体
        for app in (self.app1, self.app2, self.app3):
            if hasattr(app, 'log_text'):
                app.log_text.configure(font=fixed_font)

    def change_window_size(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        x = int((screen_width - width) / 2)
        y = int((screen_height - height) / 2)
        
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.update_font_size(width)

    def auto_fit_screen(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        target_width = int(screen_width * 0.8)
        target_height = int(screen_height * 0.8)
        
        self.change_window_size(target_width, target_height)

if __name__ == "__main__":
    # 启用高 DPI 支持
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
        
    root = tk.Tk()
    root.withdraw() # 先隐藏主窗口，进行依赖检测
    
    # 检测并自动下载缺失的依赖
    if not check_and_install_dependencies(root):
        messagebox.showerror("错误", "缺少必要的环境依赖 (ffmpeg, sox)，程序即将退出。")
        sys.exit(1)
        
    root.deiconify() # 依赖检测通过，显示主窗口
    app = MainApp(root)
    root.mainloop()
