# Method

## Three layers

| Layer | Holds | Lives in |
|---|---|---|
| Voice | How Guido writes to anyone | `references/voice.md` (this skill, public) |
| Audience | How he adapts to one person or client | the project, e.g. `my-dev-things/work-guide/client-communication-style.md` |
| Corpus | Sent Slack messages and draft-vs-sent pairs | the project, e.g. `my-dev-things/work-guide/voice/` (gitignored) |

Corpus is Slack only. Guido polishes Slack messages and writes PR and ticket comments quickly, so
those don't show his voice and shouldn't be used as examples.

Test for the layer: would the rule still hold if the message went to a different client? Yes means
voice. No means audience. Mixing them is what produces rules with exceptions ("no exclamations,
except to X").

## The loop

1. Draft with voice + audience rules + a few close examples from the corpus.
2. Guido edits, either in chat or silently in Slack.
3. Each meaningful edit becomes one rule, written as text, generalized, dated.
4. The sent version goes into the corpus. Draft-vs-sent differences are the strongest signal,
   because they catch edits he never mentioned.

How much he edits a draft before sending is the measure of progress. Fewer edits over time means
the rules are working.

## Measuring

`scripts/measure_edits.py <sent-corpus> <project-substring> --since "<date of the change>"` scores each
sent message against Claude's **first** draft (difflib similarity, 0-1) and counts the drafts before
sending, then compares medians before and after the date. Track the median first-draft score; it should
rise. The best-draft score is not a measure, because Claude often re-prints Guido's own edit just
before he sends.

Sent messages must be in the corpus verbatim and in `> ` blockquotes, or both scripts skip them.
Read a handful of messages per recipient as a direction, not proof. Log each run in the project, next
to the corpus.

## Consolidation

Run when rules contradict or the voice file passes about 60 rules:

- Merge rules that say the same thing.
- Turn an exception into a scope (move it to the audience layer if it's about one person).
- Drop a rule whose correction never came back in later sessions, after checking with Guido.

## Seeding from transcripts

`scripts/mine_corrections.py <project-substring>` lists user messages from Claude Code transcripts
that look like wording corrections, each with the end of the draft before it. Read the output,
classify each hit as voice, audience or accuracy, and keep only the first two. The output can
contain client text: print it or write it inside the project, never into this repo.

## Research behind it

- Learning from edits: CIPHER/PRELUDE (Gao et al., NeurIPS 2024, arXiv 2404.15269) infers a
  text preference from each user edit and retrieves preferences from similar past contexts. It
  beat the other methods tested on email writing, and the learned preferences stay readable and
  editable. This skill is a manual version of that loop.
- Examples alone aren't enough: "Catch Me If You Can? Not Yet" (arXiv 2509.14543, 2025) found
  few-shot examples help style matching, but going from 2 to 10 adds little, and informal
  writing (blogs, chat) is the hardest to imitate. Hence explicit rules plus 3–5 close examples.
- What to write: *Writing for Busy Readers* (Rogers & Lasky-Fink, 2023). Less is more, make
  reading easy, design for navigation, enough formatting but no more, tell readers why they should
  care, make responding easy. Several voice rules apply these.
