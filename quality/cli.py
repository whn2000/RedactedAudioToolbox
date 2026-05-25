"""
Command-line interface for the quality audit system.

Provides subcommands for each audit module:
    risk     - Risk assessment of an album directory
    log      - EAC/XLD log analysis
    dedup    - Duplicate/trump detection
    describe - Generate BBCode upload description
    audit    - Full audit (all modules combined)

Usage::

    python -m quality.cli risk --album-dir /path/to/album --format FLAC --source CD
    python -m quality.cli log --file /path/to/log.txt
    python -m quality.cli dedup --artist "Artist" --album "Album" --format FLAC
    python -m quality.cli describe --format FLAC --source WEB --bitrate Lossless
    python -m quality.cli audit --album-dir /path/to/album
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from quality.config import QualityConfig
from quality.models import (
    AudioContext,
    AudioFeatures,
    DuplicateCheckResult,
    LogAnalysis,
    RiskReport,
    TorrentInfo,
)


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _format_output(data: dict[str, Any], fmt: str) -> str:
    """Format output as JSON or text.

    Args:
        data: Output data dictionary.
        fmt: Output format ('json' or 'text').

    Returns:
        Formatted string.
    """
    if fmt == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)

    # Text format
    lines: list[str] = []
    _flatten_dict(data, lines, indent=0)
    return "\n".join(lines)


def _flatten_dict(
    d: dict[str, Any] | list[Any] | Any,
    lines: list[str],
    indent: int = 0,
    prefix: str = "",
) -> None:
    """Flatten a nested dict/list into human-readable lines."""
    pad = "  " * indent
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{prefix}{k}:")
                _flatten_dict(v, lines, indent + 1)
            else:
                lines.append(f"{pad}{prefix}{k}: {v}")
    elif isinstance(d, list):
        for i, item in enumerate(d):
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}[{i}]:")
                _flatten_dict(item, lines, indent + 1)
            else:
                lines.append(f"{pad}- {item}")
    else:
        lines.append(f"{pad}{prefix}{d}")


# ---- Subcommand: risk ----


def cmd_risk(args: argparse.Namespace) -> int:
    """Execute the risk assessment subcommand."""
    from quality.config import QualityConfig
    from quality.features.extractor import FeatureExtractor
    from quality.risk.engine import RiskEngine

    config = QualityConfig()
    engine = RiskEngine(config)

    # Build AudioContext
    ctx = AudioContext(
        format=args.format,
        source=args.source,
        bitrate=args.bitrate,
        bit_depth=args.bit_depth,
        sample_rate=args.sample_rate,
        has_log=args.has_log,
    )

    # Extract features if album-dir is provided
    if args.album_dir:
        album_path = Path(args.album_dir)
        if not album_path.exists():
            print(f"Error: Directory not found: {album_path}", file=sys.stderr)
            return 1

        ctx.album_dir = album_path
        extractor = FeatureExtractor()
        ctx.features = extractor.extract_album(album_path)

        # Auto-detect bit_depth and sample_rate from features
        from quality.features.audio_stats import get_audio_metadata
        from quality.features.spectrogram import get_audio_specs

        audio_files = extractor._find_audio_files(album_path)
        if audio_files:
            meta = get_audio_metadata(audio_files[0])
            if ctx.bit_depth is None:
                ctx.bit_depth = meta.get("bit_depth")
            if ctx.sample_rate is None:
                ctx.sample_rate = meta.get("sample_rate")

    # Parse log if available
    if args.log_file:
        from quality.log_parser.detector import detect_and_parse

        log_path = Path(args.log_file)
        if log_path.exists():
            ctx.log_analysis = detect_and_parse(path=log_path)
            ctx.has_log = True

    report = engine.evaluate(ctx)
    output = report.to_dict()
    print(_format_output(output, args.output_format))
    return 0


# ---- Subcommand: log ----


def cmd_log(args: argparse.Namespace) -> int:
    """Execute the log analysis subcommand."""
    from quality.log_parser.detector import detect_and_parse

    path = Path(args.file)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        return 1

    analysis = detect_and_parse(path=path)
    output = analysis.to_dict()
    print(_format_output(output, args.output_format))
    return 0


# ---- Subcommand: dedup ----


def cmd_dedup(args: argparse.Namespace) -> int:
    """Execute the duplicate check subcommand."""
    from quality.dedup.engine import DuplicateChecker
    from quality.dedup.providers import MockProvider

    candidate = TorrentInfo(
        artist=args.artist,
        album=args.album,
        year=args.year or 0,
        format=args.format or "FLAC",
        bitrate=args.bitrate or "Lossless",
        source=args.source or "CD",
        has_log=args.has_log,
        bit_depth=args.bit_depth,
    )

    provider = MockProvider()
    checker = DuplicateChecker(provider)
    result = checker.check(candidate)
    output = result.to_dict()
    print(_format_output(output, args.output_format))
    return 0


# ---- Subcommand: describe ----


def cmd_describe(args: argparse.Namespace) -> int:
    """Execute the description generator subcommand."""
    from quality.description.generator import DescriptionGenerator

    gen = DescriptionGenerator(
        include_risk_notice=not args.no_risk,
        include_spectrogram=not args.no_spectrogram,
    )

    # Build optional LogAnalysis
    log_analysis = None
    if args.log_file:
        from quality.log_parser.detector import detect_and_parse

        log_path = Path(args.log_file)
        if log_path.exists():
            log_analysis = detect_and_parse(path=log_path)

    # Build optional RiskReport
    risk_report = None
    if args.risk_score is not None:
        risk_report = RiskReport(
            score=args.risk_score,
            level=args.risk_level or "SAFE",
        )

    bbcode = gen.generate(
        format=args.format,
        bitrate=args.bitrate,
        source=args.source,
        bit_depth=args.bit_depth,
        sample_rate=args.sample_rate,
        log_analysis=log_analysis,
        risk_report=risk_report,
        spectrogram_url=args.spectrogram_url,
        dr_value=args.dr_value,
    )

    if args.output_format == "json":
        print(json.dumps({"bbcode": bbcode}, indent=2, ensure_ascii=False))
    else:
        print(bbcode)
    return 0


# ---- Subcommand: audit ----


def cmd_audit(args: argparse.Namespace) -> int:
    """Execute the full audit subcommand (all modules)."""
    from quality.config import QualityConfig
    from quality.dedup.engine import DuplicateChecker
    from quality.dedup.providers import MockProvider
    from quality.description.generator import DescriptionGenerator
    from quality.features.extractor import FeatureExtractor
    from quality.log_parser.detector import detect_and_parse
    from quality.risk.engine import RiskEngine

    album_path = Path(args.album_dir)
    if not album_path.exists():
        print(f"Error: Directory not found: {album_path}", file=sys.stderr)
        return 1

    config = QualityConfig()
    results: dict[str, Any] = {"album": str(album_path)}

    # 1. Feature extraction
    extractor = FeatureExtractor()
    features = extractor.extract_album(album_path)
    results["features"] = features.to_dict()

    # Auto-detect audio metadata
    audio_files = extractor._find_audio_files(album_path)
    bit_depth = args.bit_depth
    sample_rate = args.sample_rate
    if audio_files:
        from quality.features.audio_stats import get_audio_metadata

        meta = get_audio_metadata(audio_files[0])
        if bit_depth is None:
            bit_depth = meta.get("bit_depth")
        if sample_rate is None:
            sample_rate = meta.get("sample_rate")

    # 2. Log parsing
    log_analysis = None
    log_files = list(album_path.glob("*.log"))
    if log_files:
        log_analysis = detect_and_parse(path=log_files[0])
        results["log_analysis"] = log_analysis.to_dict()

    # 3. Risk assessment
    ctx = AudioContext(
        album_dir=album_path,
        format=args.format or "FLAC",
        source=args.source or "CD",
        bitrate=args.bitrate or "Lossless",
        bit_depth=bit_depth,
        sample_rate=sample_rate,
        has_log=log_analysis is not None,
        log_analysis=log_analysis,
        features=features,
    )

    engine = RiskEngine(config)
    risk_report = engine.evaluate(ctx)
    results["risk_report"] = risk_report.to_dict()

    # 4. Dedup check
    if args.artist and args.album_name:
        candidate = TorrentInfo(
            artist=args.artist,
            album=args.album_name,
            year=args.year or 0,
            format=args.format or "FLAC",
            bitrate=args.bitrate or "Lossless",
            source=args.source or "CD",
            has_log=log_analysis is not None,
            bit_depth=bit_depth,
        )
        checker = DuplicateChecker(MockProvider())
        dedup_result = checker.check(candidate)
        results["dedup"] = dedup_result.to_dict()

    # 5. Description generation
    gen = DescriptionGenerator()
    bbcode = gen.generate(
        format=args.format or "FLAC",
        bitrate=args.bitrate or "Lossless",
        source=args.source or "CD",
        bit_depth=bit_depth,
        sample_rate=sample_rate,
        log_analysis=log_analysis,
        risk_report=risk_report,
        dr_value=args.dr_value,
    )
    results["description"] = bbcode

    print(_format_output(results, args.output_format))
    return 0


# ---- Argument parser ----


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="quality",
        description="RedactedAudioToolbox Quality Audit System",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose/debug logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- risk ----
    risk_p = subparsers.add_parser("risk", help="Run risk assessment")
    risk_p.add_argument("--album-dir", help="Path to album directory")
    risk_p.add_argument("--format", help="Audio format (e.g., FLAC)")
    risk_p.add_argument("--source", help="Media source (e.g., CD, WEB)")
    risk_p.add_argument("--bitrate", help="Bitrate (e.g., Lossless, 320)")
    risk_p.add_argument("--bit-depth", type=int, help="Bit depth")
    risk_p.add_argument("--sample-rate", type=int, help="Sample rate in Hz")
    risk_p.add_argument("--has-log", action="store_true", help="Has ripping log")
    risk_p.add_argument("--log-file", help="Path to ripping log file")
    risk_p.add_argument(
        "--output-format", choices=["json", "text"], default="json",
        help="Output format (default: json)",
    )
    risk_p.set_defaults(func=cmd_risk)

    # ---- log ----
    log_p = subparsers.add_parser("log", help="Analyze ripping log")
    log_p.add_argument("--file", required=True, help="Path to log file")
    log_p.add_argument(
        "--output-format", choices=["json", "text"], default="json",
        help="Output format (default: json)",
    )
    log_p.set_defaults(func=cmd_log)

    # ---- dedup ----
    dedup_p = subparsers.add_parser("dedup", help="Check for duplicates")
    dedup_p.add_argument("--artist", required=True, help="Artist name")
    dedup_p.add_argument("--album", required=True, help="Album title")
    dedup_p.add_argument("--year", type=int, help="Release year")
    dedup_p.add_argument("--format", help="Audio format")
    dedup_p.add_argument("--bitrate", help="Bitrate")
    dedup_p.add_argument("--source", help="Media source")
    dedup_p.add_argument("--has-log", action="store_true")
    dedup_p.add_argument("--bit-depth", type=int)
    dedup_p.add_argument(
        "--output-format", choices=["json", "text"], default="json",
        help="Output format (default: json)",
    )
    dedup_p.set_defaults(func=cmd_dedup)

    # ---- describe ----
    desc_p = subparsers.add_parser("describe", help="Generate upload description")
    desc_p.add_argument("--format", help="Audio format")
    desc_p.add_argument("--bitrate", help="Bitrate")
    desc_p.add_argument("--source", help="Media source")
    desc_p.add_argument("--bit-depth", type=int)
    desc_p.add_argument("--sample-rate", type=int)
    desc_p.add_argument("--log-file", help="Path to ripping log")
    desc_p.add_argument("--spectrogram-url", help="URL to spectrogram image")
    desc_p.add_argument("--dr-value", type=int, help="Dynamic range value")
    desc_p.add_argument("--risk-score", type=int, help="Risk score (0-100)")
    desc_p.add_argument("--risk-level", help="Risk level")
    desc_p.add_argument("--no-risk", action="store_true", help="Omit risk section")
    desc_p.add_argument("--no-spectrogram", action="store_true", help="Omit spectrogram")
    desc_p.add_argument(
        "--output-format", choices=["json", "text"], default="text",
        help="Output format (default: text)",
    )
    desc_p.set_defaults(func=cmd_describe)

    # ---- audit ----
    audit_p = subparsers.add_parser("audit", help="Full quality audit")
    audit_p.add_argument("--album-dir", required=True, help="Path to album directory")
    audit_p.add_argument("--artist", help="Artist name (for dedup)")
    audit_p.add_argument("--album-name", help="Album title (for dedup)")
    audit_p.add_argument("--year", type=int, help="Release year")
    audit_p.add_argument("--format", help="Audio format")
    audit_p.add_argument("--bitrate", help="Bitrate")
    audit_p.add_argument("--source", help="Media source")
    audit_p.add_argument("--bit-depth", type=int)
    audit_p.add_argument("--sample-rate", type=int)
    audit_p.add_argument("--dr-value", type=int, help="Dynamic range value")
    audit_p.add_argument(
        "--output-format", choices=["json", "text"], default="json",
        help="Output format (default: json)",
    )
    audit_p.set_defaults(func=cmd_audit)

    return parser


def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
