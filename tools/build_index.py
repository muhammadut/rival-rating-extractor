#!/usr/bin/env python3
"""
build_index.py — Build TOC / page index from rating manual PDFs.

Reads the first N pages of each PDF, extracts table of contents structure,
and produces a toc.yaml file with section-to-page mappings and keyword index.

Usage:
    python build_index.py --pdf <path> --output <dir> --slug <slug> [--pages 10]

Requires: PyMuPDF (fitz)
    pip install PyMuPDF

If PyMuPDF is not available, this script will exit with a clear error.
The /re-init and /re-index skills fall back to Claude's Read tool for TOC extraction.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print(
        "ERROR: PyMuPDF (fitz) is required. Install with: pip install PyMuPDF",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None  # Will use JSON fallback or manual YAML writing


# ── Stop words for keyword extraction ──────────────────────────────────

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "to", "was", "were", "will", "with", "this", "but", "not",
    "all", "any", "can", "had", "her", "his", "how", "may", "no",
    "our", "out", "per", "she", "than", "them", "then", "they", "too",
    "two", "way", "who", "also", "been", "have", "each", "make",
    "like", "long", "many", "over", "such", "take", "into", "year",
    "your", "some", "could", "other", "about", "which", "their",
    "would", "there", "these", "more", "upon", "what", "when",
    "section", "page", "table", "appendix",
}

# ── Insurance domain synonyms ─────────────────────────────────────────

SYNONYMS = {
    "discount": ["credit"],
    "surcharge": ["loading"],
    "premium": ["rate"],
    "territory": ["territorial", "zone"],
    "territorial": ["territory", "zone"],
    "deductible": ["ded"],
    "liability": ["liab"],
    "vehicle": ["auto", "car"],
    "multi-vehicle": ["multi vehicle", "multivehicle"],
    "endorsement": ["endorsment"],  # common misspelling
}


def get_page_count(pdf_path: str) -> int:
    """Return total page count of a PDF."""
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count


def extract_text_from_pages(pdf_path: str, start: int, end: int) -> list[dict]:
    """Extract text from a range of pages (0-indexed internally, 1-indexed externally)."""
    doc = fitz.open(pdf_path)
    pages = []
    for i in range(start - 1, min(end, len(doc))):
        page = doc[i]
        text = page.get_text("text")
        pages.append({
            "page_number": i + 1,
            "text": text,
        })
    doc.close()
    return pages


def find_toc_entries(pages: list[dict]) -> list[dict]:
    """
    Attempt to extract TOC entries from the first few pages.

    Looks for patterns like:
      Section Name ......... 42
      Section Name           42
      Section Name . . . . . 42
      4.1 Section Name       42
    """
    entries = []

    # Pattern: text followed by dots/spaces and a page number
    toc_pattern = re.compile(
        r"^(.+?)\s*[.\s·]{3,}\s*(\d{1,3})\s*$", re.MULTILINE
    )

    # Pattern: numbered section with page number
    numbered_pattern = re.compile(
        r"^(\d+(?:\.\d+)*\.?\s+.+?)\s{2,}(\d{1,3})\s*$", re.MULTILINE
    )

    for page_data in pages:
        text = page_data["text"]

        # Try dotted leader pattern
        for match in toc_pattern.finditer(text):
            name = match.group(1).strip()
            page_num = int(match.group(2))
            if page_num > 0 and len(name) > 2:
                entries.append({"name": name, "start_page": page_num})

        # Try numbered section pattern
        if not entries:
            for match in numbered_pattern.finditer(text):
                name = match.group(1).strip()
                page_num = int(match.group(2))
                if page_num > 0 and len(name) > 2:
                    entries.append({"name": name, "start_page": page_num})

    # Deduplicate by name
    seen = set()
    unique = []
    for entry in entries:
        key = entry["name"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(entry)

    # Sort by page number
    unique.sort(key=lambda e: e["start_page"])

    return unique


def compute_page_ranges(entries: list[dict], total_pages: int) -> list[dict]:
    """Convert start pages to [start, end] ranges."""
    sections = []
    for i, entry in enumerate(entries):
        start = entry["start_page"]
        if i + 1 < len(entries):
            end = entries[i + 1]["start_page"] - 1
        else:
            end = total_pages
        # Ensure valid range
        end = max(end, start)
        sections.append({
            "name": entry["name"],
            "pages": [start, end],
        })
    return sections


def build_keyword_index(sections: list[dict]) -> dict:
    """Build keyword → [start, end] mapping from section names."""
    keywords = {}

    for section in sections:
        name = section["name"]
        pages = section["pages"]

        # Tokenize
        tokens = re.split(r"[\s/\-–—,;:()\[\]]+", name.lower())
        tokens = [t.strip(".!?'\"") for t in tokens if t.strip(".!?'\"")]

        # Filter stop words and short tokens
        meaningful = [t for t in tokens if t not in STOP_WORDS and len(t) > 1]

        for token in meaningful:
            if token not in keywords:
                keywords[token] = pages
            else:
                # Expand range to cover both sections
                existing = keywords[token]
                keywords[token] = [
                    min(existing[0], pages[0]),
                    max(existing[1], pages[1]),
                ]

            # Add synonyms
            for syn in SYNONYMS.get(token, []):
                if syn not in keywords:
                    keywords[syn] = pages
                else:
                    existing = keywords[syn]
                    keywords[syn] = [
                        min(existing[0], pages[0]),
                        max(existing[1], pages[1]),
                    ]

        # Also add multi-word phrases (2-grams)
        for i in range(len(meaningful) - 1):
            phrase = f"{meaningful[i]} {meaningful[i+1]}"
            if phrase not in keywords:
                keywords[phrase] = pages

    return dict(sorted(keywords.items()))


def write_toc_yaml(toc_data: dict, output_path: str):
    """Write toc.yaml — uses PyYAML if available, otherwise manual formatting."""
    if yaml is not None:
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(
                toc_data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=120,
            )
    else:
        # Manual YAML writing as fallback
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f'manual_slug: "{toc_data["manual_slug"]}"\n')
            f.write(f'title: "{toc_data["title"]}"\n')
            f.write(f'source_file: "{toc_data["source_file"]}"\n')
            f.write(f'source_path: "{toc_data["source_path"]}"\n')
            f.write(f'total_pages: {toc_data["total_pages"]}\n')
            f.write(f'indexed_at: "{toc_data["indexed_at"]}"\n')

            f.write("sections:\n")
            for sec in toc_data["sections"]:
                name_escaped = sec["name"].replace('"', '\\"')
                f.write(f'  - name: "{name_escaped}"\n')
                f.write(f"    pages: [{sec['pages'][0]}, {sec['pages'][1]}]\n")

            f.write("keyword_index:\n")
            for kw, pages in toc_data["keyword_index"].items():
                kw_escaped = kw.replace('"', '\\"')
                f.write(f'  "{kw_escaped}": [{pages[0]}, {pages[1]}]\n')


def main():
    parser = argparse.ArgumentParser(
        description="Build TOC/page index from a rating manual PDF"
    )
    parser.add_argument("--pdf", required=True, help="Path to the PDF file")
    parser.add_argument("--output", required=True, help="Output directory for toc.yaml")
    parser.add_argument("--slug", required=True, help="Manual slug (kebab-case identifier)")
    parser.add_argument(
        "--pages", type=int, default=10,
        help="Number of initial pages to scan for TOC (default: 10)"
    )
    parser.add_argument(
        "--title", default=None,
        help="Manual title (if not provided, derived from filename)"
    )
    args = parser.parse_args()

    pdf_path = os.path.abspath(args.pdf)
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    # Get page count
    total_pages = get_page_count(pdf_path)
    print(f"PDF: {os.path.basename(pdf_path)} ({total_pages} pages)")

    # Extract text from first N pages
    print(f"Reading first {args.pages} pages for TOC extraction...")
    pages = extract_text_from_pages(pdf_path, 1, args.pages)

    # Find TOC entries
    entries = find_toc_entries(pages)
    print(f"Found {len(entries)} TOC entries")

    if not entries:
        print("WARNING: No TOC entries found. Try increasing --pages or check PDF format.")
        # Create a minimal index with just the full document
        entries = [{"name": "Full Document", "start_page": 1}]

    # Compute page ranges
    sections = compute_page_ranges(entries, total_pages)

    # Build keyword index
    keyword_index = build_keyword_index(sections)
    print(f"Built keyword index with {len(keyword_index)} entries")

    # Derive title if not provided
    title = args.title or os.path.splitext(os.path.basename(pdf_path))[0]

    # Build toc.yaml data
    toc_data = {
        "manual_slug": args.slug,
        "title": title,
        "source_file": os.path.basename(pdf_path),
        "source_path": pdf_path,
        "total_pages": total_pages,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
        "keyword_index": keyword_index,
    }

    # Write output
    output_path = os.path.join(output_dir, "toc.yaml")
    write_toc_yaml(toc_data, output_path)
    print(f"Written: {output_path}")

    # Also write a manifest.json with metadata
    manifest = {
        "slug": args.slug,
        "pdf_path": pdf_path,
        "total_pages": total_pages,
        "sections_count": len(sections),
        "keywords_count": len(keyword_index),
        "indexed_at": toc_data["indexed_at"],
        "chunks": [],  # Phase 3: populated by split_manuals.py
    }
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Written: {manifest_path}")


if __name__ == "__main__":
    main()
