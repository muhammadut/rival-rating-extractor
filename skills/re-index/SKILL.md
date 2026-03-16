---
name: re-index
description: Scan a folder of rating manual PDFs, spawn sub-agents to read first pages, extract rich metadata and TOC, build the master catalog. Run this first before /re-init.
user-invocable: true
---

# /re-index — Build the Master Manual Catalog

## What This Plugin Is

**Rating Extractor** bridges insurance rating manual PDFs with VB.NET carrier code.
It answers questions about rating manuals with page citations and maps business rules
to code locations. Carrier-agnostic — swap the PDFs and it works for any insurance company.

## Step 0: Pre-flight — Poppler Check (MUST RUN FIRST)

Before doing anything else, check if Poppler is installed. This plugin uses Claude's
built-in Read tool to read PDFs as visual/multimodal input (Claude *sees* each page).
The Read tool depends on `pdftoppm` from Poppler to render PDF pages as images.
**Without Poppler, PDF reading silently fails and nothing works.**

Run this check:

```
Bash: pdftoppm -v
```

### If pdftoppm IS found (shows version like "pdftoppm version 25.12.0"):

Great — proceed to Step 1. No further setup needed.

### If pdftoppm is NOT found ("not recognized" / "command not found"):

Tell the user:

```
Poppler is required but not installed.

This plugin reads insurance rating manual PDFs using Claude's built-in Read tool.
The Read tool needs Poppler (pdftoppm) to render PDF pages as images so Claude
can visually read tables, rate grids, and complex formatting.

Follow the steps below for your operating system:
```

**Then detect the OS and show the right instructions:**

#### Windows Setup:

```
STEP 1: Download Poppler
  Go to: https://github.com/oschwartz10612/poppler-windows/releases
  Download the latest .zip file (e.g., poppler-XX.XX.X.zip)

STEP 2: Extract
  Extract the zip to C:\poppler-XX.XX.X\
  (You should see C:\poppler-XX.XX.X\Library\bin\pdftoppm.exe)

STEP 3: Add to PATH
  Open PowerShell as Administrator and run:

  [Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "Machine") + ";C:\poppler-XX.XX.X\Library\bin", "Machine")

  Replace XX.XX.X with the actual version number you downloaded.

STEP 4: Verify PATH was set
  Close PowerShell. Open a NEW PowerShell window and run:

  where.exe pdftoppm

  You should see: C:\poppler-XX.XX.X\Library\bin\pdftoppm.exe
  If you see "could not find files", the PATH was not set correctly — go back to Step 3.

STEP 5: Restart VS Code / Claude Code
  IMPORTANT: You must fully close and reopen VS Code (or your terminal).
  Claude Code inherits the PATH from the process that launched it.
  If you just restart Claude Code inside the same VS Code window, it may
  still use the old PATH. Close the entire VS Code window, reopen it,
  then start Claude Code again.

STEP 6: Verify it works
  Run /re-index again. I will re-check for pdftoppm.
```

#### Mac Setup:

```
STEP 1: Install via Homebrew
  brew install poppler

STEP 2: Verify
  pdftoppm -v

STEP 3: Restart Claude Code (close and reopen terminal)

STEP 4: Run /re-index again
```

#### Linux Setup:

```
STEP 1: Install via apt
  sudo apt install poppler-utils

STEP 2: Verify
  pdftoppm -v

STEP 3: Restart Claude Code (close and reopen terminal)

STEP 4: Run /re-index again
```

### Troubleshooting (if pdftoppm still not found after install):

If the user says they installed Poppler but it's still not found, run these diagnostic steps:

```
# 1. Check if the file actually exists
Bash: ls "C:/poppler-*/Library/bin/pdftoppm.exe" 2>/dev/null || echo "pdftoppm.exe not found on disk"

# 2. Check if cmd.exe can find it (Windows PATH)
Bash: cmd.exe //c "where pdftoppm" 2>/dev/null || echo "Not in Windows PATH"

# 3. Check what PATH Claude Code's process sees
Bash: echo "$PATH" | tr ':' '\n' | grep -i poppler || echo "Poppler not in bash PATH"
```

Then tell the user based on results:

- **File exists but not in PATH:** "Poppler is installed but not in your PATH.
  Open PowerShell as Administrator and run the command from Step 3 above."

- **In Windows PATH but not bash PATH:** "PATH is set in Windows but Claude Code
  can't see it. You need to fully close VS Code (not just restart the terminal)
  and reopen it. The PATH is only picked up when a new process starts."

- **File doesn't exist:** "The Poppler download may not have extracted correctly.
  Check that `C:\poppler-XX.XX.X\Library\bin\pdftoppm.exe` exists."

**Do NOT proceed past Step 0 until `pdftoppm -v` succeeds.**

## Context Management — Orchestrator Pattern

**The orchestrator (this command) NEVER reads PDFs directly.** PDF pages are huge
multimodal context items (~50K tokens per 20 pages). Reading 21 PDFs inline would
blow the main context window.

Instead, `/re-index` follows the **capsule pattern** from the iq-update plugin:

1. Orchestrator scans the folder, lists PDFs (lightweight — just filenames)
2. Orchestrator checks the cache — skip PDFs already indexed (unless `--rebuild`)
3. Orchestrator builds a **brief** per PDF (path + what to extract)
4. Orchestrator spawns **sub-agents** (max 4 at a time) to read each PDF's first pages
5. Sub-agents use Claude's Read tool (multimodal), extract metadata + TOC, return concise results
6. Orchestrator receives concise results (~2-3K tokens each), aggregates into YAML files
7. Main context stays clean — never sees PDF content

**HARD LIMIT: Never spawn more than 4 sub-agents at a time.** Wait for a batch to
complete before launching the next batch.

## Index Caching — Only Index Once

The index is persisted in `{plugin_root}/knowledge/`. Once built, it serves all
subsequent commands (`/re-init`, `/re-query`, `/re-bridge`) without re-reading PDFs.

### Cache Check (Step 2 — before spawning any agents)

When `/re-index` runs, BEFORE spawning sub-agents:

1. Check if `{plugin_root}/knowledge/manual-catalog.yaml` exists
2. If it exists, read it and compare:
   - `source_folder` — does it match the folder being indexed?
   - `indexed_at` — when was the last index?
   - `pdf_files` — list of filenames at index time
3. Glob the current folder for `*.pdf` files
4. Compare current PDF list against cached `pdf_files` list:
   - **No changes:** Show status and stop:
     ```
     Index already exists (built 2026-03-12T14:00:00Z)
     Source: C:\manuals (21 PDFs)
     No changes detected — all 21 PDFs match the existing index.

     Use --rebuild to force a full re-index.
     Ready: cd to a carrier folder and run /re-init
     ```
   - **New PDFs found:** Only index the new ones:
     ```
     Index exists (built 2026-03-12T14:00:00Z, 18 PDFs)
     3 new PDFs detected:
       - New Manual 2026.pdf
       - Updated Auto Rates.pdf
       - Farm Manual v2.pdf

     Indexing new PDFs only...
     ```
   - **PDFs removed:** Warn but don't delete index entries:
     ```
     Warning: 2 PDFs in the index are no longer in the folder:
       - Old Manual 2025.pdf
       - Deprecated Rates.pdf
     Their index entries are preserved. Use --rebuild to clean up.
     ```
5. If `--rebuild` flag is present: ignore cache, re-index everything from scratch

## Purpose

Takes a path to a folder where the developer saved rating manual PDFs. Spawns sub-agents
that use Claude's Read tool to visually read the first few pages of each PDF, extracting
rich metadata and table of contents. Produces a **master catalog** that maps carrier names
to their manuals, plus a TOC index per manual for query routing.

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

1. **`manual-catalog.yaml`** — Master lookup: carrier name → list of manuals with paths + cache metadata
2. **`manual-index/{slug}/toc.yaml`** — Per-manual TOC with section→page mappings + keyword index
3. **`manual-index/{slug}/manifest.json`** — Per-manual metadata (page count, section count, etc.)

## Steps

### Step 1: Resolve Plugin Root

Determine plugin root from THIS skill file's location:
```
plugin_root = go up from skills/re-index/SKILL.md → rating-extractor/
```

### Step 2: Cache Check + Scan the Folder (Orchestrator — Lightweight)

1. If no path in `$ARGUMENTS`, ask: "Where did you save the rating manual PDFs?"

2. Validate the path exists and is a directory

3. List all `.pdf` files in the folder (non-recursive):
   ```
   Glob: {path}/*.pdf
   ```

4. If zero PDFs found:
   - "No PDF files found in `{path}`. Check the path and try again."
   - Stop.

5. **Check cache** — read `{plugin_root}/knowledge/manual-catalog.yaml` if it exists.
   Compare `pdf_files` list against current folder. Follow the Cache Check logic above.
   If no changes and no `--rebuild`, show status and stop.

6. Present what will be indexed:
   ```
   Found 21 PDFs in C:\manuals:
     1. 2025 04 01 Auto Rate Manual (posted 2025 01 24).pdf
     2. December 2025 ON Residential Pro Manual.pdf
     3. Auto Pro Manual ON_2026_01.pdf
     ...

   Spawning sub-agents to read first pages (max 4 at a time)...
   ```

**NOTE:** The orchestrator only lists filenames here. It does NOT read any PDF content.

### Step 3: Spawn PDF Reader Sub-Agents

For each PDF that needs indexing, spawn a sub-agent to read its first pages and extract
metadata + TOC. **Launch exactly 4 agents at a time, no more.** Wait for the batch to
complete, then launch the next batch of up to 4.

**Sub-agent brief (the prompt passed to each Agent call):**

```
You are a PDF metadata extractor for insurance rating manuals.

PDF PATH: {absolute path to PDF}
FILENAME: {filename}

════════════════════════════════════════════════════════════════════
MANDATORY: HOW TO READ THE PDF
════════════════════════════════════════════════════════════════════

You MUST use Claude Code's built-in Read tool. This is a HARD REQUIREMENT.

The Read tool natively reads PDF files as visual/multimodal input.
Claude sees each page as an image — tables, formatting, layout are
all preserved exactly as printed. This is critical for insurance
documents with dense rate grids and complex formatting.

To read pages 1-5, call:
  Read(file_path="{pdf_path}", pages="1-5")

To read pages 6-10, call:
  Read(file_path="{pdf_path}", pages="6-10")

ABSOLUTELY FORBIDDEN:
  - Do NOT use Bash to run any command
  - Do NOT use Python, pdftotext, pdfjs, pdf-parse, or ANY external tool
  - Do NOT try to install anything
  - Do NOT try to extract text programmatically
  - Do NOT use any tool other than Read to access the PDF

If you use anything other than the Read tool, your output will be
discarded and the PDF will be re-processed. Just use Read.

════════════════════════════════════════════════════════════════════

INSTRUCTIONS:

1. Read pages 1-5 of the PDF:
   Read(file_path="{pdf_path}", pages="1-5")

2. If a Table of Contents extends beyond page 5, read pages 6-10:
   Read(file_path="{pdf_path}", pages="6-10")

3. If the carrier name is not found on page 1, check page footers/headers
   on every page you read. Carrier names often appear in footers (e.g.,
   "RRM" = Red River Mutual, "AB 2025-09" = Alberta revision). Also check
   pages 5-10 where binding authority sections often first mention the carrier.

4. ONLY extract from pages 1-10. Do NOT read beyond page 10.
   You are doing a quick scan — like a human flipping through the first
   few pages and reading the Table of Contents. Everything below comes
   from the cover page, TOC headings, and page headers/footers.

   METADATA (required — from cover page, title page, headers, footers):
   - carrier_name: The insurance carrier / company name
   - carrier_aliases: Other names/abbreviations (from headers, footers, logos)
   - lob: Line of business (Auto, Residential, Farm, Condo, Tenant, etc.)
   - province: 2-letter code (ON, AB, MB, SK, BC, NB, NS, etc.)
   - province_full: Full name (Ontario, Alberta, Manitoba, etc.)
   - effective_date: When this manual takes effect (YYYY-MM-DD)
   - title: The manual's own printed title
   - total_pages: From PDF metadata or last visible page number
   - confidence: HIGH / MEDIUM / LOW

   METADATA (from TOC headings and page footers — only if visible on pages 1-10):
   - organization_type: "facility_association" | "private_carrier" | "mutual" | "other"
   - revision_id: Version/revision stamp from footers (e.g., "2025-09", "v1.0")
   - page_numbering: "sequential" | "dual" (if TOC uses section-based like A-1, B-2)
   - footer_pattern: The repeating footer text pattern you see on the pages you read
   - rule_numbering: Numbering convention visible in TOC (e.g., "Rule 100-129", "Section A-N")
   - multi_province: true if cover/title states multiple provinces (e.g., "NB & NS")
   - product_lines: Scan TOC headings for package/product names
     (e.g., ["Homeowners Comprehensive", "Tenants", "Condo", "Seasonal", "Farm"])
   - discount_types: Scan TOC headings for discount section names
     (e.g., ["Claims Free", "Multi-Vehicle", "New Home", "genNow!"])
   - surcharge_types: Scan TOC headings for surcharge section names
     (e.g., ["Claims Surcharge", "Heating Surcharge", "Conviction Surcharge"])
   - rating_variables: Scan TOC headings for rating factor names
     (e.g., ["Territory", "Rating Class", "Vehicle Rate Group", "Grid", "Deductible"])
   - endorsement_codes: Scan TOC headings for form/endorsement codes
     (e.g., ["Form 2170", "END 44", "SPF 9", "VAP-1225"])
   - coverage_types: Scan TOC headings for coverage type names
     (e.g., ["Liability", "Accident Benefits", "Physical Damage", "All Perils"])

   All enrichment fields above are harvested from TOC HEADINGS — they are
   section names you can see in the Table of Contents. Do not read into the
   manual body to find these. If a TOC doesn't list discounts/surcharges/etc.
   by name, just leave those fields empty.

   TABLE OF CONTENTS:
   - Extract every section name and its starting page number as printed in the TOC
   - Preserve the exact section names (including rule numbers, form codes)
   - Include sub-sections if visible (e.g., "Rule 108 — Clean Driver Discount")
   - If no formal TOC page, extract section headings visible on pages 1-10
   - Note the physical PDF page where each section starts (not internal section numbering)

5. Return your findings in this EXACT format (YAML):

   ```yaml
   metadata:
     carrier_name: "Portage Mutual"
     carrier_aliases: ["Portage", "OMAP"]
     lob: "Auto"
     province: "ON"
     province_full: "Ontario"
     effective_date: "2025-04-01"
     title: "OMAP Auto Rate Manual"
     total_pages: 269
     confidence: HIGH
     organization_type: "facility_association"
     revision_id: "2025-04"
     page_numbering: "sequential"
     footer_pattern: "Alberta {date} {page_code} FACILITY ASSOCIATION"
     rule_numbering: "Rule 100-129"
     multi_province: false
     product_lines: ["Private Passenger", "Commercial", "Public"]
     discount_types: ["Clean Driver Discount", "Multi Vehicle Discount", "New Driver Credit"]
     surcharge_types: ["Conviction Surcharges"]
     rating_variables: ["Rating Territory", "Rating Class", "Vehicle Rate Group", "Grid", "Driving Record"]
     endorsement_codes: ["END 44", "SPF 9", "POL 7", "POL 8"]
     coverage_types: ["Liability", "Accident Benefits", "Physical Damage", "DCPD"]

   toc_entries:
     - name: "Section A — General Information"
       start_page: 4
     - name: "Rule 108 — Clean Driver Discount"
       start_page: 15
     - name: "Rule 120 — Grid"
       start_page: 22
   ```

6. If you cannot determine the carrier name, set carrier_name to "UNKNOWN"
   and add a notes field explaining what you see.

IMPORTANT: Return ONLY the YAML block. No extra commentary.
```

**Agent call pattern:**
```
Agent tool:
  subagent_type: "pdf-extractor"
  description: "Read PDF: {filename}"
  prompt: {the brief above}
```

The `pdf-extractor` agent (defined in `agents/pdf-extractor.md`) has `tools: Read` —
it physically CANNOT run Bash, Python, pip install, or any external tool. Only the
Read tool is available to it. This is enforced at the agent level, not just by prompt.

**Batching: NEVER more than 4 agents at a time.**
- Batch 1: PDFs 1-4 (launch 4 agents in parallel)
- Wait for Batch 1 to complete
- Batch 2: PDFs 5-8 (launch 4 agents in parallel)
- Wait for Batch 2 to complete
- Continue until all PDFs processed

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
   - Pattern: `{carrier}-{lob}-{province}-{date}` in kebab-case
   - Examples: `portage-auto-on-2025-04`, `sem-residential-nb-2026-04`, `rrm-residential-mb-2025-12`

2. **Compute page ranges** from TOC entries:
   - Start page = listed TOC page number
   - End page = next section's start page - 1
   - Last section = total_pages

3. **Build keyword index** from ALL available data:
   - Tokenize each section name into keywords
   - Remove stop words (the, of, and, for, in, etc.)
   - Add ALL extracted enrichment data as keywords:
     - Each discount_type name → its TOC section's pages
     - Each surcharge_type name → its TOC section's pages
     - Each rating_variable name → its TOC section's pages
     - Each endorsement_code → its TOC section's pages
     - Each product_line name → its TOC section's pages
     - Each coverage_type → its TOC section's pages
   - Add insurance domain synonyms:
     - "discount" ↔ "credit"
     - "surcharge" ↔ "loading"
     - "territory" ↔ "territorial" ↔ "zone"
     - "deductible" ↔ "ded"
     - "liability" ↔ "liab"
     - "premium" ↔ "rate"
     - "homeowners" ↔ "homeowner" ↔ "home"
     - "condominium" ↔ "condo"
     - "seasonal" ↔ "cottage"
   - Map each keyword to its section's page range

4. **Write `{plugin_root}/knowledge/manual-index/{slug}/toc.yaml`:**
   ```yaml
   manual_slug: "portage-auto-on-2025-04"
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
   organization_type: "facility_association"
   revision_id: "2025-04"
   page_numbering: "sequential"
   rule_numbering: "Rule 100-129"
   multi_province: false
   product_lines: ["Private Passenger", "Commercial", "Public"]
   discount_types: ["Clean Driver Discount", "Multi Vehicle Discount"]
   surcharge_types: ["Conviction Surcharges"]
   rating_variables: ["Rating Territory", "Rating Class", "Grid"]
   endorsement_codes: ["END 44", "SPF 9"]
   coverage_types: ["Liability", "Accident Benefits", "Physical Damage"]
   sections:
     - name: "Section A — General Information"
       pages: [4, 9]
     - name: "Section B — Private Passenger"
       pages: [10, 120]
     - name: "Rule 108 — Clean Driver Discount"
       pages: [15, 16]
   keyword_index:
     "clean driver": [15, 16]
     "discount": [15, 22]
     "territory": [17, 20]
     "grid": [22, 35]
     "gennow": [45, 52]
     "end 44": [78, 80]
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
# /re-index reads this file to check the cache before re-indexing.

source_folder: "C:\\manuals"
indexed_at: "2026-03-12T14:00:00Z"
total_manuals: 21

# Cache: list of PDF filenames at index time (for change detection)
pdf_files:
  - "2025 04 01 Auto Rate Manual (posted 2025 01 24).pdf"
  - "December 2025 ON Residential Pro Manual.pdf"
  - "Auto Pro Manual ON_2026_01.pdf"
  # ... all 21 filenames

carriers:
  "Portage Mutual":
    aliases: ["Portage", "OMAP", "Ontario Mutual Automobile Plan"]
    manuals:
      - slug: "portage-auto-on-2025-04"
        title: "OMAP Auto Rate Manual"
        lob: "Auto"
        province: "ON"
        effective_date: "2025-04-01"
        source_path: "C:\\manuals\\2025 04 01 Auto Rate Manual (posted 2025 01 24).pdf"
        total_pages: 269
        toc_path: "manual-index/portage-auto-on-2025-04/toc.yaml"

  "Red River Mutual":
    aliases: ["RRM", "Red River"]
    manuals:
      - slug: "rrm-residential-mb-2025-12"
        title: "Residential Underwriting Manual"
        lob: "Residential"
        province: "MB"
        effective_date: "2025-12-01"
        source_path: "C:\\manuals\\Manitoba (Guidewire) Residential Rate Manual December 2025.pdf"
        total_pages: 92
        toc_path: "manual-index/rrm-residential-mb-2025-12/toc.yaml"
```

### Step 7: Handle Ambiguous PDFs

If any PDFs couldn't be confidently mapped to a carrier:

```
Could not determine carrier for 1 PDF:
  - "Generic Rate Guide 2025.pdf" — no carrier name found on first 10 pages

Options:
  1. Assign it manually — tell me which carrier it belongs to
  2. Skip it for now
```

Wait for developer input before finalizing.

### Step 8: Present Summary

```
Master catalog built from C:\manuals

Carriers found:
  Portage Mutual    — 5 manuals (Auto Rate, Auto Pro, Residential, Farm AB, Farm MB)
  Red River Mutual  — 2 manuals (Residential MB, Residential SK)
  SE Mutual         — 1 manual (Rate Manual NB/NS)
  Facility Assoc.   — 1 manual (AB Auto)

Total: 21 manuals indexed, 0 skipped
Index saved: {plugin_root}/knowledge/manual-catalog.yaml

Next: cd to a carrier folder and run /re-init
```

## Re-running /re-index

When manuals are updated (new PDFs downloaded from SharePoint):
- Run `/re-index {path}` again — cache check detects new/changed PDFs, indexes only those
- Use `--rebuild` to discard and recreate everything from scratch
- Without `--rebuild`, existing entries are preserved and new PDFs are added

## Error Handling

| Error | Action |
|-------|--------|
| No path provided | Ask for it |
| Path doesn't exist | "Folder not found: `{path}`. Check the path." |
| No PDFs in folder | "No PDF files found. Check that the folder contains `.pdf` files." |
| Sub-agent fails for a PDF | Skip it, warn developer, continue with remaining |
| Sub-agent uses wrong tool | Discard result, warn developer, suggest re-run |
| Can't extract carrier name | Flag for manual assignment (Step 7) |
| TOC extraction fails | Build approximate index from headings; note in manifest |
| .docx files in folder | Skip — only `.pdf` files are supported. Warn developer. |
| Index already exists, no changes | Show status, suggest --rebuild if needed |
