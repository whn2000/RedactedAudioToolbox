import os
import subprocess
import glob

def generate_dirty_chain(input_dir: str, output_dir: str):
    """
    基于给定的真无损/高解析度音频文件夹，自动化生成各种脏链测试集。
    依赖系统安装了 ffmpeg 和 sox。
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    input_files = glob.glob(os.path.join(input_dir, "*.flac"))
    if not input_files:
        print(f"No FLAC files found in {input_dir}")
        return
        
    for f in input_files:
        basename = os.path.basename(f)
        name, _ = os.path.splitext(basename)
        
        # 1. Fake Lossless: FLAC -> MP3 320k -> FLAC
        mp3_tmp = os.path.join(output_dir, f"{name}_tmp.mp3")
        fake_lossless_out = os.path.join(output_dir, f"{name}_fake_lossless.flac")
        
        # Encode to MP3
        subprocess.run(["ffmpeg", "-y", "-i", f, "-b:a", "320k", mp3_tmp], capture_output=True)
        # Decode back to FLAC
        subprocess.run(["ffmpeg", "-y", "-i", mp3_tmp, fake_lossless_out], capture_output=True)
        os.remove(mp3_tmp)
        
        # 2. Fake Hi-Res: FLAC(Assume 24/96) -> 16/44.1 -> 24/96
        cd_tmp = os.path.join(output_dir, f"{name}_tmp_cd.flac")
        fake_hires_out = os.path.join(output_dir, f"{name}_fake_hires.flac")
        
        # Downsample to CD quality
        subprocess.run(["ffmpeg", "-y", "-i", f, "-ar", "44100", "-sample_fmt", "s16", cd_tmp], capture_output=True)
        # Upsample back to Hi-Res
        subprocess.run(["ffmpeg", "-y", "-i", cd_tmp, "-ar", "96000", "-sample_fmt", "s32", fake_hires_out], capture_output=True)
        os.remove(cd_tmp)
        
        # 3. Copy True file for control
        subprocess.run(["cp", f, os.path.join(output_dir, f"{name}_true.flac")], capture_output=True)
        
    print("Dirty chain dataset generation complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", help="Dir with True FLACs")
    parser.add_argument("output_dir", help="Output dir for dataset")
    args = parser.parse_args()
    generate_dirty_chain(args.input_dir, args.output_dir)
