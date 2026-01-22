"""
Enhanced PDF converter with support for images and charts.
"""

import os
import re
from markdown_pdf import MarkdownPdf, Section
from typing import Optional


def convert_md_to_pdf(md_content: str, output_path: str) -> None:
    """
    Convert markdown content to PDF with support for embedded images and charts.

    Args:
        md_content: Markdown content string (may contain image references)
        output_path: Path where the PDF file will be saved
    """
    try:
        # Process markdown to handle relative image paths
        processed_content = _process_image_paths(md_content, output_path)

        # Ensure markdown starts with a level 1 heading (required by markdown-pdf)
        processed_content = _ensure_valid_markdown_hierarchy(processed_content)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Create PDF with enhanced settings
        try:
            pdf = MarkdownPdf(toc_level=3)
            pdf.add_section(Section(processed_content))
            pdf.save(output_path)
            print(f"PDF generated successfully at: {output_path}")
        except Exception as e:
            # If toc_level causes issues, try without it
            print(f"Retrying PDF generation without TOC: {e}")
            pdf = MarkdownPdf()
            pdf.add_section(Section(processed_content))
            pdf.save(output_path)
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


def _ensure_valid_markdown_hierarchy(md_content: str) -> str:
    """
    Ensure markdown has proper heading hierarchy.
    The markdown-pdf library requires:
    1. Documents must start with # (level 1 heading)
    2. Headings must not skip levels (e.g., # then ### is invalid)

    Args:
        md_content: Original markdown content

    Returns:
        Markdown content with valid hierarchy
    """
    lines = md_content.strip().split("\n")

    if not lines:
        return "# Báo Cáo Tài Chính\n\n"

    result_lines = []
    current_level = 0
    title_added = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check if this is a heading line
        if stripped.startswith("#"):
            # Count heading level
            level = 0
            for char in stripped:
                if char == "#":
                    level += 1
                else:
                    break

            heading_text = stripped[level:].strip()

            # First heading must be level 1
            if not title_added:
                if level != 1:
                    # Force first heading to be level 1
                    result_lines.append(f"# {heading_text}")
                    current_level = 1
                else:
                    result_lines.append(line)
                    current_level = 1
                title_added = True
            else:
                # Ensure we don't skip levels
                # e.g., if current is 1, next can only be 1 or 2, not 3
                max_allowed_level = current_level + 1

                if level > max_allowed_level:
                    # Adjust to max allowed level
                    adjusted_level = max_allowed_level
                    result_lines.append(("#" * adjusted_level) + " " + heading_text)
                    current_level = adjusted_level
                else:
                    result_lines.append(line)
                    current_level = level
        else:
            # Not a heading line
            # If we haven't added a title yet and this is content, add default title
            if not title_added and stripped:
                result_lines.append("# Báo Cáo Tài Chính\n")
                title_added = True
                current_level = 1

            result_lines.append(line)

    # If no title was added at all, add one at the beginning
    if not title_added:
        result_lines.insert(0, "# Báo Cáo Tài Chính\n")

    return "\n".join(result_lines)


def _process_image_paths(md_content: str, output_path: str) -> str:
    """
    Process markdown content to convert relative image paths to absolute paths.

    Args:
        md_content: Original markdown content
        output_path: Output PDF path (used to resolve relative paths)

    Returns:
        Processed markdown content with absolute image paths
    """
    # Find all image references in markdown: ![alt text](path)
    image_pattern = r"!\[([^\]]*)\]\(([^\)]+)\)"

    def replace_image_path(match):
        alt_text = match.group(1)
        image_path = match.group(2)

        # Skip if already absolute path or URL
        if image_path.startswith(("http://", "https://", "/", "file://")):
            return match.group(0)

        # Convert relative path to absolute
        base_dir = os.getcwd()
        abs_image_path = os.path.abspath(os.path.join(base_dir, image_path))

        # Check if file exists
        if os.path.exists(abs_image_path):
            # Use file:// protocol for local files
            abs_image_path = abs_image_path.replace("\\", "/")
            return f"![{alt_text}](file:///{abs_image_path})"
        else:
            # Keep original if file doesn't exist
            return match.group(0)

    processed_content = re.sub(image_pattern, replace_image_path, md_content)
    return processed_content
