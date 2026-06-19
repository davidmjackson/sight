# Sprintsight — Learning Log

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

*Next entries get added when the build introduces a genuinely new idea. Ask any time for an entry on something already above if you want it deeper.*
