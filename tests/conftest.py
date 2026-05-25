"""
Shared test fixtures for the quality audit test suite.

Provides pre-built AudioContext, AudioFeatures, LogAnalysis, and
TorrentInfo instances for use across all test modules.
"""

from __future__ import annotations

import pytest

from quality.models import (
    AudioContext,
    AudioFeatures,
    LogAnalysis,
    RiskReport,
    RuleResult,
    TorrentInfo,
)


# ---------------------------------------------------------------------------
# AudioFeatures fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_features() -> AudioFeatures:
    """Features representing a clean, genuine lossless release."""
    return AudioFeatures(
        cutoff_freq=22000.0,
        hf_energy_ratio=0.15,
        spectrogram_gap_detected=False,
        channel_similarity=0.45,
        fake_hires_score=0.0,
        mp3_signature_score=0.0,
        hf_rolloff_smoothness=0.2,
        avg_bitrate_kbps=950.0,
    )


@pytest.fixture
def suspicious_features() -> AudioFeatures:
    """Features with moderate quality concerns."""
    return AudioFeatures(
        cutoff_freq=19500.0,
        hf_energy_ratio=0.08,
        spectrogram_gap_detected=False,
        channel_similarity=0.65,
        fake_hires_score=0.3,
        mp3_signature_score=0.25,
        hf_rolloff_smoothness=0.55,
        avg_bitrate_kbps=800.0,
    )


@pytest.fixture
def transcode_features() -> AudioFeatures:
    """Features strongly indicating a lossy transcode."""
    return AudioFeatures(
        cutoff_freq=16000.0,
        hf_energy_ratio=0.02,
        spectrogram_gap_detected=True,
        channel_similarity=0.50,
        fake_hires_score=0.0,
        mp3_signature_score=0.8,
        hf_rolloff_smoothness=0.92,
        avg_bitrate_kbps=700.0,
    )


@pytest.fixture
def fake_hires_features() -> AudioFeatures:
    """Features indicating fake Hi-Res (upsampled)."""
    return AudioFeatures(
        cutoff_freq=21000.0,
        hf_energy_ratio=0.03,
        spectrogram_gap_detected=False,
        channel_similarity=0.40,
        fake_hires_score=0.8,
        mp3_signature_score=0.0,
        hf_rolloff_smoothness=0.3,
        avg_bitrate_kbps=3200.0,
    )


# ---------------------------------------------------------------------------
# AudioContext fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_context(clean_features: AudioFeatures) -> AudioContext:
    """AudioContext for a clean CD rip with perfect log."""
    return AudioContext(
        format="FLAC",
        source="CD",
        bitrate="Lossless",
        bit_depth=16,
        sample_rate=44100,
        has_log=True,
        log_analysis=LogAnalysis(
            log_type="EAC",
            score=100,
            confidence="HIGH",
            flags={"accuraterip_ok": True, "secure_mode": True, "test_copy_crc_match": True},
        ),
        features=clean_features,
    )


@pytest.fixture
def web_context(clean_features: AudioFeatures) -> AudioContext:
    """AudioContext for a WEB source release."""
    return AudioContext(
        format="FLAC",
        source="WEB",
        bitrate="Lossless",
        bit_depth=16,
        sample_rate=44100,
        has_log=False,
        features=clean_features,
    )


@pytest.fixture
def transcode_context(transcode_features: AudioFeatures) -> AudioContext:
    """AudioContext for a likely MP3 transcode."""
    return AudioContext(
        format="FLAC",
        source="CD",
        bitrate="Lossless",
        bit_depth=16,
        sample_rate=44100,
        has_log=False,
        features=transcode_features,
    )


@pytest.fixture
def hires_context(fake_hires_features: AudioFeatures) -> AudioContext:
    """AudioContext for a fake Hi-Res release."""
    return AudioContext(
        format="FLAC",
        source="WEB",
        bitrate="24bit Lossless",
        bit_depth=24,
        sample_rate=96000,
        has_log=False,
        features=fake_hires_features,
    )


@pytest.fixture
def no_log_cd_context(clean_features: AudioFeatures) -> AudioContext:
    """AudioContext for a CD source without log."""
    return AudioContext(
        format="FLAC",
        source="CD",
        bitrate="Lossless",
        bit_depth=16,
        sample_rate=44100,
        has_log=False,
        features=clean_features,
    )


# ---------------------------------------------------------------------------
# LogAnalysis fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def perfect_eac_log() -> LogAnalysis:
    """A perfect EAC log analysis."""
    return LogAnalysis(
        log_type="EAC",
        score=100,
        confidence="HIGH",
        issues=[],
        flags={
            "secure_mode": True,
            "accuraterip_ok": True,
            "test_copy_crc_match": True,
            "drive_offset_configured": True,
            "timing_problem": False,
            "suspicious_positions": False,
            "read_errors": False,
            "null_samples_issue": False,
        },
        metadata={"eac_version": "1.6", "drive": "PLEXTOR PX-W4824TA"},
    )


@pytest.fixture
def flawed_eac_log() -> LogAnalysis:
    """An EAC log with issues."""
    return LogAnalysis(
        log_type="EAC",
        score=65,
        confidence="MEDIUM",
        issues=[
            "AccurateRip: 8/10 tracks verified (2 failed)",
            "Timing problems detected during extraction",
        ],
        flags={
            "secure_mode": True,
            "accuraterip_ok": False,
            "test_copy_crc_match": True,
            "drive_offset_configured": True,
            "timing_problem": True,
            "suspicious_positions": False,
            "read_errors": False,
            "null_samples_issue": False,
        },
    )


# ---------------------------------------------------------------------------
# TorrentInfo fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def candidate_torrent() -> TorrentInfo:
    """A candidate torrent for dedup testing."""
    return TorrentInfo(
        artist="Radiohead",
        album="OK Computer",
        year=1997,
        format="FLAC",
        bitrate="Lossless",
        source="CD",
        has_log=False,
        bit_depth=16,
    )


# ---------------------------------------------------------------------------
# Sample log content
# ---------------------------------------------------------------------------


@pytest.fixture
def eac_log_content() -> str:
    """Sample EAC log content for parser testing."""
    return """Exact Audio Copy V1.6 from 23. October 2020

EAC extraction logfile from 15. March 2023

Radiohead / OK Computer

Used drive  : PLEXTOR DVDR PX-L890SA   Adapter: 1  ID: 0

Read mode                 : Secure
Utilize accurate stream             : Yes
Defeat audio cache                  : Yes
Make use of C2 pointers             : No

Read offset correction                      : 6
Overread into Lead-In and Lead-Out          : No
Fill up missing offset samples with silence : Yes
Delete leading and trailing silent blocks   : No
Null samples used in CRC calculations       : Yes
Used interface                              : Native Win32 interface for Win NT & 2000
Gap handling                                : Appended to previous track

Used output format              : User Defined Encoder
Selected bitrate                : 1024 kBit/s
Quality                         : High
Add ID3 tag                     : No
Command line compressor          : flac.exe

TOC of the extracted CD

     Track |   Start  |  Length  | Start sector | End sector
    ---------------------------------------------------------
        1  |  0:00.00 |  4:44.26 |         0    |    21325
        2  |  4:44.26 |  4:23.08 |     21326    |    41058
        3  |  9:07.34 |  5:24.10 |     41059    |    65368

Track  1

     Filename D:\\Music\\Radiohead - OK Computer\\01 Airbag.wav

     Pre-gap length  0:00:02.00

     Peak level 98.2 %
     Extraction speed 8.5 X
     Track quality 100.0 %
     Test CRC 3A12B456
     Copy CRC 3A12B456
     Copy OK

Track  2

     Filename D:\\Music\\Radiohead - OK Computer\\02 Paranoid Android.wav

     Peak level 99.1 %
     Extraction speed 9.0 X
     Track quality 100.0 %
     Test CRC 7B34C567
     Copy CRC 7B34C567
     Copy OK

Track  3

     Filename D:\\Music\\Radiohead - OK Computer\\03 Subterranean Homesick Alien.wav

     Peak level 95.0 %
     Extraction speed 8.8 X
     Track quality 100.0 %
     Test CRC 9D56E789
     Copy CRC 9D56E789
     Copy OK


All tracks accurately ripped

No errors occurred

End of status report

==== Log checksum ABCDEF1234567890ABCDEF1234567890ABCDEF12 ====
"""


@pytest.fixture
def xld_log_content() -> str:
    """Sample XLD log content for parser testing."""
    return """X Lossless Decoder version 20210101 (153.1)

XLD extraction logfile from 2023-03-15 14:30:00

Radiohead / OK Computer

Used drive : MATSHITA BD-MLT UJ272 (revision KB19)
Media type : Pressed CD

Ripper mode             : XLD Secure Ripper
Disable audio cache     : OK
Make use of C2 pointers : NO

Read offset correction                      : 102
Max retry count                              : 20
Gap status                                   : Analyzed, Appended

TOC of the extracted CD

     Track |   Start  |  Length  | Start sector | End sector
    ---------------------------------------------------------
        1  |  0:00.00 |  4:44.26 |         0    |    21325
        2  |  4:44.26 |  4:23.08 |     21326    |    41058
        3  |  9:07.34 |  5:24.10 |     41059    |    65368

AccurateRip Summary

    Track 1 : OK (confidence 200)
    Track 2 : OK (confidence 200)
    Track 3 : OK (confidence 200)

All tracks accurately ripped

Track 1

    Filename : /Volumes/Music/01 Airbag.flac

    CRC32 hash (test run)  : 3A12B456
    CRC32 hash             : 3A12B456

    AccurateRip
        Track  1 : OK (confidence 200)

    Result : OK

Track 2

    Filename : /Volumes/Music/02 Paranoid Android.flac

    CRC32 hash (test run)  : 7B34C567
    CRC32 hash             : 7B34C567

    AccurateRip
        Track  2 : OK (confidence 200)

    Result : OK

Track 3

    Filename : /Volumes/Music/03 Subterranean Homesick Alien.flac

    CRC32 hash (test run)  : 9D56E789
    CRC32 hash             : 9D56E789

    AccurateRip
        Track  3 : OK (confidence 200)

    Result : OK

No errors occurred

End of status report
"""
