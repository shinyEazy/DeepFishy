# python utils/convert_md_to_pdf.py --md_path "utils/test.md" --pdf_path "utils/test.pdf"

import os
import re
import sys
import argparse
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from deepfishy.infra.config.paths import PROJECT_ROOT

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.pdf_layout import build_pdf_html, build_pdf_stylesheet  # noqa: E402


def _format_markdown_content(md_content: str) -> str:
    """Format markdown content to fix common issues like source formatting."""
    # 1. Fix sources formatting
    # If citations are separated by single newlines, make them double so they render as separate paragraphs
    content = re.sub(r"\n(\[\d+\]\s+)", r"\n\n\1", md_content)

    # If citations are glued on the same line after a URL (common LLM artifact)
    content = re.sub(r"(https?://[^\s]+)\s+(\[\d+\]\s+)", r"\1\n\n\2", content)

    # If citations are glued after a period
    content = re.sub(r"(\.\s+)(\[\d+\]\s+)", r"\1\n\n\2", content)

    # 2. Collapse duplicate adjacent citations, e.g. [21][21] -> [21]
    # Keep distinct citations in their original order, e.g. [24][24][3] -> [24][3]
    citation_run_pattern = re.compile(r"(?:\[\d+\]\s*){2,}")

    def _dedupe_citation_run(match: re.Match[str]) -> str:
        citation_run = match.group(0)
        seen: set[str] = set()
        ordered_citations: list[str] = []

        for citation in re.findall(r"\[\d+\]", citation_run):
            if citation not in seen:
                seen.add(citation)
                ordered_citations.append(citation)

        trailing_space = " " if citation_run.endswith(" ") else ""
        return "".join(ordered_citations) + trailing_space

    content = citation_run_pattern.sub(_dedupe_citation_run, content)

    return content


def convert_md_to_pdf(
    md_content: str, output_path: str, base_path: str | None = None
) -> None:
    """
    Convert markdown content to PDF using WeasyPrint with support for Vietnamese fonts.

    Args:
        md_content: Markdown content string
        output_path: Path where the PDF file will be saved
        base_path: Base directory used to resolve relative assets like images
    """
    try:
        # Pre-format content for source lists
        md_content = _format_markdown_content(md_content)

        # Build a richer HTML document with a clickable TOC and print-friendly styling.
        html_content = build_pdf_html(md_content)

        font_config = FontConfiguration()
        css = CSS(
            string=build_pdf_stylesheet(),
            font_config=font_config,
        )

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Resolve relative Markdown assets like images from the Markdown file's directory.
        resolved_base_path = os.path.abspath(base_path or os.getcwd())

        # Generate PDF
        HTML(string=html_content, base_url=resolved_base_path).write_pdf(
            output_path, stylesheets=[css], font_config=font_config
        )

        print(f"PDF generated successfully at: {output_path}")

    except Exception as e:
        print(f"Error generating PDF: {e}")
        # Last resort fallback - save as text file
        try:
            txt_path = output_path.replace(".pdf", ".txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"Failed to generate PDF, saved as text at: {txt_path}")
        except Exception as e2:
            print(f"Failed to save output: {e2}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--md_path", type=str, required=True, help="Path to markdown file"
    )
    parser.add_argument(
        "--pdf_path", type=str, required=True, help="Path to output PDF file"
    )
    args = parser.parse_args()

    if not os.path.exists(args.md_path):
        print(f"Error: Markdown file not found at {args.md_path}")
        exit(1)

    with open(args.md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    convert_md_to_pdf(
        md_content,
        args.pdf_path,
        base_path=os.path.dirname(os.path.abspath(args.md_path)),
    )
