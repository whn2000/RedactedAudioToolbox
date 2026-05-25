import os
import sys
import subprocess
import zipfile
import shutil
import threading
from pathlib import Path
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox

# 判断是否是 PyInstaller 打包后的环境
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

# 存放依赖的目录 (与 exe 同级或与 py 文件同级)
BIN_DIR = BASE_DIR / "bin"

# 工具的下载链接 (Windows)
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
SOX_URL = "https://jaist.dl.sourceforge.net/project/sox/sox/14.4.2/sox-14.4.2-win32.zip"

def setup_environment():
    """将 bin 目录加入环境变量 PATH"""
    if not BIN_DIR.exists():
        BIN_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = str(BIN_DIR) + os.pathsep + os.environ["PATH"]

import shutil

def is_installed(cmd):
    """检查命令是否可用"""
    # 优先在 bin 目录检查
    if (BIN_DIR / f"{cmd}.exe").exists():
        return True
    # 再检查系统 PATH
    if shutil.which(cmd):
        return True
    
    # 兼容原有的 subprocess 检查
    try:
        subprocess.run([cmd, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception:
        return False

class DependencyDownloaderDialog(tk.Toplevel):
    def __init__(self, parent, missing_tools):
        super().__init__(parent)
        self.title("环境依赖自动安装")
        self.geometry("500x200")
        self.resizable(False, False)
        
        # 居中显示
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.missing_tools = missing_tools
        self.success = False
        
        self.label = ttk.Label(self, text="正在检测和下载缺失的依赖项，请稍候...", font=("Microsoft YaHei", 10))
        self.label.pack(pady=20)
        
        self.progress = ttk.Progressbar(self, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress.pack(pady=10)
        
        self.status_var = tk.StringVar(value="准备下载...")
        self.status_label = ttk.Label(self, textvariable=self.status_var, font=("Microsoft YaHei", 9))
        self.status_label.pack(pady=5)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 启动下载线程
        threading.Thread(target=self.download_and_extract, daemon=True).start()

    def on_close(self):
        if not self.success:
            if messagebox.askyesno("警告", "依赖未安装完成，软件可能无法正常工作。确定要退出下载吗？"):
                self.destroy()
        else:
            self.destroy()

    def download_file(self, url, dest_path):
        def report_hook(count, block_size, total_size):
            if total_size > 0:
                percent = int(count * block_size * 100 / total_size)
                self.progress['value'] = min(percent, 100)
                self.update_idletasks()
                
        urllib.request.urlretrieve(url, dest_path, reporthook=report_hook)

    def download_and_extract(self):
        try:
            if "ffmpeg" in self.missing_tools:
                self.status_var.set("正在下载 FFmpeg...")
                zip_path = BIN_DIR / "ffmpeg.zip"
                self.progress['value'] = 0
                self.download_file(FFMPEG_URL, zip_path)
                
                self.status_var.set("正在解压 FFmpeg...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # 找到包含 bin/ffmpeg.exe 的路径
                    for info in zip_ref.infolist():
                        if info.filename.endswith('bin/ffmpeg.exe') or info.filename.endswith('bin/ffprobe.exe'):
                            source = zip_ref.open(info)
                            target_path = BIN_DIR / Path(info.filename).name
                            with open(target_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                zip_path.unlink()

            if "sox" in self.missing_tools:
                self.status_var.set("正在下载 SoX...")
                zip_path = BIN_DIR / "sox.zip"
                self.progress['value'] = 0
                
                # 添加 User-Agent 防止被拒绝
                req = urllib.request.Request(SOX_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                    total_length = response.getheader('content-length')
                    if total_length is None:
                        out_file.write(response.read())
                    else:
                        total_length = int(total_length)
                        downloaded = 0
                        chunk_size = max(4096, total_length // 100)
                        while True:
                            buffer = response.read(chunk_size)
                            if not buffer:
                                break
                            downloaded += len(buffer)
                            out_file.write(buffer)
                            self.progress['value'] = int(downloaded * 100 / total_length)
                            self.update_idletasks()

                self.status_var.set("正在解压 SoX...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    for info in zip_ref.infolist():
                        # SoX zip 包含很多依赖 DLL，需要全部解压到 bin 目录下
                        if info.filename.endswith('/'): continue
                        filename = Path(info.filename).name
                        source = zip_ref.open(info)
                        target_path = BIN_DIR / filename
                        with open(target_path, "wb") as target:
                            shutil.copyfileobj(source, target)
                zip_path.unlink()

            self.status_var.set("依赖安装完成！")
            self.progress['value'] = 100
            self.success = True
            self.after(1000, self.destroy)
            
        except Exception as e:
            self.status_var.set("下载或解压失败！")
            messagebox.showerror("错误", f"自动下载环境依赖失败:\n{str(e)}\n\n请手动下载并将其放入程序的 bin 目录中。")
            self.after(0, self.destroy)

def check_and_install_dependencies(root):
    setup_environment()
    missing_tools = []
    
    if not is_installed("ffmpeg") or not is_installed("ffprobe"):
        missing_tools.append("ffmpeg")
    if not is_installed("sox"):
        missing_tools.append("sox")
        
    if missing_tools:
        dialog = DependencyDownloaderDialog(root, missing_tools)
        root.wait_window(dialog)
        # 再次检查
        return is_installed("ffmpeg") and is_installed("sox")
    return True
