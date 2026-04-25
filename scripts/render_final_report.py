"""Render memo/FINAL_REPORT.md to memo/FINAL_REPORT.pdf with professional styling."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import markdown
from weasyprint import CSS, HTML

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "memo" / "FINAL_REPORT.md"
OUT = REPO / "memo" / "FINAL_REPORT.pdf"


CSS_TEMPLATE = """
@page {
    size: Letter;
    margin: 0.75in 0.85in 1.0in 0.85in;
    @bottom-left {
        content: "Conversion Engine — Final Submission";
        font-family: 'Helvetica', 'Arial', sans-serif;
        font-size: 8.5pt;
        color: #6b6b6b;
    }
    @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-family: 'Helvetica', 'Arial', sans-serif;
        font-size: 8.5pt;
        color: #6b6b6b;
    }
}

body {
    font-family: 'Helvetica', 'Arial', sans-serif;
    font-size: 9.5pt;
    line-height: 1.45;
    color: #1f1f1f;
}

h1 {
    font-size: 22pt;
    color: #0a2540;
    border-bottom: 2.5px solid #0a2540;
    padding-bottom: 8px;
    margin-top: 0;
    margin-bottom: 20px;
    line-height: 1.2;
}

h2 {
    font-size: 14pt;
    color: #0a2540;
    margin-top: 22px;
    margin-bottom: 10px;
    border-bottom: 1px solid #d0d7e2;
    padding-bottom: 4px;
    page-break-after: avoid;
}

h3 {
    font-size: 11.5pt;
    color: #16334d;
    margin-top: 16px;
    margin-bottom: 6px;
    page-break-after: avoid;
}

h4 {
    font-size: 10.5pt;
    color: #2a4d6c;
    margin-top: 10px;
    margin-bottom: 4px;
    page-break-after: avoid;
}

p {
    margin: 6px 0 8px 0;
    text-align: left;
}

ul, ol {
    margin: 4px 0 8px 0;
    padding-left: 22px;
}

li {
    margin: 2px 0;
}

strong { color: #0a2540; }

code {
    font-family: 'Menlo', 'Consolas', 'Courier New', monospace;
    font-size: 8.5pt;
    background: #f4f5f7;
    padding: 1px 4px;
    border-radius: 3px;
    color: #b8364a;
}

pre {
    background: #f4f5f7;
    border-left: 3px solid #0a2540;
    padding: 8px 10px;
    font-family: 'Menlo', 'Consolas', 'Courier New', monospace;
    font-size: 8.0pt;
    line-height: 1.35;
    overflow: hidden;
    page-break-inside: avoid;
    color: #1f1f1f;
    border-radius: 3px;
    margin: 8px 0;
}

pre code {
    background: transparent;
    padding: 0;
    color: inherit;
    font-size: inherit;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 8px 0 12px 0;
    font-size: 9pt;
    page-break-inside: avoid;
}

th {
    background: #0a2540;
    color: #ffffff;
    text-align: left;
    padding: 5px 8px;
    font-weight: 600;
    border: 1px solid #0a2540;
}

td {
    padding: 4px 8px;
    border: 1px solid #d0d7e2;
    vertical-align: top;
}

tbody tr:nth-child(even) td {
    background: #f7f9fc;
}

blockquote {
    border-left: 3px solid #c9a13b;
    background: #fdf8ec;
    padding: 6px 12px;
    margin: 8px 0;
    color: #4a4031;
    font-style: italic;
}

hr {
    border: none;
    border-top: 1px solid #d0d7e2;
    margin: 18px 0;
}

a {
    color: #0a66c2;
    text-decoration: none;
}

/* Section title page-break helpers */
h1, h2 {
    page-break-after: avoid;
}

table, pre, blockquote {
    page-break-inside: avoid;
}
"""


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: missing {SRC}", file=sys.stderr)
        return 2

    md_text = SRC.read_text()
    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists"],
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Conversion Engine — Final Submission Report</title>
</head>
<body>
{html_body}
</body>
</html>
"""

    HTML(string=html_doc).write_pdf(
        str(OUT),
        stylesheets=[CSS(string=CSS_TEMPLATE)],
    )
    size = OUT.stat().st_size
    print(f"OK  rendered {OUT} ({size:,} bytes) at {dt.datetime.now().isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
