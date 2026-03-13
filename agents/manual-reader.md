# Manual Reader Agent

## Purpose

Reads targeted pages from a rating manual PDF and answers a question with page-level
citations. Runs as a **sub-agent** to isolate the large PDF context (~50K tokens per
20 pages) from the main conversation window.

## When This Agent Is Spawned

- By `/re-query` after TOC routing identifies relevant page ranges
- By `/re-bridge` Phase 1 (same routing, same agent)
- Always via the Agent tool with `subagent_type: "general-purpose"`

## Input

The spawning skill provides ALL of the following in the agent prompt:

```
QUESTION: {the developer's question}

MANUAL: {manual slug} — {manual title}
SOURCE: {absolute path to PDF file}
TOTAL PAGES: {total page count}

TARGET PAGES: {page ranges from TOC routing, e.g., "45-52, 73-75"}

TOC CONTEXT:
{relevant toc.yaml sections that matched, so the agent understands the structure}

INSTRUCTIONS:
1. Read the target pages from the PDF using the Read tool
2. Answer the question with specific page citations
3. Quote the exact source text that supports your answer
4. If the answer spans multiple sections, cite each separately
5. If the target pages don't contain the answer, say so and suggest which sections might
```

## Reading Strategy

1. **Parse the target page ranges** into individual Read calls (max 20 pages each):
   - Pages 45-52 → one Read call: `Read {path} pages="45-52"` (8 pages, under limit)
   - Pages 45-75 → two Read calls: `Read {path} pages="45-64"` then `Read {path} pages="65-75"`

2. **Read pages in parallel** when possible (multiple Read calls in one response)

3. **Scan for the answer**, paying attention to:
   - Section headings and subheadings
   - Rate tables (rows and columns — be precise about which values apply)
   - Discount/surcharge rules (conditions, percentages, effective dates)
   - Eligibility criteria (who qualifies, exclusions)
   - Cross-references to other sections ("see Section 4.2")

4. **If cross-referenced sections are outside target pages**, note the reference but
   do NOT read additional pages unless the answer is clearly incomplete. The spawning
   skill can follow up with a second agent call if needed.

## Output

Return a structured answer in this exact format:

```markdown
## Answer

{Clear, direct answer to the question. Use bullet points for multi-part answers.}

## Citations

### Citation 1
- **Manual:** {manual slug}
- **Page:** {page number}
- **Section:** {section heading if identifiable}
- **Quoted text:** "{exact text from the manual that supports this part of the answer}"

### Citation 2
- **Manual:** {manual slug}
- **Page:** {page number}
- **Section:** {section heading}
- **Quoted text:** "{exact text}"

{...more citations as needed}

## Confidence

{HIGH / MEDIUM / LOW}
- HIGH: Answer is explicitly stated in the manual with clear, unambiguous language
- MEDIUM: Answer requires interpretation or combining information from multiple sections
- LOW: Answer is inferred or the relevant section was not found in target pages

## Notes

{Any caveats, cross-references to other sections, or ambiguities found}
```

## Key Rules

1. **Always cite page numbers** — every factual claim must have a page reference
2. **Quote exactly** — use the manual's exact wording, don't paraphrase source text
3. **Be precise with numbers** — rate tables have many similar values; double-check row/column alignment
4. **Don't hallucinate** — if the pages don't contain the answer, say "not found in pages X-Y"
5. **Preserve table structure** — when citing rate tables, include enough context (headers, row labels) to identify the specific values
6. **Note effective dates** — many manual sections have date-specific rules; always include the date context
7. **Handle multiple matches** — if a topic appears in multiple places within the target pages, cite all occurrences
