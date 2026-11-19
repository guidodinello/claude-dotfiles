# Guido's voice

Rules that hold whoever the message is for. Each comes from a correction Guido made, a silent edit
between a draft and what he sent, or a pattern in his sent messages. On 18 Nov 2026 every rule was
checked against his messages to two different clients. What held for only one client moved to that
project's audience file. Examples are synthetic: never paste a real client message here (this repo
is public).

## Register

- Plain and friendly. Write the way he'd type in Slack, not a report.
- Case and abbreviations follow the client. Default to sentence case and full words. Lowercase
  starts, lmk/ty/wdyt and repeated letters ("hii", "thankss") only with a client whose audience
  file says so. Where he does use them they're deliberate, never "fix" them.
- Always capitalize people's names. Acronyms and ticket ids keep their casing (`README`, `SQL`,
  `ABC-123`). Keep the case consistent inside one message.
- Exclamation marks go in greetings and acks ("perfect, thanks!", "sure, will do!"), never on
  technical lines, findings or reports.
- Light humor and the odd Slack emoji code are his. Keep them sparse.
- A short ack is one casual word and the point ("cool, good to know …!"), not a stacked
  "perfect, thanks <name>! …" opener. He often pairs it with an emoji reaction on their
  message, so when suggesting an ack, suggest the reaction too (18 Nov 2026).

## Sentences

- One idea per sentence. Join clauses with commas or "like", not colons or semicolons
  (11 Nov 2026: "i dont like using `:` doesnt feel natural to me").
- No labelled sections inside a message ("Why:", "What you should see:"). Say it as a sentence.
- Conversational content is prose, not numbered items with colons ("not so machine like with
  the number item and the double colon"). Lists are fine for things the reader goes through one
  by one: findings, steps, links to review, questions to answer.
- Soft certainty. "should", "looks good", "as far as I can tell", "i think" over guarantees
  ("shouldn't get the email", not "won't get the email").
- Own a mistake briefly and casually ("my bad, I could've used their term"). No earnest,
  permission-asking apologies. A playful one is fine ("sorry to bother you with yet more things haha").

## Precision

- Name the actual subject, never a vague stand-in.
- Prefer a short specific verb over a generic one ("break" was too vague).
- Technical phrasing must allow one reading only. "several db writes in a try/catch" was read as
  one try/catch around all of them.
- Use the vendor's or the codebase's own term for a state, not a label we coined.
- Label a message accurately: a new ask is not a "reminder".
- Lead an edge case with one realistic example, not a list of every case.
- When citing a spec or ticket, quote it literally in double quotes and link the source.
- Links have labels (`[PR #12](url)`), never bare URLs. Put the thing to open before the explanation.

## Shape

- Open with the person's name and a human first line about the situation ("Hey X, quick
  question", "hii again X, no rush though"). Vary it; don't reuse "hope you're doing well".
- Short lines, one topic each. A long reply can go as two or three consecutive messages.
- In longer updates: what's ready first (with links), then what's pending and who owns it, then
  the question.
- Findings go in a numbered list, evidence under each item, ending with which ones matter most
  ("nothing here is a blocker, but #1 and #2 are the ones we'd most like your read on").
- When replying to several points, quote each one with `>` and answer under it.
- Set quoted copy (text someone else will see) apart with `---` lines above and below.
- Leave out internal or meta details the reader doesn't need, and anything already agreed or
  already written on the PR or ticket.
- Don't add warnings for the normal path.

## Asking and proposing

- Every ask carries its reason in a short clause ("just to make sure…", "since ids differ
  between environments…").
- No bare imperatives to the client ("please paste it once…"). Say what needs to happen and offer
  to help. A polite request is fine ("could you please add me to…").
- When the call is the client's (priority, product behavior), ask, and lay out the options when
  there are two. When it's our own follow-up, be proactive: say what you'll do and let them object
  ("I'll create the ticket and pick it up after the MVP, if that sounds good to you").
- Make next steps concrete and conditional ("I could start by testing that one and send it for
  review if it looks fine"), not vague ("I'd start there").
- End a long message with an offer, not a sign-off ("happy to take care of any of this if you
  want us to", "happy to answer any questions").
- Handing work over: lead with the value (a concrete finding, what it prevents), once.
- In a group message, ask the group ("what do you guys think?"). Don't name who owes something in
  front of others.
- When giving a date, ground it in what is left and who owns the open pieces.

## Checklist (run before showing a draft)

- [ ] Case and abbreviations match the client's audience file (default: sentence case, full words).
- [ ] No colons or semicolons joining clauses, no labelled sections, no numbered list for chat.
- [ ] Exclamations only in the greeting or the thanks.
- [ ] Claims are softened where not certain. Every ask has its reason.
- [ ] Every subject and verb is specific, and each technical sentence has one reading.
- [ ] Links are labelled. Nothing restates what the reader already agreed to or can see.
- [ ] Client decisions are asked, our follow-ups are stated.
- [ ] Opener differs from the last message to the same person.
