# Metacognition Philosophy

> **Purpose**: the *why* behind the brief the `/metacognition` skill writes
> before a big or complex task. Heuristics M1 to M27 each state a rule, the
> reasoning, the sources, what to put in the brief, and where authorities
> disagree or the evidence is thin.
>
> **Who reads this**: `/metacognition` reads the section for the question it
> is answering (Scope first, then Q1 to Q4, plus the LLM section). Humans read
> it to settle a judgment call.
>
> **Provenance**: compiled 2026-11-26 from web research. A second pass the
> same day re-fetched every source URL with curl and checked each quote and
> number against the raw text. `[V]` now means checked in that pass. Books and
> sources with no URL were not re-checked, and some pages could only be read
> through a Wayback copy or a secondary page. Never print a `[B]` or `[S]`
> claim as a quote, and spot-check a `[V~]` quote before printing it as exact.

Across fields, the sources agree on a few points. The hardest part of a
software task is deciding what to build (Brooks, Jackson, Polya), and the
requester usually cannot state it up front. Planning effort should scale with
novelty, irreversibility and the cost of being wrong, not be fixed (Boehm,
Fairbanks, Klein, Ubl, Fowler, and Anthropic's own agent guidance). The
check that proves the work correct should be chosen before the work, because
a check chosen afterwards drifts toward what the output already shows (Nosek,
Gelman and Loken, Scrum's Definition of Done). Felt understanding is
unreliable for how things work (Rozenblit and Keil), and for LLMs the same
holds for self-critique: gains come from contact with an external signal such
as tests, a compiler, the repo or the user (Huang, Stechly, Kambhampati,
Reflexion). The evidence for the *rituals* is much weaker than the evidence
for those principles. Test-first order has a mixed record (Fucci et al.).
The one study of specification artifacts found no defect reduction (Hill).
Pre-mortems lack outcome evidence. Excess reasoning has measured costs
(Cuadron et al., Meincke et al.). Most LLM planning gains were measured on
2022-2023 models and small, checkable tasks. So the brief should be short,
specific to the task, and anchored to executable checks and a human gate.

## How to read the heuristics

Every heuristic has the same fields in the same order: **Rule**, **Why**,
**Sources**, **Apply**, **Disagreement**. The index gives an evidence
strength. It reflects what the notes support, not how famous the idea is.

| Strength | Meaning |
|---|---|
| **Strong** | Direct empirical evidence on the target setting (here, LLM coding agents), with a consistent direction across sources. Still bounded by the model generation stated. |
| **Mixed** | Real evidence exists but it points both ways, comes from a neighbouring setting, or is correlational. |
| **Weak** | Practitioner reports, expert opinion or advocacy, with no outcome measurement found. |
| **Analogy** | Solid result in another field (human cognition, science methods). Transfer to an LLM agent is the note-takers' inference. |

Verification tags show the result of the second pass. A source line carries
the weakest tag among that source's claims in the heuristic.

| Tag | Meaning |
|---|---|
| **[V]** | Checked in the second pass against the raw text of the primary source. Quoted wording is verbatim; unquoted text is a paraphrase the source supports. |
| **[V~]** | Checked only against a secondary page (for example Wikipedia or a reviewer's summary), or not fully re-checked in the pass. Spot-check before printing as exact. |
| **[B]** | Book with no free full text. Paraphrase only, never quote. |
| **[S]** | Secondary source or search snippet. Paraphrase only. |

Two cautions apply to every LLM result. Each one names the model generation it
was measured on, because 2022-2023 numbers (GPT-3, GPT-4) may not transfer to
current reasoning models. And no fetched study measures plan prompts on 2026
frontier coding models for repository-level tasks.

### Index

| # | Rule (short) | Serves | Strength |
|---|---|---|---|
| M1 | Scale design effort to novelty, irreversibility and blast radius; skip for obvious changes | Scope | Mixed |
| M2 | Bound deliberation; a brief that never ends in action has a cost | Scope | Mixed |
| M3 | A written brief is not evidence of quality; the checks and the human gate carry the weight | Scope | Weak |
| M4 | Defer design where change is cheap; design earlier where it is not | Scope | Mixed |
| M5 | State the goal as an outcome in the problem world, with explicit non-goals | Q1 | Weak |
| M6 | Assume the requester cannot fully specify; plan an extraction step | Q1 | Weak |
| M7 | Do not trust your own sense that a task is well specified; ask about what only the user knows | Q1 | Strong |
| M8 | Fix a budget first and let scope flex | Q1 | Weak |
| M9 | List only unknowns that change the approach; resolve each by read, run or ask | Q2 | Mixed |
| M10 | A feeling of understanding a mechanism is weak evidence; read the code | Q2 | Analogy |
| M11 | Gather context before editing | Q2 | Mixed |
| M12 | Build a representation of the problem first; set a point to abandon an approach | Q2 | Analogy |
| M13 | Anchor estimates on analogous past tasks (outside view) | Q2 | Weak |
| M14 | Use a pre-mortem as a cheap risk prompt, not as proof | Q2 | Weak |
| M15 | Name a rejected alternative and why | Q3 | Weak |
| M16 | Put the riskiest slice first, as a thin end-to-end slice | Q3 | Mixed |
| M17 | Treat irreversible steps differently from reversible ones | Q3 | Weak |
| M18 | Fix the done-signal before building | Q4 | Analogy |
| M19 | Decide the check and keep steps small; do not require test-first order | Q4 | Mixed |
| M20 | Name the oracle; separate verification from validation | Q4 | Weak |
| M21 | Pick the check level that crosses the real boundary where the risk lives | Q4 | Mixed |
| M22 | Check the check: confirm it can fail | Q4 | Mixed |
| M23 | State what the checks cannot show | Q4 | Weak |
| M24 | Do not rely on the same model to critique its own plan or output; use an external check | LLM | Strong |
| M25 | Do not pad the brief with step-by-step reasoning for its own sake | LLM | Mixed |
| M26 | Treat 2022-2023 prompt-planning gains as motivation, not proof | LLM | Weak |
| M27 | Build the brief against known agent failure modes | LLM | Mixed |

---

## Scope: when to design first and how much

**M1. Scale design effort to novelty, irreversibility and blast radius, and skip the design for obvious changes.**

**Rule:** Run the full brief only when the task is unfamiliar, spans several components, or is hard to undo. For a small or well-understood change, write one paragraph or none and start work.

**Why:** Fairbanks: use risk "to help you decide how much architecture planning to do", and do enough "until the risk of technical failure (...) is lower than non-technical risks (...)", where the non-technical risks include the "risk of building the wrong thing" [V]. Boehm's later spiral characteristics say risk determines effort and degree of detail [V~, via Wikipedia]. Ubl says a design doc has little value when the solution is not ambiguous, and an obvious solution with no trade-offs suggests writing the program right away [V]. Cynefin maps the mode: clear problems, just do; complicated, analyse; complex, probe [V~, via Wikipedia]. Klein's fireground work (recognition-primed decision) found experienced commanders acted on a recognised first option and used simulation only to check it [S]. Anthropic advises "finding the simplest solution possible, and only increasing complexity when needed" [V]. The scaling rule "irreversibility x uncertainty x blast radius" is the note-taker's synthesis, not a sourced formula.

**Sources:** Fairbanks, risk-driven model, <https://www.georgefairbanks.com/software-architecture/risk-driven-model/> [V]. Ubl, "Design Docs at Google", <https://www.industrialempathy.com/posts/design-docs-at-google/> [V]. Boehm 1988 spiral model, via <https://en.wikipedia.org/wiki/Spiral_model> [V~]; primary PDF not fetched [S]. Cynefin, <https://en.wikipedia.org/wiki/Cynefin_framework> [V~]. Klein, Calderwood and Clinton-Cirocco 1986 (recognition-primed decision), via search results only [S]. Anthropic, "Building effective agents", <https://www.anthropic.com/engineering/building-effective-agents> [V].

**Apply:** Open the brief with a one-line scope call: "full brief" or "short brief, because <obvious / familiar / reversible>". If short, give goal, done-signal and stop. If the task is trivial, say so and do not write a brief.

**Disagreement:** Classic planning advice (Polya) targets novel problems, while Klein shows experts in familiar situations act on recognition. Where "familiar" ends is a judgment call; the notes give no threshold.

**M2. Bound the deliberation: a brief that never ends in action has a cost.**

**Rule:** Time-box the brief. Stop reading and listing when the next item would not change the approach. After two failed corrections of the same approach, stop and rewrite the plan or the prompt rather than correct a third time.

**Why:** Cuadron et al. (2025) studied 4,018 SWE-bench Verified trajectories: "higher overthinking scores correlate with decreased performance", with patterns they call Analysis Paralysis, Rogue Actions and Premature Disengagement; picking the lower-overthinking candidate "can improve model performance by almost 30%" and cut compute 43% [V]. The result is correlational and was measured on 2025 reasoning models. Claude Code docs: effort `max` "tends to overthink", and after two failed corrections run `/clear` and write a better prompt [V]. Mehtiyev and Assuncao (2026) found that longer trajectories look worse only because harder tasks are longer; once difficulty is controlled the direction reverses [V]. So length alone is not evidence that planning hurts. The notes found no source on plan drift or stale plans.

**Sources:** Cuadron et al. 2025, "The Danger of Overthinking", <https://arxiv.org/abs/2502.08235> [V]. Claude Code best practices, <https://code.claude.com/docs/en/best-practices> [V]. Mehtiyev and Assuncao 2026, <https://arxiv.org/abs/2604.02547> [V].

**Apply:** Keep the brief to one screen. Record, in one line, the point at which you will stop investigating and ask. Do not list unknowns that would not change the approach.

**Disagreement:** The overthinking result is a correlation, and Mehtiyev and Assuncao show a difficulty confound for the related length effect. Two opposite failures exist (acting too early and deliberating too long), so the bound must not become an excuse to skip reading. "Re-plan when reality contradicts the plan" is a design choice here, not an evidence-backed rule.

**M3. A written brief is not evidence of quality; the executable checks and the human gate carry the weight.**

**Rule:** Do not present the brief as proof that the work will be correct. Anchor it to checks the environment or the user can run, and stop for approval before building.

**Why:** Hill (ESEM 2026) analysed 88,052 pull requests across 119 open-source repositories. After propensity matching, PRs with and without specification artifacts were "indistinguishable in defect introduction (-0.6 percentage points (pp), p = 0.133)", and spec quality predicted neither defects nor rework. Hill's reading: "Specification artifacts proxy for task complexity, not quality improvement" [V]. The paper states its own limits: what it measured is "overwhelmingly references to tracking issues and tickets", and "SDD tool adoption itself remains untested" (SDD is spec-driven development). It is a single independent author. A vendor-adjacent blog benchmark (50 Python tickets) found spec helped on feature and data-pipeline tickets, not on bug-fix, refactor or test-writing tickets [S].

**Sources:** Hill, "Specification Artifacts in Open-Source Pull Request Workflows Do Not Reduce Defects", ESEM 2026, <https://drops.dagstuhl.de/storage/00lipics/lipics-vol394-esem2026/LIPIcs.ESEM.2026.84/LIPIcs.ESEM.2026.84.pdf> [V]. Uvik benchmark, <https://uvik.net/spec-driven-development-benchmark/> [S]. Claude Code best practices (interview pattern, goal condition) [V].

**Apply:** In the brief, make the done-signals (M18) the core and keep prose short. Say that the user's approval, not the brief's existence, is the quality gate.

**Disagreement:** Claude Code docs recommend an interview and writing the result to spec.md [V]. That is vendor guidance, not tested evidence. The notes found no evidence on plan-approval gates as an intervention. Hill did not test spec-driven tools.

**M4. Defer design where change is cheap; design earlier where it is not.**

**Rule:** Do not build for a need that is not yet real, unless the code would be hard to change later. Spend up-front design on interfaces, data and decisions that are expensive to reverse.

**Why:** Fowler: "Yagni is only a viable strategy if the code is easy to change", and it does not apply to effort that makes software easier to modify. A presumptive feature has four costs: build, delay, carry and repair [V]. In "Is Design Dead?" he says YAGNI is sensible only with XP or a similar technique that lowers the cost of change [V]. Brooks says deciding what to build is the part "more difficult to rectify later" [V]. The two camps meet in "enough design for the risk" (M1).

**Sources:** Fowler, "Yagni", <https://martinfowler.com/bliki/Yagni.html> [V]. Fowler, "Is Design Dead?", <https://martinfowler.com/articles/designDead.html> [V]. Brooks 1986, "No Silver Bullet", <https://www.cs.unc.edu/techreports/86-020.pdf> [V].

**Apply:** In "Approach", mark each component as "easy to change later" or "hard to change" and design only the second kind in detail. Mention nothing speculative as a deliverable.

**Disagreement:** The cost-of-change curve is contested. Critics say the steep curve came from large projects (Boehm 1981) and that Beck's flattening claim rested on anecdote; tests and CI are argued to flatten it [S, search snippets, not fetched]. The origin of the "100:1" figure is unverified. The notes found no rigorous study of the net payoff of up-front design.

---

## Q1: what to build

**M5. State the goal as an outcome in the problem world, and list non-goals.**

**Rule:** Write what changes for whom as something observable, not as an activity. List what is excluded, meaning things that could reasonably be goals but were left out.

**Why:** Jackson: software is "building a machine ... to solve a problem in a given domain (a part of the ... world) ... to meet a customer's ... needs (the requirement)", and "problems are in the world" [V]. Polya's first phase asks "What is the unknown?", "What are the data?", "What is the condition?" [V~]. Ubl defines non-goals as "things that could reasonably be goals, but are explicitly chosen not to be goals", not negated goals [V]. Shape Up asks for no-gos: "if there's anything we're not doing in this concept, it's good to mention it here" [V]. The notes found no primary source for "outcomes rather than activities" as a principle, and Gause and Weinberg (1989) is [B] and kept to its thesis.

**Sources:** Jackson, MIT 6898 problem-frames slides, <https://people.csail.mit.edu/dnj/teaching/6898/lecture-notes/session8/slides/mj-problem-frames.pdf> [V]. Polya via <https://en.wikipedia.org/wiki/How_to_Solve_It> [V~]. Ubl [V]. Shape Up, <https://basecamp.com/shapeup/1.5-chapter-06> [V]. Gause and Weinberg 1989 [B].

**Apply:** Fill "Goal" with one observable sentence and its source, quoted. Fill "Out of scope" with at least the likely scope-creep items. If the goal is only an activity ("add a service"), rewrite it.

**Disagreement:** None found in the notes on the principle. All of it is practitioner and expert guidance; no outcome measurement was found.

**M6. Assume the requester cannot fully specify the task; plan how to extract the rest.**

**Rule:** Treat missing requirements as questions to extract, not gaps to fill with assumptions. Where the user cannot answer in the abstract, use a small prototype or example to get a reaction.

**Why:** Brooks: "The hardest single part of building a software system is deciding precisely what to build", and "the client does not know what he wants". He recommends "rapid prototyping of systems as part of the iterative specification of requirements" [V]. Brooks calls the assumption that the work can be fully specified up front "fundamentally wrong" [V]. Polya asks whether the condition is sufficient to determine the unknown [V~].

**Sources:** Brooks, <https://www.cs.unc.edu/techreports/86-020.pdf> [V] (1986 report; the 1987 IEEE version was not compared). Polya, via Wikipedia [V~].

**Apply:** Put each ambiguity that changes the design under "Open questions" instead of choosing silently. If a prototype or example would settle one, name it as the first slice.

**Disagreement:** Expert argument, not measurement. Ubl and Nygard also push for writing decisions down early, which sits in tension with deferral (see M4).

**M7. Do not trust your own sense that a task is well specified; ask about what only the user knows.**

**Rule:** Decide whether to ask by a checklist, not by a feeling of being unsure. Split unknowns into "readable from the code" and "only the user knows", then ask about the second group before building.

**Why:** Vijayvargiya et al. (ICLR 2026, Ambig-SWE, an underspecified variant of SWE-bench Verified with a simulated user) found that interaction improves performance "up to 74% over the non-interactive settings", and that "models struggle to distinguish between well-specified and underspecified instructions" [V]. The paper adds that "LLMs default to non-interactive behavior without explicit encouragement" [V]. Models were 2025 proprietary and open-weight models [V~]. Edwards and Schuster (2026) say current agents are "largely optimized for autonomous execution" [V]; a scaffold that separates underspecification detection from code execution reached a 69.40% resolve rate [V] and asked fewer questions on simple tasks and more on complex ones [V~]. Cemri et al. list "fail to ask for clarification" at 6.8% of multi-agent failures (GPT-4, Claude 3, Qwen2.5 and CodeLlama era frameworks) [V~].

**Sources:** Vijayvargiya et al., <https://arxiv.org/abs/2502.13069> [V~]. Edwards and Schuster, <https://arxiv.org/abs/2603.26233> [V~]. Cemri et al., <https://arxiv.org/abs/2503.13657> [V~].

**Apply:** In "Open questions", list only what the code cannot answer. In the brief, say which unknowns you resolved by reading, so the user sees the questions are not lazy.

**Disagreement:** The gains come from question-asking with a simulated user, not from a formal plan-approval step, and the notes found no evidence for the latter. Claude Code docs also say a vague prompt is "completely fine" when exploring rather than fixing something specific [V].

**M8. Fix a budget first and let scope flex.**

**Rule:** Decide how much effort the task is worth before designing, then cut scope to fit instead of extending effort.

**Why:** Shape Up: appetite is "The amount of time we want to spend on a project, as opposed to an estimate." "Estimates start with a design and end with a number. Appetites start with a number and end with a design." The principle is "fixed time, variable scope" [V]. Brooks and Shape Up converge on cutting scope over stretching time (note-taker's inference).

**Sources:** Shape Up ch. 2 (the appetite definition), <https://basecamp.com/shapeup/1.1-chapter-02> [V]; ch. 3 (the "Estimates start with a design" sentence and "fixed time, variable scope"), <https://basecamp.com/shapeup/1.2-chapter-03> [V].

**Apply:** If the user gave a deadline or size, state it as the budget. If not, propose one and mark it as an assumption.

**Disagreement:** None found in the notes, but this is a practitioner framework for human teams with no measured effect, and its fit to an agent session is unexamined.

---

## Q2: what we need to know

**M9. List only the unknowns that change the approach, and resolve each by read, run or ask.**

**Rule:** For each unknown, say what it is, why it would change the approach, and how it gets resolved. Pick the cheapest probe that matches the kind of unknown.

**Why:** In the Artima interview with Hunt and Thomas (the text does not mark which of them says the feedback sentence), a tracer is one thin line of execution that goes end to end ("The more quickly you can get feedback, the less change you need to get back on target"), while a prototype investigates one specific question and prototypes "are designed to be thrown away" [V]. Shape Up calls a part "too unknown, complex, or open-ended to bet on" a rabbit hole, and notes it sometimes needs only a few lines of text to patch [V]. Cynefin links the mode to the kind of unknown [V~]. The mapping "unknown requirement: ask or prototype; feasibility: timeboxed spike; integration: tracer; unknown unknowns: safe-to-fail probe" is the note-taker's inference. Value of information (gather only if it could change the decision and its expected value exceeds its cost) is [B], not researched, paraphrase only. Polya's "work a simpler related problem" fits here [V~].

**Sources:** Hunt and Thomas, Artima, <https://www.artima.com/articles/tracer-bullets-and-prototypes> [V]. Shape Up ch. 6, <https://basecamp.com/shapeup/1.5-chapter-06> [V]. Cynefin [V~]. Value of information (Howard 1966) [B]. Cockburn's walking skeleton and the spike definition could only be seen in snippets or not at all [S]; do not quote.

**Apply:** Write the unknowns in a short list tagged read, run or ask. Resolve read items now and cite `file:line`. Run cheap read-only experiments now. Label any probe "throwaway" or "kept".

**Disagreement:** Sources differ on whether tracer code is kept or thrown away; the book emphasis (kept) is [B] and one secondary source says throwaway [S]. Nothing measured shows that listing unknowns improves outcomes.

**M10. A feeling of understanding how something works is weak evidence; read the code.**

**Rule:** Before building on "I know how this module works", try to explain, in a few sentences, how it handles one specific input from start to finish. If you cannot, read the code before designing.

**Why:** Rozenblit and Keil (2002) found people "feel they understand complex phenomena with far greater precision, coherence, and depth than they really do". The illusion is "far stronger for explanatory knowledge than many other kinds of knowledge", and attempting to explain "led to a decrease in self-rated understanding". It is strongest for causal mechanisms: mean overconfidence was .918 for devices and .291 for facts, and -.173 for procedures [V]. So "why does this service behave so" is more at risk than "how to run the build". Applying this to an LLM agent is the note-takers' inference; the notes found no study of LLM self-assessment on this effect.

**Sources:** Rozenblit and Keil 2002, Cognitive Science 26(5), <https://pmc.ncbi.nlm.nih.gov/articles/PMC3062901/> [V]. The PMC page itself returned a reCAPTCHA page, so the text was read from a Wayback copy of it. Mills and Keil 2004 (children) [S].

**Apply:** Put only checked facts under "What we know", each with `file:line`. Put everything else under "Assumptions" with what breaks if it is wrong. For "how does this flow work" questions, trace it rather than recall it.

**Disagreement:** None found in the notes, and no failed replication was found, though replication was not searched for. Transfer to LLM agents is unverified.

**M11. Gather context before editing.**

**Rule:** Read the files, tests and conventions around the change before choosing the approach. Do not ask the user for facts the repo can answer.

**Why:** Mehtiyev and Assuncao (2026) analysed 9,374 trajectories from 19 agents (8 frameworks, 14 LLMs) on 500 tasks. Agents that gather context before editing and invest in validation succeed more often. The study is observational, and the strategies are set by the agent, not adapted per task [V]. A separate study of OpenHands, SWE-agent and Prometheus found most trajectories identify the problematic files (72 to 81%, even in failures) [V]. Claude Code docs say current models are very good at reading code to find layout, conventions and the test framework [V]. Kadavath et al. (Anthropic, 2022) found large models well calibrated on multiple-choice questions but struggling on new tasks with calibration of p(ik), the probability that "I know" the answer to a question [V]. That was 2022-era models answering questions, not agents.

**Sources:** Mehtiyev and Assuncao, <https://arxiv.org/abs/2604.02547> [V]. "Understanding Code Agent Behaviour", <https://arxiv.org/abs/2511.00197> [V]. Claude Code best practices [V]. Kadavath et al., <https://arxiv.org/abs/2207.05221> [V].

**Apply:** Do the reading before writing the brief. Cite what you read. In "Open questions" list nothing the code could have told you.

**Disagreement:** The two trajectory papers differ on whether trajectory length predicts failure (raw correlation versus confound-adjusted). The notes found no study of whether an agent's verbal confidence about a code change tracks correctness.

**M12. Build a representation of the problem first, and set a point at which to abandon an approach.**

**Rule:** Spend effort understanding what is being asked and which known pattern it resembles before generating code. Decide in advance what evidence would make you drop the first approach.

**Why:** Chi, Feltovich and Glaser (1981): experts categorise physics problems by underlying principle, novices by surface features [S]. A Schoenfeld case on a course page: the expert mathematician "spent more than half of his allotted time trying to make sense of the problem", and students "kept working on it, despite clear evidence that they were not making progress" [V~]. The page does not cite the Schoenfeld paper precisely, and the "about 60%" quick-decision figure traces to sources that could not be fetched [S]. Larkin et al. (1980) on forward versus backward working is [B].

**Sources:** Chi, Feltovich and Glaser 1981 [S]. SERC Carleton page, <https://serc.carleton.edu/quantskills/workshop05/metacognition.html> [V~]. Larkin, McDermott, Simon and Simon 1980 [B]. DeFranco 1996 (URL seen, not fetched) [S].

**Apply:** In "Approach", describe the problem in your own words before the solution, and name the first approach's abandon trigger (for example "if the spike shows X, switch to Y").

**Disagreement:** DeFranco (1996) found expert mathematicians who neither solved the problems nor showed the expert control behaviour Schoenfeld described, so "experts plan and monitor" is not universal [S]. The evidence is physics and mathematics, and the notes found no software replication. The time-fraction numbers do not carry over to tasks that are already recognised.

**M13. Anchor estimates on analogous past tasks (the outside view).**

**Rule:** Before estimating size or risk, find similar past tasks in this repo or its history and note how they went. State which class of past tasks you used.

**Why:** Buehler, Griffin and Ross (1994) report students estimating 33.9 days against an actual 55.5 for a thesis [S]. People underestimate their own tasks but not other people's. Reference-class forecasting means: pick a reference class of past projects, find the distribution of outcomes, place the current project in it. The class must be broad enough to be meaningful and narrow enough to be comparable [S]. Precedent can miss extreme outcomes.

**Sources:** Buehler, Griffin and Ross 1994, JPSP 67(3), PDF fetched but unreadable [S]. PMI article on reference class forecasting, <https://www.pmi.org/learning/library/nobel-project-management-reference-class-forecasting-8068> [S]; the direct fetch returned 403, so it was read through a Wayback copy (the text is Flyvbjerg's 2006 paper). Flyvbjerg 2006 [S]. Flyvbjerg and Gardner 2023 [B].

**Apply:** Add one line under "Approach" or "Assumptions": "Similar past change: <commit or PR>, which touched <n> files and needed <thing>". If no analogue exists, say so.

**Disagreement:** Whether the outside view helps for novel software tasks with no reference class was not found. Every source here is [S] or [B]; the effect on agents is untested.

**M14. Use a pre-mortem as a cheap risk prompt, not as proof.**

**Rule:** Assume the work has already failed and write the few most likely causes. Use the answers to add checks or reorder slices. Do not cite it as a proven technique.

**Why:** Klein's premortem has team members "assume that the project they are planning has just failed", with the aim of making it "safe for dissenters ... to speak up" [V, HBR intro page only; paywalled]. The lab basis is Mitchell, Russo and Pennington (1989): explanations for events described as certain were longer and relied more on specific episodes [V~, via Wikipedia]. A widely repeated "30%" improvement figure could not be traced to a measure and study, so it is not used here [S]. Wikipedia notes the analysis "may be identifying threats/weaknesses that are not in fact real" [V~]. The notes found no evidence that premortems improve project outcomes; the evidence is about idea generation.

**Sources:** Klein 2007, HBR, <https://hbr.org/2007/09/performing-a-project-premortem> [V] (intro only). Mitchell, Russo and Pennington 1989, JBDM 2(1), DOI 10.1002/bdm.3960020103 [S]. <https://en.wikipedia.org/wiki/Pre-mortem> [V~].

**Apply:** For a big task, add the top three failure causes to "Assumptions" or "Not covered by the checks", each tied to a check or a slice. Skip it for small tasks.

**Disagreement:** The effect on outcomes is unknown, and the exercise can invent threats. Treat it as optional.

---

## Q3: how to build it

**M15. Name a rejected alternative and the reason.**

**Rule:** Describe the approach in terms of the components it touches, and name at least one alternative you did not choose, with the reason. If you cannot name one, you have not looked at the option space.

**Why:** Ubl calls the alternatives section "one of the most important ones", listing other designs that could reach similar outcomes with trade-offs and why the chosen one fits the goals better [V~]. Nygard's decision record covers Context, Decision, Status and Consequences, and exists because the motivation behind decisions is among the hardest things to track; it avoids "blind acceptance or blind reversal" [V]. The note-taker's minimum pre-implementation content (context, goals, non-goals, approach, one rejected alternative, consequences or open questions) is an inference. The notes found no RFC-process source and no evidence that design documents improve outcomes; Ubl's piece is a practice report.

**Sources:** Ubl [V~]. Nygard 2011, "Documenting Architecture Decisions", <https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions> [V].

**Apply:** Fill "Rejected" with one alternative and a one-clause reason that is specific to this codebase. Do not invent a strawman.

**Disagreement:** Ubl himself says to skip the document when the solution is obvious with no trade-offs (M1). Reasoning only: a rejected alternative that nobody would pick is filler.

**M16. Put the riskiest slice first, as a thin end-to-end slice.**

**Rule:** Cut the work into small slices that each end in something checkable. Do first the slice that could invalidate the approach (feasibility, integration, unclear requirement).

**Why:** Boehm's spiral model makes risk determine the order and the detail of work, and warns that it is not "simply a sequence of waterfall increments" [V~, via Wikipedia; primary PDF returned 404]. DORA: "working in small batches predicts software delivery performance and organizational performance", it lets you test hypotheses quickly and course correct, and it prevents "the sunk-cost fallacy" [V]. The page gives no effect sizes. Hunt and Thomas: quick feedback means less change needed to get back on target [V~]. Shape Up uses a small batch of one or two weeks for a small team [V~]. "Riskiest first" as a slogan and vertical versus horizontal slicing have no fetched primary source, and Reinertsen on batch size is [B].

**Sources:** Boehm 1988 [S]; Wikipedia rendering [V~]. DORA, <https://dora.dev/capabilities/working-in-small-batches/> [V]. Hunt and Thomas [V~]. Shape Up ch. 3 [V~].

**Apply:** Order "Slices" by risk, and mark the first one as the slice that tests the main assumption. Give each slice a done-signal (M18).

**Disagreement:** The notes found no empirical test of "riskiest first". DORA's finding is about delivery performance in human teams, not agent sessions.

**M17. Treat irreversible steps differently from reversible ones.**

**Rule:** Identify steps that are hard or impossible to undo: data migrations, deleted data, published interfaces, external side effects. Give those steps more analysis, an explicit guard and, where needed, the user's approval. Move reversible steps fast.

**Why:** Bezos (2015 shareholder letter): "Some decisions are consequential and irreversible or nearly irreversible - one-way doors -", and "these decisions must be made methodically, carefully, slowly, with great deliberation and consultation." Most decisions "are changeable, reversible - they're two-way doors", and those "can and should be made quickly by high judgment individuals or small groups" [V]. The page also has an unrelated passage with a "70%" figure, about facility expansion; it is not used. Fowler conditions YAGNI on cheap change, which is the same distinction (M4) [V~]. The notes found no source on classifying agent actions as reversible.

**Sources:** Bezos, 2015 letter, <https://www.sec.gov/Archives/edgar/data/1018724/000119312516530910/d168744dex991.htm> [V]. Fowler, "Yagni" [V~]. Poppendieck's "last responsible moment" (2003) is secondhand wording [S/B]; Cockburn and Wirfs-Brock dispute treating it as a single instant [S].

**Apply:** In "Approach", add a line "Hard to reverse: <step>, guarded by <backup, dry run, approval, feature flag>". If nothing is irreversible, say "none".

**Disagreement:** Poppendieck's "delay commitment until the cost of delay exceeds the benefit" is contested by Cockburn and Wirfs-Brock (who prefers "most responsible moment") [S]. The one-way and two-way framing is a practitioner heuristic with no empirical test in the notes.

---

## Q4: how to verify it

**M18. Fix the done-signal before building.**

**Rule:** For each slice, write the command, test or screen state, and the result that counts as a pass, before the code exists. If no check is possible, say so up front.

**Why:** Nosek et al. (2018): "Mistaking generation of postdictions with testing of predictions reduces the credibility of research findings", and "ordinary biases in human reasoning such as hindsight bias make it hard to avoid this mistake". Both modes are valuable, postdiction for discovery and prediction for testing [V, author copy; PNAS page returned 403]. Gelman and Loken: analysis details can become "highly contingent on data, without the researcher performing any conscious procedure of fishing" [V]. The software analogue (a check written after seeing the output is a postdiction) is the note-takers' inference; no source claims it for software, and no software study of pre-set criteria was found. The Scrum Guide says "The Definition of Done is a formal description of the state of the Increment when it meets the quality measures required for the product", and "The Developers are required to conform to the Definition of Done" [V]. Claude Code docs: "Claude said it was done and it wasn't quite, usually because it had no way to check its own work"; ask for evidence, the command and its output [V].

**Sources:** Nosek, Ebersole, DeHaven and Mellor 2018, PNAS 115(11), <https://errorstatistics.com/wp-content/uploads/2017/07/nosek-et-al-preregistration-revolution.pdf> [V]. Gelman and Loken, <https://sites.stat.columbia.edu/gelman/research/unpublished/forking.pdf> [V]. Scrum Guide 2020, <https://scrumguides.org/scrum-guide.html> [V]. Claude Code best practices [V]. Kerr 1998 (HARKing) [S].

**Apply:** Each slice in the brief ends "Done when: <command> shows <result>". Label exploratory work (a spike) as exploratory and pin its finding with a check afterwards.

**Disagreement:** Ledgerwood (2018) argues preregistration conflates preregistering a prediction with preregistering an analysis plan [S]. Whether preregistration improves the credibility of science is itself debated [S]. The transfer to software is analogy only.

**M19. Decide the check and keep steps small; do not require test-first order.**

**Rule:** Name the observable behaviour and its check before each step, and work in short steps. Do not insist on writing the test before the code as a rule, because the notes do not show that order matters.

**Why:** Fucci et al. (2017, IEEE TSE; 82 data points from 39 professionals): "Sequencing, the order in which test and production code are written, had no important influence", and benefits "may not be due to its distinctive test-first dynamic, but rather due to the fact that TDD-like processes encourage fine-grained, steady steps". Quality and productivity improvements were primarily positively associated with granularity and uniformity [V]. The authors say they did not tackle the potential benefits of test-first in resolving requirements uncertainty, and mention longer-term studies with larger tasks [V]. Nagappan et al. (2008) report 40 to 90% lower pre-release defect density and, subjectively, a 15 to 35% increase in initial development time across four industrial teams, but with no enforcement of TDD, team self-selection and after-the-fact comparison projects [V~]. Erdogmus et al. (2005): 24 subjects, more tests and higher productivity for test-first, mixed quality [S]. North frames a test name as a sentence about the next behaviour, asking "What's the next most important thing the system doesn't do?" [V]. Beck's and Adzic's claims are advocacy and [B]. Karac and Turhan (2018) could not be fetched [S].

**Sources:** Fucci et al., <https://arxiv.org/pdf/1611.05994> [V]. Nagappan et al., <https://neverworkintheory.org/2012/01/25/realizing-quality-improvement-through-test-driven-development.html> [V~]. Erdogmus et al. 2005 [S]. North, <https://dannorth.net/blog/introducing-bdd/> [V]. Beck 2002, Adzic 2011 [B].

**Apply:** In each slice, write the done-signal as a behaviour statement. Keep slices small enough that the check can run in minutes. Do not write "TDD" in the brief unless the repo already works that way.

**Disagreement:** This is the largest disagreement in the notes. Advocates (Beck, North) say test-first changes design and clarity. The strongest process-level evidence (Fucci) finds order unimportant. Industrial studies show large defect reductions but are uncontrolled. Controlled experiments are small and student-heavy. No meta-analysis was fetched.

**M20. Name the oracle, and separate verification from validation.**

**Rule:** For each check, say how a result is judged correct: a spec, reference implementation, invariant, earlier output or a human. If there is no oracle, say the check is a human judgment and whose. Say whether the check shows "built to the spec" or "the right thing built".

**Why:** Barr et al. survey the oracle problem and ways to automate oracles through models, specifications, contract-driven development and metamorphic testing [V]. Boehm's pair (verification: "Am I building the product right?", validation: "Am I building the right product?") appears in a 2005 slide deck that cites Boehm, "Verifying and Validating Software Requirements and Design Specifications", IEEE Software, 1984; the Boehm text itself was not read [S]. IEEE 1012 wording was not confirmed [S]. That verification can pass while validation fails is the note-takers' inference.

**Sources:** Barr, Harman, McMinn, Shahbaz and Yoo, "The Oracle Problem in Software Testing: A Survey", <https://web.eecs.umich.edu/~weimerw/2018-481/readings/testoracles.pdf> [V]. The year (2015), the venue (IEEE TSE) and the DOI 10.1109/TSE.2014.2372785 are not printed in the fetched text and stay unconfirmed [S]. Boehm 1984 via <https://ndia.dtic.mil/wp-content/uploads/2005/systems/tuesday/olson.pdf> [S].

**Apply:** Add the oracle to each done-signal ("shows X, compared against Y"). If a slice has only a characterisation check (it records what the code does now), label it "detects change, not correctness".

**Disagreement:** None found in the notes. No primary text for Boehm or IEEE 1012 was read, so keep those parts as paraphrase.

**M21. Pick the check level that crosses the real boundary where the risk lives.**

**Rule:** Choose the cheapest check that can show the failure you care about. If the risk is at an integration boundary, a unit test with that boundary mocked does not show the integration works.

**Why:** Google (Software Engineering at Google, ch. 11) suggests about 80% narrow unit tests, 15% medium, 5% end-to-end, and says "Some of the worst offenders of brittle tests come from the misuse of mock objects" [V]. Fowler and Vocke: push tests as far down as you can, and "If a higher-level test spots an error and there's no lower-level test failing, you need to write a lower-level test"; contract tests keep consumer and provider to the agreed contract [V]. DORA: "when the tests pass we should be confident the software is releasable", with feedback in less than ten minutes [V]. That a mocked boundary only shows your assumption is self-consistent is the note-taker's inference; the contract-test passage is the closest sourced support.

**Sources:** SWE at Google ch. 11, <https://abseil.io/resources/swe-book/html/ch11.html> [V]. Fowler and Vocke, <https://martinfowler.com/articles/practical-test-pyramid.html> [V]. DORA, <https://dora.dev/capabilities/test-automation/> [V].

**Apply:** Next to each done-signal, state the level (unit, integration, end to end, manual) and why it can see the risk. If the check needs a fixture, harness or seeded sandbox that does not exist, add it as a slice.

**Disagreement:** Pyramid (mostly unit) versus trophy (mostly integration). The trophy position has no fetched source. All sources agree that unreliable or over-mocked tests lose value. No empirical study comparing levels was found.

**M22. Check the check: confirm it can fail.**

**Rule:** Before trusting a pass, show the check fails when the behaviour is broken. Run it red first, or break the code on purpose.

**Why:** Goodhart (1975) and Strathern (1997): "When a measure becomes a target, it ceases to be a good measure" [V~, via Wikipedia; originals not fetched]. Campbell's law circulates in varying wordings and should not be cited as primary [V~]. Google reports mutation testing, which inserts small faults to assess suite efficacy, used by 6,000 engineers in code review [V]. Feathers coined the term characterisation test, a test that describes the actual behaviour of an existing piece of software [V~]. The agent-specific failure modes (tests written after the code to match its output, assertions on mocks, assertions that cannot fail) are the note-taker's inference; no study of LLM tests gaming checks was retrieved.

**Sources:** Goodhart's law, <https://en.wikipedia.org/wiki/Goodhart%27s_law> [V~]. Petrovic and Ivankovic 2018, <https://research.google/pubs/state-of-mutation-testing-at-google/> [V]. Feathers 2004 via <https://en.wikipedia.org/wiki/Characterization_test> [V~]; book [B].

**Apply:** In the plan for each slice, include a "fails when" note: the change that must make the check go red. Golden-master testing, reproduce-before-fix and eval-driven development have no fetched sources, so do not cite them.

**Disagreement:** The cost and noise of mutation testing in practice are not covered in the notes.

**M23. State what the checks cannot show.**

**Rule:** In the brief, list what the checks exercised, what environment they ran in, what was not run, and what a pass does not imply.

**Why:** Dijkstra (EWD249, 1970): "Program testing can be used to show the presence of bugs, but never to show their absence!" Exhaustive testing is out of the question [V]. Wording varies across secondary sources; quote only this form. The notes treat it as an argument for targeted checks plus reasoning, types and contracts where tests cannot reach, not for skipping tests. The structure of the residual-risk statement is the note-taker's construction, not sourced.

**Sources:** Dijkstra, EWD249, <https://www.cs.utexas.edu/users/EWD/transcriptions/EWD02xx/EWD249/EWD249.html> [V]. Section number not seen; Wikiquote cites section 3 [S].

**Apply:** Fill "Not covered by the checks" with specifics, such as "real payment gateway not exercised, only the sandbox", not "edge cases".

**Disagreement:** None found in the notes. No source on formats for residual-risk reporting (safety or assurance cases) was retrieved.

---

## For an LLM agent specifically

**M24. Do not rely on the same model to critique its own plan or output; use an external check.**

**Rule:** Anchor the plan to checks that run outside the model: tests, a compiler, the repo, or the user. Treat a review of the plan by the same model as weak evidence.

**Why:** Huang et al. (ICLR 2024; the models tested were not confirmed): "LLMs struggle to self-correct their responses without external feedback", and "their performance even degrades after self-correction" [V]. Stechly, Valmeekam and Kambhampati (ICLR 2025; GPT-4 on Game of 24, graph colouring, STRIPS planning): "significant performance collapse with self-critique" and "significant performance gains with sound external verification" [V]. Kambhampati et al., a position paper on formal planning benchmarks (venue not confirmed): "auto-regressive LLMs cannot, by themselves, do planning or self-verification"; pair them with "external model-based verifiers" [V]. Reflexion reports 91% pass@1 on HumanEval against 80% for GPT-4, using feedback signals from external or internally simulated sources [V]. Whether that squares with Huang et al. depends on how much of the feedback was external, which the abstract does not settle; Huang et al. studied correction without external feedback. SWT-Bench found LLM-generated tests are "an effective filter for proposed code fixes, doubling the precision of SWE-Agent" (2024 models) [V]. Valmeekam et al. 2023 on self-critiquing plans is cited by its title only: the PDF was fetched, but only the title was checked [S].

**Sources:** Huang et al., <https://arxiv.org/abs/2310.01798> [V]. Stechly et al., <https://arxiv.org/abs/2402.08115> [V]. Kambhampati et al., <https://arxiv.org/abs/2402.01817> [V]. Shinn et al., <https://arxiv.org/abs/2303.11366> [V]. Mundler et al., <https://arxiv.org/abs/2406.12952> [V]. Valmeekam et al. 2023, <https://arxiv.org/pdf/2310.08118> [S].

**Apply:** Every done-signal in the brief must be something a command or the user can run. Do not write "review the plan again" as a check. A failing reproduction test before a fix is supported indirectly (SWT-Bench), not by a controlled test-first agent experiment.

**Disagreement:** The self-correction results are for 2023-2024 models and intrinsic correction only. The notes did not test current frontier models. Kambhampati's claims concern formal planning, not software tasks.

**M25. Do not pad the brief with step-by-step reasoning for its own sake.**

**Rule:** Keep the brief to the facts, decisions and checks. Do not add long reasoning chains or a larger effort setting because the task feels important.

**Why:** Meincke, Mollick, Mollick and Shapiro (Wharton, 2025; mid-2025 models): "CoT prompting often results in only marginal, if any, gains in answer accuracy" for reasoning models, a small gain for non-reasoning models, and it "significantly increases the time and tokens needed" and "can introduce more variability in answers" [V]. The Wharton tech-report page adds GPQA Diamond (198 questions), 25 trials per condition, 8 models and 20 to 80% more time [S]. Sprague et al. (2024) is titled "Chain-of-thought helps mainly on math and symbolic reasoning" [V]. Claude Code docs say effort `max` may be no better than high, and "keep going" style prompts are more likely to cause over-work than fix a stall [V].

**Sources:** Meincke et al., <https://arxiv.org/abs/2506.07142> [V]. Detail numbers via <https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/> [S]. Sprague et al., <https://arxiv.org/abs/2409.12183> [V]. Claude Code best practices [V].

**Apply:** Write the brief as short, specific lines. Spend the budget on reading the repo (M11) and on naming checks (M18), not on narrative.

**Disagreement:** The Wharton benchmark is question answering, not planning a software change. This heuristic is about extra reasoning chains, not about whether to plan at all (see M1 and M2).

**M26. Treat 2022-2023 prompt-planning gains as motivation, not proof.**

**Rule:** Do not cite plan-first, decompose-first or reflect-first prompting results as proof that a brief improves a repository-level change.

**Why:** Plan-and-Solve (GPT-3): "consistently outperforms Zero-shot-CoT across all datasets by a large margin" [V]. ReAct (PaLM and GPT-3 era) beat imitation and RL methods on ALFWorld and WebShop by absolute success rates of 34% and 10% [V~]. Least-to-Most (code-davinci-002): SCAN at least 99% with 14 exemplars against 16% for chain of thought, on a synthetic task [V~]. Tree of Thoughts (GPT-4): Game of 24 at 74% against about 4% [V]. Metacognitive Prompting and Self-Ask were read as abstracts only and tested language-understanding or QA tasks [S]. The biggest effects are on small puzzles with a clear success check. The common useful ingredient in ReAct and Reflexion is contact with an external signal, not thinking alone.

**Sources:** Wang et al., <https://arxiv.org/abs/2305.04091> [V]. Yao et al. (ReAct), <https://arxiv.org/abs/2210.03629> [V~]. Zhou et al., <https://arxiv.org/abs/2205.10625> [V~]. Yao et al. (Tree of Thoughts), <https://arxiv.org/abs/2305.10601> [V]. Press et al. (Self-Ask), <https://arxiv.org/abs/2210.03350> [S]. Wang and Zhao, <https://aclanthology.org/2024.naacl-long.106> [S].

**Apply:** Do not claim a measured benefit for the brief itself. Justify it by the cheap-to-catch-early argument and the user's approval gate.

**Disagreement:** None found in the notes. Nothing here was verified on 2026 frontier models.

**M27. Build the brief against known agent failure modes.**

**Rule:** Make the brief guard against failing early (no verification, wrong or over-specific fix, ignoring the task spec) and against stalling (analysis paralysis). Say how to verify with an executable check, not just "verify".

**Why:** Cemri et al. (2025, 1,642 traces, 7 multi-agent frameworks; GPT-4, Claude 3, Qwen2.5 and CodeLlama era) list failure modes including: disobey task specification 11.8%, reasoning-action mismatch 13.2%, no or incomplete verification 8.2%, incorrect verification 9.1%, premature termination 6.2% [V]. Step repetition at 15.7% was derived from scrambled figure text and is unconfirmed [V~]. The paper's category sums are not stated by the authors, and the sums in the notes (such as 23.5% for task verification) are the note-taker's own arithmetic, so they are not used here. These are multi-agent systems, not single coding agents. The SWE-agent paper says "about half (52.0%) of unresolved instances fall into the Incorrect Implementation or Overly Specific Implementation categories" [V]. Mehtiyev and Assuncao found never-solved tasks needed only simple patches but failed on gaps in architectural reasoning and domain knowledge [V~]. Agentless (2024) reached 32.00% on SWE-bench Lite [V]. Its authors manually classified the problems and "found problems with exact ground truth patch or insufficient/misleading issue descriptions" [V]. It uses a fixed localisation, repair and validation pipeline [S].

**Sources:** Cemri et al., <https://arxiv.org/abs/2503.13657> [V~]. SWE-agent, <https://arxiv.org/pdf/2405.15793> [V]. Mehtiyev and Assuncao [V~]. Xia et al. (Agentless), <https://arxiv.org/abs/2407.01489> [S].

**Apply:** Check the brief: does every slice have an executable done-signal (M18)? Is the task spec quoted (M5)? Is there a stop point (M2)? Is there an assumption list (M10)?

**Disagreement:** No controlled comparison of plan-then-execute against interleaved work on software tasks was found. The notes found no fetched taxonomy attributing SWE-bench failures to "misunderstood the task" with a percentage.

---

## Known gaps

What the research did not cover or could not verify, for a later pass.

- **Primary texts not read** (paywall, 403 or 404, unreadable PDF, or only a secondary page): Flavell 1979, Schraw 1994 and 1998, Chi et al. 1981, Schoenfeld 1985 and 1992, Larkin 1980, Buehler et al. 1994 (PDF unreadable), Mitchell et al. 1989, Boehm 1988 and 1984 (the 1984 wording was seen only in a 2005 slide deck that cites it), Kerr 1998, Karac and Turhan 2018, Erdogmus et al. 2005, Nagappan et al. 2008 (abstract via a reviewer page only), Valmeekam et al. 2023 (PDF fetched, only the title checked). The Rozenblit and Keil text and the PMI article were read through Wayback copies.
- **Not re-checked in the second pass** (no URL in the file, or a detail the pass did not cover): Klein et al. 1986 (M1); Ubl on the alternatives section, Boehm spiral wording, Hunt and Thomas and Shape Up small-batch claims (M15, M16); Fowler in M17; the Claude Code docs claims in M11, M18, M25 and M27's Mehtiyev and Assuncao detail; the 2025 model dating in M7 and the complex-task half of the Edwards and Schuster claim; the model lists behind Huang et al., Stechly et al. (also its ICLR 2025 venue), Plan-and-Solve, ReAct and Least-to-Most; the Kambhampati venue; the Barr year, venue and DOI; the Cemri step repetition figure of 15.7%; the Agentless pipeline description. Books and sources with no URL were not re-checked.
- **Books, paraphrase only**: Polya (checklist wording not obtained), Gause and Weinberg, Beck, Adzic, Feathers, Reinertsen, Flyvbjerg and Gardner, Simon on satisficing, Howard on value of information.
- **No source at all**: golden-master testing, reproduce-before-fix, eval-driven development, canaries and smoke checks, the test trophy, RFC processes, "outcomes rather than activities", plan drift and stale plans, how long a brief should be, effect of a plan-approval step on task success, verbal confidence of coding agents, hallucinated APIs and files.
- **No software evidence**: pre-mortems, outside view, Schoenfeld-style monitoring, illusion of explanatory depth, preregistration analogy. Transfer to coding agents is inference.
- **No test on current models**: no fetched study measures plan prompts on 2026 frontier coding models for repository-level tasks. The OpenAI and Google agent guides and the Kiro and Spec Kit docs were not fetched.
- **Number provenance**: the "30%" prospective-hindsight figure is untraceable and unused. The 23.5% verification-failure sum is the note-taker's arithmetic and unused. The "100:1" cost-of-change figure and the "60%" Schoenfeld quick-decision figure are unverified. The Poppendieck wording is secondhand.
- **Identifiers to avoid**: arXiv 1802.01188, 1802.08646 and 2405.20253 resolved to unrelated papers and must not be cited. Karac and Turhan 2018 has no verified URL. Other 2026 arXiv items seen only in search results (2604.05278, 2611.05094, 2608.25202) were not fetched and are not used.
- **Tag inconsistencies**: Campbell's law and the Dijkstra quote circulate in several wordings. The Brooks quote is from the 1986 report, not compared with the 1987 IEEE version. Ledgerwood and Nosek reply PMC ids were not matched to their papers.
