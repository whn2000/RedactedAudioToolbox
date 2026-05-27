import argparse
import json
import os
import sys
import librosa
import numpy as np

# 将当前目录加入 path 解决 import 问题
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aafs.extractors.brickwall import detect_brickwall
from aafs.extractors.spectral_holes import detect_spectral_holes
from aafs.extractors.bit_depth import detect_fake_bit_depth_via_lsb
from aafs.extractors.provenance import detect_tape_hiss_or_analog_noise
from aafs.inference.scorer import SimpleScorer

def analyze_audio(file_path: str):
    if not os.path.exists(file_path):
        print(json.dumps({"error": f"File not found: {file_path}"}))
        return
        
    try:
        # Load audio (mono for simplicity in MVP)
        y, sr = librosa.load(file_path, sr=None, mono=True)
        
        # Determine nominal characteristics
        # Since we use librosa, it normalizes to float32. We assume nominal 24bit for hi-res
        # In a real app we would use soundfile/mutagen to parse metadata
        nominal_sr = sr
        nominal_bit_depth = 24 if sr > 48000 else 16
        
        # STFT Compute
        S_complex = librosa.stft(y, n_fft=2048, hop_length=512, window='blackmanharris')
        S_mag = np.abs(S_complex)
        S_db = librosa.amplitude_to_db(S_mag, ref=np.max)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        
        evidences = []
        
        # 1. Brickwall (if hi-res)
        if sr > 48000:
            ev_bw = detect_brickwall(S_db, freqs, nyquist_check=22050)
            if ev_bw: evidences.append(ev_bw)
            ev_bw2 = detect_brickwall(S_db, freqs, nyquist_check=24000)
            if ev_bw2: evidences.append(ev_bw2)
            
        # 2. Spectral Holes
        ev_holes = detect_spectral_holes(S_mag, freqs, start_freq=16000.0)
        if ev_holes: evidences.append(ev_holes)
            
        # 3. Bit depth LSB
        ev_lsb = detect_fake_bit_depth_via_lsb(y, declared_bit_depth=nominal_bit_depth)
        if ev_lsb: evidences.append(ev_lsb)
            
        # 4. Provenance
        ev_prov = detect_tape_hiss_or_analog_noise(S_mag, freqs)
        if ev_prov: evidences.append(ev_prov)
            
        # Score
        scorer = SimpleScorer()
        result = scorer.evaluate(evidences)
        
        result["file"] = os.path.basename(file_path)
        result["metadata"] = {"samplerate": sr, "assumed_bitdepth": nominal_bit_depth}
        
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AAFS: Audio Authenticity Forensics System")
    parser.add_argument("file", help="Path to the audio file")
    args = parser.parse_args()
    
    analyze_audio(args.file)
