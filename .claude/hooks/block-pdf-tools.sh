#!/bin/bash
# block-pdf-tools.sh — Hard-block PDF extraction tools in rating-extractor
#
# This hook intercepts every Bash command and blocks any that try to use
# Python, pdftotext, PyMuPDF, or other external PDF tools.
#
# WHY: Sub-agents must use Claude's native Read tool for PDFs (multimodal).
# External parsers mangle complex insurance rate tables. The Read tool
# sees each page as an image — preserving formatting exactly.
#
# HOW: Exit code 2 = BLOCK the command. Stderr becomes feedback to Claude.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# If we can't parse the command, allow it (fail-open)
if [ -z "$COMMAND" ]; then
    exit 0
fi

# Block patterns: Python PDF libraries, text extraction tools, pip installs
# Case-insensitive match
if echo "$COMMAND" | grep -qiE '(pymupdf|pdftotext|pdf-parse|pdfjs|fitz\.|import fitz|pip install|pdf2text|tabula|camelot|docling|marker-pdf)'; then
    cat >&2 <<'EOF'
BLOCKED: External PDF tools are not allowed.

This plugin uses Claude's native Read tool for PDFs (multimodal visual input).
The Read tool sees each page as an image — it handles dense rate tables,
merged cells, and complex formatting better than any text parser.

Use instead:
  Read(file_path="path/to/file.pdf", pages="1-5")

Do NOT use Python, pdftotext, PyMuPDF, or any external PDF library.
EOF
    exit 2
fi

# Allow everything else
exit 0
