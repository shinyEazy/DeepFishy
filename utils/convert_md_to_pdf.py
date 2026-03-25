import os
import re
import argparse
import markdown
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration


def _format_markdown_content(md_content: str) -> str:
    """Format markdown content to fix common issues like source formatting."""
    # 1. Fix sources formatting
    # If citations are separated by single newlines, make them double so they render as separate paragraphs
    content = re.sub(r"\n(\[\d+\]\s+)", r"\n\n\1", md_content)

    # If citations are glued on the same line after a URL (common LLM artifact)
    content = re.sub(r"(https?://[^\s]+)\s+(\[\d+\]\s+)", r"\1\n\n\2", content)

    # If citations are glued after a period
    content = re.sub(r"(\.\s+)(\[\d+\]\s+)", r"\1\n\n\2", content)

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

        # Convert Markdown to HTML
        # Using extensions for tables, fenced code, and attributes (common in MD)
        extensions = ["extra", "tables", "fenced_code", "toc", "attr_list"]
        html_content = markdown.markdown(md_content, extensions=extensions)

        # Define CSS for Vietnamese fonts and basic styling
        # Using Noto Sans as primary font for better Vietnamese support
        font_config = FontConfiguration()
        css = CSS(
            string="""
            @page {
                margin: 2cm;
                @bottom-right {
                    content: counter(page);
                }
            }
            body {
                font-family: "Noto Sans", "DejaVu Sans", Arial, sans-serif;
                font-size: 12pt;
                line-height: 1.6;
                color: #333;
                text-align: justify;
            }
            h1, h2, h3, h4, h5, h6 {
                font-family: "Noto Sans", "DejaVu Sans", Arial, sans-serif;
                color: #1a1a1a;
                margin-top: 1em;
                margin-bottom: 0.5em;
            }
            h1 { font-size: 24pt; border-bottom: 1px solid #ccc; padding-bottom: 10px; }
            h2 { font-size: 18pt; margin-top: 1.5em; }
            h3 { font-size: 14pt; }
            code {
                font-family: "Noto Sans Mono", "DejaVu Sans Mono", monospace;
                background-color: #f4f4f4;
                padding: 2px 4px;
                border-radius: 4px;
            }
            pre {
                background-color: #f4f4f4;
                padding: 1em;
                border-radius: 8px;
                white-space: pre-wrap;
                word-wrap: break-word;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 1em 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
            img {
                max-width: 100%;
                height: auto;
                display: block;
                margin: 1em auto;
            }
            blockquote {
                border-left: 5px solid #ccc;
                margin: 1.5em 10px;
                padding: 0.5em 10px;
                color: #666;
                font-style: italic;
            }
        """,
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
