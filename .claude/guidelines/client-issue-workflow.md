# Client-Reported Issue Workflow

When a client reports a bug or unexpected behavior, follow this sequence:

## 1. Acknowledge

Reply immediately to confirm the report was received and you are looking into it. Keep it brief — no conclusions yet.

## 2. Investigate

Trace the code and logs to understand what actually happens. Document findings before responding further.

## 3. Explain

Reply with how the system currently works in plain language, no jargon. Stay neutral — do not label it a bug or a feature yet.

## 4. Decide and Act

**If it is clearly a bug** (behavior contradicts the spec or causes data loss): fix it, then inform the client.

**If it is a product decision ambiguity** (the behavior was intentional but may not match the client's expectation): present two or three clear options and ask how they want it to work. Do not implement until they choose.

---

## Communication Rules

- Don't frame product decisions as bugs. If the behavior was intentional, calling it a "bug fix" is incorrect and erodes trust.
- Be specific about scope. Say what was done and what is still being investigated — don't make blanket claims.
- When presenting options, give a clear recommendation and name the tradeoff. Don't make the client choose blindly.
- Ask product questions before implementing when a fix changes behavior. The client's answer often changes the shape of the fix entirely.
