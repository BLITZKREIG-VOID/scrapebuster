#!/usr/bin/env python3
"""Build the clean control dataset straight from origin HTML (master plan §9).

Reads demo_site/pages/*.html (never through the edge, so no canaries can be present),
extracts the <main> text with stdlib html.parser and writes one dataset-contract record
per page: {"url","fetched_at","title","text"}. Block elements become paragraphs separated
by a blank line, matching the chunking used by the RAG index.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "blockquote", "tr", "div", "section", "article", "dd", "dt"}
SKIP_TAGS = {"script", "style", "template", "noscript"}


class MainTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.paragraphs: list[str] = []
        self.main_count = 0
        self._in_title = False
        self._main_depth = 0
        self._skip_depth = 0
        self._buf: list[str] = []

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        if text:
            self.paragraphs.append(text)
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag == "main":
            self.main_count += 1
            self._main_depth += 1
        elif self._main_depth and tag in SKIP_TAGS:
            self._skip_depth += 1
        elif self._main_depth and tag in BLOCK_TAGS:
            self._flush()
        elif self._main_depth and tag == "br":
            self._buf.append(" ")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "main" and self._main_depth:
            self._flush()
            self._main_depth -= 1
        elif self._main_depth and tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif self._main_depth and tag in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._main_depth and not self._skip_depth:
            self._buf.append(data)


def extract(html: str) -> tuple[str, str, int]:
    parser = MainTextExtractor()
    parser.feed(html)
    parser.close()
    return re.sub(r"\s+", " ", parser.title).strip(), "\n\n".join(parser.paragraphs), parser.main_count


def build(pages_dir: Path, out_path: Path) -> int:
    pages = sorted(pages_dir.glob("*.html"))
    if not pages:
        raise SystemExit(f"no *.html files in {pages_dir}")
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    records = []
    for page in pages:
        title, text, main_count = extract(page.read_text(encoding="utf-8"))
        if main_count != 1:
            raise SystemExit(f"{page}: expected exactly one <main>, found {main_count}")
        if not text:
            raise SystemExit(f"{page}: <main> has no text")
        rel = page.relative_to(REPO_ROOT) if page.is_relative_to(REPO_ROOT) else page
        records.append({"url": f"file://{rel.as_posix()}", "fetched_at": fetched_at, "title": title, "text": text})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(records)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pages", type=Path, default=REPO_ROOT / "demo_site" / "pages")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "control" / "control_clean.jsonl")
    args = ap.parse_args(argv)
    if not args.pages.is_dir():
        print(f"error: {args.pages} does not exist", file=sys.stderr)
        return 1
    count = build(args.pages.resolve(), args.out)
    print(f"wrote {count} records to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
