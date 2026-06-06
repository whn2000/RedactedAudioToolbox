#!/usr/bin/env python3
import os
import subprocess
import argparse
from pathlib import Path
import shutil
import json
import concurrent.futures

LOSSLESS_EXTENSIONS = {'.flac', '.m4a', '.alac', '.ape', '.wav', '.aiff', '.aif', '.wv', '.tta'}

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
        '-c:a', 'flac',                   # 强制编码为 flac
        '-sample_fmt', 's16',             # 强制转换为 16bit
        '-ar', '44100',                   # 统一重采样为 44.1kHz (若想保留原采样率，请将此行注释掉)
        '-compression_level', '8',        # FLAC 最高压缩率
        str(output_path), '-y'
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **SUBPROCESS_KWARGS)
    return input_path.name

def convert_to_mp3(input_path, output_path, is_v0=False):
    """使用 ffmpeg 转换为 MP3，并保留所有元数据"""
    cmd = [
        'ffmpeg', '-i', str(input_path),
        '-map', '0:a', '-map', '0:v?',    # 映射音频流和可能存在的视频流（封面图）
        '-c:v', 'copy',                   # 复制封面图片，不重新编码
        '-c:a', 'libmp3lame'
    ]
    if is_v0:
        cmd.extend(['-q:a', '0'])
    else:
        cmd.extend(['-b:a', '320k'])
    cmd.extend([str(output_path), '-y'])
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


def get_16bit_dir_name(original_name: str) -> str:
    """获取 16bit 目录名称，限制长度以避免 RED 种子文件名过长报错"""
    name_bytes = original_name.encode('utf-8')
    if len(name_bytes) > 60:
        truncated = name_bytes[:60].decode('utf-8', 'ignore').strip()
        if truncated.endswith('-'):
            truncated = truncated[:-1].strip()
        return f"{truncated} (16bit)"
    return f"{original_name} (16bit)"

def get_mp3_dir_name(original_name: str, fmt_name: str) -> str:
    """获取 MP3 目录名称，限制长度以避免 RED 种子文件名过长报错"""
    name_bytes = original_name.encode('utf-8')
    if len(name_bytes) > 60:
        truncated = name_bytes[:60].decode('utf-8', 'ignore').strip()
        if truncated.endswith('-'):
            truncated = truncated[:-1].strip()
        return f"{truncated} ({fmt_name})"
    return f"{original_name} ({fmt_name})"

def process_album(input_path, tracker_url, source_flag):
    """处理单张专辑的逻辑"""
    audio_files = [f for f in input_path.glob('**/*') if f.is_file() and f.suffix.lower() in LOSSLESS_EXTENSIONS]
    if not audio_files:
        print(f"  -> ⚠️ 未找到无损音频文件，跳过。")
        return

    # 检查是否包含 24bit 文件或非FLAC文件 (并发检查)
    needs_conversion = False
    needs_flac_encode = False
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(get_audio_info, f): f for f in audio_files}
        for future in concurrent.futures.as_completed(futures):
            f = futures[future]
            if future.result() > 16:
                needs_conversion = True
            if f.suffix.lower() != '.flac':
                needs_flac_encode = True

    if not needs_conversion and not needs_flac_encode:
        print(f"  -> ⏭️ 已经是 16bit FLAC，跳过转换。")
        return

    # 创建输出目录，并限制长度
    output_dir_name = get_16bit_dir_name(input_path.name)
    output_path = input_path.parent / output_dir_name
    output_path.mkdir(exist_ok=True)
    print(f"  -> 输出目录: {output_path.name}")

    # 收集需要转换和复制的任务
    conversion_tasks = []
    copy_tasks = []

    for item in input_path.glob('**/*'):
        rel_path = item.relative_to(input_path)
        
        # 处理可能的长文件名
        parts = list(rel_path.parts)
        if not item.is_dir():
            filename = parts[-1]
            folder_len = len(output_path.name.encode('utf-8'))
            subdirs_len = sum(len(p.encode('utf-8')) + 1 for p in parts[:-1])
            allowed_filename_bytes = 170 - folder_len - subdirs_len - 1
            if allowed_filename_bytes < 20:
                allowed_filename_bytes = 20
                
            filename_bytes = filename.encode('utf-8')
            if len(filename_bytes) > allowed_filename_bytes:
                ext = '.flac' if item.suffix.lower() in LOSSLESS_EXTENSIONS else item.suffix
                ext_bytes = ext.encode('utf-8')
                base_len = allowed_filename_bytes - len(ext_bytes)
                safe_base = filename_bytes[:base_len].decode('utf-8', 'ignore').strip()
                parts[-1] = safe_base + ext
            else:
                if item.suffix.lower() in LOSSLESS_EXTENSIONS:
                    parts[-1] = Path(filename).stem + ".flac"

        target_item = output_path.joinpath(*parts)

        if item.is_dir():
            target_item.mkdir(exist_ok=True)
            continue
            
        if item.suffix.lower() in LOSSLESS_EXTENSIONS:
            bits = get_audio_info(item)
            if bits > 16 or item.suffix.lower() != '.flac':
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

def process_mp3_album(input_path, tracker_url, source_flag):
    """处理单张专辑转码为 MP3 (320k 和 V0) 的逻辑"""
    process_mp3_album_with_options(input_path, tracker_url, source_flag, mp3_320=True, mp3_v0=True)

def process_mp3_album_with_options(input_path, tracker_url, source_flag, mp3_320=True, mp3_v0=True):
    """处理单张专辑转码为指定 MP3 格式的逻辑"""
    audio_files = [item for item in input_path.glob('**/*') if item.is_file() and item.suffix.lower() in LOSSLESS_EXTENSIONS]
    if not audio_files:
        print(f"  -> ⚠️ 未找到无损音频文件，跳过 MP3 转换。")
        return

    formats = []
    if mp3_320:
        formats.append(("320", False))
    if mp3_v0:
        formats.append(("V0", True))
        
    for fmt_name, is_v0 in formats:
        output_dir_name = get_mp3_dir_name(input_path.name, fmt_name)
        output_path = input_path.parent / output_dir_name
        output_path.mkdir(exist_ok=True)
        print(f"  -> 输出 MP3 {fmt_name} 目录: {output_path.name}")
        
        conversion_tasks = []
        copy_tasks = []

        for item in input_path.glob('**/*'):
            rel_path = item.relative_to(input_path)
            parts = list(rel_path.parts)
            if not item.is_dir():
                filename = parts[-1]
                folder_len = len(output_path.name.encode('utf-8'))
                subdirs_len = sum(len(p.encode('utf-8')) + 1 for p in parts[:-1])
                allowed_filename_bytes = 170 - folder_len - subdirs_len - 1
                if allowed_filename_bytes < 20: 
                    allowed_filename_bytes = 20
                
                filename_bytes = filename.encode('utf-8')
                if len(filename_bytes) > allowed_filename_bytes:
                    ext = ".mp3" if item.suffix.lower() in LOSSLESS_EXTENSIONS else item.suffix
                    ext_bytes = ext.encode('utf-8')
                    base_len = allowed_filename_bytes - len(ext_bytes)
                    safe_base = filename_bytes[:base_len].decode('utf-8', 'ignore').strip()
                    parts[-1] = safe_base + ext
                else:
                    if item.suffix.lower() in LOSSLESS_EXTENSIONS:
                        parts[-1] = Path(filename).stem + ".mp3"

            target_item = output_path.joinpath(*parts)

            if item.is_dir():
                target_item.mkdir(exist_ok=True)
                continue
                
            if item.suffix.lower() in LOSSLESS_EXTENSIONS:
                conversion_tasks.append((item, target_item))
            else:
                copy_tasks.append((item, target_item))

        for src, dst in copy_tasks:
            shutil.copy2(src, dst)

        if conversion_tasks:
            print(f"  -> 正在并发转换 {len(conversion_tasks)} 个 {fmt_name} MP3 文件...")
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_file = {executor.submit(convert_to_mp3, src, dst, is_v0): src for src, dst in conversion_tasks}
                for future in concurrent.futures.as_completed(future_to_file):
                    filename = future.result()
                    
        print(f"  -> {fmt_name} MP3 音频处理完成。")
        torrent_file = input_path.parent / f"{output_path.name}.torrent"
        create_pt_torrent(output_path, torrent_file, tracker_url, source_flag)


def process_batch(base_dir, tracker_url, source_flag):
    """遍历总文件夹下的每一张专辑并分别处理 (默认仅 16bit FLAC)"""
    process_batch_with_options(base_dir, tracker_url, source_flag, flac_out=True, mp3_320_out=False, mp3_v0_out=False)

def process_batch_with_options(base_dir, tracker_url, source_flag, flac_out=True, mp3_320_out=False, mp3_v0_out=False):
    """遍历总文件夹下的每一张专辑并分别处理指定的格式"""
    check_dependencies()
    
    base_path = Path(base_dir).resolve()
    if not base_path.is_dir():
        print(f"错误: 目录 {base_path} 不存在。")
        return

    print(f"开始扫描总目录: {base_path.name}\n")
    
    # 遍历第一层子目录 (识别为独立的专辑)
    for album_dir in base_path.iterdir():
        if album_dir.is_dir():
            # 过滤已生成格式目录，防止无限循环
            if album_dir.name.endswith("(16bit)") or album_dir.name.endswith("(320)") or album_dir.name.endswith("(V0)"):
                continue
                
            print(f"{'-'*60}")
            print(f"💿 正在检查专辑: {album_dir.name}")
            
            # 1. 16-bit FLAC conversion
            if flac_out:
                process_album(album_dir, tracker_url, source_flag)
                
            # 2. MP3 conversion
            if mp3_320_out or mp3_v0_out:
                process_mp3_album_with_options(album_dir, tracker_url, source_flag, mp3_320_out, mp3_v0_out)

    print(f"\n{'='*60}\n🎉 所有扫描与处理任务已完成！")



import customtkinter as ctk
from i18n import _

class RedirectText:
    def __init__(self, text_ctrl):
        self.output = text_ctrl

    def write(self, string):
        def _write():
            try:
                self.output.insert(tk.END, string)
                self.output.see(tk.END)
            except Exception:
                pass
        self.output.after(0, _write)

    def flush(self):
        pass

class FlacDownsamplerGUI:
    def __init__(self, parent):
        self.parent = parent
        self.is_running = False
        
        self.input_dir_var = tk.StringVar()
        self.tracker_var = tk.StringVar()
        self.source_var = tk.StringVar()

        self.output_flac_var = tk.BooleanVar(value=True)
        self.output_320_var = tk.BooleanVar(value=False)
        self.output_v0_var = tk.BooleanVar(value=False)

        self.build_ui()

    def build_ui(self):
        self.scrollable_frame = ctk.CTkScrollableFrame(self.parent)
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        config_frame = ctk.CTkFrame(self.scrollable_frame)
        config_frame.pack(fill=tk.X, padx=5, pady=5)
        ctk.CTkLabel(config_frame, text=_("config"), font=("", 16, "bold")).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5, padx=5)

        ctk.CTkLabel(config_frame, text=_("album_dir")).grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.input_dir_var, width=400).grid(row=1, column=1, sticky=tk.W, padx=5)
        ctk.CTkButton(config_frame, text=_("browse"), command=self.browse_dir, width=80).grid(row=1, column=2, padx=5)

        ctk.CTkLabel(config_frame, text=_("tracker_url")).grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.tracker_var, width=400).grid(row=2, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text=_("source_flag")).grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        ctk.CTkEntry(config_frame, textvariable=self.source_var, width=200).grid(row=3, column=1, sticky=tk.W, padx=5)

        ctk.CTkLabel(config_frame, text="输出格式 (Formats)").grid(row=4, column=0, sticky=tk.W, pady=5, padx=5)
        formats_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        formats_frame.grid(row=4, column=1, sticky=tk.W, pady=5, padx=5)
        ctk.CTkCheckBox(formats_frame, text="16-bit FLAC", variable=self.output_flac_var, width=100).pack(side=tk.LEFT, padx=5)
        ctk.CTkCheckBox(formats_frame, text="MP3 320k", variable=self.output_320_var, width=100).pack(side=tk.LEFT, padx=5)
        ctk.CTkCheckBox(formats_frame, text="MP3 V0", variable=self.output_v0_var, width=100).pack(side=tk.LEFT, padx=5)

        btn_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.start_btn = ctk.CTkButton(btn_frame, text=_("start_downsample"), command=self.start_process, fg_color="#28a745", hover_color="#218838")
        self.start_btn.pack(side=tk.LEFT, padx=5)

        log_frame = ctk.CTkFrame(self.parent)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        ctk.CTkLabel(log_frame, text=_("run_logs"), font=("", 16, "bold")).pack(anchor=tk.W, padx=5, pady=5)
        
        self.log_text = ctk.CTkTextbox(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def browse_dir(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.input_dir_var.set(dir_path)

    def start_process(self):
        if not self.input_dir_var.get() or not self.tracker_var.get():
            tk.messagebox.showwarning("提示", "请填写完整的输入目录和 Tracker URL！")
            return
            
        if not (self.output_flac_var.get() or self.output_320_var.get() or self.output_v0_var.get()):
            tk.messagebox.showwarning("提示", "请选择至少一个输出格式！")
            return
            
        self.start_btn.configure(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        
        threading.Thread(target=self.run_thread, daemon=True).start()

    def run_thread(self):
        old_stdout = sys.stdout
        sys.stdout = RedirectText(self.log_text)
        try:
            print(">>> 正在启动多格式转码与制种任务...\n")
            process_batch_with_options(
                self.input_dir_var.get(),
                self.tracker_var.get(),
                self.source_var.get(),
                self.output_flac_var.get(),
                self.output_320_var.get(),
                self.output_v0_var.get()
            )
        except Exception as e:
            print(f"\n❌ [错误]: {str(e)}")
        finally:
            sys.stdout = old_stdout
            try:
                self.parent.after(0, lambda: self.start_btn.configure(state=tk.NORMAL))
            except:
                pass

if __name__ == "__main__":
    pass