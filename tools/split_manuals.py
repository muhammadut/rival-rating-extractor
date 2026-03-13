#!/usr/bin/env python3
"""
split_manuals.py — Split large rating manual PDFs into ≤100-page chunks.

Phase 3 tool for Citations API path. Splits PDFs that exceed Claude's 100-page
document limit into smaller chunks, producing a manifest.json with chunk metadata.

Usage:
    python split_manuals.py --pdf <path> --output <dir> --slug <slug> [--max-pages 100]

Requires: PyMuPDF (fitz)
    pip install PyMuPDF

Status: Phase 3 — placeholder. Core logic TBD.
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(
        description="Split large PDFs into ≤100-page chunks for Citations API"
    )
    parser.add_argument("--pdf", required=True, help="Path to the PDF file")
    parser.add_argument("--output", required=True, help="Output directory for chunks")
    parser.add_argument("--slug", required=True, help="Manual slug")
    parser.add_argument("--max-pages", type=int, default=100, help="Max pages per chunk")
    args = parser.parse_args()

    print("split_manuals.py is a Phase 3 placeholder. Not yet implemented.")
    print("For now, use Claude's Read tool with the pages parameter for targeted reading.")
    sys.exit(0)


if __name__ == "__main__":
    main()
