---
name: re-index
description: Scan a folder of rating manual PDFs, read first pages to extract carrier/LOB metadata and TOC, build the master catalog. Run this first before /re-init.
user-invocable: true
---

# /re-index — Build the Master Manual Catalog

## Purpose

Takes a path to a folder where the developer saved rating manual PDFs. Reads the first
few pages of each PDF to extract metadata (carrier name, LOB, province, effective date)
and table of contents. Produces a **master catalog** that maps carrier names to their
manuals, plus a TOC index per manual for query routing.

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

### Step 2: Scan the Folder for PDFs

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
   Found 8 PDFs in C:\manuals:
     1. 2025 04 01 Auto Rate Manual (posted 2025 01 24).pdf
     2. December 2025 ON Residential Pro Manual.pdf
     3. Auto Pro Manual ON_2026_01.pdf
     ...

   Reading first pages to extract metadata...
   ```

### Step 3: Read Each PDF — Extract Metadata + TOC

For each PDF, read the first 5-10 pages to extract:

1. **Read pages 1-5** using the Read tool:
   ```
   Read {pdf_path} pages="1-5"
   ```

2. **Extract metadata** from cover page / title page / headers:
   - **Carrier name** — look for carrier/company name (e.g., "Portage Mutual", "OMAP",
     "Ontario Mutual Automobile Plan", "Unica", "The Commonwell", etc.)
   - **LOB** — Auto, Home/Residential, Condo, Tenant, Farm, etc.
   - **Province** — Ontario, Alberta, etc. (or abbreviation: ON, AB)
   - **Effective date** — the date this manual takes effect
   - **Title** — the manual's own title as printed

3. **Extract TOC** (may need pages 1-10):
   - Look for a "Table of Contents" / "Contents" page
   - Extract section names and their page numbers
   - If no formal TOC, note headings from the first 5 pages

4. **If metadata is ambiguous** (e.g., can't determine carrier), flag it for Step 5.

**Parallelism:** Read multiple PDFs in parallel where possible (up to 3-4 concurrent
Read calls). Each PDF is independent.

### Step 4: Build TOC + Keyword Index Per Manual

For each PDF:

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

### Step 5: Build the Master Catalog

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

### Step 6: Handle Ambiguous PDFs

If any PDFs couldn't be confidently mapped to a carrier:

```
Could not determine carrier for 1 PDF:
  - "Generic Rate Guide 2025.pdf" — no carrier name found on first 5 pages

Options:
  1. Assign it manually — tell me which carrier it belongs to
  2. Skip it for now
```

Wait for developer input before finalizing.

### Step 7: Present Summary

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
| PDF unreadable | Skip it, warn developer, continue with remaining |
| Can't extract carrier name | Flag for manual assignment (Step 6) |
| TOC extraction fails | Build approximate index from headings; note in manifest |
