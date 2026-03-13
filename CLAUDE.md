# Rating Extractor Plugin

This plugin bridges insurance rating manual PDFs with VB.NET carrier code. It answers
questions about rating manuals with page citations and maps business rules to code
locations. Carrier-agnostic — swap the PDFs and it works for any insurance company.

**Origin:** During IQ Update testing, an AI agent removed an if/else line and reviewers
couldn't verify correctness without checking the rating manual. This plugin automates
that lookup.

## User Journey

```
1. Download manuals from SharePoint → local folder (e.g., C:\manuals)
2. /re-index C:\manuals          → scans PDFs, extracts carrier names, builds master catalog + TOC
3. cd E:\...\Portage Mutual
4. /re-init                      → matches "Portage Mutual" to catalog, sets up .re-workstreams/
5. /re-query "What is genNow?"   → cited answer from the manual
6. /re-bridge "What is genNow?"  → manual answer + VB.NET code location
```

## Plugin Path Resolution

**`/re-index`** is self-contained — it takes a folder path argument and writes to the plugin directory. No `paths.md` needed.

**`/re-init`** reads the master catalog from `{plugin_root}/knowledge/manual-catalog.yaml` and creates `.re-workstreams/paths.md` at the carrier root.

**Every other `/re-*` command MUST read `.re-workstreams/paths.md` as its very first action.** This file contains all absolute paths — plugin root, agent specs, manual locations, tool paths. No discovery, no globbing, no fallback chains. Just read the file.

If `.re-workstreams/paths.md` does not exist, tell the developer: `"Run /re-init first."`

## Commands

- `/re-index`  — Scan a PDF folder, build master catalog + TOC per manual (**run first**)
- `/re-init`   — Initialize for a carrier (matches CWD to catalog, writes .re-workstreams/)
- `/re-query`  — Ask a question about a rating manual (returns cited answer)
- `/re-bridge` — Bridge manual logic to VB.NET code (manual answer + code location)

Each command runs in a **fresh context window**. The developer can `/clear` between
commands with zero information loss — all state is persisted on disk.

## Key Rules

1. **`/re-index` before `/re-init`** — catalog must exist before carrier init
2. **Read `paths.md` first** — every `/re-*` command except `/re-index` and `/re-init`
3. **TOC-first routing** — use `toc.yaml` keyword matching to target 10-30 pages, never scan full manuals
4. **Sub-agents for heavy reads** — PDF pages are huge context items; launch manual-reader sub-agent to keep main context clean
5. **Page citations are mandatory** — every answer must include manual slug, page numbers, and quoted source text
6. **20-page Read limit** — Claude's Read tool handles max 20 PDF pages per call; split larger ranges into multiple reads
7. **Fresh context per command** — each `/re-*` command reads ALL state from disk, never from memory
8. **Windows path safety** — use Python `os.path` for path operations, never bash string manipulation
9. **Python-only for scripting** — use Python for YAML generation, PDF processing, data operations
10. **NEVER use `sleep`** — if an agent call fails, log the error and fall back; no retry loops
11. **Graceful degradation** — `/re-query` works after init; `/re-bridge` warns if vb-parser unavailable

## Plugin Architecture

```
rating-extractor/                        <- PLUGIN CODE (ships to marketplace)
  CLAUDE.md                              <- This file (master instructions)
  skills/
    re-index/SKILL.md                    <- /re-index: scan PDFs, build catalog + TOC
    re-init/SKILL.md                     <- /re-init: match carrier, set up workspace
    re-query/SKILL.md                    <- /re-query: answer manual questions
    re-bridge/SKILL.md                   <- /re-bridge: manual answer + code location
  agents/
    manual-reader.md                     <- Reads PDF pages, returns cited answers
    code-mapper.md                       <- Maps manual rules to VB.NET code
  contracts/
    contract_registry.yaml               <- Artifact schemas (source of truth)
  tools/
    build_index.py                       <- Automated TOC extraction (PyMuPDF)
    split_manuals.py                     <- PDF chunking (Phase 3)
  knowledge/
    prompt.md                            <- Bootstrap spec (reference)
    rating_manual/                       <- Sample PDFs (gitignored)
    manual-catalog.yaml                  <- MASTER CATALOG (built by /re-index)
    manual-index/{slug}/                 <- Per-manual TOC + metadata (built by /re-index)
      toc.yaml
      manifest.json

{carrier_root}/.re-workstreams/          <- WORKSPACE (created by /re-init per carrier)
  paths.md                               <- All absolute paths (MUST read first)
  config.yaml                            <- Carrier name, matched manuals, structure
```

## Data Flow

```
/re-index:
  PDF folder → [Read first pages] → manual-catalog.yaml + manual-index/{slug}/toc.yaml

/re-init:
  CWD carrier name + manual-catalog.yaml → .re-workstreams/paths.md + config.yaml

/re-query:
  Question + toc.yaml keyword matching → manual-reader sub-agent → Cited Answer

/re-bridge:
  Question → manual-reader → code-mapper sub-agent → Manual + Code Result
```

## TOC Routing Strategy

The `toc.yaml` per manual maps section headings to page ranges with a keyword index.
When a query arrives:

1. Tokenize the question into keywords
2. Match keywords against `toc.yaml` keyword_index
3. Expand matches to their page ranges
4. Launch manual-reader sub-agent with those targeted pages (typically 10-30 pages)

This avoids scanning 269+ pages for every question.

## Integration with .iq-update (Loose Coupling)

1. **Understand agent** — checks for `.re-workstreams/paths.md` and queries the manual
2. **`/iq-investigate` TYPE 8** — MANUAL LOOKUP delegates to rating-extractor
3. **vb-parser.exe** — `/re-init` discovers parser path from `.iq-workstreams/paths.md`
   or `.iq-update/tools/win-x64/vb-parser.exe` for structural VB.NET analysis in `/re-bridge`

## Agent Architecture

**manual-reader:** Receives question + PDF paths + targeted page ranges. Returns answer
with citations (manual slug, page number, quoted text, confidence). Runs as sub-agent
to isolate PDF context (~50K tokens per 20 pages) from main window.

**code-mapper:** Receives extracted rules + carrier root + scope. Uses vb-parser.exe
(Roslyn-based) for structural analysis — function boundaries, call chains, line numbers.
Grep for file discovery only. Falls back to grep+Read if parser unavailable (with warning).
