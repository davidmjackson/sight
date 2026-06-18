# Design: LLM-backed report-writer (Stage 2, arc 2)

- **Date:** 2026-06-18
- **Story context:** Stage 2 (Status Report Agent, Epic SS-1), arc 2 — the LLM-backed
  report-writer node per ADR-0001, dropped in behind the existing `ReportWriter` seam.
- **Status:** Approved (design); pending spec review.
- **Author:** David + Claude Code.

## Goal

Replace the deterministic `compose` writer's prose with genuinely LLM-authored, audience-tuned
narrative, behind the **same** `ReportWriter` seam, without weakening any grounding/citation/
fabrication guarantee. The deterministic `compose` remains the CI eval gate and the fallback path.

## Non-goals (lean MVP — each a later Story)

- New eval dimensions (LLM-as-judge readability/tone, stricter differentiation).
- Surfacing a moat behaviour in the narrative (B1 cross-team slip, etc.).
- Promoting the writer to a LangGraph node (that is Stage 3 per ADR-0001).
- Persistence, Langfuse tracing of the writer (deferred; Stage 4 for tracing).

## Done bar (drop-in parity)

The LLM writer passes the **same existing 4 report-eval cases** that `compose` passes
(`boreas-exec`, `atlas-programme`, `echo-thin`, `audience-triple`), proving it works behind the
`ReportWriter` seam. `compose` stays the CI gate; the LLM path is exercised by an offline unit
test (fake client) in CI and by a manual live run when a real key is present.

## Locked decisions (from brainstorming, 2026-06-18)

1. **Build + run live this session.** A real `sk-ant` key is pasted into `.env` via a shell
   variable (never into chat or git). CI never needs the key.
2. **Hybrid grounding.** Numbers, RAG status, risk/dependency lines, and citations are produced
   **deterministically** (reusing `compose`'s parsers). The LLM authors only the audience-facing
   section *prose*. This makes the hard eval assertions pass by construction.
3. **Drop-in parity scope** (see Done bar).
4. **Structure: two-layer writer with per-section fallback** (approach A) — not repair-retry,
   not wholesale fallback.

## Architecture

### Seam (unchanged)

`ReportWriter = Callable[[dict[str, Any]], Report]` in `sprintsight/report/writer.py`. The LLM
writer is a new `ReportWriter` produced by a factory; nothing else about the seam changes.

### New module: `sprintsight/report/llm_writer.py`

```
make_llm_writer(complete: Completer | None = None, model: str = <default>) -> ReportWriter
```

- `Completer = Callable[[str, str, dict], dict]` — an injected completion function
  `(system_prompt, user_prompt, output_schema) -> parsed_dict`. Default: a real Anthropic-backed
  completer (see Anthropic client). Tests inject a fake returning canned prose.
- The returned `ReportWriter` runs: deterministic core → (skip LLM if thin-data) → LLM prose
  layer → validation + per-section fallback → assemble `Report`.

### Component 1 — deterministic core (shared, refactored out of `compose`)

Extract `compose`'s fact-gathering into a shared helper (e.g. `_grounded_facts(inputs) -> Facts`
and the section-prose builders) so both `compose` and the LLM writer call the same code. The
`Facts` bundle carries: team, audience, profile, resolved artifact ids
(`burndown_id`/`status_id`/`raid_id`), parsed `Metrics`, reported `rag` + its citation id, risk
lines, dependency lines, the look-ahead blurb, and the deterministic `claims` list.

- The **thin-data guard** (no burndown id → `insufficient_evidence=True`) lives here and short-
  circuits before any LLM call.
- The **`claims` list with citations** is produced here and used verbatim in the final `Report`.
  The LLM never produces or edits claims. → assertions A (coverage), B (validity), C (grounding),
  F (no-fabrication) hold by construction.

This is a targeted refactor (single-sourcing grounding logic), not a rewrite; `compose`'s public
behaviour and output are unchanged.

### Component 2 — LLM prose layer

One Anthropic call per report. Input to the model:

- The audience profile's `required_sections` (the keys it must fill).
- The grounded facts as plain text (numbers, RAG, risk lines, dependencies, look-ahead) — the
  model writes *from* these, never inventing.
- The profile constraints: `max_words`, `forbid_ticket_ids`, `forbid_mechanics` (with the
  concrete `MECHANICS_TERMS` and the ticket-id shape).

Output: structured `{section_key: prose}` for exactly the required keys (tool-use / JSON schema,
so parsing is reliable). Thin-data (`insufficient_evidence`) returns the abstaining `Report`
**without** calling the LLM — no fabrication surface.

### Component 3 — validation + per-section fallback

Validation is two-tier, because the eval measures the word cap on the **whole rendered report**
(all section values + claim texts joined), while the marker checks are naturally per-section.

**Per-section marker checks** — for each required section key, fall back to `compose`'s prose
for that key if the LLM prose:

- contains a `TICKET_ID` match — **unconditionally, for every audience** (anti-fabrication guard:
  the LLM is never given any ticket id in its facts, so a ticket id appearing in LLM prose is
  always fabricated; this is stricter than the per-profile `forbid_ticket_ids` flag, which still
  governs the eval's audience-fit scoring), or
- contains a `MECHANICS_TERMS` term when `forbid_mechanics`, or
- is missing / empty.

**Report-level word-cap check** — after assembling sections + the deterministic claims, if the
rendered word count exceeds `profile.max_words`, fall the LLM sections back to `compose`'s prose
(which is known to fit the cap). `compose`'s output is the proven-within-cap baseline, so this
guarantees the assembled report respects the cap.

`claims` are always the deterministic list. Net: assertions D (audience fit) and E (required
sections) hold even if the LLM misbehaves — worst case the report degrades to template prose.

Note on the `audience-triple` case: differentiation (distinct text, exec < programme/team words,
exec clean, team granular) is satisfied because per-section fallback preserves `compose`'s
audience shaping; LLM prose only improves wording within those bounds.

### Component 4 — Anthropic client (the default completer)

- Anthropic Messages API with **structured output** (tool-use / JSON schema), API key read from
  the environment (`ANTHROPIC_API_KEY`). **ZDR is account/org-level configuration in the Anthropic
  Console, NOT a per-request header** (confirmed against the `claude-api` skill during
  implementation — the earlier `extra_headers={"anthropic-beta": "zdr"}` sketch was wrong and is
  not used); enable ZDR for the org to satisfy the locked "ZDR on Anthropic API" decision.
- Model id `claude-sonnet-4-6` and the tool-use call shape were confirmed against the `claude-api`
  skill at implementation time. Sonnet 4.6 is the default for cost/quality; `model` is a factory
  argument so it is configurable.
- No persistence; no logging of artifact bodies beyond the in-process call. Single external-call
  decision flagged per security-first: outbound to the Anthropic API on synthetic data, ZDR
  enabled at the org level — consistent with the locked "ZDR on Anthropic API" decision.

## Data flow

```
inputs(team, audience, artifacts)
   -> _grounded_facts()                     # deterministic; thin-data guard
       -> [thin data] return abstaining Report (no LLM)
   -> LLM prose layer (Completer)           # {section_key: prose}
   -> per-section marker check               # ticket id / mechanics / empty -> compose prose
   -> assemble Report(sections, claims=deterministic)
   -> report-level word-cap check            # over cap -> fall LLM sections back to compose prose
   -> Report
```

## Testing (eval-first)

1. **Offline unit test (CI, no key):** build `make_llm_writer(complete=fake)` where `fake`
   returns canned per-section prose (including a deliberately over-cap / ticket-id-containing
   section to exercise the fallback), and assert the full report eval passes. Proves seam +
   validation + fallback deterministically.
2. **CI eval gate unchanged:** `scripts/run_report_eval.py` keeps running `compose`.
3. **Live check (manual, key present):** a `--llm` flag on `scripts/run_report_eval.py` (or a
   small sibling script) runs the eval through the real Anthropic completer. Gated on key
   detection so CI never calls the API.

## Risks & mitigations

- **LLM paraphrases a number / invents a citation** → impossible to fail the eval: claims are
  deterministic; the LLM only writes prose, validated to contain no forbidden markers.
- **LLM omits a required section** → per-section fallback fills it from `compose`.
- **Placeholder/invalid key** → live path errors clearly; CI and offline tests are unaffected
  (they use the fake completer). Real key wired via shell var this session.
- **Refactor regresses `compose`** → `compose`'s existing 4-case green run is the guard; the
  refactor must keep it green before the LLM path is added.

## Open-wiring (unchanged, not blocking)

Persistent Supabase Postgres+pgvector; finalise the 1024-dim embedding model (D1); populate
`artifact.team_id`. None gate this arc.
