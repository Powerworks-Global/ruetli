#!/usr/bin/env python3
"""Build publication-grade Powerworks_Report.pdf from technical_report.md (HackApertus Track 2B).

Ensures strict compliance with HackApertus submission requirements:
- PDF format
- Exactly <= 6 pages
- Named Powerworks_Report.pdf in track_2b/
"""

import subprocess
import sys
from pathlib import Path

TRACK_ROOT = Path(__file__).resolve().parents[1]
MD_PATH = TRACK_ROOT / "technical_report.md"
PDF_PATH = TRACK_ROOT / "Powerworks_Report.pdf"
HTML_TEMP = Path("/tmp/ruetli_report.html")

CSS = """
@page {
    size: A4;
    margin: 1.6cm 1.5cm 1.6cm 1.5cm;
    @bottom-right {
        content: counter(page) " / " counter(pages);
        font-size: 8pt;
        color: #57606a;
    }
}
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 9.2pt;
    line-height: 1.35;
    color: #1f2328;
    background-color: #ffffff;
}
h1 {
    font-size: 16pt;
    font-weight: 700;
    margin-top: 0;
    margin-bottom: 6pt;
    color: #092540;
    border-bottom: 2pt solid #0969da;
    padding-bottom: 4pt;
}
h2 {
    font-size: 11.5pt;
    font-weight: 600;
    margin-top: 9pt;
    margin-bottom: 3pt;
    color: #092540;
    border-bottom: 0.75pt solid #d0d7de;
    padding-bottom: 2pt;
    page-break-after: avoid;
}
h3 {
    font-size: 9.8pt;
    font-weight: 600;
    margin-top: 7pt;
    margin-bottom: 2pt;
    color: #24292f;
    page-break-after: avoid;
}
p {
    margin-top: 0;
    margin-bottom: 4pt;
    text-align: justify;
}
ul, ol {
    margin-top: 0;
    margin-bottom: 4pt;
    padding-left: 16pt;
}
li {
    margin-bottom: 1.5pt;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin-top: 4pt;
    margin-bottom: 6pt;
    font-size: 8.2pt;
    page-break-inside: avoid;
}
th, td {
    border: 0.5pt solid #d0d7de;
    padding: 3pt 5pt;
    text-align: left;
    vertical-align: top;
}
th {
    background-color: #f6f8fa;
    font-weight: 600;
    color: #1f2328;
}
tr:nth-child(even) td {
    background-color: #fcfcfc;
}
pre {
    background-color: #f6f8fa;
    border: 0.5pt solid #d0d7de;
    border-radius: 3pt;
    padding: 4pt 6pt;
    font-size: 7.2pt;
    line-height: 1.2;
    margin-top: 3pt;
    margin-bottom: 5pt;
    page-break-inside: avoid;
    overflow-x: hidden;
}
code {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    font-size: 8.2pt;
    background-color: #f6f8fa;
    padding: 1pt 3pt;
    border-radius: 2pt;
}
pre code {
    background-color: transparent;
    padding: 0;
    font-size: 7.2pt;
}
blockquote {
    margin: 3pt 0;
    padding: 2pt 8pt;
    border-left: 2.5pt solid #0969da;
    background-color: #f6f8fa;
    color: #57606a;
    font-style: italic;
}
hr {
    border: none;
    border-top: 0.5pt solid #d0d7de;
    margin: 6pt 0;
}
strong {
    color: #092540;
}
"""


def main():
    css_temp = Path("/tmp/ruetli_style.css")
    css_temp.write_text(CSS, encoding="utf-8")

    print(f"1. Converting {MD_PATH.name} to standalone HTML with Pandoc...")
    cmd_pandoc = [
        "pandoc",
        str(MD_PATH),
        "-s",
        f"--css={css_temp}",
        "-o",
        str(HTML_TEMP),
    ]
    subprocess.run(cmd_pandoc, check=True)

    print(f"2. Rendering PDF with Chromium to {PDF_PATH.name}...")
    cmd_chrome = [
        "chromium-browser",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--print-to-pdf={PDF_PATH}",
        str(HTML_TEMP),
    ]
    subprocess.run(cmd_chrome, check=True)

    try:
        import pypdf
        reader = pypdf.PdfReader(str(PDF_PATH))
        pages = len(reader.pages)
        print(f"3. Verification: PDF generated successfully with {pages} pages.")
        if pages > 6:
            print(f"WARNING: Page count ({pages}) exceeds the HackApertus 6-page limit!", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"SUCCESS: Page count ({pages}) satisfies the strict <= 6-page limit.")
    except ImportError:
        print("pypdf not available for page check, file written to:", PDF_PATH)


if __name__ == "__main__":
    main()
