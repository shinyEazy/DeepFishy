"""Shared PDF utilities."""

"""Shared PDF utilities for report rendering and benchmark evaluation."""

from deepfishy.shared.pdf.converter import convert_md_to_pdf
from deepfishy.shared.pdf.helpers import benchmark_md_to_pdf, load_report_as_pdf
from deepfishy.shared.pdf.layout import build_pdf_html, build_pdf_stylesheet

__all__ = [
    "benchmark_md_to_pdf",
    "build_pdf_html",
    "build_pdf_stylesheet",
    "convert_md_to_pdf",
    "load_report_as_pdf",
]
