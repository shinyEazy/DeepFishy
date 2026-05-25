"""PDF conversion and loading helpers used by benchmark flows."""

import os
import re
import shutil
import tempfile
from pathlib import Path

from deepfishy.infra.config.paths import PROJECT_ROOT
from deepfishy.shared.logging import logger


def _normalize_image_paths(md_content: str, report_dir: str) -> str:
    """Rewrite image paths in markdown to be relative to the report directory."""
    report_dir_path = Path(report_dir).resolve()

    def _rewrite(match):
        alt = match.group(1)
        img_path = match.group(2)
        path = Path(img_path)

        if (
            path.is_absolute()
            or img_path.startswith("./")
            or img_path.startswith("../")
        ):
            return match.group(0)

        abs_from_root = (PROJECT_ROOT / path).resolve()
        if abs_from_root.exists():
            try:
                relative_path = abs_from_root.relative_to(report_dir_path)
                return f"![{alt}](./{relative_path.as_posix()})"
            except ValueError:
                return f"![{alt}]({abs_from_root.as_posix()})"

        return match.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _rewrite, md_content)


def _compress_images_to_tmpdir(
    md_content: str, report_dir: str, max_width: int = 1200, quality: int = 70
) -> tuple[str, str]:
    """Compress images referenced in markdown into a temporary directory."""
    from PIL import Image

    normalized_content = _normalize_image_paths(md_content, report_dir)
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
        except Exception as error:
            logger.warning(f"Failed to process image {src}: {error}")
            return match.group(0)

    modified_md = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)", _process_image, normalized_content
    )
    return modified_md, tmp_dir


def benchmark_md_to_pdf(md_content: str, report_dir: str) -> bytes | None:
    """Convert markdown to PDF with compressed images."""
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
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        pdf = MarkdownPdf(toc_level=0, optimize=True)
        pdf.add_section(Section(modified_md, toc=False, root=tmp_dir))
        pdf.save(tmp_path)

        with open(tmp_path, "rb") as file_handle:
            return file_handle.read()
    except Exception as error:
        logger.error(f"PDF conversion failed: {error}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def read_pdf_bytes(path: str | Path) -> bytes | None:
    """Read a PDF file and return its raw bytes."""
    resolved = Path(path) if Path(path).is_absolute() else PROJECT_ROOT / path
    if not resolved.exists():
        logger.warning(f"PDF file not found: {resolved}")
        return None
    with open(resolved, "rb") as file_handle:
        return file_handle.read()


def load_report_as_pdf(file_path: Path) -> bytes | None:
    """Load a report (.pdf or .md) as PDF bytes."""
    if file_path.suffix.lower() == ".pdf":
        return read_pdf_bytes(file_path)
    if file_path.suffix.lower() == ".md":
        md_content = file_path.read_text(encoding="utf-8")
        pdf_bytes = benchmark_md_to_pdf(md_content, str(file_path.parent))
        if pdf_bytes is None:
            logger.warning(f"Failed to convert {file_path} to PDF, skipping")
        return pdf_bytes

    logger.warning(f"Unsupported file type: {file_path.suffix}")
    return None


__all__ = ["benchmark_md_to_pdf", "load_report_as_pdf", "read_pdf_bytes"]
