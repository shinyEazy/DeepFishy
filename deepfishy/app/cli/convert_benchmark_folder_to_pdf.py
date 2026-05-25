"""CLI helper to convert a folder of markdown benchmark reports to PDFs."""

import argparse
from pathlib import Path

from deepfishy.shared.pdf.converter import convert_md_to_pdf


def build_parser() -> argparse.ArgumentParser:
    """Build the folder conversion CLI parser."""
    parser = argparse.ArgumentParser(
        description="Convert all .md files in a folder to .pdf in the same folder."
    )
    parser.add_argument(
        "--folder",
        type=str,
        required=True,
        help="Path to the folder containing .md files",
    )
    return parser


def main() -> None:
    """Convert all markdown files in the folder to PDFs."""
    parser = build_parser()
    args = parser.parse_args()

    folder_path = Path(args.folder)
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"Error: Folder not found or is not a directory: {args.folder}")
        raise SystemExit(1)

    md_files = list(folder_path.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {args.folder}")
        return

    print(f"Found {len(md_files)} .md file(s) in {args.folder}")
    for md_path in md_files:
        pdf_path = md_path.with_suffix(".pdf")
        print(f"Converting: {md_path.name} -> {pdf_path.name}")
        try:
            md_content = md_path.read_text(encoding="utf-8")
            convert_md_to_pdf(
                md_content,
                str(pdf_path),
                base_path=str(md_path.parent.resolve()),
            )
        except Exception as error:
            print(f"Failed to convert {md_path.name}: {error}")

    print("Bulk conversion completed.")


__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    main()
