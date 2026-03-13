# Code Mapper Agent

## Purpose

Maps business rules extracted from a rating manual answer to their VB.NET code
implementations. Uses vb-parser.exe (Roslyn-based) for structural analysis — function
boundaries, call chains, line numbers. Grep is for file discovery only.

Runs as a **sub-agent** to keep the code search context separate from the main window.

**Status: Phase 2 — not yet implemented.**

## When This Agent Is Spawned

- By `/re-bridge` Phase 2, after manual-reader has returned a cited answer
- Always via the Agent tool with `subagent_type: "general-purpose"`

## Input

The spawning skill provides ALL of the following in the agent prompt:

```
RULES: {extracted business rules from manual-reader answer}

CARRIER ROOT: {absolute path to carrier folder}
PROVINCE: {2-letter code, e.g., "ON"} (optional — search all if not specified)
LOB: {line of business, e.g., "Auto"} (optional)
CODE DIR: {absolute path to Code/ directory}

VB PARSER: {absolute path to vb-parser.exe, or "NOT_FOUND"}

MANUAL CONTEXT:
{The full manual-reader answer with citations, so the code-mapper understands
what business logic it's looking for}

INSTRUCTIONS:
1. Use grep to discover candidate files (by keyword, function name pattern)
2. Use vb-parser to analyze file structure (function boundaries, call chains)
3. Map each rule to its code implementation
4. Return file paths, function names, line numbers, code snippets
5. Rate match confidence: EXACT / PROBABLE / POSSIBLE
```

## Code Analysis Strategy

### Primary: vb-parser.exe (Roslyn-based)

When vb-parser is available, use these commands:

1. **Project map:** `vb-parser project {file.vbproj}` — lists all source files and their roles
2. **File structure:** `vb-parser parse {file.vb}` — returns all functions with line numbers
3. **Single function:** `vb-parser function {file.vb} {name}` — returns function body with context

### Fallback: Grep + Read (degraded mode)

When vb-parser is NOT available:

1. Warn: "vb-parser not available — using grep+Read (results may be incomplete)"
2. Use Grep to find files containing keywords from the manual rules
3. Use Read to examine function bodies
4. Manually identify function boundaries (look for `Function`/`End Function`, `Sub`/`End Sub`)

## Output

Return a structured result in this exact format:

```markdown
## Code Mapping Results

### Rule 1: {rule description from manual}

**Match: {EXACT / PROBABLE / POSSIBLE}** | Confidence: {HIGH / MEDIUM / LOW}

- **File:** {relative path from carrier root}
- **Function:** {function name}
- **Lines:** {start}-{end}
- **Snippet:**
  ```vb
  {relevant code excerpt, 5-15 lines}
  ```
- **Reasoning:** {why this code implements this rule}

### Rule 2: ...

## Unmatched Rules

{List any rules from the manual that could not be mapped to code}

## Notes

{Parser mode used, any caveats, suggestions for manual review}
```

## Key Rules

1. **Parser first** — always prefer vb-parser.exe over grep for structural analysis
2. **Grep for discovery** — use grep to find candidate files, then parser for structure
3. **Never guess line numbers** — use parser or Read tool to get exact line numbers
4. **Show context** — include enough surrounding code for the match to be verifiable
5. **Confidence is honest** — EXACT means the code clearly implements the rule; POSSIBLE means it might be related
6. **Warn on degraded mode** — if using grep+Read fallback, always note it in the output
