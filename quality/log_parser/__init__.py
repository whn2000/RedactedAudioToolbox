"""
EAC / XLD ripping log parser.

Provides pluggable log parsers with automatic type detection for
Exact Audio Copy (EAC) and X Lossless Decoder (XLD) ripping logs.
"""

from quality.log_parser.detector import detect_and_parse, detect_log_type

__all__ = ["detect_and_parse", "detect_log_type"]
