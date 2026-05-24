#!/usr/bin/env python3
import os
import subprocess
import argparse
from pathlib import Path
import shutil
import json
import concurrent.futures

if os.name == 'nt':
    SUBPROCESS_KWARGS = {'creationflags': 0x08000000}
else:
    SUBPROCESS_KWARGS = {}

try:
    from torf import Torrent
except ImportError:
    pass

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
import sys

def check_dependencies():
    """检查是否安装了 ffmpeg 和 ffprobe"""
    missing = []
    for cmd in ['ffmpeg', 'ffprobe']:
        try:
            subprocess.run([cmd, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **SUBPROCESS_KWARGS)
        except FileNotFoundError:
            missing.append(cmd)
    if missing:
        print(f"错误: 缺少核心依赖: {', '.join(missing)}。请确保它们已安装并添加到系统环境变量 PATH 中。")
        exit(1)

def get_audio_info(filepath):
    """使用 ffprobe 获取音频的位深（重构为稳定的 JSON 解析）"""
    cmd_bits = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', '-select_streams', 'a:0',
        str(filepath)
    ]
    try:
        output = subprocess.run(cmd_bits, capture_output=True, text=True, check=True, **SUBPROCESS_KWARGS)
        data = json.loads(output.stdout)
        
        # 从 streams 中提取
        if "streams" in data and len(data["streams"]) > 0:
            stream = data["streams"][0]
            # 优先检查 bits_per_raw_sample，其次 bits_per_sample
            bps = stream.get("bits_per_raw_sample")
            if not bps:
                bps = stream.get("bits_per_sample")
                
            if bps and str(bps).isdigit():
                return int(bps)
    except Exception:
        pass
        
    return 0


def convert_to_16bit(input_path, output_path):
    """使用 ffmpeg 转换为 16bit/44.1kHz FLAC，并保留所有元数据"""
    cmd = [
        'ffmpeg', '-i', str(input_path),
        '-map', '0:a', '-map', '0:v?',    # 映射音频流和可能存在的视频流（封面图）
        '-c:v', 'copy',                   # 复制封面图片，不重新编码
        '-sample_fmt', 's16',             # 强制转换为 16bit
        '-ar', '44100',                   # 统一重采样为 44.1kHz (若想保留原采样率，请将此行注释掉)
        '-compression_level', '8',        # FLAC 最高压缩率
        str(output_path), '-y'
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **SUBPROCESS_KWARGS)
    return input_path.name


def create_pt_torrent(source_dir, torrent_path, tracker_url, source_flag):
    """创建符合 PT 规范的私有种子"""
    print(f"  正在生成种子文件: {torrent_path.name} ...")
    t = Torrent(path=str(source_dir),
                trackers=[tracker_url],
                source=source_flag,
                private=True) # PT 站必须为 True
    
    # torf 会自动分块和计算哈希
    t.generate()
    t.write(str(torrent_path), overwrite=True)
    print(f"  ✅ 种子已生成: {torrent_path.name}")


def process_album(input_path, tracker_url, source_flag):
    """处理单张专辑的逻辑"""
    flac_files = list(input_path.glob('**/*.flac'))
    if not flac_files:
        print(f"  -> ⚠️ 未找到 FLAC 文件，跳过。")
        return

    # 检查是否包含 24bit 文件 (并发检查)
    needs_conversion = False
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(get_audio_info, flac): flac for flac in flac_files}
        for future in concurrent.futures.as_completed(futures):
            if future.result() > 16:
                needs_conversion = True
                # 不要 break，必须让已经启动的 future 跑完或者取消
                # concurrent.futures 不太好取消，所以就让它们跑完

    if not needs_conversion:
        print(f"  -> ⏭️ 已经是 16bit 或以下，跳过转换。")
        return

    # 创建输出目录，例如 "Album Name (16bit)"
    output_path = input_path.parent / f"{input_path.name} (16bit)"
    output_path.mkdir(exist_ok=True)
    print(f"  -> 输出目录: {output_path.name}")

    # 收集需要转换和复制的任务
    conversion_tasks = []
    copy_tasks = []

    for item in input_path.glob('**/*'):
        rel_path = item.relative_to(input_path)
        target_item = output_path / rel_path

        if item.is_dir():
            target_item.mkdir(exist_ok=True)
            continue
            
        if item.suffix.lower() == '.flac':
            bits = get_audio_info(item)
            if bits > 16:
                conversion_tasks.append((item, target_item))
            else:
                copy_tasks.append((item, target_item))
        else:
            copy_tasks.append((item, target_item))

    # 执行附件复制
    for src, dst in copy_tasks:
        shutil.copy2(src, dst)

    # 执行并发转换
    if conversion_tasks:
        print(f"  -> 正在并发转换 {len(conversion_tasks)} 个音频文件...")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_file = {executor.submit(convert_to_16bit, src, dst): src for src, dst in conversion_tasks}
            for future in concurrent.futures.as_completed(future_to_file):
                filename = future.result()
                print(f"    ✅ 完成转换: {filename}")
                
    print("  -> 音频及附件处理完成。")
    
    # 在同级目录生成种子
    torrent_file = input_path.parent / f"{output_path.name}.torrent"
    create_pt_torrent(output_path, torrent_file, tracker_url, source_flag)


def process_batch(base_dir, tracker_url, source_flag):
    """遍历总文件夹下的每一张专辑并分别处理"""
    check_dependencies()
    
    base_path = Path(base_dir).resolve()
    if not base_path.is_dir():
        print(f"错误: 目录 {base_path} 不存在。")
        return

    print(f"开始扫描总目录: {base_path.name}\n")
    
    # 遍历第一层子目录 (识别为独立的专辑)
    for album_dir in base_path.iterdir():
        if album_dir.is_dir():
            # 过滤掉已经生成过的 (16bit) 文件夹，防止无限套娃
            if album_dir.name.endswith("(16bit)"):
                continue
                
            print(f"{'-'*60}")
            print(f"💿 正在检查专辑: {album_dir.name}")
            process_album(album_dir, tracker_url, source_flag)

    print(f"\n{'='*60}\n🎉 所有扫描与处理任务已完成！")



class RedirectText:
    def __init__(self, text_ctrl):
        self.output = text_ctrl

    def write(self, string):
        self.output.insert(tk.END, string)
        self.output.see(tk.END)

    def flush(self):
        pass

class FlacDownsamplerGUI:
    def __init__(self, parent):
        self.parent = parent
        self.is_running = False
        
        self.input_dir_var = tk.StringVar()
        self.tracker_var = tk.StringVar()
        self.source_var = tk.StringVar()

        self.build_ui()

    def build_ui(self):
        config_frame = ttk.LabelFrame(self.parent, text="配置项 (Configuration)", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(config_frame, text="专辑主文件夹 (Album Dir):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.input_dir_var, width=50).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(config_frame, text="浏览... (Browse...)", command=self.browse_dir).grid(row=0, column=2, padx=5)

        ttk.Label(config_frame, text="Tracker URL:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.tracker_var, width=50).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(config_frame, text="Source 标识 (Source Flag):").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.source_var, width=20).grid(row=2, column=1, sticky=tk.W, padx=5)

        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_btn = ttk.Button(btn_frame, text="▶ 开始降频与制种 (Start Downsample & Make Torrent)", command=self.start_process)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        log_frame = ttk.LabelFrame(self.parent, text="运行日志 (Run Logs)", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.NORMAL, bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def browse_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.input_dir_var.set(dir_path)

    def start_process(self):
        if not self.input_dir_var.get() or not self.tracker_var.get():
            tk.messagebox.showwarning("提示", "请填写完整的输入目录和 Tracker URL！")
            return
            
        self.start_btn.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        
        threading.Thread(target=self.run_thread, daemon=True).start()

    def run_thread(self):
        old_stdout = sys.stdout
        sys.stdout = RedirectText(self.log_text)
        try:
            print(">>> 正在启动 FLAC 降频与制种任务...\n")
            process_batch(self.input_dir_var.get(), self.tracker_var.get(), self.source_var.get())
        except Exception as e:
            print(f"\n❌ [错误]: {str(e)}")
        finally:
            sys.stdout = old_stdout
            self.parent.after(0, lambda: self.start_btn.config(state=tk.NORMAL))

if __name__ == "__main__":
    pass