---
name: my-voice
description: "Trigger: draft a message, Slack reply, write to the client, in my voice, sound like me, I'd write it like, tone fix. Draft as Guido and learn from his edits."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.0"
---

## Activation Contract

Load before drafting a Slack message Guido will send under his own name, and when he corrects the wording of one, to record the correction. Slack is where he polishes; for PR or ticket comments apply only the Register and Precision rules, and don't record corrections. Not for docs, code comments, commit messages or PR descriptions.

## Hard Rules

- This skill lives in a public repo. Never write real client messages, names, project details or PHI into it. Examples in `references/voice.md` stay synthetic.
- Client evidence (sent messages, draft-vs-sent pairs, audience notes) lives in the project, in a gitignored folder. Default: `my-dev-things/work-guide/voice/` and `my-dev-things/work-guide/client-communication-style.md`.
- Voice rules apply to everyone. A rule that only holds for one person or one client is an audience rule and goes in the project, not here.
- Never correct deliberate quirks: lowercase starts, repeated letters ("hii", "thankss"), light abbreviations.
- Accuracy problems (wrong fact, impossible offer) are not style. Fix them; don't record them as voice rules.

## Decision Gates

| Situation | Action |
|---|---|
| Drafting a message | Steps 1–4 |
| Guido edits or rejects wording | Step 5 |
| Guido says he sent it (or a sent version is visible) | Step 6 |
| Rules contradict or the voice file grows past ~60 rules | Consolidate per `references/method.md` |
| Guido asks if the skill is working | Run `scripts/measure_edits.py` per `references/method.md` § Measuring |

## Execution Steps

1. Read `references/voice.md` (global voice).
2. If the project has an audience file, read the section for the recipient. Recipient rules win over voice rules.
3. If the project has a sent corpus, pick 3–5 messages to the same recipient and of the same kind (status, ask, ack, proposal, follow-up) and match them. Don't load the whole corpus.
4. Draft. Then check it against `references/voice.md` § Checklist before showing it.
5. On a correction: state the rule you inferred in one line, say whether it is voice (global) or audience (project), and add it to the right file with the date and, for audience rules, a source. Generalize the rule; don't copy the client text.
6. When the sent version is available, compare it with the draft. Record each meaningful difference as in step 5 and append the sent message to the project corpus.

## Output Contract

- Return the draft ready to paste, set apart with `---` lines, and nothing else around it unless a fact needs checking.
- After a correction: one line with the rule, its layer and the file it was added to.

## References

- `references/voice.md`: the global voice rules and the pre-send checklist.
- `references/method.md`: the three layers, the correction-to-rule loop, consolidation, and the research behind it.
- `scripts/mine_corrections.py`: finds past wording corrections in Claude Code transcripts, to seed or refresh the rules.
- `scripts/pair_drafts.py`: pairs each message in a sent corpus with the earliest Claude draft that matches it, to find silent edits.
- `scripts/measure_edits.py`: scores how close each sent message is to Claude's first draft, before vs after a date, to check the rules are working.
