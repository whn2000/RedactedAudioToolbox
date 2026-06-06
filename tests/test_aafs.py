import pytest
import numpy as np
from aafs.core.evidence import Evidence
from aafs.inference.scorer import SimpleScorer
from aafs.inference.suppressor import apply_provenance_suppression
from aafs.extractors.mqa import _check_mqa_syncword, MAGIC

def test_evidence_to_dict():
    ev = Evidence(
        name="test_ev",
        value=1.5,
        confidence=0.8,
        category="lossy_trace",
        provenance_sensitive=False,
        description="Test description"
    )
    d = ev.to_dict()
    assert d["name"] == "test_ev"
    assert d["value"] == 1.5
    assert d["confidence"] == 0.8
    assert d["category"] == "lossy_trace"
    assert d["description"] == "Test description"

def test_suppressor():
    # 1. Without analog noise, no suppression
    ev1 = Evidence("brickwall", 22000, 0.9, "upsample_trace", True, "Brickwall filter")
    evidences = [ev1]
    res = apply_provenance_suppression(evidences)
    assert res[0].confidence == 0.9
    
    # 2. With analog noise, sensitive evidence is suppressed
    ev_noise = Evidence("analog_tape_hiss", 1.0, 0.8, "provenance", False, "Analog tape hiss")
    evidences2 = [ev1, ev_noise]
    
    # Reload ev1 to reset state
    ev1 = Evidence("brickwall", 22000, 0.9, "upsample_trace", True, "Brickwall filter")
    evidences2 = [ev1, ev_noise]
    res2 = apply_provenance_suppression(evidences2)
    assert res2[0].confidence < 0.9
    assert "Suppressed" in res2[0].description

def test_scorer_genuine():
    scorer = SimpleScorer()
    ev = Evidence("clean", 0.0, 0.1, "lossy_trace", False, "Clean")
    res = scorer.evaluate([ev])
    assert res["classification"] == "genuine"

def test_scorer_fake_lossless():
    scorer = SimpleScorer()
    ev = Evidence("lossy", 0.0, 0.8, "lossy_trace", False, "Lossy trace")
    res = scorer.evaluate([ev])
    assert res["classification"] == "fake_lossless (transcoded)"

def test_scorer_fake_hi_res():
    scorer = SimpleScorer()
    ev = Evidence("upsample", 0.0, 0.8, "upsample_trace", False, "Upsample trace")
    res = scorer.evaluate([ev])
    assert res["classification"] == "fake_hi_res (upsampled / padded)"

def test_scorer_mqa():
    scorer = SimpleScorer()
    ev = Evidence("mqa_detected", 1.0, 1.0, "lossy_trace", False, "MQA detected")
    res = scorer.evaluate([ev])
    assert res["classification"] == "MQA encoded (lossy)"

def test_mqa_syncword_detection():
    # Mock left/right channels
    # Set up random channels
    np.random.seed(42)
    left = np.random.randint(-10000, 10000, size=1000, dtype=np.int32)
    right = np.random.randint(-10000, 10000, size=1000, dtype=np.int32)
    
    # Should not match MQA
    assert not _check_mqa_syncword(left, right)
    
    # Embed magic syncword in bits 16-23 of left ^ right
    # magic length is 36 bits
    magic_len = len(MAGIC)
    # Pick a bit position, say 18
    bit_pos = 18
    
    # Inject pattern
    for i in range(magic_len):
        target_bit = MAGIC[i]
        # Calculate required xor bit
        # left ^ right = (left ^ right) but set bit_pos to target_bit
        xor_val = left[i] ^ right[i]
        # clear bit
        xor_val &= ~(1 << bit_pos)
        # set bit
        xor_val |= (int(target_bit) << bit_pos)
        # adjust right to achieve this xor
        right[i] = left[i] ^ xor_val
        
    assert _check_mqa_syncword(left, right)

import os
from unittest.mock import MagicMock, patch
from core.log_checker import parse_log_file, verify_album_against_log
from core.transmission_client import TransmissionClient

def test_log_checker_parse_eac():
    eac_log = """Exact Audio Copy V1.6 from 23. October 2020
EAC extraction logfile from 15. March 2023
Radiohead / OK Computer
Read mode                 : Secure
Defeat audio cache                  : Yes
Make use of C2 pointers             : No
TOC of the extracted CD
     Track |   Start  |  Length  | Start sector | End sector
    ---------------------------------------------------------
        1  |  0:00.00 |  4:44.26 |         0    |    21325
Track  1
     Filename D:\\Music\\01 Airbag.wav
     Pre-gap length  0:00:02.00
     Test CRC 3A12B456
     Copy CRC 3A12B456
     Copy OK
==== Log checksum ABCDEF1234567890ABCDEF1234567890ABCDEF12 ====
"""
    temp_log_path = "tests/temp_test_eac.log"
    with open(temp_log_path, "w", encoding="utf-8") as f:
        f.write(eac_log)
        
    try:
        res = parse_log_file(temp_log_path)
        assert res is not None
        assert res.log_type == "EAC"
        assert res.score == 100
        assert res.checksum_ok is True
        assert len(res.tracks) == 1
        assert res.tracks[0]["track"] == 1
        assert res.tracks[0]["log_crc"] == "3A12B456"
    finally:
        if os.path.exists(temp_log_path):
            os.remove(temp_log_path)

def test_log_checker_read_mode_penalty():
    eac_log = """Exact Audio Copy V1.6
Read mode                 : Burst
Defeat audio cache                  : No
Timing problem
Track  1
     Copy CRC 3A12B456
"""
    temp_log_path = "tests/temp_test_penalty.log"
    with open(temp_log_path, "w", encoding="utf-8") as f:
        f.write(eac_log)
        
    try:
        res = parse_log_file(temp_log_path)
        assert res is not None
        assert res.score == 25
        assert len(res.issues) == 4
    finally:
        if os.path.exists(temp_log_path):
            os.remove(temp_log_path)

@patch('core.transmission_client.Client')
def test_transmission_client_add_torrent(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    client = TransmissionClient(host="127.0.0.1", port=9091)
    assert client.client is not None
    
    temp_torrent = "tests/temp_test.torrent"
    with open(temp_torrent, "wb") as f:
        f.write(b"d8:announce12:http://test/ee")
        
    try:
        res = client.add_torrent(temp_torrent, "/save/path")
        assert res is True
        mock_client.add_torrent.assert_called_once_with(b"d8:announce12:http://test/ee", download_dir="/save/path")
    finally:
        if os.path.exists(temp_torrent):
            os.remove(temp_torrent)
