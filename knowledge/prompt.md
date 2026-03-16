# Rating Radar — VM Bootstrap Prompt (HISTORICAL REFERENCE)

> **SUPERSEDED:** This document is the original bootstrap spec from the POC phase.
> The plugin architecture has changed significantly since this was written:
> - No Python PDF libraries (PyMuPDF, Docling, Marker) — uses Claude's native Read tool
> - No RAG pipeline, no vector stores, no chunking scripts
> - Orchestrator + sub-agent pattern for context management
> - See CLAUDE.md and skills/*.md for the current architecture.

Copy this entire file into your VM's Claude Code session to get up to speed instantly.

---

## What is Rating Radar?

A **Claude Code plugin** that answers questions about insurance rating manuals (PDFs). It's carrier-agnostic — swap the PDFs and it works for any insurance company.

**Origin story:** During testing of the IQ Update plugin (a Claude Code plugin for modifying VB.NET manufactured rating code), an AI agent removed an if/else line — "if renewal, do X" / else "do Y" — and reviewers couldn't tell if it was correct without checking the rating manual. This project automates that lookup.

## Use cases

1. **IQ Update support** — AI agents and devs query the manual to verify VB.NET rating code changes. E.g., "Is the genNow! discount 20% or 10% for renewal policies with business use?"
2. **Legacy-to-new-engine conversion** — Cross-reference VB.NET code against manuals when porting to a new rating engine.
3. **General Q&A** — Any developer question against any rating manual, with cited page references.

## Source documents

Three Portage Mutual / OMAP rating manuals for Ontario (629 pages total). Place them in `rating_manual/`:

| Manual | Pages | Filename |
|--------|------:|----------|
| OMAP Auto Rate Manual (Apr 2025) | 269 | `2025 04 01 Auto Rate Manual (posted 2025 01 24).pdf` |
| Portage Auto Pro Manual ON (Jan 2026) | 242 | `Auto Pro Manual ON_2026_01.pdf` |
| Portage Residential Pro Manual ON (Dec 2025) | 118 | `December 2025 ON Residential Pro Manual.pdf` |

## Architecture decision: SKIP the RAG pipeline, use Claude directly

We originally planned a full RAG pipeline (Docling parser → chunker → vector store → FastAPI). We ran POCs with Docling, PyMuPDF, and Marker for PDF parsing.

**New direction:** Build this as a **Claude Code plugin with a skill** that:
- Splits PDFs into ≤100-page chunks (already done — see `poc/citations-poc/split_manuals.py`)
- Uses Claude's **Citations API** to send PDF chunks directly to Claude with `citations: {enabled: true}`
- Uses Claude Code's **built-in PDF reader** (the Read tool can read PDFs natively) for the skill
- Returns answers with page numbers and quoted source text

This is simpler, more accurate, and avoids the entire parsing/embedding/vector-store stack.

## What already exists

### 1. PDF chunking (DONE)
`poc/citations-poc/split_manuals.py` — splits each manual into ≤100-page chunks (Claude API limit). Chunks are in `poc/citations-poc/chunks/` with a `manifest.json`.

### 2. Citations API query script (DONE)
`poc/citations-poc/query.py` — CLI tool that sends PDF chunks to Claude with citations enabled. Works. Example:
```bash
python poc/citations-poc/query.py --manual auto-rate "What is the genNow! discount?"
```

### 3. Claude Code skill (DRAFT)
`.claude/commands/rating-manual.md` — A slash command (`/rating-manual`) that:
- Takes a question as `$ARGUMENTS`
- Reads PDF chunks from `poc/citations-poc/chunks/`
- Uses Claude Code's built-in Read tool to read the PDFs
- Returns cited answers with page numbers and quoted text

### 4. Docling stress test results
`poc/docling-poc/results/` has Markdown output from 3 parsers (docling, pymupdf, marker) on 8 test pages. This was exploratory — we're moving away from the parsing approach.

### 5. Test page visual references
`docs/` has single-page PDFs + PNGs of 8 representative pages covering easy (text, simple tables), medium (multi-table, discount rules), and hard (giant 20+ column rate grids, diagrams) content.

## What needs to be built

### Goal: A proper Claude Code plugin

Convert the current prototype into a real Claude Code plugin. The plugin should have:

#### 1. Plugin structure
```
rating-radar/
  .claude/
    plugin.json              # Plugin manifest
    commands/
      rating-manual.md       # Skill: answer questions about rating manuals
    agents/                   # Optional: specialized agents
  poc/citations-poc/
    chunks/                   # Pre-split PDF chunks (already exists)
    manifest.json             # Chunk metadata (already exists)
    split_manuals.py          # Chunking script (already exists)
    query.py                  # Citations API script (already exists)
```

#### 2. The `/rating-manual` skill (improve existing draft)
The current skill at `.claude/commands/rating-manual.md` works but needs improvement:
- Better routing logic — the skill should be smarter about which chunks to read based on the question
- Handle the fact that Claude Code's Read tool can read PDFs directly (up to 20 pages at a time with the `pages` parameter)
- Consider using the full manuals in `rating_manual/` with page ranges instead of pre-chunked files
- Better citation formatting

#### 3. Optional: Citations API agent
An agent that uses the Anthropic SDK to call the Citations API programmatically (like `query.py` does) for cases where you need to search across many pages efficiently.

## Key technical details

- **Claude's Read tool** can read PDFs natively. For large PDFs (>10 pages), you MUST provide the `pages` parameter (e.g., `pages: "1-20"`). Max 20 pages per request.
- **Claude Citations API** accepts PDFs as base64 document content blocks with `citations: {enabled: true}`. Max 100 pages per PDF document. Returns `cite` blocks with `cited_text`, `document_title`, and `start_page_number`.
- **Prompt caching** works with `cache_control: {type: "ephemeral"}` on document blocks — important for repeated queries against the same manual.
- The manuals contain dense rate grids (20+ columns of tiny numbers) — these are the hardest content to parse. Claude reading the PDF directly handles them better than any parser we tested.

## Environment

- Python 3.10+
- `pyproject.toml` exists with optional poc dependencies (docling, pymupdf4llm, marker-pdf)
- `.env` file needed with `ANTHROPIC_API_KEY=sk-ant-xxxxx` (for the Citations API query script)
- Rating manual PDFs go in `rating_manual/` (not committed to git)

## Immediate next steps

1. Read the existing skill at `.claude/commands/rating-manual.md` and the query script at `poc/citations-poc/query.py`
2. Create a proper `plugin.json` manifest
3. Improve the `/rating-manual` skill to be production-quality
4. Test with real questions against the manuals
