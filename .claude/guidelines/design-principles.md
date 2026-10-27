## Design principles
Apply when designing or reviewing code that enforces a policy (privacy, security, access, data retention).
- **Privacy and security controls fail closed.** When a policy can't decide (a missing marker, an unknown value, a parse error), the default is the restrictive outcome (hide, deny, drop), never the permissive one.
- **Don't key behavior on human-readable text.** Comments, labels and error messages are documentation; they get reworded. Declare behavior as data (an enum, a decorator, a typed registry) and generate the text from it.
