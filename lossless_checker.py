import os
import sys
import subprocess
from pathlib import Path
from PIL import Image
import concurrent.futures
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

if os.name == 'nt':
    SUBPROCESS_KWARGS = {'creationflags': 0x08000000}
else:
    SUBPROCESS_KWARGS = {}

# 增加 Pillow 处理最大像素限制，防止拼接超长图时报错
Image.MAX_IMAGE_PIXELS = None

def check_sox_installed():
    """检查系统是否安装了 sox"""
    try:
        subprocess.run(["sox", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, **SUBPROCESS_KWARGS)
        return True
    except FileNotFoundError:
        return False

def get_audio_nyquist(file_path):
    """通过 soxi 获取音频的采样率并计算尼奎斯特频率"""
    try:
        result = subprocess.run(["sox", "--info", "-r", str(file_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **SUBPROCESS_KWARGS)
        samplerate = int(result.stdout.strip())
        return samplerate / 2
    except Exception:
        return 22050

def get_audio_specs(file_path):
    """通过 soxi 获取音频的位深和采样率"""
    try:
        res_sr = subprocess.run(["sox", "--info", "-r", str(file_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **SUBPROCESS_KWARGS)
        sample_rate = int(res_sr.stdout.strip())
        res_b = subprocess.run(["sox", "--info", "-b", str(file_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **SUBPROCESS_KWARGS)
        bit_depth = int(res_b.stdout.strip())
        return bit_depth, sample_rate
    except Exception:
        return 16, 44100

def analyze_spectrogram(raw_img_path, nyquist_freq, threshold=10):
    """分析无坐标轴的纯净频谱图，计算截止频率"""
    try:
        img = Image.open(raw_img_path).convert('L')
        width, height = img.size
        
        cutoff_row = 0
        for y in range(height):
            row_pixels = [img.getpixel((x, y)) for x in range(width)]
            
            # 使用更宽容的策略来照顾频谱不饱满的舒缓歌曲：
            # 只要有少量较高亮度的点(>30)占比超过1%，或者出现过明显的高频峰值(>80)，就认为该频段存在有效信号
            # 这能避免平均亮度(avg_brightness)被大面积黑色稀释导致的错判
            bright_pixels = sum(1 for p in row_pixels if p > 30)
            if bright_pixels > width * 0.01 or max(row_pixels) > 80:
                cutoff_row = y
                break
        
        cutoff_freq = nyquist_freq * (1 - (cutoff_row / height))
        return round(cutoff_freq, 2)
    except Exception as e:
        print(f"[-] 图像分析失败: {e}")
        return None

def judge_lossless(cutoff_freq, bit_depth, sample_rate):
    """根据截止频率和原始参数综合判断真伪及 Hi-Res"""
    specs = f"{bit_depth}bit/{sample_rate/1000:g}kHz"
    
    # 检查是否是假高解析度 (Fake Hi-Res)
    if sample_rate > 48000:
        if cutoff_freq < 24000:
            return f"❌ 假Hi-Res ({specs})", "高频被切断，疑为低采样率拉升。"
        elif cutoff_freq >= 30000:
            return f"✅ 真Hi-Res ({specs})", "高频延伸符合高解析度特征。"
        else:
            return f"⚠️ 疑似假Hi-Res ({specs})", "高频延伸不足预期。"
            
    if sample_rate == 48000:
        if cutoff_freq >= 20000:
            return f"✅ 真无损 ({specs})", "高频延伸正常。"
        elif cutoff_freq < 18000:
            return f"❌ 假无损/假Hi-Res ({specs})", "高频严重缺失。"
        else:
            return f"⚠️ 疑似假无损 ({specs})", "高频稍有不足(可能是自然衰减)。"
            
    # 默认 44.1kHz 逻辑
    if cutoff_freq >= 19500:
        return f"✅ 真无损 ({specs})", "高频延伸正常。"
    elif 18000 <= cutoff_freq < 19500:
        return f"⚠️ 疑似假无损 ({specs})", "高频在18k-19.5k被切断(可能是舒缓乐曲自然衰减)。"
    elif 15000 <= cutoff_freq < 18000:
        return f"❌ 严重假无损 ({specs})", "高频在15k-18k之间就被明显切断。"
    else:
        return f"🚨 极差音质 ({specs})", "高频严重缺失。"

def analyze_single_file(file_path, idx, total, output_dir, fast_mode=False):
    """处理单个文件的并发任务"""
    filename = file_path.name
    base_name = file_path.stem
    print(f"[{idx}/{total}] 正在处理: {filename}")

    nyquist = get_audio_nyquist(file_path)
    bit_depth, sample_rate = get_audio_specs(file_path)
    
    raw_img = output_dir / f"temp_raw_{idx}.png"
    temp_view_img = output_dir / f"temp_view_{idx}.png"

    result_dict = {"file": filename, "cutoff": None, "verdict": "处理失败", "specs": f"{bit_depth}bit/{sample_rate/1000:g}kHz", "view_img": None}

    try:
        # 并发执行这两条命令也可以，但为了简单，这里直接顺序执行
        subprocess.run(["sox", str(file_path), "-n", "spectrogram", "-r", "-Y", "512", "-o", str(raw_img)], 
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, **SUBPROCESS_KWARGS)
        
        if not fast_mode:
            subprocess.run(["sox", str(file_path), "-n", "spectrogram", "-t", base_name, "-o", str(temp_view_img)], 
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, **SUBPROCESS_KWARGS)

        if raw_img.exists():
            cutoff = analyze_spectrogram(raw_img, nyquist)
            raw_img.unlink() # 清理纯净图
            
            if cutoff is not None:
                verdict, _ = judge_lossless(cutoff, bit_depth, sample_rate)
                result_dict["cutoff"] = cutoff
                result_dict["verdict"] = verdict
                print(f"    -> {filename} 截止频率: {cutoff} Hz | 结论: {verdict}")
            
        if temp_view_img.exists():
            result_dict["view_img"] = temp_view_img

    except Exception as e:
        print(f"    -> {filename} 处理异常: {e}")

    return result_dict


def process_album(album_dir, output_dir=None, fast_mode=False):
    if not check_sox_installed():
        print("错误: 系统未检测到 'sox' 命令。")
        return

    album_path = Path(album_dir)
    if not output_dir:
        output_dir = album_path / "Spectrograms"
    else:
        output_dir = Path(output_dir)
        
    output_dir.mkdir(parents=True, exist_ok=True)

    # 优雅的文件扫描
    audio_files = []
    for ext in ('.flac', '.wav', '.ape', '.alac', '.m4a'):
        # rglob('*') 配合 lower() 检查，可以递归搜索所有子文件夹并且忽略大小写
        audio_files.extend([f for f in album_path.rglob('*') if f.is_file() and f.suffix.lower() == ext])

    if not audio_files:
        print("未在指定目录中找到无损音频文件。")
        return

    # 按文件名排序
    audio_files.sort(key=lambda x: x.name)
    total_files = len(audio_files)

    print(f"找到 {total_files} 个音频文件，开始并发分析并生成合并长图...")
    print("-" * 80)
    
    results = []
    view_images_to_stitch = []

    # 引入并发加速
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(analyze_single_file, f, idx+1, total_files, output_dir, fast_mode): f for idx, f in enumerate(audio_files)}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results.append(res)

    # 为了保证合并时长图顺序正确，需要对结果进行排序
    results.sort(key=lambda x: x["file"])
    for r in results:
        if r["view_img"]:
            view_images_to_stitch.append(r["view_img"])

    # 拼接图
    if view_images_to_stitch:
        if len(view_images_to_stitch) > 50:
            print(f"\n⚠️ 警告: 音频文件数量 ({len(view_images_to_stitch)}) 较多，合并的长图可能会非常大，请耐心等待...")
        else:
            print("\n正在将所有单曲频谱图拼接为一张整专辑长图，请稍候...")
            
        try:
            images = [Image.open(img_path) for img_path in view_images_to_stitch]
            
            widths, heights = zip(*(i.size for i in images))
            total_height = sum(heights)
            max_width = max(widths)

            stitched_img = Image.new('RGB', (max_width, total_height), color=(255, 255, 255))

            y_offset = 0
            for im in images:
                stitched_img.paste(im, (0, y_offset))
                y_offset += im.size[1]
                im.close()

            final_img_path = output_dir / "整张专辑频谱合并长图.png"
            stitched_img.save(final_img_path)
            print(f"✅ 拼接成功！已保存至: {final_img_path}")

            for img_path in view_images_to_stitch:
                img_path.unlink()

        except Exception as e:
            print(f"❌ 拼接长图失败: {e}")

    # 输出报告
    print("\n" + "="*35 + " 专辑无损检测报告 " + "="*35)
    
    # 汇总结论，如果都是真无损则返回 True
    all_lossless = True
    for r in results:
        cutoff_str = f"{r['cutoff']:.1f} Hz" if r['cutoff'] is not None else "N/A"
        print(f"{r['file'][:38]:<40} | {cutoff_str:<10} | {r['verdict']}")
        if "假" in r['verdict'] or "差" in r['verdict'] or "失败" in r['verdict']:
            all_lossless = False
            
    print("=" * 88)
    return all_lossless


import customtkinter as ctk
from i18n import _

class RedirectText:
    def __init__(self, text_ctrl):
        self.output = text_ctrl

    def write(self, string):
        try:
            yview = self.output.yview()
            is_at_bottom = yview[1] >= 0.99
            
            self.output.insert(tk.END, string)
            
            if is_at_bottom:
                self.output.see(tk.END)
        except Exception:
            pass

    def flush(self):
        pass

class LosslessCheckerGUI:
    def __init__(self, parent):
        self.parent = parent
        
        self.input_dir_var = tk.StringVar()
        self.fast_mode_var = tk.BooleanVar(value=False)

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

        ctk.CTkCheckBox(config_frame, text="快速模式 (仅检查不生成可视图形)", variable=self.fast_mode_var).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=10, padx=5)

        btn_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.start_btn = ctk.CTkButton(btn_frame, text=_("start_check"), command=self.start_process, fg_color="#28a745", hover_color="#218838")
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
        if not self.input_dir_var.get():
            tk.messagebox.showwarning("提示", "请选择要检测的专辑文件夹！")
            return
            
        self.start_btn.configure(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)
        
        threading.Thread(target=self.run_thread, daemon=True).start()

    def run_thread(self):
        old_stdout = sys.stdout
        sys.stdout = RedirectText(self.log_text)
        try:
            mode_str = " (快速模式)" if self.fast_mode_var.get() else ""
            print(f">>> 正在启动真假无损/Hi-Res 检测{mode_str}...\n")
            process_album(self.input_dir_var.get(), fast_mode=self.fast_mode_var.get())
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