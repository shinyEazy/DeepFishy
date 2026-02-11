"""PDF conversion helpers for benchmark evaluation.

Handles markdown-to-PDF conversion with image compression,
PDF reading, and unified report loading.
"""

import os
import re
import shutil
import tempfile
from pathlib import Path

from core.logging import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _compress_images_to_tmpdir(
    md_content: str, report_dir: str, max_width: int = 1200, quality: int = 70
) -> tuple[str, str]:
    """Compress images referenced in markdown into a temp directory.

    Returns:
        Tuple of (modified markdown content, temp directory path).
    """
    from PIL import Image

    tmp_dir = tempfile.mkdtemp(prefix="md2pdf_")

    def _process_image(match):
        alt = match.group(1)
        img_path = match.group(2)
        src = (
            Path(img_path)
            if Path(img_path).is_absolute()
            else Path(report_dir) / img_path
        )
        if not src.exists():
            return match.group(0)

        try:
            img = Image.open(src)
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            rel_path = Path(img_path)
            dest = Path(tmp_dir) / rel_path.with_suffix(".jpg")
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, "JPEG", quality=quality, optimize=True)
            return f"![{alt}]({rel_path.with_suffix('.jpg')})"
        except Exception as e:
            logger.warning(f"Failed to process image {src}: {e}")

    modified_md = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _process_image, md_content)
    return modified_md, tmp_dir


def benchmark_md_to_pdf(md_content: str, report_dir: str) -> bytes | None:
    """Convert markdown to PDF with compressed images. Returns bytes or None."""
    try:
        from markdown_pdf import MarkdownPdf, Section
    except ImportError:
        logger.error(
            "markdown-pdf not installed. Install with: pip install markdown-pdf"
        )
        return None

    report_dir_abs = str(Path(report_dir).resolve())
    tmp_dir = None
    tmp_path = None
    try:
        modified_md, tmp_dir = _compress_images_to_tmpdir(md_content, report_dir_abs)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        pdf = MarkdownPdf(toc_level=0, optimize=True)
        pdf.add_section(Section(modified_md, toc=False, root=tmp_dir))
        pdf.save(tmp_path)

        with open(tmp_path, "rb") as f:
            return f.read()
    except Exception as e:
        logger.error(f"PDF conversion failed: {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def read_pdf_bytes(path: str | Path) -> bytes | None:
    """Read a PDF file and return its raw bytes."""
    p = Path(path) if Path(path).is_absolute() else PROJECT_ROOT / path
    if not p.exists():
        logger.warning(f"PDF file not found: {p}")
        return None
    with open(p, "rb") as f:
        return f.read()


def load_report_as_pdf(file_path: Path) -> bytes | None:
    """Load a report (.pdf or .md) as PDF bytes."""
    if file_path.suffix.lower() == ".pdf":
        return read_pdf_bytes(file_path)
    elif file_path.suffix.lower() == ".md":
        md_content = file_path.read_text(encoding="utf-8")
        pdf_bytes = benchmark_md_to_pdf(md_content, str(file_path.parent))
        if pdf_bytes is None:
            logger.warning(f"Failed to convert {file_path} to PDF, skipping")
        return pdf_bytes
    else:
        logger.warning(f"Unsupported file type: {file_path.suffix}")
        return None
