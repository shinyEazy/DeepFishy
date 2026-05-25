"""Helpers for assembling final report output from section drafts."""

import glob
import os
import re
from typing import Any

from deepfishy.shared.logging import logger


def _split_section_references(section_markdown: str) -> tuple[str, str]:
    match = re.search(
        r"(?im)^\s*###\s+references\s*$", section_markdown or "", flags=re.MULTILINE
    )
    if not match:
        return (section_markdown or "").strip(), ""
    body = (section_markdown or "")[: match.start()].rstrip()
    references = (section_markdown or "")[match.end() :].strip()
    return body, references


def _parse_reference_entries(reference_block: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for raw_line in (reference_block or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        local_id: int | None = None
        bracketed_match = re.match(r"^\[(\d+)\]\s*", line)
        ordered_match = re.match(r"^(\d+)\.\s*", line)
        if bracketed_match:
            local_id = int(bracketed_match.group(1))
            line = line[bracketed_match.end() :].strip()
        elif ordered_match:
            local_id = int(ordered_match.group(1))
            line = line[ordered_match.end() :].strip()

        url = ""
        title = line

        markdown_url_match = re.search(r"\[([^\]]+)\]\((https?://[^)]+)\)", line)
        if markdown_url_match:
            url = markdown_url_match.group(2).strip()
            title_prefix = line[: markdown_url_match.start()].strip()
            title = (
                title_prefix.rstrip(":").strip()
                or markdown_url_match.group(1).strip()
                or url
            )
        else:
            plain_url_match = re.search(r"(https?://\S+?)(?=[.,;)]*(?:\s|$))", line)
            if plain_url_match:
                url = plain_url_match.group(1)
                title = line[: plain_url_match.start()].rstrip(": ").strip() or url
            else:
                title = line.rstrip(":").strip()

        if local_id is None and not title and not url:
            continue

        entries.append(
            {
                "local_id": local_id,
                "title": title or url or "Unknown source",
                "url": url,
            }
        )

    return entries


def _reference_key(reference: dict[str, Any]) -> str:
    url = str(reference.get("url", "")).strip().lower()
    if url:
        return f"url::{url}"
    title = re.sub(r"\s+", " ", str(reference.get("title", "")).strip().lower())
    return f"title::{title}"


def _reference_title_score(title: str) -> tuple[int, int]:
    cleaned = str(title or "").strip()
    if not cleaned:
        return (0, 0)
    generic = cleaned.lower() in {"unknown source", "source", "nguon", "nguồn"}
    looks_like_url = cleaned.startswith("http://") or cleaned.startswith("https://")
    return (
        0 if generic or looks_like_url else 1,
        len(cleaned),
    )


def _renumber_inline_citations(
    section_body: str, local_to_global: dict[int, int]
) -> str:
    if not local_to_global:
        return section_body

    def replace_match(match: re.Match[str]) -> str:
        raw_numbers = match.group(1)
        numbers = [part.strip() for part in raw_numbers.split(",") if part.strip()]
        remapped: list[str] = []
        seen = set()
        for number in numbers:
            try:
                mapped = int(local_to_global.get(int(number), int(number)))
            except ValueError:
                return match.group(0)
            if mapped in seen:
                continue
            seen.add(mapped)
            remapped.append(str(mapped))

        if not remapped:
            return match.group(0)
        return f"[{', '.join(remapped)}]"

    return re.sub(r"\[(\d+(?:\s*,\s*\d+)*)\](?!\()", replace_match, section_body)


def normalize_report_references(
    sections: list[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    normalized_sections: list[str] = []
    global_references: list[dict[str, Any]] = []
    reference_key_to_index: dict[str, int] = {}

    for section in sections:
        body, reference_block = _split_section_references(section)
        local_references = _parse_reference_entries(reference_block)
        local_to_global: dict[int, int] = {}

        for reference in local_references:
            key = _reference_key(reference)
            if key in {"url::", "title::"}:
                continue

            global_index = reference_key_to_index.get(key)
            if global_index is None:
                global_index = len(global_references) + 1
                reference_key_to_index[key] = global_index
                global_references.append(
                    {
                        "index": global_index,
                        "title": str(reference.get("title", "")).strip()
                        or "Unknown source",
                        "url": str(reference.get("url", "")).strip(),
                    }
                )
            else:
                existing = global_references[global_index - 1]
                current_title = str(reference.get("title", "")).strip()
                if _reference_title_score(current_title) > _reference_title_score(
                    str(existing.get("title", "")).strip()
                ):
                    existing["title"] = current_title
                if not str(existing.get("url", "")).strip():
                    existing["url"] = str(reference.get("url", "")).strip()

            local_id = reference.get("local_id")
            if isinstance(local_id, int):
                local_to_global[local_id] = global_index

        normalized_sections.append(
            _renumber_inline_citations(body.strip(), local_to_global).strip()
        )

    return normalized_sections, global_references


def concatenate_drafts_to_final(workspace_path: str) -> str:
    """Concatenate section drafts into one final markdown file."""
    pattern = os.path.join(workspace_path, "section_*", "draft.md")
    draft_files = glob.glob(pattern)

    if not draft_files:
        logger.warning(f"No draft files found matching pattern: {pattern}")
        return ""

    def extract_section_num(path: str) -> int:
        match = re.search(r"section_(\d+)", path)
        return int(match.group(1)) if match else 0

    draft_files.sort(key=extract_section_num)

    combined_content: list[str] = []
    for draft_path in draft_files:
        section_name = os.path.basename(os.path.dirname(draft_path))
        logger.info(f"Reading draft from {section_name}")
        try:
            with open(draft_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    combined_content.append(content)
        except (IOError, FileNotFoundError) as exc:
            logger.warning(f"Failed to read {draft_path}: {exc}")

    normalized_sections, global_references = normalize_report_references(
        combined_content
    )

    reference_lines: list[str] = []
    if global_references:
        reference_lines.extend(["## References", ""])
        for reference in global_references:
            url = str(reference.get("url", "")).strip()
            title = str(reference.get("title", "")).strip() or url or "Unknown source"
            index = int(reference.get("index", 0) or 0)
            if url:
                reference_lines.append(f"[{index}] {title}: [{url}]({url})")
            else:
                reference_lines.append(f"[{index}] {title}")

    final_path = os.path.join(workspace_path, "final.md")
    final_parts = [part for part in normalized_sections if part.strip()]
    if reference_lines:
        final_parts.append("\n".join(reference_lines).strip())
    final_content = "\n\n---\n\n".join(final_parts)

    image_path_pattern = re.compile(r"outputs/\d{8}_\d{6}/images/")
    final_content = image_path_pattern.sub("./images/", final_content)

    with open(final_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    logger.info(f"Created final.md with {len(draft_files)} sections at {final_path}")
    return final_path
