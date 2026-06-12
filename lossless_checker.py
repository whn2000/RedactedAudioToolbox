import os
import sys
import subprocess
from pathlib import Path
from PIL import Image
import concurrent.futures
import threading
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, scrolledtext
except (ImportError, ModuleNotFoundError):
    tk = None

# AAFS Imports
import sys
from pathlib import Path
current_dir = Path(__file__).parent.absolute()
aafs_dir = current_dir / "aafs"
if str(aafs_dir) not in sys.path:
    sys.path.insert(0, str(aafs_dir))

import numpy as np
import librosa
from aafs.extractors.brickwall import detect_brickwall
from aafs.extractors.spectral_holes import detect_spectral_holes
from aafs.extractors.bit_depth import detect_fake_bit_depth_via_lsb
from aafs.extractors.provenance import detect_tape_hiss_or_analog_noise
from aafs.extractors.mqa import detect_mqa_file
from aafs.extractors.wasted_bits import detect_wasted_bits
from aafs.inference.scorer import SimpleScorer

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



from i18n import _, CURRENT_LANG

def translate_aafs_reason(reason_str):
    if CURRENT_LANG != "zh_CN":
        return reason_str
    
    reason_str = reason_str.replace("fake_lossless (transcoded)", "假无损 (由低音质转码)")
    reason_str = reason_str.replace("fake_hi_res (upsampled)", "假高解析 (由低采样率拉升)")
    reason_str = reason_str.replace("fake_hi_res (padded_bitdepth)", "假高解析 (位深填充)")
    reason_str = reason_str.replace("fake_hi_res (upsampled / padded)", "假高解析 (由低采样率拉升/位深填充)")
    reason_str = reason_str.replace("MQA encoded (lossy)", "MQA 编码 (有损)")
    reason_str = reason_str.replace("genuine", "真无损/高解析")
    
    if "Brickwall filter detected with cutoff around" in reason_str:
        reason_str = reason_str.replace("Brickwall filter detected with cutoff around", "检测到截止频率在")
        reason_str = reason_str.replace("Hz. Suspected upsample from lower sample rate.", "Hz 附近的砖墙滤波。疑似由低采样率拉升。")
        
    if "are quantization dead zones in high-energy frames." in reason_str:
        reason_str = reason_str.replace("of high-frequency bins (> ", "的高频区(> ")
        reason_str = reason_str.replace("kHz) are quantization dead zones in high-energy frames.", "kHz) 为量化死区。")
        reason_str = reason_str.replace("Indicative of psychoacoustic lossy compression.", "这是心理声学有损压缩的显著特征。")
        
    if "LSB autocorrelation energy is" in reason_str:
        reason_str = reason_str.replace("LSB autocorrelation energy is", "LSB 自相关能量为")
        reason_str = reason_str.replace(", indicating synthetic TPDF dither rather than acoustic noise floor.", "，表明其为人工添加的 TPDF 抖动而非原声底噪。")
        reason_str = reason_str.replace("Effective bit-depth is", "实际有效位深约为")
        
    if "zero-padding was detected" in reason_str:
        reason_str = reason_str.replace("The file claims to be 24-bit, but 16-bit to 24-bit zero-padding was detected. Effective bit-depth is 16.", "文件声称为 24-bit，但检测到了 16-bit 到 24-bit 的补零填充。实际有效位深为 16。")
        
    return reason_str

def analyze_single_file(file_path, idx, total, output_dir, fast_mode=False):
    """处理单个文件的并发任务 (AAFS 集成版)"""
    filename = file_path.name
    base_name = file_path.stem

    nyquist = get_audio_nyquist(file_path)
    bit_depth, sample_rate = get_audio_specs(file_path)
    
    temp_view_img = output_dir / f"temp_view_{idx}.png"

    result_dict = {"file": filename, "verdict": "处理失败", "specs": f"{bit_depth}bit/{sample_rate/1000:g}kHz", "view_img": None, "is_fake": True}

    try:
        # 保留 SoX 生成频谱图的功能（为了最后拼长图）
        if not fast_mode:
            subprocess.run(["sox", str(file_path), "-n", "spectrogram", "-t", base_name, "-o", str(temp_view_img)], 
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, **SUBPROCESS_KWARGS)

        # 启动 AAFS 法医级核心分析
        y, sr = librosa.load(file_path, sr=None, mono=True)
        S_complex = librosa.stft(y, n_fft=2048, hop_length=512, window='blackmanharris')
        S_mag = np.abs(S_complex)
        S_db = librosa.amplitude_to_db(S_mag, ref=np.max)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        
        evidences = []
        
        # 1. Brickwall (如果名义上是 Hi-Res)
        is_hi_res = (sr >= 48000) or (bit_depth >= 24)
        if is_hi_res or sr == 48000:
            ev_bw = detect_brickwall(S_db, freqs, nyquist_check=22050)
            if ev_bw: evidences.append(ev_bw)
            if sr > 48000:
                ev_bw2 = detect_brickwall(S_db, freqs, nyquist_check=24000)
                if ev_bw2: evidences.append(ev_bw2)
            
        # 2. Spectral Holes
        ev_holes = detect_spectral_holes(S_mag, freqs, start_freq=16000.0)
        if ev_holes: evidences.append(ev_holes)
            
        # 3. Bit depth LSB
        if bit_depth > 16:
            ev_lsb = detect_fake_bit_depth_via_lsb(y, declared_bit_depth=bit_depth)
            if ev_lsb: evidences.append(ev_lsb)
            
        # 4. Provenance
        ev_prov = detect_tape_hiss_or_analog_noise(S_mag, freqs)
        if ev_prov: evidences.append(ev_prov)

        # 5. MQA Detection
        ev_mqa = detect_mqa_file(str(file_path))
        if ev_mqa: evidences.append(ev_mqa)

        # 6. Wasted Bits Upconvert Detection
        if bit_depth > 16:
            ev_wasted = detect_wasted_bits(str(file_path), declared_bit_depth=bit_depth)
            if ev_wasted: evidences.append(ev_wasted)
            
        # 评分与降权
        scorer = SimpleScorer()
        score_res = scorer.evaluate(evidences)
        
        verdict = score_res["classification"]
        reasons = score_res["summary_reasons"]
        
        if verdict == "genuine":
            result_dict["verdict"] = _("log_aafs_genuine")
            result_dict["is_fake"] = False
        else:
            translated_reasons = [translate_aafs_reason(r) for r in reasons]
            reason_str = " | ".join(translated_reasons)
            translated_verdict = translate_aafs_reason(verdict)
            reason_format = _("log_aafs_fake_reason").format(reason_str=reason_str)
            result_dict["verdict"] = f"❌ {translated_verdict}{reason_format}"
            result_dict["is_fake"] = True
            
        if temp_view_img.exists():
            result_dict["view_img"] = temp_view_img

    except Exception as e:
        result_dict["verdict"] = _("log_aafs_exception").format(e=e)

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

    print(_("log_found_files_aafs").format(total_files=total_files))
    print("-" * 80)
    
    results = []
    view_images_to_stitch = []
    completed = 0

    # 引入并发加速
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(analyze_single_file, f, idx+1, total_files, output_dir, fast_mode): f for idx, f in enumerate(audio_files)}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results.append(res)
            completed += 1
            print(f"[{completed}/{total_files}] {res['file']}\n    => {res['verdict']}\n")

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
        print(f"{r['file'][:38]:<40} | {r['verdict']}")
        if r["is_fake"]:
            all_lossless = False
            
    print("=" * 88)

    # 查找并校验 Ripping Log
    log_files = list(album_path.glob("*.log"))
    if log_files:
        print("\n" + "="*35 + " Ripping Log 校验报告 " + "="*35)
        from core.log_checker import parse_log_file, verify_album_against_log
        for log_f in log_files:
            print(f"📄 正在校验日志: {log_f.name}")
            log_res = parse_log_file(str(log_f))
            if not log_res:
                print("  ❌ 无法解析日志文件。")
                continue
                
            print(f"  日志类型: {log_res.log_type}")
            print(f"  日志得分: {log_res.score}/100")
            print(f"  Checksum: {'✅ OK' if log_res.checksum_ok else '❌ 损坏/缺失'}")
            if log_res.issues:
                print("  存在的问题:")
                for issue in log_res.issues:
                    print(f"    - {issue}")
                    
            print("  逐轨 CRC 比对:")
            verif_details = verify_album_against_log(str(album_path), log_res)
            all_match = True
            for det in verif_details:
                status_str = "✅ 匹配" if det["matches"] else f"❌ 不匹配 (Log: {det['log_crc']} vs Calc: {det['calculated_crc']})"
                if not det["matches"]:
                    all_match = False
                print(f"    音轨 {det['track']}: {det['file'][:30]} => {status_str}")
                
            if all_match and log_res.checksum_ok:
                print("  🎉 日志校验成功！所有音轨的 CRC 校验码与抓取日志完美匹配。")
            else:
                print("  ⚠️ 警告: 存在 CRC 不匹配或日志篡改风险，请务必人工核对！")
        print("=" * 88)
        
    return all_lossless


try:
    import customtkinter as ctk
    from gui.widgets import RedirectText
except (ImportError, ModuleNotFoundError):
    ctk = None
    RedirectText = None

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
            mode_str = (" (Fast Mode)" if CURRENT_LANG != "zh_CN" else " (快速模式)") if self.fast_mode_var.get() else ""
            print(_("log_start_aafs_check").format(mode_str=mode_str))
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