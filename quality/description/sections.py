"""
Section renderers for BBCode description generation.

Each function renders a single section of the upload description.
The generator.py module composes these sections into the final output.

This separation allows:
- Independent testing of each section
- Easy addition of new sections
- Future localization support
"""

from __future__ import annotations

from quality.description import templates as tpl
from quality.models import LogAnalysis, RiskReport


def render_header() -> str:
    """Render the description header section."""
    return tpl.HEADER_TEMPLATE


def render_format_section(
    format: str | None = None,
    bitrate: str | None = None,
    source: str | None = None,
    bit_depth: int | None = None,
    sample_rate: int | None = None,
) -> str:
    """Render the format/bitrate/source section.

    Args:
        format: Audio format (e.g., 'FLAC').
        bitrate: Bitrate string (e.g., 'Lossless', '320').
        source: Media source (e.g., 'CD', 'WEB').
        bit_depth: Bit depth in bits.
        sample_rate: Sample rate in Hz.

    Returns:
        BBCode string for the format section.
    """
    result = tpl.FORMAT_SECTION.format(
        format=format or "Unknown",
        bitrate=bitrate or "Unknown",
        source=source or "Unknown",
    )

    if bit_depth is not None:
        result += tpl.BIT_DEPTH_LINE.format(bit_depth=bit_depth)

    if sample_rate is not None:
        result += tpl.SAMPLE_RATE_LINE.format(sample_rate=sample_rate)

    return result


def render_tools_section(tools: list[str] | None = None) -> str:
    """Render the tools used section.

    Args:
        tools: List of tool names/versions.

    Returns:
        BBCode string for the tools section, or empty string if no tools.
    """
    if not tools:
        default_tools = [
            "RedactedAudioToolbox v1.0",
            "SoX (spectrogram analysis)",
            "FFmpeg (format conversion)",
        ]
        tools = default_tools

    tools_list = "\n".join(f"• {tool}" for tool in tools)
    return tpl.TOOLS_SECTION.format(tools_list=tools_list)


def render_log_section(log_analysis: LogAnalysis | None) -> str:
    """Render the log analysis section.

    Args:
        log_analysis: Parsed log analysis result.

    Returns:
        BBCode string for the log section, or empty string if no log.
    """
    if log_analysis is None:
        return ""

    result = tpl.LOG_SECTION.format(
        log_type=log_analysis.log_type,
        log_score=log_analysis.score,
        confidence=log_analysis.confidence,
    )

    if log_analysis.issues:
        result += tpl.LOG_ISSUES_HEADER
        for issue in log_analysis.issues:
            result += tpl.LOG_ISSUE_LINE.format(issue=issue)
    else:
        result += tpl.LOG_NO_ISSUES

    return result


def render_spectrogram_section(
    spectrogram_url: str | None = None,
) -> str:
    """Render the spectrogram section.

    Args:
        spectrogram_url: URL or path to the spectrogram image.

    Returns:
        BBCode string for the spectrogram section, or empty string.
    """
    if not spectrogram_url:
        return ""

    return tpl.SPECTROGRAM_SECTION.format(spectrogram_url=spectrogram_url)


def render_dynamic_range_section(dr_value: int | None = None) -> str:
    """Render the dynamic range section.

    Args:
        dr_value: Dynamic range value.

    Returns:
        BBCode string for the DR section, or empty string.
    """
    if dr_value is None:
        return ""

    return tpl.DYNAMIC_RANGE_SECTION.format(dr_value=dr_value)


def render_risk_section(
    risk_report: RiskReport | None,
    include: bool = True,
) -> str:
    """Render the risk assessment section.

    Uses different templates based on risk level:
    - SAFE/LOW_RISK: green header
    - SUSPICIOUS: orange warning header
    - HIGH_RISK/LIKELY_TRANSCODE: red danger header

    Args:
        risk_report: Risk assessment report.
        include: Whether to include this section.

    Returns:
        BBCode string for the risk section, or empty string.
    """
    if risk_report is None or not include:
        return ""

    level = risk_report.level

    if level in ("SAFE", "LOW_RISK"):
        section = tpl.RISK_SECTION_SAFE.format(
            level=level, score=risk_report.score
        )
    elif level == "SUSPICIOUS":
        section = tpl.RISK_SECTION_WARNING.format(
            level=level, score=risk_report.score
        )
    else:
        section = tpl.RISK_SECTION_DANGER.format(
            level=level, score=risk_report.score
        )

    for reason in risk_report.reasons:
        section += tpl.RISK_REASON_LINE.format(reason=reason)

    for suggestion in risk_report.suggestions:
        section += tpl.RISK_SUGGESTION_LINE.format(suggestion=suggestion)

    return section


def render_footer() -> str:
    """Render the description footer."""
    return tpl.FOOTER_TEMPLATE
