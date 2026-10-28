# Test Design Philosophy

> **Purpose**: the *why* behind every rule the `/write-tests` and `/test-health`
> skills apply. Each heuristic T1–T39 states a rule, the reasoning, the
> sources, how an audit can check it, a severity, and where authorities
> disagree.
>
> **Who reads this**: `/write-tests` reads the themes relevant to the test it
> is writing (see its Step 3); `/test-health` reads all of it before
> classifying findings. Humans read it to settle a judgment call.
>
> **Provenance**: compiled 2026-10-28 from web research across primary
> sources (books, papers, Google engineering guidance, tool docs). Every claim
> carries a verification tag; never print a `[B]` or `[S]` claim as a quote.
> "Example from this project" lines are real cases from the Fitted repo.

The authoritative sources agree on more than their public disagreements suggest. Beck's Test Desiderata, *Software Engineering at Google*, Fowler and Khorikov all hold that a good test specifies **observable behaviour through the interface a real client uses**, and even the mockist Freeman and Pryce insist a test be "as precise as possible, but not more precise". Such a test is **deterministic and independent of other tests**, it **fails for a useful reason with a diagnosable message**, and it changes only when requirements change. The empirical literature supplies the audit priorities. Luo et al. found **async waits, concurrency and order dependency behind 125 of 161 classified flaky-test fixes**, with **78% of flaky tests flaky from the day they were written**. Inozemtseva and Holmes found coverage **only weakly to moderately correlated with mutation-measured suite effectiveness** once suite size is controlled. Panichella et al. found that an established smell detector **misclassified over 70% of smells**. Together these justify a severity scheme: tests that cannot fail or that give nondeterministic results are high-severity findings, and readability smells are low-severity review prompts. The real disputes are narrower than they look. They are London versus classicist mocking (where mocks belong), pyramid versus trophy versus honeycomb (mostly what "unit" means), naming templates (taste), and retries (how visible they must be). The 39 heuristics below (T1–T39) are grouped into six themes and written so they can be lifted into a test-writing skill and a test-suite audit skill.

## How to read the heuristics

Every heuristic uses the same fields in the same order: **Rule**, **Why**, **Sources**, **Audit check**, **Severity**, **Disagreement**, and, where a real case exists, **Example from this project**. Severity uses a closed vocabulary:

| Severity | Meaning |
|---|---|
| **High** | The test can pass while behaviour is wrong, its result is nondeterministic, or it leaks state into other tests. |
| **Medium** | The test is brittle or coupled to implementation, a double can drift from reality, or the test hides signals a human would want. |
| **Low** | Readability or diagnosability smell. Report it as a review prompt, never as a defect. |
| **Info** | A suite-level metric to report, not a finding against a specific test. |

Verification tags are carried over from the research notes. Tags were assigned per note, so the same book can carry different tags depending on which note quoted it.

| Tag | Meaning |
|---|---|
| **[V]** | Wording checked against the fetched primary source. Covers the notes' [V] and [fetched], the raw-checked quotes in the isolation note, and the curl-fetched xunitpatterns.com and OOPSLA 2004 text. Quotes may be printed verbatim. xunitpatterns.com pages are pre-publication web drafts that warn the printed book changed. |
| **[V~]** | Fetched through a summarising tool, or fetched in-session but left untagged in the notes. Short quotes are near-verbatim and must be spot-checked before printing as exact. This applies to the test-doubles note's SWE ch.13, Fowler's "Mocks Aren't Stubs", Vitest API, MSW, Dodds and Testing Library pages; the pytest-socket README; and the untagged shape-and-UI note. |
| **[B]** | Book with no free full text. Paraphrased from known content and never quoted. |
| **[S]** | Secondary, search snippet, or "not re-fetched". Paraphrased only. |

**"Isolation" means five different things in these sources.** Pin the meaning down before applying any rule that uses the word.

1. **London school:** the system under test (SUT) is isolated from its collaborators.
2. **Classical school, Beck, and *Clean Code*'s "Independent":** tests are isolated from each other, so the result does not depend on run order.
3. **The 2009 FIRST card:** "Tests isolate failures", which means failure localisation.
4. **Google:** hermeticity, meaning the test owns its whole environment.
5. **Vitest:** per-file runtime isolation, where each file gets its own worker.

Unqualified, "isolated" in this report means sense 2. Freeman et al. use "boundary object" for a leaf or value object, which is not the same as Khorikov's system boundary.

### Index

| # | Rule (short) | Severity | Mechanical? |
|---|---|---|---|
| T1 | Test observable behaviour through the public API | Medium | Partial |
| T2 | One behaviour per test, one Act, related asserts allowed | Low | Partial |
| T3 | Name the test as a behaviour sentence in domain language | Low | Partial |
| T4 | Straight-line test code, no conditionals or loops | Medium | Yes |
| T5 | DAMP: show relevant inputs, hide irrelevant construction | Low | Partial |
| T6 | Failure output states expected, actual, parameters | Low | Partial |
| T7 | Tests change only when behaviour changes; prefer output-based | Medium | Partial |
| T8 | Real > fake > stub > interaction verification | Medium | Partial |
| T9 | Mock only unmanaged out-of-process dependencies | Medium | Partial |
| T10 | Never assert on stubs; verify only outgoing state-changing calls | Medium | Yes |
| T11 | Don't mock types you don't own; wrap them in owned adapters | Medium | Partial |
| T12 | Constrain doubles to the real API (spec/autospec/typed) | Medium | Yes |
| T13 | Frontend: mock at the network boundary, not your own client | Medium | Yes |
| T14 | Fakes are owned and contract-tested for fidelity | Medium | No |
| T15 | Prefer injected seams over patching module globals | Low | Partial |
| T16 | Hermetic tests; enforce size limits with tooling | High | Yes |
| T17 | Order-independent; detect with random order and parallel runs | High | Yes |
| T18 | No bare sleeps or fixed waits; wait on conditions | High | Yes |
| T19 | Control time, randomness, float and collection-order nondeterminism | High | Yes |
| T20 | Reset per-test state; know what your runner does not reset | High | Partial |
| T21 | Flakes are bugs: visible retries, capped quarantine, no deletion | High | Yes |
| T22 | Gate new and changed tests for flakiness at birth | Medium | Yes |
| T23 | Classify tests by size (resources) separately from scope | Info | Yes |
| T24 | Cover each behaviour at the lowest level that can catch it | Low | No |
| T25 | UI tests through the DOM as a user: role-first queries | Low | Yes |
| T26 | Async UI: wait for observable outcomes; act warnings are bugs | High | Partial |
| T27 | Fail tests on unexpected console output | Medium | Yes |
| T28 | Every test must be able to fail | High | Yes |
| T29 | Exception assertions name the type and message | High | Yes |
| T30 | Negative assertions must run after the event had its chance | High | Partial |
| T31 | Flag weak oracles for review | Medium | Yes |
| T32 | Track skipped/xfail tests and suite health metrics | Medium | Yes |
| T33 | Coverage finds gaps; it is not a target | Info | Yes |
| T34 | Measure oracle strength with sampled mutation testing | Info | Yes |
| T35 | Use CRAP to prioritise where tests are missing | Info | Yes |
| T36 | Rank smell findings by consequence; detectors are prompts | Info | — |
| T37 | Use property-based tests where a general property exists | Low | Partial |
| T38 | Test the generators; reject "doesn't crash" as the only oracle | Medium | Partial |
| T39 | Make property failures minimal and reproducible | Low | Partial |

## A test is a specification a client could read (T1–T7)

North's BDD, Google's unit-testing chapter and Khorikov converge on one operational question: **would a client of this unit, or an external system, notice the difference?** If not, the test must not depend on it. They draw the client boundary differently. For North it is the business reader, for Google it is the team-ownership boundary, and for Khorikov it is the client's goals.

**T1. Test observable behaviour through the public API, as a real caller would.**

**Rule:** Invoke the SUT the way its users do. Assert only on what a client can observe. Never widen production APIs or add test-only branches to make assertions possible.

**Why:** "If tests work the same way as the system's users, by definition, change that breaks a test might also break a user." Such tests also double as documentation ([SWE ch.12](https://abseil.io/resources/swe-book/html/ch12.html)) [V]. "Public" is set by the ownership boundary, not language visibility [V]. Khorikov: "Intra-system communications are implementation details", while the way the system talks to the external world is its observable behaviour ([Khorikov, When to Mock](https://enterprisecraftsmanship.com/posts/when-to-mock/)) [V]. His book defines observable behaviour as operations or state that help the client achieve a goal [B]. Testing implementation details yields both false failures and false passes ([Dodds](https://kentcdodds.com/blog/testing-implementation-details)) [V~].

**Sources:** SWE ch.12 [V]; Khorikov blog [V]; [*Unit Testing PPP* ch.5](https://www.manning.com/books/unit-testing) [B]; Meszaros "Test Logic in Production" ([xunitpatterns](http://xunitpatterns.com/Test%20Smells.html)) [V]. Khorikov's advice against exposing state getters only for tests comes from a search snippet [S], so paraphrase it.

**Audit check:** Flag tests that import underscore-private names or read private attributes. Flag production code with branches on test flags or environment checks. Whether something is an implementation detail needs judgment.

**Severity:** Medium.

**Disagreement:** The London school treats interactions between owned objects as legitimate specification (see T10 and the disagreements section).

**T2. One behaviour per test: one Act, related assertions allowed.**

**Rule:** Each test covers a single behaviour, usually with one when and one then. Write one test per behaviour, not one per method. Split tests that alternate Arrange-Act-Assert. Several assertions about one outcome are fine.

**Why:** "the vast majority of unit tests require only one 'when' and one 'then' block". If the name needs "and", "there's a good chance that you're actually testing multiple behaviors" ([SWE ch.12](https://abseil.io/resources/swe-book/html/ch12.html)) [V]. Wake named AAA in 2001. He rejects strict one-assert-per-test, recommends splitting repeated A-A-A cycles, and credits Jim Newkirk with writing the Assert first ([Wake](https://xp123.com/3a-arrange-act-assert/)) [V]. Khorikov adds that a multi-line Act hints at an encapsulation problem in the SUT [B]. North: "you can only describe so much behaviour in a single sentence" ([North](https://dannorth.net/blog/introducing-bdd/)) [V].

**Sources:** SWE ch.12 [V]; Wake [V]; North [V]; Khorikov ch.3 [B].

**Audit check:** Count act/assert alternations per test body. Flag test names containing "and". tsDetect's Eager Test rule (calls to several production methods) is a rough proxy ([tsDetect](https://testsmells.org/pages/testsmells.html)) [V].

**Severity:** Low.

**Disagreement:** tsDetect's Assertion Roulette flags any test with more than one assertion that has no message. Wake and Google reject that strictness (see T36).

**T3. Name the test as a sentence about behaviour, in domain language.**

**Rule:** State the scenario and expected outcome so a domain expert could read it. Including the method name is optional, and appropriate for utility or pure functions.

**Why:** The name "will often be the first or only token visible in failure reports" ([SWE ch.12](https://abseil.io/resources/swe-book/html/ch12.html)) [V]. Sentence names made generated docs readable to "business users, analysts, and testers". A name that won't fit "The class should do something" suggests "the behaviour may belong elsewhere" ([North](https://dannorth.net/blog/introducing-bdd/)) [V].

**Sources:** North [V]; SWE ch.12 [V]; [Khorikov, naming](https://enterprisecraftsmanship.com/posts/you-naming-tests-wrong/) [V].

**Audit check:** Flag generic names (`test_1`, `test_works`, `it('renders')`) and names that only restate the function name. Template conformance is not a quality signal.

**Severity:** Low.

**Disagreement:** The disputes are about "should" and method-in-name templates (see disagreements).

**T4. Keep test code straight-line: no `if`, loops or clever logic.**

**Rule:** No conditionals, loops or computed expectations inside a test body. Use parametrisation tables (`pytest.mark.parametrize`, `it.each`) instead.

**Why:** "Clear tests are trivially correct upon inspection… if you feel like you need to write a test to verify your test, something has gone wrong!" ([SWE ch.12](https://abseil.io/resources/swe-book/html/ch12.html)) [V]. Meszaros defines Conditional Test Logic as "code that may or may not be executed" ([xunitpatterns](http://xunitpatterns.com/Test%20Smells.html)) [V]. A branch that skips the assertion is a test that silently cannot fail. That consequence is why this rule ranks above a pure readability smell.

**Sources:** SWE ch.12 [V]; Meszaros [V]; tsDetect Conditional Test Logic [V]; Khorikov ch.3 on avoiding `if` in tests [B].

**Audit check:** AST: `if`, `for`, `while`, `switch` or ternary in a test body, excluding iteration over a parametrise table. Escalate to High when an assertion sits inside the conditional branch.

**Severity:** Medium.

**Disagreement:** A commenter on the Google post defends loops ("DRY DAMP"). He is not an authority ([TotT](https://testing.googleblog.com/2019/12/testing-on-toilet-tests-too-dry-make.html)) [V].

**T5. DAMP over DRY: keep relevant inputs in the test, hide irrelevant construction.**

**Rule:** Repeat what matters to the behaviour: the inputs that drive it and the assertion. Factor out boilerplate behind well-named builders or factories with defaults. Use shared setup only to construct the SUT. Tests must not depend on particular values set in setup.

**Why:** "Since tests don't have tests, it should be easy for humans to manually inspect them for correctness, even at the expense of greater code duplication." DRY still applies to helpers for value objects ([TotT, DAMP](https://testing.googleblog.com/2019/12/testing-on-toilet-tests-too-dry-make.html)) [V]. Setup methods "can harm a test's completeness by hiding important details" ([SWE ch.12](https://abseil.io/resources/swe-book/html/ch12.html)) [V]. Shared test infrastructure is closer to production code and needs its own tests [V]. Khorikov prefers private factory methods to constructor or `setUp` fixtures [B].

**Sources:** SWE ch.12 [V]; TotT 2019 [V]; Meszaros causes of Obscure Test: Mystery Guest, General Fixture, Irrelevant Information ([xunitpatterns](http://xunitpatterns.com/Obscure%20Test.html)) [S].

**Audit check:** General Fixture means setup fields that some tests never read (tsDetect) [V]. Also flag magic values whose origin is a distant fixture.

**Severity:** Low.

**Disagreement:** None of substance. Everyone agrees on the relevant/irrelevant split.

**T6. Make failure output state expected, actual and the relevant parameters.**

**Rule:** A failure should be diagnosable from the message alone.

**Why:** It "should clearly express the desired outcome, the actual outcome, and any relevant parameters". Google contrasts "Test failed: account is closed" with "Expected an account in state CLOSED, but got account: <…>" ([SWE ch.12](https://abseil.io/resources/swe-book/html/ch12.html)) [V]. This maps to Beck's *Specific* desideratum: "if a test fails, the cause of the failure should be obvious" ([testdesiderata](https://testdesiderata.com/)) [V]. Validation helpers should "assert a single conceptual fact" [V].

**Sources:** SWE ch.12 [V]; Beck [V].

**Audit check:** Flag `assertTrue(x)` or `expect(cond).toBe(true)` on compound conditions, which lose the actual values. pytest's assertion rewriting already prints operands, so bare `assert a == b` passes this check (inference).

**Severity:** Low.

**Disagreement:** tsDetect demands a message on every multi-assert test. That rule is too strict for runners that report values (see T36).

**T7. Existing tests change only when behaviour changes; prefer output-based over state-based over communication-based.**

**Rule:** Pure refactorings, new features and bug fixes should not force edits to existing tests. Push logic into a side-effect-free core you can test by return value.

**Why:** "the ideal test is unchanging". If a refactoring breaks tests, it "isn't a pure refactoring, or… the tests were not written at an appropriate level of abstraction" ([SWE ch.12](https://abseil.io/resources/swe-book/html/ch12.html)) [V]. Beck's *Structure-insensitive* desideratum: tests "should not change their result if the structure of the code changes" ([testdesiderata](https://testdesiderata.com/)) [V]. Khorikov treats resistance to refactoring as effectively binary and non-negotiable [B; S via [dzx.fr](https://dzx.fr/blog/unit-testing-principles-practices-patterns/)]. His style ranking, from his 2016 blog: "Functional style is the best one in terms of its value proposition", while "Collaboration verification has the worst value proposition because such tests produce a lot of false positives" ([Khorikov, styles](https://enterprisecraftsmanship.com/posts/styles-of-unit-testing/)) [V]. The book renames the styles output, state and communication [B].

**Sources:** SWE ch.12 [V]; Beck [V]; Khorikov blog [V], book ch.4 and ch.6 [B].

**Audit check:** Mine history for commits labelled `refactor:` that also modify tests. Each one is a brittleness candidate. Fragile Test cannot be detected statically ([xunitpatterns](http://xunitpatterns.com/Fragile%20Test.html)) [V].

**Severity:** Medium.

**Disagreement:** London-school authors argue that classical tests force changes "to multiple tests, especially to test data" when a core class changes ([OOPSLA 2004 §5.5](http://jmock.org/oopsla2004.pdf)) [V].

## Doubles belong at boundaries the client can observe (T8–T15)

On test doubles, the classical position is backed by Fowler, Google and Khorikov, and the London position by Freeman and Pryce. Both reject mocking third-party types directly, and both read complex mock setup as a smell. They differ only on whether to mock *in-process role interfaces you own*. The rules below adopt the classical default and keep London's adapter discipline. Vocabulary follows Meszaros ([Test Double](http://xunitpatterns.com/Test%20Double.html)) [V]:

| Double | What it does |
|---|---|
| Stub | Feeds indirect inputs to the SUT. |
| Spy | Captures indirect outputs for later checking. |
| Mock | Verifies indirect outputs itself. |
| Fake | A lighter working implementation. |
| Dummy | Fills a parameter slot. |

`MagicMock` and `vi.fn` are technically spies.

**T8. Prefer real implementations, then fakes, then stubs; use interaction verification last.**

**Rule:** Use the real collaborator when it is fast and deterministic. Use a fake when it isn't. Stub only to force an input. Verify interactions only as a last resort.

**Why:** Google's "first choice for tests is to use the real implementations". "We prefer realistic tests because they give more confidence". Overused mocking produced tests that "required constant effort to maintain while rarely finding bugs" ([SWE ch.13](https://abseil.io/resources/swe-book/html/ch13.html)) [V~]. Fowler: "The classical TDD style is to use real objects if possible and a double if it's awkward to use the real thing" ([Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html)) [V~]. Dodds: "When you mock something you're removing all confidence in the integration between what you're testing and what's being mocked" ([Write tests](https://kentcdodds.com/blog/write-tests)) [V~].

**Sources:** SWE ch.13 [V~]; Fowler [V~]; Freeman et al. §4.5: don't use mocks for leaf or value objects ([OOPSLA 2004](http://jmock.org/oopsla2004.pdf)) [V].

**Audit check:** Count doubles per test. Flag doubles of in-process value objects, pure functions and data classes.

**Severity:** Medium.

**Disagreement:** See London vs classicist below.

**T9. Mock only unmanaged out-of-process dependencies; use real managed ones in integration tests.**

**Rule:** Use a double for dependencies whose interactions are visible outside the system: SMTP, message bus, third-party HTTP. Use the application's own database for real.

**Why:** "Only unmanaged dependencies should be replaced with mocks. Use real instances of managed dependencies in tests." "The database and your application must be treated as one system", so a schema change is an internal refactoring that should not break tests ([Khorikov, When to Mock](https://enterprisecraftsmanship.com/posts/when-to-mock/)) [V]. The book claims this one guideline gets "about two-thirds of the way to success" ([*Unit Testing PPP* ch.9](https://livebook.manning.com/book/unit-testing/chapter-9)) [V~, intro only].

**Sources:** Khorikov blog [V]; ch.9 intro [V~]. SWE ch.14 also advises against automated tests hitting a real third-party API ([SWE ch.14](https://abseil.io/resources/swe-book/html/ch14.html)) [V].

**Audit check:** Flag repository or ORM sessions replaced by mocks in tests that exercise data access. Flag outbound HTTP to third parties that is not doubled.

**Severity:** Medium.

**Disagreement:** Freeman et al. say mocks "are most useful within the system where the interfaces can be changed" ([OOPSLA 2004 §5.2](http://jmock.org/oopsla2004.pdf)) [V].

**T10. Never assert on stubs; verify only outgoing, state-changing calls, and only their relevant arguments.**

**Rule:** A double that only supplies data must not appear in an assertion. Verify an interaction only when the call is itself the required behaviour: a sent email, a published event, or a cache that must reduce DB calls. Check only the arguments that matter, and specify as little as possible.

**Why:** "Asserting interactions with stubs is a common anti-pattern that leads to brittle tests" ([Khorikov](https://enterprisecraftsmanship.com/posts/when-to-mock/)) [V]. Google: perform interaction testing "only for functions that are state-changing". Overuse yields "change-detector tests" that "fail in response to any change to the production code" ([SWE ch.13](https://abseil.io/resources/swe-book/html/ch13.html)) [V~]. Brittle tests "have been over-specified… A specification should be as precise as possible, but not more precise" ([OOPSLA 2004 §4.4](http://jmock.org/oopsla2004.pdf)) [V].

**Sources:** Khorikov [V]; SWE ch.13 [V~]; Freeman et al. [V]; Meszaros' "Overspecified Software" cause of Fragile Test [S].

**Audit check:** AST: a double configured with `return_value`, `side_effect` or `mockReturnValue` that is also the target of `assert_called*` or `toHaveBeenCalled*`. Also flag `assert_called_with` on getters or queries.

**Severity:** Medium.

**Disagreement:** London accepts interaction verification between owned objects, provided it follows "specify as little as possible" and "only mock immediate neighbours" (§4.4, §4.7) [V].

**T11. Don't mock types you don't own; wrap them in thin adapters and test the adapter against the real thing.**

**Rule:** Put SDKs, ORMs, HTTP clients and platform APIs behind a role interface you own. Double the adapter in unit tests. Integration-test the adapter against the real dependency. Treat a sprawling mock setup as a missing object.

**Why:** "Programmers should not write mocks for fixed types, such as those defined by the runtime or external libraries. Instead they should write thin wrappers". "Complex mock setup for a test is actually a hint that there is a missing object in the design." "The use of mock objects amplifies problems such as tight coupling" ([OOPSLA 2004 §4.1, §5.4, §4](http://jmock.org/oopsla2004.pdf)) [V]. GOOS restates this for third-party code ([findmypast quoting GOOS](https://tech.findmypast.com/dont-mock-what-you-dont-own)) [S].

**Sources:** Freeman et al. [V]; GOOS [S].

**Audit check:** Flag `patch('requests.…')`, `patch('boto3.…')`, `vi.mock('axios')` and similar targets in external packages. Flag tests with more than N configured doubles. The threshold is a team choice.

**Severity:** Medium.

**Disagreement:** Practitioners relax this rule for legacy code ([codecentric](https://blog.codecentric.de/en/2018/03/mock-what-when-how/)) [S].

**T12. Constrain every double to the real API: specced, autospecced, sealed or typed.**

**Rule:** In Python, use `create_autospec`, `patch(autospec=True)`, `spec_set` or `seal`, never a bare `Mock`/`MagicMock` standing in for a real type. In TypeScript, build module mocks with `importOriginal` or typed fakes that implement the real interface. Keep integration tests regardless.

**Why:** Per the Python docs, after a rename "any tests for code that is still using the *old api* but uses mocks instead of the real objects will still pass. This means your tests can all pass even though your code is broken". This is "another reason why you need integration tests as well as unit tests" ([unittest.mock, Autospeccing](https://docs.python.org/3/library/unittest.mock.html#autospeccing)) [V; the note marks these two quotes verbatim]. `spec` is shallow and autospec recursive. Autospec has caveats: attributes created in `__init__` are invisible, and properties execute ([same](https://docs.python.org/3/library/unittest.mock.html#autospeccing)) [V~]. `vi.mocked` is a "Type helper… Just returns the object that was passed", so it adds no runtime check, while `importOriginal` enforces a compatible factory return type ([Vitest vi](https://vitest.dev/api/vi.html)) [V~].

**Sources:** Python docs [V/V~]; Vitest [V~].

**Audit check:** AST: `Mock()`/`MagicMock()` without `spec`/`spec_set`; `patch(...)` without `autospec=True` or `new=`; `vi.mock(path, () => ({…}))` factories that don't use `importOriginal`. Specced doubles fix signature drift only, not semantic drift (see T14).

**Severity:** Medium. Raise it to High when the unspecced double replaces a type whose signature has changed since the test was written.

**Disagreement:** The docs themselves give the caveats above as the reason autospec is not the default.

**T13. Frontend: mock at the network boundary, not your own API-client module or `fetch`.**

**Rule:** Intercept HTTP with MSW-style request handlers. Keep `vi.mock` off the app's own client module. Put per-test overrides in `server.use(...)` and call `resetHandlers()` after each test.

**Why:** Mocking your client means "how do you really know the client is being used correctly". With network-level handlers, if the request is built wrong, "my server handler won't be called and my test (correctly) fails". Ad-hoc fetch mocks mean "re-implementing your entire backend… everywhere in your tests" ([Dodds, Stop mocking fetch](https://kentcdodds.com/blog/stop-mocking-fetch)) [V~]. MSW defines network behaviour as "a contract-like description of the network's expected state" ([MSW philosophy](https://mswjs.io/docs/philosophy)) [V~]. Through Khorikov's lens, the SPA's own client is an intra-system detail and the backend is the external boundary (inference from [When to Mock](https://enterprisecraftsmanship.com/posts/when-to-mock/)).

**Sources:** Dodds [V~]; MSW [V~]; Testing Library guiding principle ([Guiding Principles](https://testing-library.com/docs/guiding-principles/)) [V~].

**Audit check:** Grep `vi.mock(`/`jest.mock(` targeting in-repo API modules, and direct `global.fetch =` or `vi.stubGlobal('fetch', …)`. Check that an `afterEach` calls `resetHandlers()`.

**Severity:** Medium.

**Disagreement:** None among the sources. MSW handlers still carry the fake-drift risk in T14.

**Example from this project:** Issue 299 migrated tests that `vi.mock`'ed the app's own API client module to network-boundary mocking with MSW.

**T14. Fakes are owned by the API's owners and contract-tested for fidelity.**

**Rule:** A shared fake should be maintained by whoever owns the real implementation. Run one contract-test suite against both the fake and the real thing. Contract tests for remote-service doubles can run periodically, outside the deploy pipeline.

**Why:** A fake "should maintain fidelity to the API contracts of the real implementation". Without tests it "can diverge over time". "The team that owns the real implementation should write and maintain a fake" ([SWE ch.13](https://abseil.io/resources/swe-book/html/ch13.html)) [V~]. Fowler: replace unstable remote services with a double, backed by periodic contract tests ([Eradicating Non-Determinism](https://martinfowler.com/articles/nonDeterminism.html)) [V].

**Sources:** SWE ch.13 [V~]; Fowler [V].

**Audit check:** Not mechanical in general. Check whether each fake or MSW handler set has a test, or is generated from or validated against a schema such as OpenAPI. The notes found no primary source tying MSW to schema validation, so this check is inference.

**Severity:** Medium.

**Disagreement:** None in the notes.

**T15. Prefer injected seams over patching module globals.**

**Rule:** Pass dependencies in through constructor or parameter injection, so the test decides what to use. Use `patch` or `vi.mock` only when injection is impractical.

**Why:** "A seam is a place where you can alter behavior in your program without editing in that place" ([Feathers, WELC ch.4](https://www.informit.com/articles/article.aspx?p=359417&seqNum=2)) [V~]. Google names dependency injection as the primary seam ([SWE ch.13](https://abseil.io/resources/swe-book/html/ch13.html)) [V~]. The case against patching is inference from the sources, which never weigh the two directly. Patching couples the test to *where* a name is looked up, so moving an import breaks it without any behaviour change. Patches are process-global, so they can leak. And `vi.mock` is "hoisted… to top of the file" ([Vitest](https://vitest.dev/api/vi.html)) [V~].

**Sources:** Feathers [V~]; SWE ch.13 [V~]; the cost argument is inference.

**Audit check:** Count `patch(`/`monkeypatch.setattr`/`vi.mock` per test file against constructor-injected doubles.

**Severity:** Low.

**Disagreement:** None explicit.

## Determinism is enforced by tooling, not good intentions (T16–T22)

Luo et al. classified 161 flaky-test fixes in 51 Apache projects. **Async Wait accounted for 45%, Concurrency 20% and Test Order Dependency 12%**. **78% of flaky tests were flaky from the start**, **96% were platform-independent**, and in **24% of fixes the code under test changed, 94% of which fixed a real bug** ([Luo et al., FSE 2014](https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf)) [V]. Active reshuffling tells a different story about order dependency: **50.5% of 422 detected flaky tests were order-dependent** ([iDFlakies, ICST 2019](https://mir.cs.illinois.edu/winglam/publications/2019/LamETAL19iDFlakies.pdf)) [V]. Mined fix commits under-count it. Fowler's verdict sets the stakes: non-deterministic tests are "useless" and "a virulent infection that can completely ruin your entire test suite" ([Fowler](https://martinfowler.com/articles/nonDeterminism.html)) [V].

**T16. Make every test hermetic, and enforce small-test resource limits with tooling.**

**Rule:** Each test sets up, runs and tears down its own environment. Small tests get no network, no disk, no sleeps and no subprocesses. Medium tests may use localhost only. Enforce these limits at runtime rather than by convention. Make sure the guard covers fixture setup and teardown, not only the test body.

**Why:** "a test should contain all of the information necessary to set up, execute, and tear down its environment… they should not rely on a shared database". Small tests "aren't allowed to sleep, perform I/O operations, or make any other blocking calls". Google enforces this with a security manager that fails small tests that "establish a network connection" ([SWE ch.11](https://abseil.io/resources/swe-book/html/ch11.html)) [V]. "If a large test is nonhermetic, it is almost impossible to guarantee determinism" ([SWE ch.14](https://abseil.io/resources/swe-book/html/ch14.html)) [V]. pytest-socket's `--disable-socket` gives the small-test guard and `--allow-hosts=127.0.0.1` the medium one. Its README cautions that a higher-scoped fixture may open sockets before blocking applies, and that teardown runs under the restrictions active at setup ([pytest-socket](https://github.com/miketheman/pytest-socket)) [V~].

**Sources:** SWE ch.11, ch.14 [V]; pytest-socket [V~].

**Audit check:** Confirm a socket or network guard is active for the unit tier, and that it covers session- and module-scoped fixtures and their teardown. Grep unit tests for real file, DB and network access (tsDetect Mystery Guest) [V].

**Severity:** High.

**Disagreement:** Bazel's `size` is a time-and-resource "heaviness" label mapped to scope, with no network or disk restriction stated ([Bazel](https://bazel.build/reference/be/common-definitions)) [V].

**Example from this project:** In Issue 297, sockets opened in fixture teardown escaped the network guard. This is the isolation gap the pytest-socket caveat describes.

**T17. Tests must be order-independent; run them in random order and in parallel as a continuous check.**

**Rule:** Never rely on another test's side effects. Shuffle order on every CI run with the seed printed, and run the unit tier in parallel. Reproduce a failure with the seed and no parallelism to tell order dependency apart from cross-process resource sharing.

**Why:** Beck's *Isolated* desideratum: "tests should return the same results regardless of the order in which they are run" ([testdesiderata](https://testdesiderata.com/)) [V]. Random order "detects the most overall flaky tests" ([iDFlakies](https://mir.cs.illinois.edu/winglam/publications/2019/LamETAL19iDFlakies.pdf)) [V]. "Most Test Order Dependency flaky tests (74%) are fixed by cleaning the shared state" ([Luo et al.](https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf)) [V]. "Tests that modify global state typically cannot be run in parallel" ([pytest, Flaky tests](https://docs.pytest.org/en/stable/explanation/flaky.html)) [V]. pytest-randomly prints the seed and reseeds RNGs per test ([pytest-randomly](https://github.com/pytest-dev/pytest-randomly)) [V]. Vitest's `sequence.shuffle` is off by default ([Vitest sequence](https://vitest.dev/config/sequence)) [V]. Most order-dependent tests are *victims* polluted by earlier tests ([Parry et al. §3.2.1](https://eprints.whiterose.ac.uk/id/eprint/230095/1/parry2021.pdf)) [V]. pytest-xdist also forces deterministic collection: the order and number of collected tests must not differ across workers ([xdist limitations](https://github.com/pytest-dev/pytest-xdist/blob/master/docs/known-limitations.rst)) [V]. The notes found **no primary source evaluating parallel CI as a continuous isolation practice**. That part of the rule is inference from iDFlakies plus the pytest docs.

**Sources:** Beck [V]; iDFlakies [V]; Luo [V]; Parry [V]; pytest [V]; pytest-randomly [V]; Vitest [V].

**Audit check:** Check that CI enables a randomiser and parallel workers for the unit tier and logs the seed. Run the suite three to five times with different seeds and diff the results.

**Severity:** High.

**Disagreement:** Research tools such as ElectricTest and PraDeT schedule around dependencies. Practitioners (SWE, Fowler) forbid dependencies outright ([Parry §6.1.1](https://eprints.whiterose.ac.uk/id/eprint/230095/1/parry2021.pdf)) [V].

**Example from this project:** Issue 284 ran the unit job under pytest-xdist as a continuous isolation check. That run exposed the order-dependent tests tracked in Issue 279.

**T18. Never sleep or wait a fixed time; wait on a condition with a generous overall timeout.**

**Rule:** Replace `sleep`/`setTimeout` waits with polling, callbacks, `waitFor`/`findBy` or event hooks. Set overall timeouts with headroom for loaded CI runners, or make them configurable for CI.

**Why:** "Never use bare sleeps to wait for asynchonous responses: use a callback or polling" ([Fowler](https://martinfowler.com/articles/nonDeterminism.html)) [V]. 34% of Async Wait flakes used a simple time delay, and 54% were fixed with `waitFor`, which "often completely removes the flakiness" ([Luo et al.](https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf)) [V]. "Tests that rely on sleeps and timeouts will all start failing when the fleet running those tests becomes overloaded" ([SWE ch.14](https://abseil.io/resources/swe-book/html/ch14.html)) [V]. Testing Library's `findBy` retries until a default timeout of 1000ms ([About Queries](https://testing-library.com/docs/queries/about/)) [V~].

**Sources:** Fowler [V]; Luo [V]; SWE ch.11, ch.14 [V]; Testing Library [V~].

**Audit check:** Grep for `time.sleep`, `asyncio.sleep`, `setTimeout` and `waitForTimeout` in tests (tsDetect Sleepy Test) [V]. Also flag reliance on default async-query timeouts in UI tests that wait on network-backed rendering.

**Severity:** High.

**Disagreement:** None.

**Example from this project:** In Issue 299, two search UI tests timed out on a loaded CI runner while waiting on a fixed default timeout. This is the overload failure SWE ch.14 predicts.

**T19. Control every source of nondeterminism: clock, randomness, floating point and unordered collections.**

**Rule:** Wrap or freeze the clock. Seed RNGs per test and log the seed. Compare floats approximately. Never depend on set or dict-ordering incidentals, including in parametrisation.

**Why:** "always wrap the system clock with routines that can be replaced with a seeded value for testing" ([Fowler](https://martinfowler.com/articles/nonDeterminism.html)) [V]. Luo's other root causes include Time ("a test may fail when the midnight changes in the UTC time zone"), Randomness, Floating Point and Unordered Collections ([Luo](https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf)) [V]. "Overly strict assertions can cause problems with floating point comparison as well as timing issues", and the fix is `pytest.approx()` ([pytest](https://docs.pytest.org/en/stable/explanation/flaky.html)) [V]. freezegun freezes `datetime`/`time` calls, and freezes `monotonic`/`perf_counter` with no guarantee about their absolute values ([freezegun](https://github.com/spulec/freezegun)) [V]. Beck's *Deterministic*: "if nothing changes, the test result shouldn't change" [V].

**Sources:** Fowler [V]; Luo [V]; pytest [V]; freezegun [V]; pytest-randomly [V].

**Audit check:** Grep tests and SUT for direct `datetime.now()`/`Date.now()`/`random` calls without a freeze or seed. Flag float `==` assertions and `parametrize` over a `set`.

**Severity:** High.

**Disagreement:** None.

**T20. Reset per-test state, and know exactly what your runner does not reset.**

**Rule:** Restore environment variables, globals, mocks, module caches, storage and database state after every test. Vitest isolates per file, not per test. Its `restoreMocks`, `unstubEnvs` and `unstubGlobals` options are off by default. For databases, choose transaction rollback for speed or truncation for fidelity.

**Why:** `monkeypatch` changes "will be undone after the requesting test function or fixture has finished" ([pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)) [V]. "By default Vitest runs every test file in an isolated environment" ([Vitest perf](https://vitest.dev/guide/improving-performance)) [V]. The reset options default to `false` ([restoreMocks](https://vitest.dev/config/restoremocks)) [V]. Django's `TestCase` rolls back each test, while `TransactionTestCase` truncates and "may call commit and rollback and observe the effects" ([Django](https://docs.djangoproject.com/en/5.2/topics/testing/tools/)) [V]. Fowler prefers building a clean state *before* each test, and notes rollback "only works when you can conduct the test without committing any transactions" ([Fowler](https://martinfowler.com/articles/nonDeterminism.html)) [V]. Whether jsdom `localStorage` persists within a file is undocumented in the sources. Assume it does (inference).

**Sources:** pytest [V]; Vitest [V]; Django [V]; Fowler [V]; Luo I.10 "clean before and after" [V].

**Audit check:** Check Vitest config for `restoreMocks`/`unstubEnvs`/`unstubGlobals`, or equivalent `afterEach` calls. Flag direct `os.environ[...] =` assignments in tests. Check that DB fixtures roll back or truncate, and that integration tests point at a dedicated test database.

**Severity:** High.

**Disagreement:** Rollback cannot test commit semantics or see writes from other connections. Truncation is slower ([Django](https://docs.djangoproject.com/en/5.2/topics/testing/tools/)) [V].

**T21. Treat a flaky test as a bug: retries must be visible, quarantine capped, deletion avoided.**

**Rule:** No silent retries in the unit tier. Where retries exist (E2E, infrastructure-heavy tiers), report a pass-on-retry as *flaky*, not *passed*, and file a ticket. Cap quarantine by count or time. Don't delete or permanently `xfail` a flaky test until its root cause is known.

**Why:** Rerunning trades "CPU cycles for engineering time. At low levels of flakiness, this trade-off makes sense", but it "is only delaying the need to address the root cause" ([SWE ch.11](https://abseil.io/resources/swe-book/html/ch11.html)) [V]. Google's fail-only-if-3-in-a-row policy "encourages developers to ignore flakiness", and auto-quarantine "could easily mask a real race condition" ([Micco 2016](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html)) [V]. Bazel's `flaky` attribute "is generally discouraged" ([Bazel](https://bazel.build/reference/be/common-definitions)) [V]. Playwright reports "flaky" separately and restarts the worker before a retry ([Playwright retries](https://playwright.dev/docs/test-retries)) [V]. Fowler caps quarantine at, for example, 8 tests or one week ([Fowler](https://martinfowler.com/articles/nonDeterminism.html)) [V]. pytest calls permanent `xfail(strict=False)` quarantine "rather dangerous" ([pytest](https://docs.pytest.org/en/stable/explanation/flaky.html)) [V]. "Flaky tests should not simply be removed or disabled because they can help uncover bugs in the CUT" ([Luo I.12](https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf)) [V]. In a reply in the comments (not the post body), Listfield reports one team tracing a sixth of newly flaky tests to production bugs ([Listfield comments](https://testing.googleblog.com/2017/04/where-do-our-flaky-tests-come-from.html)) [V, comment].

**Sources:** As above.

**Audit check:** Inspect CI config for `--reruns`, `retry:` or `flaky` attributes, and check whether retried passes reach the report. Count quarantined or xfail tests and their age. Mine CI history for pass→fail→pass on the same SHA (Micco's definition: "both a passing and a failing result with the same code" [V]).

**Severity:** High.

**Disagreement:** See retries below.

**Example from this project:** Issue 285 found that tests passing only on CI retry were hidden. They are now reported.

**T22. Check new and changed tests for flakiness when they are written.**

**Rule:** Before merge, rerun new or modified tests N times, in random order and in parallel.

**Why:** "Most flaky tests (78%) are flaky the first time they are written". "Techniques that extensively check tests when they are first added can detect most flaky tests" ([Luo F.2, I.2](https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf)) [V]. Detection by brute rerun of the whole suite does not scale: FlakeFlagger was still finding flakes after 10,000 reruns ([Parry §5.1](https://eprints.whiterose.ac.uk/id/eprint/230095/1/parry2021.pdf)) [V]. Targeting only changed tests is the affordable form of rerunning (inference).

**Sources:** Luo [V]; Parry [V].

**Audit check:** Check whether CI runs changed test files repeatedly, for example with `pytest --count` or flakefinder, or repeated Vitest runs with `--sequence.shuffle`.

**Severity:** Medium (a process gap, not a defect in a given test).

**Disagreement:** None.

## Suite shape matters less than what each level isolates (T23–T27)

**T23. Classify tests by size (the resources they use) separately from scope (how much code they validate).**

**Rule:** Label tests by what they may touch: small means one process with no I/O, medium means localhost, large means anything. Gate commits on a fast, pure small tier. A narrow test that touches a local Postgres is *medium*, whatever it is called.

**Why:** Size is defined by resources because "the most important qualities we want from our test suite are speed and determinism, regardless of the scope" ([SWE ch.11](https://abseil.io/resources/swe-book/html/ch11.html)) [V]. At Google over one week, **0.5% of small, 1.6% of medium and 14% of large tests were flaky**. Binary size (r²=0.82) and RAM (r²=0.76) predicted flakiness. WebDriver's higher rates were "much" explained by test size, with the tool contributing "only a small amount" ([Listfield 2017](https://testing.googleblog.com/2017/04/where-do-our-flaky-tests-come-from.html)) [V].

**Sources:** SWE ch.11 [V]; Listfield [V].

**Audit check:** Report test counts and durations per tier (`pytest --durations=N`). Flag "unit" tests that open sockets, files or subprocesses.

**Severity:** Info.

**Disagreement:** Listfield calls human size labels "subjective" and rarely updated. Objective measures predict better [V]. Bazel conflates size with scope [V].

**T24. Cover each behaviour at the lowest level that can catch it; keep end-to-end tests few and focused on what only they can see.**

**Rule:** Push each check down to the lowest level that can catch it. Don't duplicate a behaviour across levels. When a high-level test finds a bug, add a lower-level test that reproduces it. Treat published ratios as illustrations, not targets.

**Why:** UI end-to-end tests are "brittle, expensive to write, and time consuming to run". Replicate a high-level bug with a unit test so it "stays dead" ([Fowler, TestPyramid](https://martinfowler.com/bliki/TestPyramid.html)) [V~]. "Every single test in your test suite is additional baggage". "Push your tests as far down the test pyramid as you can" ([Vocke](https://martinfowler.com/articles/practical-test-pyramid.html)) [V~]. Google warns against the ice-cream cone and the hourglass. It attributes the hourglass (few integration tests) to tight coupling that blocks instantiating dependencies in isolation ([SWE ch.11](https://abseil.io/resources/swe-book/html/ch11.html)) [V]. Beck: predictive tests are slower, and composability can buy both speed and predictiveness ([testdesiderata](https://testdesiderata.com/)) [V].

**Sources:** Fowler [V~]; Vocke [V~]; SWE ch.11 [V]; Beck [V].

**Audit check:** Not mechanical. Report the tier mix, and flag behaviours asserted identically in unit, integration and E2E tests.

**Severity:** Low.

**Disagreement:** What counts as "the lowest level that can catch it" depends on the camp. For trophy and honeycomb advocates it is the integration level for most UI and service behaviour (see shapes below).

**T25. Test UI through the DOM the way a user does: role-first queries, `screen`, user-event.**

**Rule:** Query by role, then label or text, then alt or title, and test ID last. Never use `container.querySelector`. Drive interactions with user-event (set up before render) rather than `fireEvent`. Assert on what users see, not component instances or state. Treat a failed role query as a possible accessibility defect. Automated axe checks are a partial regression guard.

**Why:** "The more your tests resemble the way your software is used, the more confidence they can give you" ([Guiding Principles](https://testing-library.com/docs/guiding-principles/)) [V~]. `getByRole` "should be your top preference for just about everything", and `getByTestId` is only for when role or text can't match ([About Queries](https://testing-library.com/docs/queries/about/)) [V~]. `fireEvent` dispatches events while user-event "simulates full interactions" ([user-event](https://testing-library.com/docs/user-event/intro)) [V~]. Dodds' common-mistakes list covers `screen`, ByRole, no `querySelector` and no redundant `act` ([Common mistakes](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)) [V~]. jest-axe "does not guarantee that what you build is accessible", and colour contrast does not work in jsdom ([jest-axe](https://github.com/nickcolley/jest-axe)) [V~]. The README's figure that automation misses about 30% of barriers comes secondhand from GDS [S], so paraphrase it.

**Sources:** Testing Library [V~]; Dodds [V~]; jest-axe [V~].

**Audit check:** Count query types per file: share of `getByTestId` and `container.querySelector` versus `*ByRole`. Flag `fireEvent` where user-event is available, and wrapping `render`/`fireEvent` in `act`.

**Severity:** Low.

**Disagreement:** The notes found no counter-authority on role-first queries. Claims that `getByRole` is slow in large jsdom trees are unverified.

**T26. In async UI tests, wait for the observable outcome; treat act warnings as unfinished work.**

**Rule:** Use `findBy*`, or `waitFor` with one assertion and no side effects. Never pass `waitFor` an empty callback. An act warning means something happened after the test stopped looking: wait for it, don't suppress it. With fake timers, run pending timers and restore real timers in `afterEach`, and pass `advanceTimers` to user-event.

**Why:** If the act warning persists, "something is happening after your test completes for which you should be waiting". Async utilities "are wrapped in act automatically" ([Dodds, act warning](https://kentcdodds.com/blog/fix-the-not-wrapped-in-act-warning)) [V~]. React's `act` applies "pending React updates before making assertions", and React recommends RTL's wrapped helpers ([react.dev act](https://react.dev/reference/react/act)) [V~]. Fake timers combined with user-event "may cause test timeouts" unless `advanceTimers` is wired ([Using Fake Timers](https://testing-library.com/docs/using-fake-timers/)) [V~]. `vi.useFakeTimers()` does not fake `nextTick`/`queueMicrotask` by default ([Vitest timers](https://vitest.dev/guide/mocking/timers)) [V~].

**Sources:** Dodds [V~]; react.dev [V~]; Testing Library [V~]; Vitest [V~].

**Audit check:** Grep for `waitFor(() => {})`, side effects inside `waitFor`, `waitFor` + `getBy` where `findBy` fits, `useFakeTimers` without a matching `useRealTimers`, and suppressed act warnings.

**Severity:** High (nondeterminism and missed post-test work).

**Disagreement:** Fake timers trade speed and determinism for coupling to timer internals and leak risk (inference from the notes).

**T27. Fail tests on unexpected console errors and warnings; assert expected logs explicitly.**

**Rule:** Install a fail-on-console hook in test setup. Declare expected output per test with a spy and an assertion. Allowlist third-party noise narrowly. Never silence output globally.

**Why:** "Jest doesn't fail the tests when there is a `console.error`". The jest-fail-on-console tool fails "each test that is logging to the console" by default, and recommends spying on expected output ([jest-fail-on-console](https://github.com/ValentinH/jest-fail-on-console)) [V~]. Shopware adopted it after "hundreds of errors and warnings… made it hard to see why a test failed and if a passing test isn't just a false positive". It accepted that tests become "a little harder to write" ([Shopware ADR](https://developer.shopware.com/docs/resources/references/adr/2021-06-14-introduce-jest-fail-on-console)) [V~]. Vitest has no built-in equivalent, but `onConsoleLog` can filter output ([Vitest](https://vitest.dev/config/onconsolelog)) [V~]. GitLab's staged rollout and React's internal throw-on-`console.error` practice reached the notes only secondhand [S]. The notes found **no Google or Testing Library statement** that test output must be clean, so don't attribute the rule to them.

**Sources:** jest-fail-on-console [V~]; Shopware [V~]; Dodds on act warnings [V~]; GitLab and React practice [S].

**Audit check:** Run the suite and count stderr blocks or console calls in passing runs. Check for a fail-on-console setup file.

**Severity:** Medium.

**Disagreement:** The objections are practical (rollout cost, library noise, authoring friction), not principled. No source argued that console errors should be ignored.

**Example from this project:** Issue 298 found 52 stderr blocks of console errors in a passing suite: undefined React Query data, state updates outside `act`, and jsdom navigation. The suite now fails tests unless the output is declared. The noise had hidden a real production bug, a `useEffect` that re-posted an analytics event in a loop.

## The oracle decides whether a passing test means anything (T28–T36)

Barr et al. define the oracle problem as "distinguishing the corresponding desired, correct behaviour from potentially incorrect behavior" ([Barr et al., TSE 2015](http://www0.cs.ucl.ac.uk/staff/M.Harman/tse-oracle.pdf)) [V]. Most high-severity audit findings are oracle failures: tests that execute code without being able to fail. Google's coverage guidance states the gap plainly. Coverage "just guarantees that they have been executed by a test", and mutation testing is "a better technique to assess whether you're… adequately asserting" ([Google, Coverage Best Practices](https://testing.googleblog.com/2020/08/code-coverage-best-practices.html)) [V].

**T28. Every test must be able to fail.**

**Rule:** No empty tests, no tests without assertions, no tautological or self-comparing assertions, and no `try/except`/`catch` that swallows the failure.

**Why:** An empty test is "more dangerous than not having a test case at all", because the runner reports it as passing ([tsDetect](https://testsmells.org/pages/testsmells.html)) [V]. Beck's *Behavioral*: "If the behavior changes, the test result should change" ([testdesiderata](https://testdesiderata.com/)) [V]. FIRST's *Self-validating*: "Tests are pass-fail" ([Agile in a Flash](https://agileinaflash.blogspot.com/2009/02/first.html)) [V].

**Sources:** tsDetect rules Empty Test, Unknown Test, Redundant Assertion and Exception Handling [V]; Beck [V]; FIRST [V].

**Audit check:** AST: a test body with no `assert`/`pytest.raises`/`pytest.warns`/mock `assert_*`, or no `expect(`. Flag `assert True`, `expect(true).toBe(true)`, `assert x == x`, and `try/except` or `catch` in a test body.

**Severity:** High.

**Disagreement:** None.

**T29. Exception assertions must name the specific type and, where it is ambiguous, the message.**

**Rule:** Never write `pytest.raises(Exception)`, `assertRaises(BaseException)` or a bare `expect(fn).toThrow()`. Pin the type and use `match=`. Remember that `match` is a regex search, so partial matches pass.

**Why:** Broad context managers pass "even if, e.g., the code under consideration raises a `SyntaxError`" ([Ruff B017](https://docs.astral.sh/ruff/rules/assert-raises-exception/)) [V]. "`pytest.raises(Error)` will catch any `Error` and may catch errors that are unrelated to the code under test" ([Ruff PT011](https://docs.astral.sh/ruff/rules/pytest-raises-too-broad/)) [V]. `pytest.raises` matches subclasses "like the standard `except` statement" ([pytest assert docs](https://docs.pytest.org/en/stable/how-to/assert.html)) [V].

**Sources:** Ruff [V]; pytest [V].

**Audit check:** Enable ruff B017 and PT011, and set `raises-require-match-for` to cover `Exception` and `ValueError`. For JS, flag argument-less `toThrow()`. eslint-plugin-jest's `require-to-throw-message` exists but was not fetched, so verify it before relying on it.

**Severity:** High.

**Disagreement:** None.

**Example from this project:** In Issue 289, a broad `except` or `pytest.raises(Exception)` around a blocked socket let tests pass. The network guard's own error satisfied the assertion, so the oracle could not tell the intended failure from the guard firing.

**T30. Negative assertions must run after the event they rule out has had its chance to happen.**

**Rule:** When asserting that something did *not* happen (no element, no request, no call), first wait for a positive signal that the triggering work completed: the response rendered, the request settled, the handler ran. Then assert the absence. State explicitly what must not happen rather than leaving it unmentioned.

**Why:** "A specification that a method should not be called, is not the same as a specification that doesn't mention the method at all" ([OOPSLA 2004 §4.3](http://jmock.org/oopsla2004.pdf)) [V]. `queryBy` returns null and is meant for asserting absence ([About Queries](https://testing-library.com/docs/queries/about/)) [V~], and Dodds says to use `query*` only for that ([Common mistakes](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)) [V~]. The timing failure is inference, not a sourced rule: an absence check that runs before async work is recorded passes vacuously, so it is a can't-fail test in the T28 sense.

**Sources:** Freeman et al. [V]; Testing Library and Dodds [V~]; timing rule is inference.

**Audit check:** Partial. Flag `queryBy…` → `not.toBeInTheDocument()`, `not.toHaveBeenCalled()` or an "no request seen" check that appears in a test before any `await`/`findBy`/`waitFor`. Confirming that the anchor is meaningful needs review.

**Severity:** High.

**Disagreement:** None.

**Example from this project:** During the Issue 299 MSW migration, review found a negative assertion that could pass vacuously because it ran before the async request was recorded.

**T31. Flag weak oracles for review: sole existence checks, mock-only assertions, "doesn't crash".**

**Rule:** A test whose only assertion is `is not None`, `toBeDefined()`, a type check, a mock call, or the absence of an exception is a weak oracle. Strengthen it to assert the value or state the behaviour produces.

**Why:** Barr et al. classify crash detection as an *implicit* oracle, limited to "'obvious' faults such as a program crash" ([Barr et al.](http://www0.cs.ucl.ac.uk/staff/M.Harman/tse-oracle.pdf)) [V]. Interaction tests "can't show the system works, only that calls happened" ([SWE ch.13](https://abseil.io/resources/swe-book/html/ch13.html)) [V~].

**Sources:** Barr [V]; SWE ch.13 [V~]; the existence-check heuristic is inference.

**Audit check:** AST: tests whose only assertions are `assert_called*`/`toHaveBeenCalled*`/`verify`, or a lone `is not None`/`toBeDefined`/`toBeTruthy`.

**Severity:** Medium. Flag for review, not as an automatic defect.

**Disagreement:** London-school tests legitimately assert interactions. Treat mock-only tests of owned roles as a review question.

**T32. Track skipped, xfail and ignored tests, and report suite health metrics.**

**Rule:** Report counts and ages of skips and xfails, prefer strict xfail, and require a reason and ticket for each. Report suite and per-test durations and the measured flake rate.

**Why:** Ignored tests add overhead and complexity ([tsDetect Ignored Test](https://testsmells.org/pages/testsmells.html)) [V]. Permanent non-strict xfail is "rather dangerous" ([pytest](https://docs.pytest.org/en/stable/explanation/flaky.html)) [V]. "Slow Tests: The tests take too long to run" ([xunitpatterns](http://xunitpatterns.com/Test%20Smells.html)) [V]. FIRST calls a test taking a second or more "an impossibly slow test" ([Agile in a Flash](https://agileinaflash.blogspot.com/2009/02/first.html)) [V]. Fowler cites Beck's ten-minute ceiling for the commit suite ([UnitTest](https://martinfowler.com/bliki/UnitTest.html)) [V].

**Sources:** As above. pytest's `xfail_strict` option was not fetched, so verify it.

**Audit check:** Grep `skip`/`xfail`/`it.skip`/`test.todo`, and use pytest `-rsx`. Use `--durations=N` or JUnit XML timings. Compute flake rate from CI history.

**Severity:** Medium (skips hiding behaviour); Info (durations, rates).

**Disagreement:** No source sets an acceptable flake rate or run time. Google reports its own rates but sets no targets. The SWE book's "approach 1%" is a value-loss threshold, not a target.

**T33. Coverage finds untested code; it is not a quality target.**

**Rule:** Read the uncovered lines in review. Gate on changed-code coverage, not a project-wide number. Merge unit and integration coverage before judging a module. Remember that some integration coverage is incidental.

**Why:** With suite size controlled, there is "a low to moderate correlation between coverage and effectiveness", and "stronger forms of coverage do not provide greater insight". Coverage "should not be used as a quality target" ([Inozemtseva & Holmes, ICSE 2014](https://www.cs.ubc.ca/~rtholmes/papers/icse_2014_inozemtseva.pdf)) [V]. Google: coverage is "a lossy and indirect metric" and "What's not covered is more meaningful than what is covered". Its guide calls 60% acceptable, 75% commendable and 90% exemplary, and says "per-commit coverage goals of 99% are reasonable, and 90% is a good lower threshold". It also says "the aggregate view of the coverage of all sources in your Pipeline (unit and integration) is paramount", while some integration and E2E coverage "is incidental and not deliberate" ([Google 2020](https://testing.googleblog.com/2020/08/code-coverage-best-practices.html)) [V]. Strathern's form of Goodhart's law is the usual citation [S]. Dodds put diminishing returns past 70%, and admits he made the number up ([Write tests](https://kentcdodds.com/blog/write-tests)) [V~].

**Sources:** Inozemtseva [V]; Google [V]; [Code Coverage at Google](https://research.google/pubs/code-coverage-at-google/) [V, abstract]; Strathern [S].

**Audit check:** Report line and branch coverage per module for unit-only, integration-only and merged runs (`coverage combine`, Istanbul merge), plus diff coverage. Flag high-coverage modules with low assertion density.

**Severity:** Info.

**Disagreement:** Google gates deployments on coverage, yet warns that targets become checkboxes. Inozemtseva says coverage is not a target. The two reconcile only if the gate is a floor on new code.

**Example from this project:** In Issue 283, unit-only coverage showed repositories at 25–45%. Combining integration coverage gave 86–97%. The merged number shows the code is exercised. Whether those integration tests assert well is a separate question (see T34).

**T34. Measure oracle strength with sampled, diff-based mutation testing; report survivors, don't gate on a score.**

**Rule:** Run mutmut or StrykerJS on changed or high-risk modules. A surviving mutant on a covered line is a concrete missing assertion. Don't chase 100%, because equivalent mutants exist.

**Why:** At Google, mutation exposure correlated with developers writing more tests (r_s = 0.9, versus −0.24 for coverage). Mutants "are indeed coupled with real faults". Fewer mutants survived over time as developers acted on them ([Petrović et al., ICSE 2021](https://arxiv.org/pdf/2103.07189)) [V]. Google made mutation testing practical by being diff-based, skipping "arid" lines and capping mutants per review ([State of Mutation Testing at Google](https://research.google/pubs/state-of-mutation-testing-at-google/); [Practical Mutation Testing at Scale](https://arxiv.org/abs/2102.11378)) [V, abstracts]. "There is no definitive way for Stryker to find and ignore" equivalent mutants ([Stryker](https://stryker-mutator.io/docs/mutation-testing-elements/equivalent-mutants/)) [V]. mutmut is incremental and needs fork support ([mutmut](https://mutmut.readthedocs.io/en/latest/)) [V].

**Sources:** As above.

**Audit check:** Report mutation score and surviving mutants per sampled module. Cross-reference survivors with coverage.

**Severity:** Info.

**Disagreement:** Sampled scores are not comparable to full-run scores (inference). The ICSE 2021 design "is not a fully randomized controlled experiment" [V].

**T35. Use CRAP (complexity combined with lack of coverage) to decide where to add tests first.**

**Rule:** Rank functions by `CRAP(m) = comp(m)² × (1 − cov(m)/100)³ + comp(m)`. Use the ranking to prioritise, never as a quality score.

**Why:** At 100% coverage CRAP reduces to complexity, because "more complex code, even if it's fully protected by tests, is usually riskier to change". Its author: "It should not be abused or misused as a proxy for code quality", and "Metrics are meant to help you think, not to do the thinking for you" ([Savoia 2007](https://www.artima.com/weblogs/viewpost.jsp?thread=210575)) [V]. The often-cited crap4j threshold of 30 was not verified [S], so leave it out or mark it unverified.

**Sources:** Savoia [V].

**Audit check:** Combine radon (Python) or eslint complexity (JS) with per-function coverage. CRAP inherits coverage's blind spots: an assertion-free test still lowers the score (inference).

**Severity:** Info.

**Disagreement:** Savoia records that some argued 100% coverage should mean zero risk. He and Bob Evans kept the complexity floor [V].

**T36. Rank smell findings by consequence; detectors produce review prompts, not verdicts.**

**Rule:** Report findings in this order:
1. Can't-fail tests (T28–T30).
2. Nondeterminism and isolation (T16–T21, T26).
3. Coupling and fidelity (T7–T14).
4. Readability smells (Assertion Roulette, Magic Number, Eager Test, General Fixture) as low or informational.

Use thresholds, not "any occurrence", for readability smells.

**Why:** For the older detection tool they benchmarked on six smells, Panichella et al. found its strategies "misclassified over 70% of test smells". Several smells "were ubiquitous on developer-written tests but virtually never correlated" with real flaws ([Panichella et al., EMSE 2022](https://research.tudelft.nl/en/publications/test-smells-20-years-later-detectability-validity-and-reliability)) [V, abstract]. Which six smells, and the per-smell numbers, were not retrieved. Spadini et al. found developers consider some default rules "too strict", and that threshold-based severities matched developers' perception ([MSR 2020](https://2020.msrconf.org/details/msr-2020-papers/14/Investigating-Severity-Thresholds-for-Test-Smells)) [V, abstract via search]. The smell vocabulary originates with van Deursen et al. 2001 ([CWI](https://ir.cwi.nl/pub/4324)) and Meszaros ([xunitpatterns](http://xunitpatterns.com/Test%20Smells.html)) [V]. The van Deursen smell count (10 vs 11) is unverified [S].

**Sources:** As above.

**Audit check:** This heuristic governs how the audit reports, not a check of its own.

**Severity:** Info.

**Disagreement:** tsDetect's Mystery Guest advice ("use mock objects in place of external resources") conflicts with real-dependency strategies such as T9. Treat it as a tier-placement question.

## Properties generalise examples when an oracle can be stated (T37–T39)

**T37. Use property-based tests where a general property exists; prefer postconditions, metamorphic and model-based properties over validity alone.**

**Rule:** Candidates include round-trips (encode/decode, serialise/parse), data structures with invariants, and functions currently covered by many same-shaped examples. Choose from Hughes' five property kinds:

| Kind | Slogan |
|---|---|
| Validity | "Every operation should return valid results" |
| Postcondition | Relates return values to the arguments of a single call |
| Metamorphic | "Related calls return related results" |
| Inductive | Properties that together form a complete specification |
| Model-based | Compare against a simpler abstract model |


**Why:** In Hughes' benchmark of eight planted bugs, "Validity properties miss many bugs (five of eight)". "Every bug is found by at least one postcondition, metamorphic property, and model-based property". Model-based testing "seemed the most effective approach overall", and metamorphic testing is "a successful approach to the oracle problem" ([Hughes, How to Specify It!](https://research.chalmers.se/publication/517894/file/517894_Fulltext.pdf)) [V]. MacIver: "If you could feasibly write a property based test as 10 example based tests… it's probably really just example based testing" ([What is PBT?](https://hypothesis.works/articles/what-is-property-based-testing/)) [V].

**Sources:** Hughes [V]; MacIver [V]; [fast-check](https://fast-check.dev/docs/introduction/why-property-based/) [V].

**Audit check:** Count `@given`/`fc.assert` usages per module. Flag round-trip function pairs and long parametrise tables with no property test.

**Severity:** Low (an opportunity, not a defect).

**Disagreement:** The evidence base is thin. The benchmark is 8 bugs in one binary search tree, and the notes found no industrial study.

**T38. Test the generators, check the input distribution, and don't accept "doesn't crash" as the only property.**

**Rule:** Custom strategies or arbitraries need a validity property, and their shrinkers need one too. Measure what the generator actually produces. Avoid filter-heavy generation. A property that only checks for no exception is an implicit oracle.

**Why:** "Test your tests". "Invalid test data provokes false positives". Measure the distribution ([Hughes](https://research.chalmers.se/publication/517894/file/517894_Fulltext.pdf)) [V]. MacIver now thinks "doesn't crash" testing "probably doesn't count" as PBT ([MacIver](https://hypothesis.works/articles/what-is-property-based-testing/)) [V].

**Sources:** Hughes [V]; MacIver [V]; Barr on implicit oracles [V]. Hypothesis health checks for excessive filtering were not fetched, so verify them.

**Audit check:** Flag custom strategies with no validity test, heavy `assume()`/`.filter()` use, and property bodies with no assertion beyond the call.

**Severity:** Medium.

**Disagreement:** Whether fuzz-style "doesn't crash" counts as PBT: MacIver reversed his earlier view.

**T39. Make property failures minimal and reproducible: integrated shrinking and a recorded seed.**

**Rule:** Prefer libraries that shrink as part of generation (Hypothesis, fast-check). Record the failing seed or example so a failure can be replayed exactly.

**Why:** With integrated shrinking, "You can guarantee that shrinking satisfies the same invariants as generation". Type-based shrinking can produce "extremely confusing" counterexamples ([MacIver, Integrated shrinking](https://hypothesis.works/articles/integrated-shrinking/)) [V]. fast-check reports a seed that can be passed back to `fc.assert` ([fast-check](https://fast-check.dev/docs/introduction/why-property-based/)) [V]. This keeps PBT compatible with Beck's *Deterministic* desideratum (T19).

**Sources:** MacIver [V]; fast-check [V].

**Audit check:** Confirm the seed is printed in CI output and that a failure database or example replay is configured.

**Severity:** Low.

**Disagreement:** Haskell QuickCheck keeps type-based shrinking, and MacIver calls that approach bad [V].

## Four disagreements that are real, and what each side pays

**London versus classicist mocking is a dispute about where mocks belong, not whether to use doubles.** Freeman and Pryce say mock objects are "most useful when used to drive the design of the code under test… within the system where the interfaces can be changed". They treat isolation from third-party code as "a secondary aspect" ([OOPSLA 2004 §5.2](http://jmock.org/oopsla2004.pdf)) [V]. Khorikov holds the direct opposite: "Intra-system communications are implementation details". He judges that "Both schools are wrong… though the classical school is less so than the London school" ([When to Mock](https://enterprisecraftsmanship.com/posts/when-to-mock/)) [V]. Fowler sees "no compelling benefits for mockist TDD" ([Mocks Aren't Stubs](https://martinfowler.com/articles/mocksArentStubs.html)) [V~]. Google swung away from mocking frameworks after they produced tests that "rarely" found bugs ([SWE ch.13](https://abseil.io/resources/swe-book/html/ch13.html)) [V~]. **The classicist cost** is real: a change to a core class can ripple through many tests and their test data. Failures are less localised ("might even require a debugger"), and fixtures grow large (OOPSLA §5.5 [V]; Fowler [V~]). **The London cost** is coupling to call structure that "interferes with refactoring". The result is change-detector tests, plus the Python docs' warning that mocked units can all pass while the wiring is broken ([Autospeccing](https://docs.python.org/3/library/unittest.mock.html#autospeccing)) [V]. Underneath, the schools agree: don't mock types you don't own, wrap externals in adapters, and read complex mock setup as a smell. The live question is only whether to mock *owned in-process role interfaces* during outside-in design. **The notes found no empirical study comparing the two schools.** Every position is expert opinion.

**Pyramid, trophy and honeycomb mostly disagree about what "unit" means.** The pyramid wants "many more low-level UnitTests than high level BroadStackTests" ([Fowler](https://martinfowler.com/bliki/TestPyramid.html)) [V~]. Dodds' trophy makes integration the widest band because it "strike[s] a great balance on the trade-offs between confidence and speed/expense" ([Write tests](https://kentcdodds.com/blog/write-tests)) [V~]. Spotify's honeycomb says the pyramid "can be actively harmful" for microservices, and that too many unit tests restrict how code can change ([Spotify](https://engineering.atspotify.com/2018/01/testing-of-microservices)) [V~]. Fowler's 2021 reading is that trophy and honeycomb advocates object to *solitary* unit tests, and their "integration tests" resemble his *sociable* unit tests, so the dispute is largely definitional ([Shapes of Testing](https://martinfowler.com/articles/2021-test-shapes.html)) [V~]. Searls, quoted secondhand by Fowler, calls the percentage debate a distraction. In his view tests should have clear boundaries, run fast and reliably, and fail only for useful reasons [S]. Dodds agrees that "Any attempt to come to a single definition for all these terms is a futile endeavor" ([Trophy](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications)) [V~]. **The pyramid's cost** is a temptation toward solitary, mock-heavy units that pass while integration fails. **The trophy and honeycomb cost** is slower tests that fail less specifically. All three reject E2E-heavy suites. The practical resolution is to define levels by what they isolate (T23), not by a ratio.

**Naming conventions are a taste dispute with one substantive core.** North uses "should" because it invites the reader to "challenge the premise of the test" ([North](https://dannorth.net/blog/introducing-bdd/)) [V]. Khorikov calls "should be" an anti-pattern, because a test states a fact. He also calls `[MethodUnderTest]_[Scenario]_[ExpectedResult]` "one of the least helpful" conventions, because "it encourages you to focus on implementation details" ([Khorikov](https://enterprisecraftsmanship.com/posts/you-naming-tests-wrong/)) [V]. Google keeps the method in names such as `displayTransactionResults_showsLowBalanceWarning` ([SWE ch.12](https://abseil.io/resources/swe-book/html/ch12.html)) [V]. The method-first template is usually attributed to Osherove, but his post was not fetched [S]. **Method-in-name costs** coupling to a renameable symbol. **Free-form names cost** grep-ability and consistency. The substantive core everyone shares is that the name states the behaviour and its expected outcome (T3).

**Retries split pragmatists from purists, and visibility is the settlement.** The SWE book says automatic reruns make sense "at low levels of flakiness" ([ch.11](https://abseil.io/resources/swe-book/html/ch11.html)) [V]. Playwright and Vitest ship retry options, and Vitest's can be conditioned on the error message ([Vitest retry](https://vitest.dev/config/retry)) [V]. Bazel discourages its own `flaky` flag. Micco reports that retry policies made developers ignore flakiness, and that one broken 15-minute test went unnoticed for 45 minutes ([Micco](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html)) [V]. Luo found 24% of flaky-test fixes changed the code under test, 94% of those fixing real bugs [V]. **The cost of retrying** is masked races and delayed detection. **The cost of not retrying** is red builds from infrastructure noise, which concentrate in large tests (14% flaky vs 0.5% small, per Listfield [V]). The settlement that runs through these sources: no retries in the small tier, and bounded retries elsewhere, reported as "flaky" with a ticket (T21). **No controlled study measures missed-bug rates under retry policies.**

Smaller disputes appear inline:

| Dispute | Where |
|---|---|
| Assertion Roulette's strictness | T36 |
| Rollback vs truncate | T20 |
| Coverage gating vs coverage-as-target | T33 |
| Bazel size vs Google size | T16, T23 |
| Clean-before vs clean-after | Fowler vs Luo, an emphasis difference |

## Corrections the notes require

**Google's test-mix ratios are three different numbers from three places.**

| Ratio | Source | Status |
|---|---|---|
| **80/15/5** (unit / integration / E2E) | *SWE at Google* ch.11, "Test Scope" ([ch.11](https://abseil.io/resources/swe-book/html/ch11.html)) | [V] |
| **~80/20** (unit / broader-scoped) | *SWE at Google* ch.12 ([ch.12](https://abseil.io/resources/swe-book/html/ch12.html)) | [V] |
| **70/20/10** | Wacker, "Just Say No to More End-to-End Tests", Google Testing Blog, 2015 ([post](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html)) | Figure confirmed only via reader comments on that page; the article body was not retrieved, so paraphrase its wording |

70/20/10 is not from SWE ch.11. All of these figures are rules of thumb, not targets.

**Google's flake-rate figures use different denominators and must be quoted with theirs.**

| Figure | Denominator | Source |
|---|---|---|
| ~1.5% | all test runs (2016) | [Micco 2016](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html) [V] |
| ~0.15% | test runs, "hovers around" (2020) | [SWE ch.11](https://abseil.io/resources/swe-book/html/ch11.html) [V] |
| ~16% | tests with *some* flakiness (2016) | Micco [V] |
| <2% (~63K of 4.2M) | tests with a flaky run in one week (2017) | [Listfield 2017](https://testing.googleblog.com/2017/04/where-do-our-flaky-tests-come-from.html) [V] |
| 4.56% (73K of 1.6M/day) | test *failures* caused by flakes (TAP, 15 months) | [Luo et al.](https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf) [V] |
| ~84% | pass→fail *transitions* involving a flaky test | Micco [V] |
| 0.5% / 1.6% / 14% | small / medium / large tests flaky in one week | Listfield [V] |
| ~1% | threshold where tests "begin to lose value" | SWE ch.11 [V] |

The 1.5% to 0.15% gap is tenfold, and the sources do not say whether it reflects improvement or a changed definition. Outside Google, the chance that one suite run hits at least one flaky failure was "as high as 50.0%" across 82 open-source projects ([iDFlakies](https://mir.cs.illinois.edu/winglam/publications/2019/LamETAL19iDFlakies.pdf)) [V].

**Lineage**

| Heuristic | Origin (earliest source in the notes) | Later reinforcement |
|---|---|---|
| T1 Public API / observable behaviour | North 2006 (behaviour over test); SWE ch.12 (public API) | Khorikov 2020 (observable behaviour); Dodds 2020 |
| T2 One behaviour, AAA | Wake 2001 (AAA); Beck 2002 (p.97 mention) | North 2006; SWE ch.12 |
| T3 Sentence names | North 2006 (agiledox) | Khorikov 2019; SWE ch.12 |
| T4 No logic in tests | Meszaros 2007 (Conditional Test Logic) | SWE ch.12; tsDetect |
| T5 DAMP | Google TotT 2019 / SWE ch.12 | Meszaros (General Fixture, Mystery Guest); van Deursen 2001 |
| T6 Failure messages | SWE ch.12 | Beck *Specific*; FIRST "isolate failures" (2009 card) |
| T7 Unchanging / structure-insensitive | Beck desiderata; SWE ch.12 | Khorikov resistance to refactoring and styles (2016 blog, 2020 book) |
| T8 Real > fake > stub | Fowler, "Mocks Aren't Stubs" (classical TDD) | SWE ch.13 |
| T9 Mock unmanaged only | Khorikov 2020 | SWE ch.14 (no real third-party APIs) |
| T10 No asserts on stubs; minimal verification | Freeman et al. 2004 ("specify as little as possible") | Khorikov; SWE ch.13 |
| T11 Mock only owned types; adapters | Freeman et al. 2004 | GOOS |
| T12 Specced doubles | Python `unittest.mock` docs | Freeman et al. §5.6 (string-keyed mocks break on rename); Vitest |
| T13 Network-boundary mocks | Dodds ("Stop mocking fetch") | MSW philosophy; Testing Library principle |
| T14 Owned, contract-tested fakes | SWE ch.13 | Fowler 2011 (contract tests for remote doubles) |
| T15 Seams over patching | Feathers, *WELC* (seam model) | SWE ch.13 (DI as primary seam) |
| T16 Hermeticity, enforced size | SWE ch.11 / ch.14 | pytest-socket |
| T17 Order independence | *Clean Code* 2008 / FIRST; Beck *Isolated* | Luo 2014; iDFlakies 2019; Parry 2021 |
| T18 No sleeps | Fowler 2011 | Luo 2014; SWE ch.11, ch.14 |
| T19 Control time and randomness | Fowler 2011 | Luo 2014; pytest docs; freezegun; pytest-randomly |
| T20 Reset state | Fowler 2011 | Django docs; pytest monkeypatch; Vitest config |
| T21 Flakes are bugs; visible retries | Fowler 2011 (quarantine); Micco 2016 | Luo I.12; Bazel; Playwright; SWE ch.11 |
| T22 Check tests at birth | Luo 2014 (F.2, I.2) | Parry 2021 (rerun impractical) |
| T23 Size vs scope | SWE ch.11 | Listfield 2017 |
| T24 Lowest level, few E2E | Cohn 2009 (via Fowler 2012) | Vocke; SWE ch.11 |
| T25 Role-first DOM queries | Testing Library guiding principles | Dodds 2020; jest-axe |
| T26 Async UI waits | React `act`; Dodds 2020 | Testing Library fake timers; Vitest |
| T27 Fail on console | jest-fail-on-console; React internal practice [S] | Shopware ADR 2021 |
| T28 Must be able to fail | van Deursen 2001 / Meszaros; FIRST *Self-validating* | tsDetect |
| T29 Specific exceptions | Ruff/flake8-bugbear B017; PT011 | pytest docs |
| T30 Anchored negative assertions | Freeman et al. 2004 §4.3 | Testing Library `queryBy`; timing rule is inference |
| T31 Weak oracles | Barr et al. 2015 (implicit oracles) | SWE ch.13 |
| T32 Skips and health metrics | Meszaros (Slow Tests); FIRST *Fast* | tsDetect Ignored Test; pytest docs |
| T33 Coverage as signal | Inozemtseva & Holmes 2014 | Google 2019–2020; Strathern 1997 [S] |
| T34 Mutation testing | Petrović & Ivanković 2018 (practice at scale) | Petrović et al. 2021 |
| T35 CRAP | Savoia & Evans 2007 | — |
| T36 Rank smells by consequence | van Deursen 2001 (catalogue) | Panichella 2022; Spadini 2020 (validity, thresholds) |
| T37 Property kinds | Hughes 2019/2020 | MacIver; fast-check |
| T38 Test the generators | Hughes 2019/2020 | MacIver |
| T39 Integrated shrinking, seeds | MacIver (Hypothesis) | fast-check |

## Conclusion

The sources reduce test quality to two questions an auditor can actually check. **Can this test fail when behaviour is wrong?** That is an oracle question, settled by T28–T31 and measured by mutation survivors. **Will it give the same answer every time and in any order?** That is a determinism question, settled by T16–T21 and measured by shuffled, parallel, repeated runs. Everything else is a cost-of-change or readability concern that the evidence ranks lower: coupling, naming, structure and suite shape. The evidence makes that ranking necessary rather than a matter of taste, because rule-based smell detection is unreliable while flakiness and vacuous assertions demonstrably destroy trust in a green build. The Fitted cases bear this out. Each one (a guard error satisfying a broad `raises`, a guard that missed teardown, an order dependency revealed only under xdist, retries hiding flakes, console noise hiding a looping `useEffect`, a negative assertion racing its request) was a can't-fail, nondeterminism or hidden-signal defect inside a passing suite. None would have surfaced from a readability smell count.

The second implication is that the strongest checks are runtime harnesses, not lint rules: socket guards that cover fixtures, randomised parallel execution, fail-on-console, merged coverage and sampled mutation testing. A test-writing skill should make each of these the default the author works inside. A test-suite audit skill should first verify that each harness is present and actually covers what it claims to, and only then count smells. Several claims the skills might want to lean on rest on thin evidence and should stay labelled as such: an empirical comparison of the mocking schools, the missed-bug cost of retries, parallel CI as a continuous practice, and the effectiveness of property-based testing at industrial scale. The notes found no primary study of any of them.
