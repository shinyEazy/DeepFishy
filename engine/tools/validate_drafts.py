"""Validation utilities for report draft output."""

import os
import re
import glob
from typing import Dict, List

from core.logging import logger


def validate_drafts(workspace_path: str) -> Dict[str, object]:
    """Validate section drafts before final concatenation.

    Checks each section_*/draft.md for:
    - Non-empty content
    - Presence of expected markdown structure (headers)
    - Valid image references (files exist)
    - Minimum content length

    Args:
        workspace_path: Path to the workspace directory (e.g., outputs/20260206_081222)

    Returns:
        Dictionary with validation results:
        - valid: bool — all checks passed
        - sections: list of per-section results
        - warnings: list of non-critical warnings
        - errors: list of critical errors
    """
    pattern = os.path.join(workspace_path, "section_*", "draft.md")
    draft_files = sorted(glob.glob(pattern))

    if not draft_files:
        return {
            "valid": False,
            "sections": [],
            "warnings": [],
            "errors": ["No draft files found"],
        }

    sections: List[Dict] = []
    warnings: List[str] = []
    errors: List[str] = []

    for draft_path in draft_files:
        section_name = os.path.basename(os.path.dirname(draft_path))
        section_result: Dict[str, object] = {
            "section": section_name,
            "path": draft_path,
            "valid": True,
            "issues": [],
        }

        try:
            with open(draft_path, "r", encoding="utf-8") as f:
                content = f.read()
        except (IOError, FileNotFoundError) as e:
            section_result["valid"] = False
            section_result["issues"].append(f"Cannot read file: {e}")
            errors.append(f"{section_name}: Cannot read draft.md")
            sections.append(section_result)
            continue

        # Check 1: Non-empty content
        stripped = content.strip()
        if not stripped:
            section_result["valid"] = False
            section_result["issues"].append("Draft is empty")
            errors.append(f"{section_name}: Draft is empty")
            sections.append(section_result)
            continue

        # Check 2: Minimum content length (at least 200 chars for a meaningful section)
        if len(stripped) < 200:
            section_result["issues"].append(
                f"Draft is very short ({len(stripped)} chars)"
            )
            warnings.append(
                f"{section_name}: Draft is very short ({len(stripped)} chars)"
            )

        # Check 3: Has at least one markdown header
        headers = re.findall(r"^#{1,4}\s+.+", content, re.MULTILINE)
        if not headers:
            section_result["issues"].append("No markdown headers found")
            warnings.append(f"{section_name}: No markdown headers found")

        # Check 4: Validate image references
        image_refs = re.findall(r"!\[.*?\]\((.*?)\)", content)
        for img_ref in image_refs:
            # Resolve relative paths
            if img_ref.startswith("./"):
                img_path = os.path.join(workspace_path, img_ref[2:])
            elif img_ref.startswith("/"):
                img_path = os.path.join(workspace_path, img_ref[1:])
            elif not os.path.isabs(img_ref):
                img_path = os.path.join(workspace_path, img_ref)
            else:
                img_path = img_ref

            if not os.path.exists(img_path):
                section_result["issues"].append(f"Image not found: {img_ref}")
                warnings.append(f"{section_name}: Image not found: {img_ref}")

        sections.append(section_result)

    all_valid = len(errors) == 0

    result = {
        "valid": all_valid,
        "sections": sections,
        "warnings": warnings,
        "errors": errors,
        "total_sections": len(sections),
        "valid_sections": sum(1 for s in sections if s["valid"]),
    }

    if all_valid:
        logger.info(
            f"✅ Draft validation passed: {len(sections)} sections, "
            f"{len(warnings)} warnings"
        )
    else:
        logger.warning(
            f"⚠️ Draft validation failed: {len(errors)} errors, "
            f"{len(warnings)} warnings"
        )

    return result
