"""Shared HTML and CSS builders for PDF report rendering."""

import re

import markdown


def _slugify(value: str, separator: str) -> str:
    normalized = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_-]+", separator, normalized).strip(separator)


def build_pdf_html(md_content: str) -> str:
    """Render markdown into a styled HTML document with a clickable TOC."""
    md = markdown.Markdown(
        extensions=["extra", "tables", "fenced_code", "toc", "attr_list"],
        extension_configs={
            "toc": {
                "permalink": False,
                "slugify": _slugify,
                "toc_depth": "2-4",
            }
        },
    )

    body_html = md.convert(md_content)
    toc_html = md.toc if getattr(md, "toc_tokens", None) else ""

    toc_section = ""
    if toc_html:
        toc_section = f"""
        <section class="toc-page">
            <h1>Table of Contents</h1>
            <nav class="toc" role="doc-toc">
                {toc_html}
            </nav>
        </section>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="utf-8">
        <title>Financial Report</title>
    </head>
    <body>
        {toc_section}
        <main class="document-content">
            {body_html}
        </main>
    </body>
    </html>
    """


def build_pdf_stylesheet() -> str:
    """Return the shared CSS used for report-style PDF output."""
    return """
    @page {
        margin: 2cm 1.8cm 2.2cm;
        size: A4;
        @top-center {
            content: "";
            display: block;
            width: 100%;
            border-bottom: 2px solid #1f4e8c;
            margin-top: 0.28cm;
        }
        @bottom-center {
            content: "";
            display: block;
            width: 100%;
            border-top: 2px solid #1f4e8c;
            margin-bottom: 0.28cm;
        }
        @bottom-right {
            content: counter(page);
            font-family: "Noto Serif", "DejaVu Serif", "Times New Roman", serif;
            font-size: 10pt;
            font-weight: 700;
            color: #1f4e8c;
        }
    }

    html {
        color: #333;
    }

    body {
        font-family: "Noto Serif", "DejaVu Serif", "Times New Roman", serif;
        font-size: 12pt;
        line-height: 1.7;
        color: #333;
        text-align: justify;
        hyphens: auto;
    }

    .toc-page {
        page-break-after: always;
    }

    .toc-page h1 {
        margin-top: 0;
    }

    .toc {
        font-size: 11pt;
        line-height: 1.5;
    }

    .toc ul {
        list-style: none;
        margin: 0.4em 0 0.4em 0;
        padding-left: 0;
    }

    .toc ul ul {
        padding-left: 1.2em;
    }

    .toc li {
        margin: 0.25em 0;
    }

    .toc a {
        color: #1f4e8c;
        text-decoration: none;
    }

    .toc a::after {
        content: leader(".") target-counter(attr(href), page);
        color: #999;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: "Noto Serif", "DejaVu Serif", "Times New Roman", serif;
        color: #1a1a1a;
        margin-top: 1.15em;
        margin-bottom: 0.45em;
        line-height: 1.25;
        break-after: avoid;
    }

    h1 {
        font-size: 22pt;
        color: #163b68;
        border-bottom: 2px solid #2d69b3;
        padding-bottom: 10px;
        bookmark-level: 1;
        page-break-after: avoid;
    }

    h2 {
        font-size: 17pt;
        margin-top: 1.4em;
        color: #1f4e8c;
        border-left: 5px solid #4f86c6;
        padding-left: 0.55em;
        background: linear-gradient(to right, rgba(79, 134, 198, 0.12), rgba(79, 134, 198, 0));
        padding-top: 0.18em;
        padding-bottom: 0.18em;
        bookmark-level: 2;
    }

    h3 {
        font-size: 14pt;
        color: #2f5f9c;
        border-bottom: 1px solid #b9cde6;
        padding-bottom: 0.15em;
        bookmark-level: 3;
    }

    h4, h5, h6 {
        color: #35557b;
        bookmark-level: 4;
    }

    p, li {
        orphans: 3;
        widows: 3;
    }

    hr {
        display: none;
    }

    a {
        color: #24558f;
        text-decoration: none;
    }

    code {
        font-family: "Noto Sans Mono", "DejaVu Sans Mono", monospace;
        background-color: #f4f4f4;
        padding: 2px 4px;
        border-radius: 4px;
        font-size: 0.92em;
    }

    pre {
        background-color: #f4f4f4;
        padding: 1em;
        border-radius: 8px;
        white-space: pre-wrap;
        word-wrap: break-word;
        overflow-wrap: anywhere;
    }

    pre, table, blockquote, img {
        break-inside: avoid;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        margin: 1em 0;
        font-size: 10.5pt;
    }

    th, td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
        vertical-align: top;
    }

    th {
        background-color: #edf4fb;
    }

    img {
        max-width: 100%;
    }
    """
