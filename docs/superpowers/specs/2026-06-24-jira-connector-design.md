# Design: First real connector — Jira (Goal A, "prove the pipe")

Status: BUILT (2026-06-24, branch `stage7-jira-connector`, not yet merged — awaiting David's review).
Stage 7 second slice. Epic SS-5 (UX Polish + Connectors). Author: Claude Code + David.
Process: superpowers brainstorming -> writing-plans -> inline TDD build.
Offline build green (192 passed + 3 skipped, ruff clean). Live Jira/Composio paths run on a
clean-network day (create sandbox project + Composio key, then seed + live demo). Plan:
docs/superpowers/plans/2026-06-24-jira-connector.md.

## Plain-English summary (read this first)

We are adding one new part to Sprintsight: a **connector**. Think of it as a translator. It
talks to a live Jira board, picks up each ticket, and rewrites it into the exact "Artifact"
shape the rest of the app already understands. Nothing downstream changes. We prove it works
with a script that pulls real tickets, files them through the existing pipeline, and answers a
sample question using those real tickets as cited evidence.

This is **Goal A: prove the pipe.** It de-risks live integration by connecting ONE tool, end to
end. It is deliberately NOT the cross-tool watermelon on live data (that is Goal B, a later
slice). The win here is honest and small: "we can read real delivery data and turn it into
something the app reasons over."

## Locked decisions

1. **Goal A** — one connector, prove the pipe. Not the live watermelon (Goal B later).
2. **Tool = Jira**, read-only.
3. **Test board = a NEW, separate sandbox Jira project** (e.g. "SprintSight Demo Data"), never
   the SS build board. Seeded from our existing ground truth by a generated seed script (not
   hand-cranked). David creates the empty project and connects it; Claude fills it.
4. **"Done" = A1: script-level proof, NO web UI changes.** Live Jira data will not appear in the
   existing portfolio/watermelon screens (those are ground-truth-driven; live tickets have no
   labels). Surfacing in the UI is a later slice.
5. **Runtime auth = Composio Python SDK**, reusing the already-connected Jira account. The app
   needs a Composio API key (one new secret — flagged below). Not direct Jira REST.

## Architecture

New module `sprintsight/connect/` (sits beside `ingest/` and `retrieval/`, same style). Three
pieces, split so the network-risky part is tiny and isolated from the real logic:

1. **`fetch_issues() -> list[dict]`** — the ONLY piece that touches the network. Asks Jira (via
   the Composio Python SDK, reusing the connected account) for the sandbox project's issues and
   returns them as raw dictionaries. Walled off by itself so a flaky network affects nothing else.

2. **`normalize(issue: dict) -> Artifact`** — a PURE function, no network. Takes one raw Jira
   issue, returns one Artifact (the existing dataclass in `sprintsight/evals/fixtures.py`). This
   is the real new logic and the hard-tested unit. Same input always yields the same output.

3. **`JiraConnector.fetch() -> dict[str, Artifact]`** — ties them together: fetch raw issues, run
   each through `normalize`, return a bag keyed by `artifact_id`. Implements a small `Connector`
   protocol (just a `fetch()` method), so an offline twin `RecordedConnector` (reads a saved
   sample file) can stand in for tests. Same seam pattern as embedder / store / auth / writer.

### Data flow

```
live Jira board
   -> fetch_issues()          (network: the only live call)
   -> normalize(each issue)   (pure: raw ticket -> Artifact)
   -> dict[str, Artifact]
   -> ingest_corpus(...)      (UNCHANGED: chunk -> embed -> store, idempotent on content_hash)
   -> retrieval               (UNCHANGED: ask a question, get cited real tickets)
```

The right-hand half (ingest, retrieval) is already built and tested. We add only the left half;
the genuinely new brainpower is one pure function.

### Artifact mapping (what `normalize` produces)

For one Jira issue (granularity: one Artifact per issue):

| Artifact field      | Source on the Jira issue                                   |
|---------------------|-------------------------------------------------------------|
| `artifact_id`       | `jira-{ISSUE_KEY}` (e.g. `jira-SSD-42`)                      |
| `source_type`       | `"jira"`                                                     |
| `team`              | from a Jira label we set in the seed (e.g. `team:atlas` -> `Atlas`) |
| `sprint`            | from Jira's sprint field -> int (14 / 15)                    |
| `meta.source_ref`   | issue key                                                   |
| `meta.title`        | issue summary                                              |
| `meta.author`       | reporter / assignee                                        |
| `meta.source_timestamp` | issue `updated`                                        |
| `body`              | markdown render: summary, status, story points, sprint, assignee, description, latest comments |

The `body` is what gets chunked, embedded, and cited, so it carries the human-readable facts.

## The seed script (`scripts/seed_demo_board.py`)

Reads `data/ground-truth/labels.yaml` + the corpus and creates a board's worth of real Jira
tickets that mirror the known scenario: sprints 14 and 15, story points, statuses, and carry-over
so each team's burndown and velocity reproduce. Team via a Jira label, sprint via the sprint
field. Marker-tagged so re-running does not duplicate. Run by Claude via the Composio MCP on a
clean-network day. David hand-creates nothing.

Honesty note: a Jira board carries the ticket / sprint / velocity signals. It cannot carry "the
status report said green" or "the risk was raised in chat" — those are Goal B. The seed
reproduces the ticket-level half, which is exactly what proves the pipe.

## The proof (A1) — `scripts/run_connector_demo.py`

A runnable script that: fetches the sandbox board's issues, normalizes to Artifacts, ingests via
the unchanged pipeline, runs a sample question, and prints the real tickets returned as cited
evidence. This is the "done" artifact for the slice. No web UI changes.

## Testing (eval-first — our non-negotiable)

The hard-tested surface is the pure translator. Capture ONE real sample of raw tickets from the
live board once, save as `tests/fixtures/jira_sample.json`, and pin tests to it:

1. **normalize contract** — a known recorded issue produces the expected Artifact (id, team,
   sprint, source_type, and a body containing the key facts).
2. **offline end-to-end** — feed the recorded sample through the unchanged `ingest_corpus` with
   `InMemoryStore` + offline embedder; assert counts and that a re-run skips (idempotent).
3. **retrieval smoke** — a sample question returns the expected real ticket as a citation.

CI stays fully offline: it reads the recording, never calls Jira. The live fetch is exercised
only by the demo script, run by hand. Matches how the project keeps live calls out of CI.

## Security and scope (security-first flags)

- The connector is **read-only**. It never writes to Jira. (The seed script writes, but that is
  one-time human-run setup, not the app.)
- Separate sandbox project, walled off from the SS build board.
- **Least data**: pull only that project's issues, only the fields we map.
- **New secret (flagged)**: the app needs a **Composio API key** to call the Composio SDK at
  runtime. One new credential. No new Jira token (we reuse the connected account).
- **Deferred** (not this slice): web UI surfacing (A2); Goal B second connector + live
  watermelon; multi-tenant `team_id`; persistent Supabase. See offline-standins notes.

## Out of scope

- Any change to chunking, embedding, retrieval, watermelon detection, or the report writer.
- Any web UI change.
- Writing to Jira from the app.
- A second connector or cross-tool reconciliation (Goal B).
