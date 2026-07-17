# Audit Skills

A set of **stack-agnostic** audit skills for Claude Code, built while running a real
production audit. They cover HIPAA, application security, database scalability, and
general code health, and they all emit reports against one shared reporting contract.

Sharing these as an input to the company's curated AI skill set — not as a finished
product. Take the parts that are useful, ignore the rest.

> This is an **index**, not a copy. Every link below points at the canonical skill in
> this repo — there's no duplicated content to drift. To use one, see [Install](#install).

---

## The approach, and how it differs

These skills **do not carry per-language or per-framework pattern lists.** They describe
*what to look for* conceptually — entry points, user-input-to-dangerous-sink flows,
PHI-bearing tables, growth trajectories — and let the model discover the stack and its
idioms on the way in.

That's a deliberate tradeoff, and it's the opposite of the framework-dependent approach
(explicit patterns per language/framework/stack):

| | Stack-agnostic (these) | Framework-dependent |
|---|---|---|
| **New stack** | Works out of the box | Needs a new pattern set written |
| **Precision** | Depends on model reasoning; can miss framework idioms | High recall on known patterns |
| **Determinism** | Lower — varies run to run | Higher — greps are greps |
| **Maintenance** | Little; ages well | Pattern matrix grows per stack, needs upkeep |
| **Cost/speed** | More exploration per run | Cheaper, more targeted |

**These are complementary, not competing.** A curated set could plausibly use a
stack-agnostic methodology as the *spine* (surface map → findings → severity →
remediation) with framework-specific patterns as the *detection layer* under it. The
methodology is the part worth stealing; the lack of patterns is a gap, not a feature.

---

## The skills

### Audit skills

| Skill | What it does |
|---|---|
| [`hipaa-audit`](../../.claude/skills/hipaa-audit/) | HIPAA Security Rule compliance — PHI exposure, safeguards, BAA coverage, audit trails |
| [`security-audit`](../../.claude/skills/security-audit/) | OWASP-style app security — injection, authn/authz, secrets exposure, access control |
| [`db-scalability-audit`](../../.claude/skills/db-scalability-audit/) | Database scalability & architecture — provider limits, bottlenecks, growth trajectory |
| [`code-health`](../../.claude/skills/code-health/) | Readiness / tech debt — dead code, test coverage, complexity hotspots, dep vulns |

### Supporting skills

| Skill | What it does |
|---|---|
| [`audit-fact-checker`](../../.claude/skills/audit-fact-checker/) | Verifies reported findings against the actual code — catches false positives before delivery |
| [`audit-consolidation-validator`](../../.claude/skills/audit-consolidation-validator/) | Validates a client-facing consolidated doc against the internal audit files |
| [`db-migration-planner`](../../.claude/skills/db-migration-planner/) | Follow-up to `db-scalability-audit` when a migration is actually on the table |

### Shared dependencies (required — the skills break without these)

| Path | Why |
|---|---|
| [`guidelines/templates/audit-template.md`](../../.claude/guidelines/templates/audit-template.md) | The shared reporting contract. `hipaa-audit`, `security-audit`, and `db-scalability-audit` reference it directly |
| [`agents/audit-finding-verifier.md`](../../.claude/agents/audit-finding-verifier.md) | Subagent spawned by `audit-fact-checker` and `audit-consolidation-validator`, one per finding |

> A `permissions-audit` skill exists in this repo too, but it's left out here — the team
> already has that one covered.

---

## The shared reporting contract

[`guidelines/templates/audit-template.md`](../../.claude/guidelines/templates/audit-template.md)
is the piece to look at first — it's what makes different audits produce comparable
output. It fixes:

- **Severity levels** (CRITICAL → INFO) with explicit meanings
- **A dead-code rule** — before assigning CRITICAL/HIGH, verify the vulnerable path has
  production callers (grep excluding tests). Callers only in tests → downgrade to MEDIUM.
  This alone killed a lot of inflated severities.
- **Positive controls as `INFO` findings** rather than a separate section, so every
  observation lives in one place
- **Effort labels** (Tiny → XL) so the remediation table is actually plannable
- **Mandatory source citation** — no citation, no external claim
- **A key-files reference table** so engineers can navigate to the fix

---

## How they chain

```
  <domain>-audit  ──▶  audit-fact-checker  ──▶  audit-consolidation-validator
  (produce report)     (verify findings,        (validate the client-facing
                        kill false positives)     doc against internals)
                              │                          │
                              └──── audit-finding-verifier ────┘
                                    (subagent, one per finding)
```

`db-scalability-audit` hands off to `db-migration-planner` when a migration is warranted.

The fact-checking stage matters more than it sounds: an LLM audit will confidently report
findings that don't survive contact with the code. Verifying each finding with a
fresh-context subagent — one that only has `Read` and `Bash` and is asked to *refute* —
was the difference between a deliverable and a liability.

---

## Meta-skills — experimental, low confidence

| Skill | Target |
|---|---|
| [`meta-skill-hipaa-audit-improver`](../../.claude/skills/meta-skill-hipaa-audit-improver/) | `hipaa-audit/references/` |
| [`meta-skill-security-audit-improver`](../../.claude/skills/meta-skill-security-audit-improver/) | `security-audit/references/` |
| [`meta-skill-db-scalability-audit-improver`](../../.claude/skills/meta-skill-db-scalability-audit-improver/) | `db-scalability-audit/references/` |

The idea: the reference docs the audit skills lean on (OWASP cheat sheets, eCFR text, HHS
enforcement cases, provider limits) **go stale**, and that staleness is invisible until an
audit cites something wrong. These skills re-fetch from an allowlisted set of
authoritative domains, refresh the reference files, and write an `update-log.md`.

**Caveat, stated plainly: I've run each of these about twice.** There's no benchmark
behind them and I can't tell you they're worth the maintenance. The *problem* they target
is real and any curated set will hit it; whether this is the right shape of solution is
genuinely open. Treat as a prompt for discussion, not a recommendation.

---

## Install

Each skill is a self-contained directory under `.claude/skills/`. To use one, copy it into
your Claude config, plus its dependencies:

```bash
# from a clone of this repo
cp -R .claude/skills/hipaa-audit                 ~/.claude/skills/
cp -R .claude/skills/security-audit              ~/.claude/skills/
cp -R .claude/skills/db-scalability-audit        ~/.claude/skills/
cp -R .claude/skills/code-health                 ~/.claude/skills/
cp -R .claude/skills/audit-fact-checker          ~/.claude/skills/
cp -R .claude/skills/audit-consolidation-validator ~/.claude/skills/
cp -R .claude/skills/db-migration-planner        ~/.claude/skills/

# required dependencies
cp    .claude/agents/audit-finding-verifier.md   ~/.claude/agents/
cp    .claude/guidelines/templates/audit-template.md ~/.claude/guidelines/templates/
```

**Minimum per skill:**
- Any report-producing audit (`hipaa`, `security`, `db-scalability`) needs
  `guidelines/templates/audit-template.md` at that path — the reference resolves relative
  to your Claude config root.
- `audit-fact-checker` and `audit-consolidation-validator` need
  `agents/audit-finding-verifier.md`.

> **Do not edit copies** — the canonical source is `.claude/skills/` in this repo.
