---
name: re-index
description: Scan a folder of rating manual PDFs, spawn sub-agents to read first pages, extract carrier/LOB metadata and TOC, build the master catalog. Run this first before /re-init.
user-invocable: true
---

# /re-index — Build the Master Manual Catalog

## What This Plugin Is

**Rating Extractor** bridges insurance rating manual PDFs with VB.NET carrier code.
It answers questions about rating manuals with page citations and maps business rules
to code locations. Carrier-agnostic — swap the PDFs and it works for any insurance company.

## Requirements

- **Claude Code** — that's it
- **Claude's built-in Read tool** reads PDFs natively as multimodal (visual) input.
  Claude *sees* each page — dense rate grids, complex tables, merged cells, footnotes —
  exactly as a human would. No Python PDF libraries, no text parsers, no RAG pipeline.
- **No external dependencies** — no PyMuPDF, no Docling, no vector stores.
  The Read tool with `pages` parameter is the only PDF reader in this plugin.
- Rating manual PDFs downloaded from SharePoint to a local folder

## Context Management — Orchestrator Pattern

**The orchestrator (this command) NEVER reads PDFs directly.** PDF pages are huge
multimodal context items (~50K tokens per 20 pages). Reading 21 PDFs inline would
blow the main context window.

Instead, `/re-index` follows the **capsule pattern** from the iq-update plugin:

1. Orchestrator scans the folder, lists PDFs (lightweight — just filenames)
2. Orchestrator builds a **brief** per PDF (path + what to extract)
3. Orchestrator spawns **sub-agents** to read each PDF's first pages
4. Sub-agents use Claude's Read tool (multimodal), extract metadata + TOC, return concise structured results
5. Orchestrator receives concise results (~1-2K tokens each), aggregates into YAML files
6. Main context stays clean — never sees PDF content

## Purpose

Takes a path to a folder where the developer saved rating manual PDFs. Spawns sub-agents
that use Claude's Read tool to visually read the first few pages of each PDF, extracting
metadata (carrier name, LOB, province, effective date) and table of contents. Produces a
**master catalog** that maps carrier names to their manuals, plus a TOC index per manual
for query routing.

**This is the first command you run.** Before any `/re-init`, before any `/re-query`.
Download your PDFs from SharePoint, point `/re-index` at the folder, done.

## Trigger

Slash command: `/re-index {path_to_pdf_folder}`

Examples:
- `/re-index C:\manuals`
- `/re-index E:\rating-manuals\TBW`
- `/re-index` (no argument — will ask for the path)

Optional flags:
- `--rebuild` — discard existing catalog and rebuild from scratch

## Inputs

- `$ARGUMENTS` — path to the folder containing rating manual PDFs (required)
- If no argument, ask: "Where did you save the rating manual PDFs?"

## Outputs

All outputs go to `{plugin_root}/knowledge/`:

1. **`manual-catalog.yaml`** — Master lookup: carrier name → list of manuals with paths
2. **`manual-index/{slug}/toc.yaml`** — Per-manual TOC with section→page mappings + keyword index
3. **`manual-index/{slug}/manifest.json`** — Per-manual metadata (page count, section count, etc.)

## Steps

### Step 1: Resolve Plugin Root

Determine plugin root from THIS skill file's location:
```
plugin_root = go up from skills/re-index/SKILL.md → rating-extractor/
```

### Step 2: Scan the Folder for PDFs (Orchestrator — Lightweight)

1. If no path in `$ARGUMENTS`, ask: "Where did you save the rating manual PDFs?"

2. Validate the path exists and is a directory

3. List all `.pdf` files in the folder (non-recursive):
   ```
   Glob: {path}/*.pdf
   ```

4. If zero PDFs found:
   - "No PDF files found in `{path}`. Check the path and try again."
   - Stop.

5. Present what was found:
   ```
   Found 21 PDFs in C:\manuals:
     1. 2025 04 01 Auto Rate Manual (posted 2025 01 24).pdf
     2. December 2025 ON Residential Pro Manual.pdf
     3. Auto Pro Manual ON_2026_01.pdf
     ...

   Spawning sub-agents to read first pages...
   ```

**NOTE:** The orchestrator only lists filenames here. It does NOT read any PDF content.

### Step 3: Spawn PDF Reader Sub-Agents

For each PDF, spawn a sub-agent to read its first pages and extract metadata + TOC.
Launch agents in parallel (batch 3-4 at a time to avoid overload).

**Sub-agent brief (the prompt passed to each Agent call):**

```
You are a PDF metadata extractor for insurance rating manuals.

PDF PATH: {absolute path to PDF}
FILENAME: {filename}

CRITICAL RULES — READ BEFORE DOING ANYTHING:
- You MUST use Claude Code's built-in Read tool to read the PDF. The Read tool
  natively reads PDF files as visual/multimodal input — Claude sees each page
  as an image, preserving tables, formatting, and layout exactly.
- Call the Read tool like this: Read(file_path="{pdf_path}", pages="1-5")
- NEVER use Bash, Python, pdftotext, PyMuPDF, or any external tool to read PDFs.
- NEVER try to extract text from PDFs programmatically.
- The Read tool is all you need. It handles complex rate tables, merged cells,
  and dense formatting better than any text parser.

INSTRUCTIONS:
1. Read pages 1-5 of the PDF using the Read tool:
   Read(file_path="{pdf_path}", pages="1-5")

2. If a Table of Contents is found but extends beyond page 5, read additional pages
   to capture the full TOC (up to page 10):
   Read(file_path="{pdf_path}", pages="6-10")

3. From what you see (Claude visually reads each page), extract:

   METADATA:
   - carrier_name: The insurance carrier / company name
     (e.g., "Portage Mutual", "OMAP", "Ontario Mutual Automobile Plan", "PMIC",
      "SEM", "Unica", "The Commonwell", "Red River Mutual")
   - carrier_aliases: Other names this carrier goes by
   - lob: Line of business (Auto, Home/Residential, Condo, Tenant, Farm, etc.)
   - province: Province or territory (full name and 2-letter code: Ontario/ON, Alberta/AB, etc.)
   - effective_date: When this manual takes effect (YYYY-MM-DD format)
   - title: The manual's own title as printed on cover/title page
   - total_pages: Read the PDF to determine this (check last page number if visible)

   TABLE OF CONTENTS:
   - Extract every section name and its starting page number
   - Preserve the exact section names as printed
   - If no formal TOC page exists, extract section headings visible in pages 1-5

4. Return your findings in this EXACT format (YAML):

   ```yaml
   metadata:
     carrier_name: "Portage Mutual"
     carrier_aliases: ["Portage", "OMAP", "Ontario Mutual Automobile Plan"]
     lob: "Auto"
     province: "ON"
     province_full: "Ontario"
     effective_date: "2025-04-01"
     title: "OMAP Auto Rate Manual"
     total_pages: 269
     confidence: HIGH

   toc_entries:
     - name: "Section Name As Printed"
       start_page: 9
     - name: "Another Section"
       start_page: 45
   ```

   Use confidence: HIGH if carrier/LOB/province are clearly stated.
   Use confidence: MEDIUM if you had to infer some fields.
   Use confidence: LOW if major fields are unclear.

5. If you cannot determine the carrier name, set carrier_name to "UNKNOWN"
   and explain what you see in a notes field.

IMPORTANT: Return ONLY the YAML block. No extra commentary.
```

**Agent call pattern:**
```
Agent tool:
  subagent_type: "general-purpose"
  description: "Read PDF: {filename}"
  prompt: {the brief above}
```

**Parallelism:** Launch 3-4 agents in parallel per batch. Wait for batch to complete,
then launch next batch.

### Step 4: Collect and Validate Results

As each sub-agent returns:

1. Parse the YAML result from the sub-agent response
2. Validate required fields are present (carrier_name, lob, province)
3. Categorize:
   - **CONFIDENT** — carrier_name is not "UNKNOWN" and confidence is HIGH or MEDIUM
   - **AMBIGUOUS** — carrier_name is "UNKNOWN" or confidence is LOW

4. For CONFIDENT results, proceed to Step 5
5. For AMBIGUOUS results, collect for Step 7 (developer intervention)

### Step 5: Build TOC + Keyword Index Per Manual

For each CONFIDENT PDF result:

1. **Assign a slug** from the extracted metadata:
   - Pattern: `{carrier}-{lob}-{date}` in kebab-case
   - Examples: `portage-auto-rate-2025-04`, `omap-auto-pro-2026-01`, `portage-residential-2025-12`

2. **Compute page ranges** from TOC entries:
   - Start page = listed TOC page number
   - End page = next section's start page - 1
   - Last section = total_pages

3. **Build keyword index:**
   - Tokenize each section name into keywords
   - Remove stop words (the, of, and, for, in, etc.)
   - Add insurance domain synonyms:
     - "discount" ↔ "credit"
     - "surcharge" ↔ "loading"
     - "territory" ↔ "territorial" ↔ "zone"
     - "deductible" ↔ "ded"
     - "liability" ↔ "liab"
     - "premium" ↔ "rate"
   - Map each keyword to its section's page range

4. **Write `{plugin_root}/knowledge/manual-index/{slug}/toc.yaml`:**
   ```yaml
   manual_slug: "portage-auto-rate-2025-04"
   title: "OMAP Auto Rate Manual"
   carrier: "Portage Mutual"
   carrier_aliases: ["Portage", "OMAP", "Ontario Mutual Automobile Plan"]
   lob: "Auto"
   province: "ON"
   effective_date: "2025-04-01"
   source_file: "2025 04 01 Auto Rate Manual (posted 2025 01 24).pdf"
   source_path: "C:\\manuals\\2025 04 01 Auto Rate Manual (posted 2025 01 24).pdf"
   total_pages: 269
   indexed_at: "2026-03-12T14:00:00Z"
   sections:
     - name: "Territorial Base Rates"
       pages: [9, 18]
     - name: "genNow! Discount"
       pages: [45, 52]
   keyword_index:
     "gennow": [45, 52]
     "territorial": [9, 18]
     "base rate": [9, 18]
     "deductible": [73, 85]
   ```

5. **Write `manifest.json`** alongside toc.yaml with summary metadata.

### Step 6: Build the Master Catalog

Aggregate all indexed manuals into `{plugin_root}/knowledge/manual-catalog.yaml`:

```yaml
# Rating Extractor — Master Manual Catalog
# Generated by /re-index on 2026-03-12
# Source folder: C:\manuals
#
# /re-init reads this file to find manuals for a carrier.

source_folder: "C:\\manuals"
indexed_at: "2026-03-12T14:00:00Z"
total_manuals: 8

carriers:
  "Portage Mutual":
    aliases: ["Portage", "OMAP", "Ontario Mutual Automobile Plan"]
    manuals:
      - slug: "portage-auto-rate-2025-04"
        title: "OMAP Auto Rate Manual"
        lob: "Auto"
        province: "ON"
        effective_date: "2025-04-01"
        source_path: "C:\\manuals\\2025 04 01 Auto Rate Manual (posted 2025 01 24).pdf"
        total_pages: 269
        toc_path: "manual-index/portage-auto-rate-2025-04/toc.yaml"
      - slug: "portage-residential-2025-12"
        title: "December 2025 ON Residential Pro Manual"
        lob: "Residential"
        province: "ON"
        effective_date: "2025-12-01"
        source_path: "C:\\manuals\\December 2025 ON Residential Pro Manual.pdf"
        total_pages: 118
        toc_path: "manual-index/portage-residential-2025-12/toc.yaml"

  "Unica":
    aliases: ["Unica Insurance"]
    manuals:
      - slug: "unica-auto-2025-07"
        ...

  "The Commonwell":
    aliases: ["Commonwell"]
    manuals:
      - ...
```

**Carrier name matching rules:**
- Extract the carrier name from PDF content (cover page, headers, footers)
- Store aliases for fuzzy matching (e.g., "Portage Mutual" also matches "Portage", "OMAP")
- If a manual serves multiple carriers (like OMAP pool manuals), list it under each

### Step 7: Handle Ambiguous PDFs

If any PDFs couldn't be confidently mapped to a carrier:

```
Could not determine carrier for 1 PDF:
  - "Generic Rate Guide 2025.pdf" — no carrier name found on first 5 pages

Options:
  1. Assign it manually — tell me which carrier it belongs to
  2. Skip it for now
```

Wait for developer input before finalizing.

### Step 8: Present Summary

```
Master catalog built from C:\manuals

Carriers found:
  Portage Mutual    — 3 manuals (Auto Rate, Auto Pro, Residential Pro)
  Unica             — 2 manuals (Auto, Home)
  The Commonwell    — 2 manuals (Auto, Home)
  Red River         — 1 manual (Auto)

Total: 8 manuals indexed, 0 skipped

Catalog saved to: {plugin_root}/knowledge/manual-catalog.yaml
TOC indexes in:   {plugin_root}/knowledge/manual-index/

Next: cd to a carrier folder and run /re-init
```

## Re-running /re-index

When manuals are updated (new PDFs downloaded from SharePoint):
- Run `/re-index {path}` again — it will re-scan and rebuild
- Use `--rebuild` to discard and recreate everything from scratch
- Without `--rebuild`, existing entries are updated if the PDF changed, new PDFs are added

## Error Handling

| Error | Action |
|-------|--------|
| No path provided | Ask for it |
| Path doesn't exist | "Folder not found: `{path}`. Check the path." |
| No PDFs in folder | "No PDF files found. Check that the folder contains `.pdf` files." |
| Sub-agent fails for a PDF | Skip it, warn developer, continue with remaining |
| Can't extract carrier name | Flag for manual assignment (Step 7) |
| TOC extraction fails | Build approximate index from headings; note in manifest |
| .docx files in folder | Skip — only `.pdf` files are supported. Warn developer. |
