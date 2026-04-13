from deepfishy.features.reports.application.finalize_report import (
    normalize_report_references,
)


def test_normalize_report_references_merges_duplicate_references() -> None:
    sections = [
        "## A\nBody [1]\n\n### References\n[1] Alpha: https://example.com/a",
        "## B\nBody [1]\n\n### References\n[1] Alpha: https://example.com/a",
    ]

    normalized_sections, references = normalize_report_references(sections)

    assert len(normalized_sections) == 2
    assert normalized_sections[0] == "## A\nBody [1]"
    assert normalized_sections[1] == "## B\nBody [1]"
    assert len(references) == 1
    assert references[0]["index"] == 1
    assert references[0]["url"] == "https://example.com/a"
