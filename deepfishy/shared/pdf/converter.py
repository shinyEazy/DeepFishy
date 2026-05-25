"""Markdown-to-PDF conversion helpers."""

import argparse
import os
import re

from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

from deepfishy.shared.pdf.layout import build_pdf_html, build_pdf_stylesheet


def _format_markdown_content(md_content: str) -> str:
    """Format markdown content to fix common citation rendering issues."""
    content = re.sub(r"\n(\[\d+\]\s+)", r"\n\n\1", md_content)
    content = re.sub(r"(https?://[^\s]+)\s+(\[\d+\]\s+)", r"\1\n\n\2", content)
    content = re.sub(r"(\.\s+)(\[\d+\]\s+)", r"\1\n\n\2", content)

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

    return citation_run_pattern.sub(_dedupe_citation_run, content)


def convert_md_to_pdf(
    md_content: str, output_path: str, base_path: str | None = None
) -> None:
    """Convert markdown content to PDF using WeasyPrint."""
    try:
        html_content = build_pdf_html(_format_markdown_content(md_content))
        font_config = FontConfiguration()
        css = CSS(string=build_pdf_stylesheet(), font_config=font_config)

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        resolved_base_path = os.path.abspath(base_path or os.getcwd())
        HTML(string=html_content, base_url=resolved_base_path).write_pdf(
            output_path,
            stylesheets=[css],
            font_config=font_config,
        )
        print(f"PDF generated successfully at: {output_path}")
    except Exception as error:
        print(f"Error generating PDF: {error}")
        try:
            txt_path = output_path.replace(".pdf", ".txt")
            with open(txt_path, "w", encoding="utf-8") as file_handle:
                file_handle.write(md_content)
            print(f"Failed to generate PDF, saved as text at: {txt_path}")
        except Exception as fallback_error:
            print(f"Failed to save output: {fallback_error}")
            raise


def main() -> None:
    """CLI entrypoint for ad-hoc markdown to PDF conversion."""
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
        raise SystemExit(1)

    with open(args.md_path, "r", encoding="utf-8") as file_handle:
        md_content = file_handle.read()

    convert_md_to_pdf(
        md_content,
        args.pdf_path,
        base_path=os.path.dirname(os.path.abspath(args.md_path)),
    )


__all__ = ["convert_md_to_pdf", "main"]


if __name__ == "__main__":
    main()
