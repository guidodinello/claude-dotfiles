# Design Review Principles

> **Purpose**: the vocabulary and the principle catalog behind every
> `/design-review` finding. Section 1 holds the frameworks that shape the
> report; section 2 is the catalog that Step 5 checks a change against.
>
> **Rule**: a principle-based finding cites the catalog ID and the source link
> from this file. If a concern does not map to an entry here, phrase it as an
> open question, not a finding.
>
> **House rules**: entries whose source is the user's own guidelines
> (`~/.claude/guidelines/design-principles.md`) are marked **House rule**.
> They need no URL: cite them as "house rule" plus the file path, for example
> `Principle: Do not key behavior on human-readable text (P7, house rule
> ~/.claude/guidelines/design-principles.md)`.

Nothing here is original. Every entry links the source it was taken from;
quotes are verbatim from the linked page, and paraphrases are marked as such.
Section 3 lists every source and how it was verified.

---

## 1. Frameworks

### 1.1 Quality attribute vocabulary - ISO/IEC 25010:2023

ISO/IEC 25010 is the product quality model of the SQuaRE series. Edition 2
was published in November 2023 and is composed of nine characteristics, each
subdivided into subcharacteristics
([ISO catalogue](https://www.iso.org/standard/78176.html); wording taken from
search results, the page refused direct access). The breakdown below follows
[arc42 Quality](https://quality.arc42.org/standards/iso-25010) and, for
Maintainability and Flexibility, [SonarSource's ISO/IEC 25010 guide](https://www.sonarsource.com/resources/library/iso-iec-25010-explained/):

| Characteristic | Subcharacteristics |
|----------------|--------------------|
| Functional suitability | Functional completeness, correctness, appropriateness |
| Performance efficiency | Time behaviour, Resource utilization, Capacity |
| Compatibility | Co-existence, Interoperability |
| Interaction capability | Appropriateness recognizability, Learnability, Operability, User error protection, User engagement, Inclusivity, User assistance, Self-descriptiveness |
| Reliability | Faultlessness, Fault tolerance, Availability, Recoverability |
| Security | Confidentiality, Integrity, Non-repudiation, Accountability, Authenticity, Resistance |
| Maintainability | Modularity, Reusability, Analysability, Modifiability, Testability |
| Flexibility | Adaptability, Scalability, Installability, Replaceability |
| Safety | Operational constraints, Risk identification, Fail safe, Hazard warning, Safe integration |

The 2023 edition renamed terms from the 2011 edition that many people still
use (Portability also became Flexibility, and Safety is new). Use the 2023
names in reports:

| Common (2011-era) term | 2023 term to write |
|------------------------|--------------------|
| Usability | Interaction capability |
| Understandability | Interaction capability / Self-descriptiveness (for users) or Maintainability / Analysability (for developers) |

In a report, write `Characteristic / Subcharacteristic`, for example
`Security / Confidentiality` or `Maintainability / Modifiability`.

### 1.2 Quality attribute scenarios - SEI

An attribute claim is testable only when it says what happens, to what, and
how well. The SEI Quality Attribute Workshop refines a scenario into six
parts ([Barbacci et al., *Quality Attribute Workshops, 3rd ed.*, CMU/SEI-2003-TR-016](https://www.sei.cmu.edu/documents/716/2003_005_001_14249.pdf),
§3.8, verbatim):

1. stimulus - the condition that affects the system
2. response - the activity that results from the stimulus
3. source of stimulus - the entity that generated the stimulus
4. environment - the condition under which the stimulus occurred
5. artifact stimulated - the artifact that was stimulated
6. response measure - the measure by which the system's response will be evaluated

Use it in Step 3 when a claim is vague. "The retry logic improves
reliability" becomes: *an upstream service (source) times out (stimulus)
under normal load (environment); the order service (artifact) retries with
backoff and the order completes (response) without a duplicate charge
(measure: zero duplicates, p99 latency under 3 s).* If the code cannot
deliver that response, the claim is not earned.

### 1.3 Decision records - Nygard ADRs and MADR

The report's Decisions section is a compressed ADR.

- [Michael Nygard, "Documenting Architecture Decisions" (2011)](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
  defines Title, Context ("the forces at play"), Decision, Status, and
  Consequences, and insists that "All consequences should be listed here, not
  just the 'positive' ones." His motivation: "One of the hardest things to
  track during the life of a project is the motivation behind certain
  decisions," and "It's better to avoid either blind acceptance or blind
  reversal."
- [MADR 4.0.0](https://adr.github.io/madr/) adds **Considered Options**,
  **Pros and Cons of the Options**, and **Confirmation** - how compliance
  with the decision will be checked, for example by a review or an ArchUnit
  test.

| Report section | ADR / MADR source |
|----------------|-------------------|
| 1. Decisions - Chose / Why | Decision, Context, Decision Drivers |
| 1. Decisions - Rejected | MADR Considered Options |
| 2. Quality attributes | MADR Decision Drivers |
| 3. Trade-offs | Nygard Consequences (negative and neutral ones) |
| 4. Invariants and their guards | MADR Confirmation |

### 1.4 Fitness functions - Ford, Parsons, Kua

From *Building Evolutionary Architectures* (O'Reilly), as quoted by the
[Thoughtworks Technology Radar](https://www.thoughtworks.com/radar/techniques/architectural-fitness-function):
an architectural fitness function "provides an objective integrity assessment
of some architectural characteristics" and "may encompass existing
verification criteria, such as unit testing, metrics, monitors, and so on."
Book chapter (paywalled, not opened): [Chapter 2, Fitness Functions](https://oreilly.com/library/view/building-evolutionary-architectures/9781492097532/ch02.html).

Use it in Step 4: a guard counts as a fitness function when it runs without a
human and fails loudly. A test that was never seen failing has not been shown
to assess anything - when the PR claims a guard, ask whether anyone broke the
invariant once to watch it fail.

### 1.5 The heavyweight version - ATAM

The SEI Architecture Tradeoff Analysis Method is "a method for evaluating
software architectures relative to quality attribute goals"; its analysis of
scenarios "results in the identification of risks, non-risks, sensitivity
points, and tradeoff points"
([SEI ATAM collection](https://www.sei.cmu.edu/library/architecture-tradeoff-analysis-method-collection/)).
This skill is a lightweight, single-reviewer cousin: it keeps ATAM's outputs
(risks, trade-offs) and its anchoring on quality attributes, and drops the
multi-day stakeholder workshop. When a change is large enough to need the real
thing, say so under Risks.

---

## 2. Principle catalog

Each entry: **Statement** (one line), **Smell** (what in a diff signals the
violation), **Ask** (the review question), **Source**. Grouped by the quality
attribute each principle mainly serves.

### Security

#### P1 - Fail-safe defaults

- **Statement:** "Base access decisions on permission rather than exclusion"
  - the default outcome is deny, and access is granted only under identified
  conditions, so mistakes block access instead of exposing data (paraphrase
  after the quote).
- **Smell:** a denylist of what to hide; an unknown value, missing marker, or
  parse error that falls through to "allow" or "pass through unchanged".
- **Ask:** If the policy cannot decide, what happens - hide or expose?
- **Source:** [Saltzer & Schroeder, "The Protection of Information in Computer
  Systems" (1975)](https://www.cs.virginia.edu/~evans/cs551/saltzer/).
  Also a **House rule**: "Privacy and security controls fail closed"
  (`~/.claude/guidelines/design-principles.md`).

#### P2 - Complete mediation

- **Statement:** "Every access to every object must be checked for authority."
- **Smell:** the same check copied into several call sites; a new path
  (backfill, admin script, retry) that reaches the data without passing the
  check.
- **Ask:** Is there a single choke point every access goes through, and can a
  new path bypass it?
- **Source:** [Saltzer & Schroeder](https://www.cs.virginia.edu/~evans/cs551/saltzer/).

#### P3 - Economy of mechanism

- **Statement:** "Keep the design as simple and small as possible" - small
  protection code can be inspected line by line, and its flaws do not show up
  in normal use (paraphrase after the quote).
- **Smell:** a security mechanism spread across many files or layers, or one
  too large to read in one sitting.
- **Ask:** Could a reviewer verify the whole protection mechanism in one
  reading?
- **Source:** [Saltzer & Schroeder](https://www.cs.virginia.edu/~evans/cs551/saltzer/).

#### P4 - Least privilege

- **Statement:** "Every program and every user of the system should operate
  using the least set of privileges necessary to complete the job."
- **Smell:** a new credential, role, token scope, or data copy broader than the
  feature needs (`SELECT *`, admin role for a read job, all columns copied
  "in case").
- **Ask:** What is the smallest access this component needs, and is that what
  it got?
- **Source:** [Saltzer & Schroeder](https://www.cs.virginia.edu/~evans/cs551/saltzer/).

#### P5 - Separation of privilege

- **Statement:** "a protection mechanism that requires two keys to unlock it
  is more robust and flexible" - no single mistake is enough to expose
  protected data (paraphrase after the quote).
- **Smell:** a single check stands between sensitive data and its consumer,
  with no independent second check.
- **Ask:** If this one check is wrong, does anything else catch it?
- **Source:** [Saltzer & Schroeder](https://www.cs.virginia.edu/~evans/cs551/saltzer/).

#### P6 - Psychological acceptability

- **Statement:** "the human interface be designed for ease of use," so people
  apply the protection correctly as a matter of routine.
- **Smell:** a protection that each developer must remember to call by hand,
  or that needs a separate step easy to forget (edit a second file, update a
  list).
- **Ask:** Is doing the safe thing the easiest thing for the next developer?
- **Source:** [Saltzer & Schroeder](https://www.cs.virginia.edu/~evans/cs551/saltzer/).

#### P7 - Do not key behavior on human-readable text

- **Statement:** comments, labels, and messages are documentation and get
  reworded; declare behavior as data (an enum, a decorator, a typed registry)
  and generate the text from it.
- **Smell:** `if (comment.includes(...))`, matching on an error message,
  branching on a display label.
- **Ask:** What breaks if someone fixes a typo in this string?
- **Source:** **House rule**, `~/.claude/guidelines/design-principles.md`
  (no URL; cite as "house rule" plus the path).

### Functional correctness and reliability

#### P8 - Make illegal states unrepresentable

- **Statement:** shape the types so that nonsensical combinations cannot be
  constructed, moving the check from runtime to the compiler (paraphrase; the
  source makes the point with a before/after connection-state type).
- **Smell:** optional fields that must be set together; a flag that decides
  which other fields are meaningful; a runtime check for a state the type
  could have excluded.
- **Ask:** Can this invalid combination be built at all? If yes, why does the
  type allow it?
- **Source:** [Yaron Minsky, "Effective ML Revisited", Jane Street Tech Blog](https://blog.janestreet.com/effective-ml-revisited/)
  (section "Make illegal states unrepresentable").

#### P9 - Parse, don't validate

- **Statement:** "the difference between validation and parsing lies almost
  entirely in how information is preserved" - turn unstructured input into a
  precise type once, at the boundary, instead of checking it and keeping the
  loose type.
- **Smell:** `unknown`/`any`/`dict` passed inward after a boolean check;
  the same check repeated downstream ("shotgun parsing").
- **Ask:** After this check, does the type prove what was checked?
- **Source:** [Alexis King, "Parse, don't validate" (2019)](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/).

#### P10 - Guard each invariant with a fitness function

- **Statement:** an invariant the design relies on should have an automatic,
  objective check that fails when it breaks.
- **Smell:** an invariant stated only in a comment, the PR description, or a
  reviewer's memory; a guard test that was never seen failing.
- **Ask:** If someone breaks this invariant next year, what fails?
- **Source:** Ford, Parsons, Kua, *Building Evolutionary Architectures*, via
  [Thoughtworks Radar](https://www.thoughtworks.com/radar/techniques/architectural-fitness-function).

#### P11 - Every decision has a confirmation

- **Statement:** record how compliance with a decision is checked, for example
  by a review or an automated test.
- **Smell:** a decision that only holds while everyone remembers it ("all
  handlers must call X").
- **Ask:** What tells us when the codebase drifts away from this decision?
- **Source:** [MADR 4.0.0, "Confirmation"](https://adr.github.io/madr/).

### Maintainability

#### P12 - Information hiding

- **Statement:** "one begins with a list of difficult design decisions or
  design decisions which are likely to change. Each module is then designed
  to hide such a decision from the others."
- **Smell:** a decision likely to change (a storage format, a vendor, a policy
  table) visible to many modules.
- **Ask:** Which decision here is most likely to change, and how many files
  would that change touch?
- **Source:** [D. L. Parnas, "On the Criteria To Be Used in Decomposing
  Systems into Modules", CACM 15(12), 1972](https://www.cs.lafayette.edu/~gexia/cs301/resources/parnas.html)
  (ACM reprint; DOI 10.1145/361598.361623).

#### P13 - Deep modules

- **Statement:** a good module has an interface much simpler than its
  implementation; "it is more important for a module to have a simple
  interface than a simple implementation."
- **Smell:** shallow modules - an interface nearly as complex as what it does;
  pass-through methods, which "contribute no new functionality".
- **Ask:** What does a caller have to know to use this, compared with what it
  does for them?
- **Source:** John Ousterhout, *A Philosophy of Software Design*, 2nd ed.
  (Yaknyam Press, 2021); wording quoted from
  [Dan Lebrero's book notes](https://danlebrero.com/2021/02/24/philosophy-of-software-design-summary/).

#### P14 - One authoritative representation (DRY)

- **Statement:** "every piece of system knowledge should have one
  authoritative, unambiguous representation," because otherwise "the two or
  three different representations will most likely fall out of step with
  each other."
- **Smell:** a second list, map, or config that mirrors facts already declared
  elsewhere (a hand-kept list of routes that mirrors the router, a
  constant that restates a database enum). DRY is about knowledge, not similar-looking code.
- **Ask:** If this fact changes, how many places must be edited, and what
  catches a missed one?
- **Source:** [Bill Venners, interview with Dave Thomas, "Orthogonality and the
  DRY Principle", Artima (2003)](https://www.artima.com/articles/orthogonality-and-the-dry-principle);
  originally Hunt & Thomas, *The Pragmatic Programmer* (1999).

#### P15 - Locality of behaviour

- **Statement:** "The behaviour of a unit of code should be as obvious as
  possible by looking only at that unit of code."
- **Smell:** understanding one field or endpoint needs three files open; the
  rule for a thing lives far from the thing.
- **Ask:** Can a reader see what this unit does without leaving it?
- **Tension:** the essay itself notes that LoB conflicts with separation of
  concerns and sometimes with DRY; record which side a decision picks as a
  trade-off.
- **Source:** [Carson Gross, "Locality of Behaviour (LoB)", htmx essays](https://htmx.org/essays/locality-of-behaviour/).

#### P16 - Avoid information leakage

- **Statement:** information leakage "occurs when a design decision is
  reflected in multiple modules, creating dependencies."
- **Smell:** two modules that must change together because both know the same
  format, ordering, or rule.
- **Ask:** Which modules share knowledge of this decision, and could one own it?
- **Source:** Ousterhout, *A Philosophy of Software Design*; wording quoted from
  [Mark Adel's summary](https://dev.to/markadel/a-philosophy-of-software-design-summary-pk9).

#### P17 - Pull complexity downwards

- **Statement:** a module should absorb complexity rather than expose it to
  every caller; "configuration parameters push complexity upwards," so compute
  reasonable defaults instead.
- **Smell:** a new option or flag every caller must set correctly; callers
  repeating the same setup.
- **Ask:** Could the module decide this itself instead of asking every caller?
- **Source:** Ousterhout, *A Philosophy of Software Design*; wording quoted from
  [Dan Lebrero's book notes](https://danlebrero.com/2021/02/24/philosophy-of-software-design-summary/).

#### P18 - Solve today's problem (no over-engineering)

- **Statement:** watch for "over-engineering, where developers have made the
  code more generic than it needs to be"; solve the problem that exists now,
  not a speculative future one (paraphrase after the quote).
- **Smell:** a plugin system with one plugin; a generic framework for a single
  use; extension points nothing extends.
- **Ask:** Which current requirement needs this generality?
- **Source:** [Google Engineering Practices, "What to look for in a code
  review", Complexity](https://google.github.io/eng-practices/review/reviewer/looking-for.html).

#### P19 - The design fits the system

- **Statement:** "The most important thing to cover in a review is the overall
  design of the CL" - do the pieces interact sensibly, does the change belong
  in this codebase or in a library, does it integrate well with the rest of
  the system, and is now the right time for it (paraphrase after the quote).
- **Smell:** a parallel mechanism next to an existing one that does the same
  job; a change that fights the project's established patterns.
- **Ask:** Is there already a place in the system where this belongs?
- **Source:** [Google Engineering Practices, "What to look for in a code
  review", Design](https://google.github.io/eng-practices/review/reviewer/looking-for.html).

### Decision record

#### P20 - List all consequences, not just the positive ones

- **Statement:** "All consequences should be listed here, not just the
  'positive' ones."
- **Smell:** a PR description that sells the change with no cost named.
- **Ask:** What does this make harder, slower, or more coupled?
- **Source:** [Nygard, "Documenting Architecture Decisions"](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

#### P21 - Show the considered options

- **Statement:** a decision record names the alternatives it considered and
  the pros and cons of each.
- **Smell:** a non-obvious choice with no mention of the obvious alternative.
- **Ask:** What else did you consider, and why not that?
- **Source:** [MADR 4.0.0, "Considered Options"](https://adr.github.io/madr/).

### Common tensions

The catalog is not a checklist where every box can be ticked; several entries
pull against each other. When a decision picks one side, record it in the
report's Trade-offs table as `Tension P<a> vs P<b>: <what was given up>`, not
as a violation of the losing principle. Raise it as a risk only when the side
picked looks wrong for this change, and say why.

| Tension | How it shows up |
|---------|-----------------|
| P15 vs P14 - locality vs one representation | Repeating a rule next to each use keeps it visible but creates copies that drift. Gross's essay names this trade-off itself. |
| P15 vs P12 - locality vs separation of concerns | Gross notes that separation of concerns "is, however, in conflict with LoB"; hiding a decision in its own module moves it away from where it acts. |
| P2 vs P15 - single choke point vs locality | One enforcing middleware or base class means the unit it protects no longer shows the behavior. |
| P10 vs P14 - complete guard vs one representation | An exhaustive snapshot or expected-value test is a second copy of what it guards; it must change in lockstep, which is the point, but it is still churn. |
| P10 vs P3 - complete guard vs small, reviewable mechanism | A guard that checks everything grows with the system until no reviewer reads it; prefer a generated or structural check over a long hand-written list. |
| P5 vs P3 - second key vs economy of mechanism | An independent second check catches what the first misses, at the cost of more protection code to inspect. |
| P12 vs P18 - hide a likely change vs solve today's problem | Hiding a decision behind an interface costs an abstraction now; justify it with evidence that the decision will change, not a hunch. |
| P1 vs P6 - fail closed vs easy to use | A strict default rejects some legitimate requests; the safe path must stay the easy one or developers route around it. |

---

## 3. Sources

Checked on 2026-10-27. Every URL was opened to confirm the quoted wording,
except where the Notes column says otherwise.

| Source | URL | Notes |
|--------|-----|-------|
| ISO/IEC 25010:2023, catalogue entry | <https://www.iso.org/standard/78176.html> | Returned 403; edition and structure confirmed from search results only. The standard itself is paywalled |
| arc42 Quality, ISO 25010 breakdown | <https://quality.arc42.org/standards/iso-25010> | Characteristic and subcharacteristic names. Its page placed Testability under Flexibility; SonarSource places it under Maintainability, which this file follows |
| SonarSource, "ISO/IEC 25010 explained" | <https://www.sonarsource.com/resources/library/iso-iec-25010-explained/> | Maintainability and Flexibility subcharacteristics |
| Barbacci et al., *Quality Attribute Workshops, 3rd ed.* (SEI, 2003) | <https://www.sei.cmu.edu/documents/716/2003_005_001_14249.pdf> | Six-part scenario, §3.8 |
| SEI, ATAM collection | <https://www.sei.cmu.edu/library/architecture-tradeoff-analysis-method-collection/> | Purpose and outputs; the page does not define the terms |
| Nygard, "Documenting Architecture Decisions" (2011) | <https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions> | |
| MADR 4.0.0 | <https://adr.github.io/madr/> | |
| Saltzer & Schroeder (1975) | <https://www.cs.virginia.edu/~evans/cs551/saltzer/> | Mirror; the MIT copy returned 404 |
| Ford, Parsons, Kua, fitness functions | <https://www.thoughtworks.com/radar/techniques/architectural-fitness-function> | Radar page opened; the O'Reilly chapter returned 403 and was not read |
| Parnas (1972) | <https://www.cs.lafayette.edu/~gexia/cs301/resources/parnas.html> | ACM "Classic of the Month" reprint |
| Ousterhout, *A Philosophy of Software Design* | <https://danlebrero.com/2021/02/24/philosophy-of-software-design-summary/>, <https://dev.to/markadel/a-philosophy-of-software-design-summary-pk9> | Verified through secondary summaries only; the book is not online |
| Minsky, "Effective ML Revisited" | <https://blog.janestreet.com/effective-ml-revisited/> | |
| King, "Parse, don't validate" (2019) | <https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/> | |
| Gross, "Locality of Behaviour" | <https://htmx.org/essays/locality-of-behaviour/> | |
| Google Engineering Practices, "What to look for in a code review" | <https://google.github.io/eng-practices/review/reviewer/looking-for.html> | |
| Venners / Thomas, "Orthogonality and the DRY Principle" (2003) | <https://www.artima.com/articles/orthogonality-and-the-dry-principle> | |
