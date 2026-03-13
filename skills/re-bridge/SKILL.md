---
name: re-bridge
description: Bridge manual logic to VB.NET code. Combines manual answer with citations and VB.NET code location mapping.
user-invocable: true
---

# /re-bridge — Bridge Manual Logic to VB.NET Code

## Purpose

The killer feature. Takes a question about a rating manual, gets a cited answer
(via manual-reader), then maps the business rules in that answer to their VB.NET
code implementations (via code-mapper). Returns both the manual excerpt and the
code location.

**Status: Phase 2 — core orchestration defined, code-mapper agent pending.**

## Trigger

Slash command: `/re-bridge {question}`

Examples:
- `/re-bridge What is the genNow! discount?`
- `/re-bridge How is the multi-vehicle discount calculated?`
- `/re-bridge What are the deductible factors for home insurance?`

Optional flags:
- `--manual {slug}` — search only this manual
- `--province {code}` — limit code search to this province (e.g., `ON`)
- `--lob {name}` — limit code search to this LOB (e.g., `Auto`)

## Inputs

- `$ARGUMENTS` — the question (required) + optional flags
- `.re-workstreams/paths.md` — resolved paths (MUST read first)
- `.re-workstreams/config.yaml` — carrier metadata + manual inventory

## Outputs

A combined result showing:
1. Manual answer with page citations (from manual-reader)
2. VB.NET code location(s) that implement the rule (from code-mapper)
3. Match confidence assessment

## Steps

### Step 0: Read Paths (MANDATORY)

Read `.re-workstreams/paths.md`. If not found: `"Run /re-init first."`

Extract all paths including `vb_parser` and `code_mapper_agent`.

### Phase 1: Get Manual Answer

Run the full `/re-query` logic internally:

1. Parse the question and extract keywords
2. Route via TOC to find relevant page ranges
3. Launch manual-reader sub-agent with targeted pages
4. Receive cited answer

This is identical to `/re-query` Steps 1-5.

### Phase 2: Map to Code

1. Extract business rules from the manual-reader answer:
   - Discount percentages, conditions, eligibility criteria
   - Rate table structures, factor values
   - Named business concepts (e.g., "genNow! discount", "multi-vehicle credit")

2. Read the code-mapper agent spec from `{plugin_root}/agents/code-mapper.md`

3. Determine search scope:
   - Province from `--province` flag or infer from manual context
   - LOB from `--lob` flag or infer from manual title
   - Code directory from `config.yaml`

4. Launch code-mapper sub-agent:
   ```
   Agent tool:
     subagent_type: "general-purpose"
     prompt: {built prompt with rules, paths, scope}
     description: "Map manual rules to VB.NET code"
   ```

5. If `vb_parser` is "NOT_FOUND":
   - Warn: "vb-parser.exe not available. Code mapping will use grep+Read (degraded mode). Results may be incomplete."
   - Still launch code-mapper — it has its own fallback logic

### Step 3: Present Combined Result

```markdown
## Rating Manual ↔ Code Bridge

**Question:** {original question}

---

### Manual Answer

**Source:** {manual title} (pages {page range})

{full answer from manual-reader with citations}

---

### Code Implementation

{results from code-mapper: file paths, function names, line numbers, snippets}

---

### Bridge Assessment

| Manual Rule | Code Location | Match |
|-------------|---------------|-------|
| {rule 1} | {file:function:line} | {EXACT/PROBABLE/POSSIBLE} |
| {rule 2} | {file:function:line} | {EXACT/PROBABLE/POSSIBLE} |

**Overall confidence:** {HIGH / MEDIUM / LOW}
**Parser mode:** {vb-parser / grep+Read (degraded)}

{Any unmatched rules or notes}
```

## Error Handling

| Error | Action |
|-------|--------|
| `paths.md` not found | "Run `/re-init` first." |
| Manual answer phase fails | Report error, suggest `/re-query` for manual-only |
| vb-parser not found | Warn, proceed with degraded grep+Read mode |
| No code matches found | Show manual answer anyway, note "no code implementation found" |
| Carrier structure not configured | "Run `/re-init` with a carrier path for code bridge support." |
