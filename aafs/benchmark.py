import os
import glob
from cli import analyze_audio
import json
import contextlib
import io

def run_benchmark(dataset_dir: str):
    """
    法医级系统核心要求： FPR @ 0.001 时的 TPR。
    运行前需通过 dirty_chain_gen.py 生成好数据集。
    """
    files = glob.glob(os.path.join(dataset_dir, "*.flac"))
    
    true_positives = 0  # 正确检出假无损
    false_positives = 0 # 误杀真无损
    true_negatives = 0  # 正确放过真无损
    false_negatives = 0 # 漏掉假无损
    
    for f in files:
        basename = os.path.basename(f)
        
        # 捕获 stdout
        f_stdout = io.StringIO()
        with contextlib.redirect_stdout(f_stdout):
            analyze_audio(f)
            
        output = f_stdout.getvalue()
        try:
            result = json.loads(output)
        except json.JSONDecodeError:
            print(f"Error parsing {basename}")
            continue
            
        predicted_fake = result.get("classification") != "genuine"
        is_actually_fake = "fake" in basename
        
        if is_actually_fake and predicted_fake:
            true_positives += 1
        elif is_actually_fake and not predicted_fake:
            false_negatives += 1
        elif not is_actually_fake and not predicted_fake:
            true_negatives += 1
        elif not is_actually_fake and predicted_fake:
            false_positives += 1
            
    print("=== AAFS Forensic Benchmark Results ===")
    total_fakes = true_positives + false_negatives
    total_trues = false_positives + true_negatives
    
    tpr = true_positives / total_fakes if total_fakes > 0 else 0
    fpr = false_positives / total_trues if total_trues > 0 else 0
    
    print(f"Total True Files: {total_trues}")
    print(f"Total Fake Files: {total_fakes}")
    print(f"TPR (Recall - Caught Fakes): {tpr*100:.2f}%")
    print(f"FPR (False Alarms - Killed Trues): {fpr*100:.2f}%")
    
    if fpr > 0.001:
        print("WARNING: System does not meet forensic FPR requirements (< 0.1%). Tuning required.")
    else:
        print("SUCCESS: System meets forensic FPR requirements.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_dir", help="Directory containing the benchmark dataset")
    args = parser.parse_args()
    run_benchmark(args.dataset_dir)
