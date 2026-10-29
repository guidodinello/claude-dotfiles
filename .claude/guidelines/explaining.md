## Explaining tasks and mechanisms
Apply when explaining how something works or what a task involves, especially work that spans several components.
- **Map first.** List the components by exact name (which service, which instance, which database inside it), and the links between them, naming the kind of link (points to, is allowed through, reads from). With more than two components, draw a small box-and-arrow diagram.
- **Why second.** Say what problem the change solves in one or two sentences, before any step.
- **Steps last.** Tag each step with what it touches, how it is done (terraform, manual, code) and who runs it.
- **No bare ambiguous nouns.** Never write just "the service", "the connection" or "the user": name the specific thing every time, even if it repeats.
- **Define a term the first time it appears.**
