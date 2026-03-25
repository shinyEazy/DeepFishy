import sys
import argparse
from pathlib import Path
from utils.convert_md_to_pdf import convert_md_to_pdf

# Setup path and encoding first to handle imports from root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(
        description="Convert all .md files in a folder to .pdf in the same folder."
    )
    parser.add_argument(
        "--folder",
        type=str,
        required=True,
        help="Path to the folder containing .md files",
    )
    args = parser.parse_args()

    folder_path = Path(args.folder)
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"Error: Folder not found or is not a directory: {args.folder}")
        sys.exit(1)

    # Find all .md files in the folder (not recursive)
    md_files = list(folder_path.glob("*.md"))

    if not md_files:
        print(f"No .md files found in {args.folder}")
        return

    print(f"Found {len(md_files)} .md file(s) in {args.folder}")

    for md_path in md_files:
        pdf_path = md_path.with_suffix(".pdf")

        print(f"Converting: {md_path.name} -> {pdf_path.name}")

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()

            convert_md_to_pdf(
                md_content, str(pdf_path), base_path=str(md_path.parent.resolve())
            )
        except Exception as e:
            print(f"Failed to convert {md_path.name}: {e}")

    print("Bulk conversion completed.")


if __name__ == "__main__":
    main()
