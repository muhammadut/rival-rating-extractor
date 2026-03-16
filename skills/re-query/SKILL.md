---
name: re-query
description: Ask a question about a rating manual. Routes via TOC keyword matching, launches manual-reader sub-agent, returns cited answer.
user-invocable: true
---

# /re-query — Ask a Question About a Rating Manual

## Context Management — Orchestrator Pattern

**The orchestrator (this command) NEVER reads PDFs directly.** It handles only
lightweight operations (reading paths.md, reading toc.yaml for keyword routing)
and delegates all PDF reading to a **manual-reader sub-agent**.

1. Orchestrator reads paths.md + toc.yaml (small YAML, ~1-2K tokens)
2. Orchestrator does keyword matching to identify target page ranges
3. Orchestrator spawns manual-reader sub-agent with a self-contained brief
4. Sub-agent reads PDF pages via Read tool (heavy — ~50K tokens per 20 pages)
5. Sub-agent returns concise cited answer (~1-2K tokens)
6. Orchestrator presents the result to the developer

## Purpose

Takes a natural language question about an insurance rating manual and returns a cited
answer with page numbers and quoted source text. Uses TOC-based routing to target the
relevant 10-30 pages instead of scanning the full manual.

## Trigger

Slash command: `/re-query {question}`

Examples:
- `/re-query What is the genNow! discount for renewal policies with business use?`
- `/re-query What are the territorial base rates for zone 8?`
- `/re-query How is the multi-vehicle discount calculated?`

Optional flags:
- `--manual {slug}` — search only this manual (e.g., `--manual auto-rate-2025-04`)
- `--pages {range}` — override TOC routing, read these specific pages
- `--all` — search all manuals (default: search all, return best match)

## Inputs

- `$ARGUMENTS` — the question (required) + optional flags
- `.re-workstreams/paths.md` — resolved paths (MUST read first)
- `toc:{slug}` from paths.md — TOC for each manual (lives in plugin_root/knowledge/manual-index/)

## Outputs

A cited answer displayed to the developer, containing:
- Direct answer to the question
- Page citations with quoted source text
- Confidence level (HIGH / MEDIUM / LOW)
- Notes on any ambiguities or cross-references

## Steps

### Step 0: Read Paths (MANDATORY)

Read `.re-workstreams/paths.md` from the current working directory or from the carrier
root. Extract all paths. If the file doesn't exist:
```
"Run /re-init first to set up the rating extractor."
```

From `paths.md`, resolve:
- `plugin_root` — to find agent specs
- `manual:{slug}` — absolute path to each manual PDF
- `toc:{slug}` — absolute path to each `toc.yaml`
- `manual_reader_agent` — path to `agents/manual-reader.md`

### Step 1: Parse the Question

1. Extract the question text from `$ARGUMENTS`
2. Check for flags: `--manual`, `--pages`, `--all`
3. Tokenize the question into search keywords:
   - Remove stop words (the, is, what, how, etc.)
   - Keep domain terms (discount, rate, territorial, deductible, etc.)
   - Keep proper nouns and branded terms (genNow, OMAP, etc.)
   - Lowercase for matching (but preserve original for display)

### Step 2: Route via TOC

For each manual (or just the specified `--manual`):

1. Read the manual's `toc.yaml`

2. Match question keywords against the `keyword_index`:
   - Exact match: keyword appears as a key → take its page ranges
   - Partial match: keyword is a substring of a key → take those page ranges
   - Section name match: keyword appears in a section `name` → take that section's pages

3. Score each manual by match quality:
   - Count of matched keywords
   - Specificity (exact > partial > section name)
   - Relevance of matched sections

4. If `--pages` was specified, skip TOC routing entirely and use those pages.

5. If NO matches found in any manual:
   - Try broader matching (stemming, synonyms)
   - If still no matches, fall back to reading the TOC pages themselves (pages 1-5)
     and ask Claude to identify which sections might be relevant
   - As last resort, tell the developer: "No matching sections found. Try `/re-query --pages 1-20` to browse, or rephrase your question."

6. Collect the target page ranges. Merge overlapping ranges. Cap at 60 pages total
   (3 Read calls). If more than 60 pages match, prioritize by match score and take
   the top-scoring sections.

### Step 3: Read the Agent Spec

Read the manual-reader agent spec from `{plugin_root}/agents/manual-reader.md`.
This tells you the exact input/output format the agent expects.

### Step 4: Launch Manual Reader Sub-Agent

For the best-matching manual (or each manual if `--all` and multiple match):

1. Build the agent prompt using the manual-reader input format:

   ```
   QUESTION: {original question}

   MANUAL: {slug} — {title}
   SOURCE: {absolute path to PDF}
   TOTAL PAGES: {total pages}

   TARGET PAGES: {merged page ranges, e.g., "45-52, 73-75"}

   TOC CONTEXT:
   Matched sections from toc.yaml:
   - "genNow! Discount" (pages 45-52) — matched keyword "gennow"
   - "Discount Summary" (pages 73-75) — matched keyword "discount"

   INSTRUCTIONS:
   1. Read the target pages from the PDF using the Read tool
   2. Answer the question with specific page citations
   3. Quote the exact source text that supports your answer
   4. If the answer spans multiple sections, cite each separately
   5. If the target pages don't contain the answer, say so and suggest which sections might
   ```

2. Launch the sub-agent:
   ```
   Agent tool:
     subagent_type: "general-purpose"
     prompt: {the built prompt above}
     description: "Read manual pages for query"
   ```

3. If searching multiple manuals, launch agents in parallel (one per manual).

### Step 5: Present the Result

1. Receive the manual-reader's response

2. Format and display to the developer:

   ```markdown
   ## Rating Manual Answer

   **Question:** {original question}
   **Source:** {manual title} ({total pages} pages)

   {answer from manual-reader, with citations}
   ```

3. If multiple manuals were searched, present the best result first, then note
   any additional findings from other manuals.

4. If the manual-reader returned LOW confidence, suggest:
   - Trying a different manual
   - Broadening the search with `--pages`
   - Rephrasing the question

## Error Handling

| Error | Action |
|-------|--------|
| `paths.md` not found | "Run `/re-init` first." |
| `toc.yaml` not found for a manual | Skip that manual, warn developer, suggest `/re-index` |
| No keyword matches | Fall back to TOC page scan, then suggest rephrasing |
| Manual-reader agent fails | Report error, suggest `--pages` for manual override |
| PDF unreadable | Report the specific PDF error, try other manuals |
| Too many pages matched (>60) | Take top-scoring sections, note that results may be incomplete |
