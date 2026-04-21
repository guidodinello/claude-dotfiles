# Update Log

## 2026-04-21 — Initial version

**Created by:** Guido Dinello via Claude Code (claude-sonnet-4-6)

**Scope:** Initial skill creation. Covers OWASP Top 10 categories most relevant to Node.js/TypeScript web applications:
- Injection (SQL, command, path traversal, mass assignment, prototype pollution, SSTI)
- Broken authentication and session management
- IDOR and access control weaknesses
- CSRF
- JWT weaknesses
- Secrets exposure
- Sensitive data in logs and URLs
- XSS
- Security headers
- Information disclosure
- Weak cryptography

**What's not yet covered:**
- XML/XXE injection (lower prevalence in modern JSON APIs)
- Insecure deserialization (Node.js-specific patterns)
- SSRF (Server-Side Request Forgery)
- WebSocket-specific vulnerabilities
- GraphQL-specific attack surface (batching, introspection abuse)
- Dependency vulnerability scanning (npm audit integration)
- Rate limiting audit patterns
