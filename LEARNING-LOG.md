# Sprintsight Learning Log

**What this is.** A plain-English running record of the ideas behind Sprintsight, written for David. No jargon without a translation. This document is yours. If an entry is pitched too high or too low, say so and we adjust the level.

**How it works.**
- One concept at a time, introduced as the project reaches it.
- Each entry follows the same shape: what it is, a simple analogy, where it shows up in Sprintsight.
- The test of a good entry: you can say the idea back in your own words. If you cannot, the entry has not done its job yet, so we redo it.

**How to read an entry.** Skim the bold lines first. Go into the detail only where you want it.

---

## Entry 1 (2026-06-18): The big picture

### What Sprintsight actually is (plain version)
Sprintsight is software that reads all the places your delivery information already lives (Jira, Confluence, Slack, RAID logs), works out what is really going on, and writes the status report for you, tuned for whoever is reading it (team, programme, or exec). It shows where every fact came from, and it flags teams that report green when the underlying data says they are not (a "watermelon": green outside, red inside).

### The core ideas the project rests on
Six ideas. Each one is short on purpose. This is a reference you revisit, not a wall to read in one go.

**1. RAG (Retrieval-Augmented Generation)**
- What: before the AI answers, it goes and reads your actual documents, then answers using only what it found.
- Analogy: a good analyst reads the file before the meeting. A bad one blags it from memory. RAG forces the AI to read the file first.
- In Sprintsight: this is how every claim in a report can point back to the exact Slack message or Jira ticket it came from.

**2. Embeddings and the vector store**
- What: a way to turn text into numbers so the computer can find things that *mean* the same, even when the words are different.
- Analogy: filing documents by meaning, not by exact word. "Auth API is late" and "login service slipping" get filed together.
- In Sprintsight: how it finds the right artifacts to read when answering. (The size of these number-codes is locked at 1024.)

**3. Evals (evaluations)**
- What: an automatic marking scheme that checks the AI's answers against known-correct answers before any human sees them.
- Analogy: a test the AI must pass before it is allowed to speak.
- In Sprintsight: the watermelon test and the report-quality test run automatically. If either fails, the build is blocked. This is the spine of the whole project.

**4. Agents and the graph (LangGraph)**
- What: instead of one giant prompt doing everything, several small specialists, each with one job, passing work down a line.
- Analogy: a small delivery team with clear roles, not one person doing everything badly.
- In Sprintsight: three specialists in a line. One finds the relevant info, one assesses risk, one writes the report. (Deliberately cut from six to three to stay lean.)

**5. The reasoning log (observability, via Langfuse)**
- What: a recorder that captures every step the AI took and why.
- Analogy: showing your working in maths. The answer alone is not enough; the steps prove it.
- In Sprintsight: this is what makes it "production-grade, not a clever demo." When an exec asks "how do you know," you can show the working.

**6. ZDR (Zero Data Retention)**
- What: a setting that tells the AI provider not to keep any of the data we send through it.
- Analogy: a meeting with a strict no-recording, no-notes rule. Said, used, gone.
- In Sprintsight: switched on for all traffic to the AI. Part of the security-first promise.

### The one sentence to remember
Sprintsight reads your real delivery data (RAG), finds things by meaning (embeddings), is proven correct before it speaks (evals), does its work as a small team of specialists (the graph), shows its working (reasoning log), and keeps your data private (ZDR).

### Where the project is right now (so the ideas have something to point at)
The engine works end to end on made-up (synthetic) test data. The three specialists are wired together, both automatic tests pass, and it can already write a cited report and catch a watermelon team. It is not yet connected to a real database or to live tools like Jira; that is deliberately later.

---

## Entry 2 (2026-06-18): The specialists are now wired together

### What happened, in plain terms
Until now the three specialists (find the info, assess the risk, write the report) were three separate pieces of code. Each one worked on its own, but they were not joined up. This stage joined them into a single line, where each one does its bit and hands its result to the next. The tool that holds them in a line is LangGraph (see Entry 1, item 4).

### The new idea worth keeping: change the structure, prove you changed nothing
We deliberately did not rewrite any of the three specialists. We wrapped each existing piece in a thin connector, then ran the exact same two automatic tests (the watermelon test and the report-quality test) through the new joined-up version. Both still scored full marks.
- Analogy: moving three people from separate desks into one shared room. The work each person does is identical. Only the hand-over between them changed. To prove nothing broke, you give them the same exam they already passed and check the marks did not move.
- Why it matters: this is the safe way to restructure software. If the old tests still pass through the new structure, the behaviour did not drift. Engineers call this an equivalence check, and it is why this stage was low risk.

### One deliberate "not yet"
The "find the info" specialist now genuinely runs and gathers relevant material. The other two do not read that gathered material yet (they still read the source documents directly, as before). That last connection is left for a later stage, on purpose, so this step stayed small and safe.

### Where it shows up
The new `sprintsight/graph/` folder is the joined-up pipeline. The whole stage was "orchestration only": joining what already worked, not adding new behaviour.

---

## Entry 3 (2026-06-18): Evals, in depth

**Your definition (the one to keep):** Evals are a set of tests with answers we know to be true. We score the output against these tests for accuracy before we ship any feature.

That is correct. Everything below is just the why and the how.

**The three ingredients**
- **Cases:** a fixed set of test inputs.
- **Ground truth:** the answer we already know is correct for each case, decided by hand up front. Without it you cannot score anything, and the AI cannot mark its own work (it can be confidently wrong).
- **A pass bar:** the score it must hit (for example 4 out of 4), or the build is blocked.

**Who runs it, and when.** We run evals during the build, like automated tests in a pipeline. Not the model checking itself before every live reply. Pass the bar, then the feature ships.

**Analogy.** A driving test with a fixed marking sheet. The examiner marks you against the sheet at test time. Pass, and you are licensed. You do not re-mark yourself at every junction afterwards.

**You already know this idea.** Evals are acceptance criteria for AI output, run automatically. You never marked a story Done on "looks good"; you checked it against the ACs. Same move. And "eval-first" just means writing the test before the feature, so "correct" is defined before anyone builds, exactly like writing ACs before the dev starts.

**In Sprintsight.** Two live evals gate the build: the watermelon eval (4 teams with known truth; must get both the label and the evidence right) and the report-quality eval. If either drops below its bar, the build stops.

**Where else it applies.** Your Job Search duplicate matcher would want one too: a set of known duplicate pairs and known non-duplicate pairs, scored, to tune the threshold and control false positives instead of guessing.

---

## Entry 4 (2026-06-19): LLM-as-judge (grading the soft stuff)

### The problem with deterministic evals

The watermelon eval and the report-quality eval both work by checking a known, fixed answer. Is this team classified as red? Did the report cite its sources? There is one right answer. A machine can mark it automatically. That is what "deterministic" means: the result is the same every time, and there is no argument about whether it is correct.

But some qualities cannot be settled that cleanly. Is this report easy to read? Does it feel right for an executive rather than a developer? Is the argument coherent from start to finish? These things matter a great deal, but they have no single correct answer. A machine cannot mark a multiple-choice answer when there is no answer sheet.

### The solution: a second AI grades the prose

We give a second AI the finished report and a marking rubric (a structured list of things to look for) and ask it to score the prose on four dimensions: clarity, audience fit, coherence, and actionability. Each dimension is scored one to five. To pass, every dimension must hit three or above, and the average must reach four. This is the LLM-as-judge approach: one AI writes, a separate AI grades.

**Analogy.** The deterministic eval is a multiple-choice test marked automatically by a machine. The LLM-as-judge is an essay graded by a second examiner against a marking rubric. The first examiner (the writer) never marks their own work.

### The trap: AI marking its own homework

The obvious risk is that the AI-writer and the AI-judge share the same biases. If the writer uses inflated language, the judge might praise it. We reduce this risk in two ways.

First, the judge has a completely separate prompt and a completely separate role. It is told explicitly to be a critical reader, not a writer. It is given the rubric, not the output it just wrote.

Second, and more importantly, we test the judge before we trust it. We have a set of known anchor reports: some deliberately good, some deliberately bad. Before the judge becomes part of the build gate, we run a calibration meta-eval. The judge must correctly separate the good from the bad. This is called the calibration step. Think of it as giving the examiner a set of papers that have already been graded by the university board, and checking that the examiner's marks agree. If they do not agree, the examiner is not ready to mark real papers.

### Where it sits in Sprintsight right now

The readability judge exists and runs, but it is advisory only. It does not block the build. The deterministic watermelon eval and the report-quality eval still gate the build. The judge becomes a hard gate only once calibration proves it reliably separates good from bad. That is a deliberate choice: trust it first, promote it later.

To avoid sending live data to the AI in tests, the judge is key-gated (it only runs when an API key is present). In the normal automated build, a fake grader stands in.

---

## Entry 5 (2026-06-19): The AI writes the words, but it cannot make up the facts

**Your definition (the one to keep):** The AI is wired so it cannot produce fabricated output. The facts come from the skeleton, not from the AI. The term is "grounded by construction": you build it so bad output is impossible by design. That is also why the eval's no-fabrication check cannot fail. And a RAG rating never comes from someone's opinion, it comes from the actual metrics, enforced by the application.

That is right. Two things to add so it is complete: the AI is not idle, it writes all the prose (the readable sentences), it just never owns the facts; and there is a backstop, if its prose ever breaks a rule a checker swaps that section for the plain version. Everything below is the why and the how.

**What it is.** Every report is split into two layers.
- The skeleton: every number, status, and cited fact, built by plain deterministic code reading the real data. The AI never touches it.
- The prose: the sentences that join the facts into readable, audience-tuned English. The only part the AI writes.
The AI is handed the facts and asked to write them up. It is never asked what the facts are. So an invented figure has nowhere to land.

**Analogy.** A courtroom. The clerk enters the evidence (exhibits, dates, figures) into the record and it is fixed. The barrister writes a persuasive speech around that evidence but cannot add new evidence mid-speech. The words are theirs, the facts are not. A line that strays beyond the evidence gets struck.

**The safety net.** If the AI's prose breaks the rules (too long, or sneaks in a claim), a validator throws that section away and falls back to the plain deterministic version. Worst case is a less elegant sentence, never a wrong one.

**Why this name.** "Grounded by construction" (or "correct by construction") means you arrange things so the bad outcome is impossible by design, not just discouraged. The no-fabrication eval passes by construction: the wiring will not let it fail, rather than us getting lucky on a run.

**You already know this idea.** It is "separate data from judgement" turned into code. Data (facts, citations) is owned by deterministic code. Judgement (phrasing, emphasis, tone) is the AI's. You never let a status RAG rating come from gut feel; it came from the metrics, with the narrative wrapped around it. Same split, now enforced by the machine.

**In Sprintsight.** This is what lets an LLM sit next to an exec report without the usual risk. The fluent, audience-tuned writing is real AI value. The trust (cited, accurate, no invented numbers) is protected by the structure, not by hope. It is the line between a clever demo and production-grade. Code lives in sprintsight/report/llm_writer.py; the deterministic compose stays as the fallback and the CI gate.

---

## Entry 6 (2026-06-19): When the marker asks for something you are not allowed to invent

**What happened, in plain terms.** We pointed our readability marker (the LLM-as-judge from Entry 4) at our real reports. It kept marking the "what to do next" line down hard, because it wanted a named owner, a due date, and a specific decision. We do not have those in the data, and our number-one rule is that we never make facts up (Entry 5). So the marker was asking for the one thing we are forbidden to produce. The marker and our core principle were pulling in opposite directions.

**The new idea worth keeping.** When your quality check demands something you must never fabricate, you have three moves, and only one is honest. (1) Invent the owner and date to pass: forbidden, it breaks the whole product. (2) Lower the bar so any weak answer passes: that is gaming, you learn nothing. (3) Correct what the bar actually asks for: tell the marker that a grounded recommendation ("this is the most exposed risk, escalate if it slips") is a full answer, and that the absence of an invented owner or date is not a fault. We did (3).

**The guard that makes (3) honest, not just (1) in disguise.** We have a second check that grades the marker itself against known-good and known-bad example reports (the calibration meta-eval, Entry 4). After we adjusted the bar, we re-ran it: the genuinely good report still scored top marks, and the deliberately weak "vague ask" report still failed. So we corrected a rule that demanded fabrication, we did not quietly wave bad writing through. If that guard had slipped, we would have backed the change out.

**Analogy.** An exam question asks "name the suspect." But you are a forensics lab that is only allowed to report what the evidence proves, and the evidence does not name a suspect. You do not guess a name (fabrication) and you do not accept blank answers from everyone (lowering the bar). You fix the question to "state what the evidence supports," and you re-check that strong and weak answers still sort correctly.

**The other thing we learned.** The plain deterministic writer hit a ceiling around "clean and correct but terse." Pushing past it (real business-impact narrative) is exactly what the AI writer is for: under the corrected bar, the AI writer passed the exec report outright. That is the case for the next piece of work.

**In Sprintsight.** The corrected dimension lives in the judge prompt (`sprintsight/evals/judge.py`, the actionability definition); the guard is `scripts/run_calibration.py` over the anchors in `sprintsight/evals/calibration.py`; the writer fixes are in `sprintsight/report/writer.py`. Compose stays the grounded fallback and CI gate; the AI writer is the path to a fully passing report.

---

*Next entries get added when the build introduces a genuinely new idea. Ask any time for an entry on something already above if you want it deeper.*
