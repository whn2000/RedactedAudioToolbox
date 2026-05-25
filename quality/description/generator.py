"""
Upload description generator.

Composes section renderers into a complete BBCode description for
RED/OPS uploads. Supports customizable section ordering and
conditional inclusion based on available data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from quality.description.sections import (
    render_dynamic_range_section,
    render_footer,
    render_format_section,
    render_header,
    render_log_section,
    render_risk_section,
    render_spectrogram_section,
    render_tools_section,
)
from quality.models import LogAnalysis, RiskReport

logger = logging.getLogger(__name__)


class DescriptionGenerator:
    """Generates BBCode upload descriptions from analysis results.

    Composes section renderers in order, skipping sections when their
    data is unavailable. Supports customizable template names and
    conditional inclusion of risk notices.

    Args:
        template_name: Template name (currently only 'default' is supported).
        include_risk_notice: Whether to include the risk assessment section.
        include_spectrogram: Whether to include the spectrogram section.

    Usage::

        gen = DescriptionGenerator()
        bbcode = gen.generate(
            format="FLAC",
            bitrate="Lossless",
            source="CD",
            log_analysis=log_result,
            risk_report=risk_result,
        )
        print(bbcode)
    """

    def __init__(
        self,
        template_name: str = "default",
        include_risk_notice: bool = True,
        include_spectrogram: bool = True,
    ) -> None:
        self._template_name = template_name
        self._include_risk_notice = include_risk_notice
        self._include_spectrogram = include_spectrogram

    def generate(
        self,
        format: str | None = None,
        bitrate: str | None = None,
        source: str | None = None,
        bit_depth: int | None = None,
        sample_rate: int | None = None,
        log_analysis: LogAnalysis | None = None,
        risk_report: RiskReport | None = None,
        spectrogram_url: str | None = None,
        dr_value: int | None = None,
        tools: list[str] | None = None,
    ) -> str:
        """Generate a complete BBCode description.

        All parameters are optional. Sections are only included when
        their corresponding data is available.

        Args:
            format: Audio format (e.g., 'FLAC').
            bitrate: Bitrate string (e.g., 'Lossless').
            source: Media source (e.g., 'CD', 'WEB').
            bit_depth: Bit depth in bits.
            sample_rate: Sample rate in Hz.
            log_analysis: Parsed log analysis result.
            risk_report: Risk assessment report.
            spectrogram_url: URL to the spectrogram image.
            dr_value: Dynamic range value.
            tools: List of tools used.

        Returns:
            Complete BBCode string ready for upload.
        """
        sections: list[str] = []

        sections.append(render_header())

        sections.append(render_format_section(
            format=format,
            bitrate=bitrate,
            source=source,
            bit_depth=bit_depth,
            sample_rate=sample_rate,
        ))

        tools_section = render_tools_section(tools)
        if tools_section:
            sections.append(tools_section)

        log_section = render_log_section(log_analysis)
        if log_section:
            sections.append(log_section)

        if self._include_spectrogram:
            spec_section = render_spectrogram_section(spectrogram_url)
            if spec_section:
                sections.append(spec_section)

        dr_section = render_dynamic_range_section(dr_value)
        if dr_section:
            sections.append(dr_section)

        if self._include_risk_notice:
            risk_section = render_risk_section(
                risk_report, include=self._include_risk_notice
            )
            if risk_section:
                sections.append(risk_section)

        sections.append(render_footer())

        result = "\n".join(sections)
        logger.info(
            "Generated description: %d chars, %d sections",
            len(result), len(sections),
        )
        return result

    def generate_from_dict(self, data: dict[str, Any]) -> str:
        """Generate a description from a dictionary of parameters.

        Convenience method that unpacks a dictionary into generate().

        Args:
            data: Dictionary with parameter names matching generate().

        Returns:
            Complete BBCode string.
        """
        return self.generate(
            format=data.get("format"),
            bitrate=data.get("bitrate"),
            source=data.get("source"),
            bit_depth=data.get("bit_depth"),
            sample_rate=data.get("sample_rate"),
            log_analysis=data.get("log_analysis"),
            risk_report=data.get("risk_report"),
            spectrogram_url=data.get("spectrogram_url"),
            dr_value=data.get("dr_value"),
            tools=data.get("tools"),
        )
