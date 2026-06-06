import os
import re
import zlib
import soundfile as sf
from typing import List, Dict, Any, Optional

def calculate_pcm_crc32(filepath: str) -> Optional[str]:
    """
    Calculate the CRC32 of the raw PCM audio data in a FLAC/WAV file.
    Decodes the file to 16-bit signed PCM (little-endian interleaved) to match EAC/XLD.
    """
    if not os.path.exists(filepath):
        return None
    try:
        # Read file as 16-bit integer PCM
        data, samplerate = sf.read(filepath, dtype='int16')
        # data is shape (N, channels). tobytes() yields C-contiguous interleaved PCM bytes
        pcm_bytes = data.tobytes()
        crc = zlib.crc32(pcm_bytes) & 0xFFFFFFFF
        return format(crc, '08X')
    except Exception:
        return None

class LogVerificationResult:
    def __init__(self, log_type: str):
        self.log_type = log_type
        self.score = 100
        self.checksum_ok = True
        self.tracks: List[Dict[str, Any]] = []
        self.issues: List[str] = []

def parse_log_file(log_path: str) -> Optional[LogVerificationResult]:
    """
    Parse an EAC or XLD log file to extract track CRCs and check integrity.
    """
    if not os.path.exists(log_path):
        return None

    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_text = f.read()
    except Exception:
        return None

    # Detect log type
    if "Exact Audio Copy" in log_text or "EAC extraction logfile" in log_text:
        log_type = "EAC"
    elif "X Lossless Decoder" in log_text or "XLD extraction logfile" in log_text:
        log_type = "XLD"
    else:
        # Fallback
        log_type = "Unknown"

    result = LogVerificationResult(log_type)

    # 1. Check checksum line (simple text-based heuristic)
    if log_type == "EAC":
        if "Log checksum" in log_text:
            if "OK" not in log_text and "==== Log checksum" not in log_text:
                result.checksum_ok = False
                result.issues.append("EAC Log checksum missing or invalid.")
                result.score -= 15
        else:
            result.checksum_ok = False
            result.issues.append("No log checksum found.")
            result.score -= 15
    elif log_type == "XLD":
        if "-----BEGIN EXTERNAL SIGNATURE-----" not in log_text:
            # XLD logs usually have a signature, but sometimes not if disabled
            pass

    # 2. Check for read/timing/cache issues
    insecure_regexes = [
        (r"Read mode\s*:\s*Burst", "Burst read mode used instead of Secure", 20),
        (r"Defeat audio cache\s*:\s*No", "Audio cache not defeated", 10),
        (r"Make use of C2 pointers\s*:\s*Yes", "C2 pointers utilized (insecure)", 10),
        (r"Timing problem", "Timing problem detected during rip", 30),
        (r"Suspicious position", "Suspicious position reported", 20),
        (r"Read error", "Read errors occurred during rip", 30),
        (r"Damaged sector", "Damaged sectors encountered", 30),
    ]

    for pattern, desc, penalty in insecure_regexes:
        if re.search(pattern, log_text, re.IGNORECASE):
            result.issues.append(desc)
            result.score -= penalty

    result.score = max(0, result.score)

    # 3. Extract track CRCs
    # EAC track logic
    if log_type == "EAC":
        # Split log by "Track" sections
        tracks_data = re.split(r'Track\s+(\d+)', log_text)
        if len(tracks_data) > 1:
            for idx in range(1, len(tracks_data), 2):
                track_num = int(tracks_data[idx])
                track_content = tracks_data[idx+1]
                
                # Search for Test/Copy CRC
                test_match = re.search(r'Test CRC\s+([0-9A-F]{8})', track_content, re.IGNORECASE)
                copy_match = re.search(r'Copy CRC\s+([0-9A-F]{8})', track_content, re.IGNORECASE)
                
                test_crc = test_match.group(1).upper() if test_match else None
                copy_crc = copy_match.group(1).upper() if copy_match else None
                
                if copy_crc or test_crc:
                    result.tracks.append({
                        "track": track_num,
                        "log_crc": copy_crc or test_crc,
                        "test_crc": test_crc,
                        "copy_crc": copy_crc
                    })
    # XLD track logic
    elif log_type == "XLD":
        # XLD lists tracks as "Track 01", etc.
        tracks_data = re.split(r'Track\s+(\d+)', log_text)
        if len(tracks_data) > 1:
            for idx in range(1, len(tracks_data), 2):
                track_num = int(tracks_data[idx])
                track_content = tracks_data[idx+1]
                
                # Search for CRC32 hash
                crc_match = re.search(r'CRC32 hash\s*(?:\(test run\))?\s*:\s*([0-9A-F]{8})', track_content, re.IGNORECASE)
                copy_match = re.search(r'CRC32 hash\s*:\s*([0-9A-F]{8})', track_content, re.IGNORECASE)
                
                test_crc = crc_match.group(1).upper() if crc_match else None
                copy_crc = copy_match.group(1).upper() if copy_match else None
                
                if copy_crc or test_crc:
                    result.tracks.append({
                        "track": track_num,
                        "log_crc": copy_crc or test_crc,
                        "test_crc": test_crc,
                        "copy_crc": copy_crc
                    })

    # Sort tracks by track number
    result.tracks.sort(key=lambda x: x["track"])
    return result

def verify_album_against_log(album_dir: str, log_result: LogVerificationResult) -> List[Dict[str, Any]]:
    """
    Match files in the album directory to the parsed log track list,
    calculate their CRCs, and compare.
    """
    # Find all audio files (FLAC/WAV/etc.)
    audio_files = []
    for root, _, files in os.walk(album_dir):
        for f in files:
            if f.lower().endswith(('.flac', '.wav')):
                audio_files.append(os.path.join(root, f))
                
    # Sort files to match log track order
    audio_files.sort(key=lambda x: os.path.basename(x))
    
    verification_details = []
    
    # Verify 1-to-1 matching
    for idx, track_info in enumerate(log_result.tracks):
        if idx >= len(audio_files):
            verification_details.append({
                "track": track_info["track"],
                "file": "Missing File",
                "log_crc": track_info["log_crc"],
                "calculated_crc": None,
                "matches": False
            })
            continue
            
        filepath = audio_files[idx]
        filename = os.path.basename(filepath)
        calc_crc = calculate_pcm_crc32(filepath)
        
        matches = (calc_crc == track_info["log_crc"])
        
        verification_details.append({
            "track": track_info["track"],
            "file": filename,
            "log_crc": track_info["log_crc"],
            "calculated_crc": calc_crc,
            "matches": matches
        })
        
    return verification_details
