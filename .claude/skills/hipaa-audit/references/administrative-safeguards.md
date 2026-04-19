# Administrative Safeguards Reference

Code-auditable requirements extracted from 45 CFR § 164.308. This file covers only the
administrative safeguard standards and implementation specifications that have direct
implications for code, system design, or configuration review.

Source: 45 CFR § 164.308 — Administrative Safeguards
https://www.law.cornell.edu/cfr/text/45/164.308

---

## Overview of § 164.308 Structure

§ 164.308 defines administrative safeguards as "administrative actions, and policies and
procedures, to manage the selection, development, implementation, and maintenance of security
measures to protect ePHI and to manage the conduct of the covered entity's or business
associate's workforce."

Standards covered here (selected for code-audit relevance):

| § | Standard | Required / Addressable |
|---|---|---|
| (a)(1) | Security Management Process | Required (risk analysis, risk mgmt, sanction policy, activity review) |
| (a)(4) | Information Access Management | Mixed (see below) |
| (a)(5) | Security Awareness and Training | Required standard; all specs Addressable |
| (a)(6) | Security Incident Procedures | Required |
| (a)(7) | Contingency Plan | Mixed (see below) |
| (a)(8) | Evaluation | Required |

---

## § 164.308(a)(1) — Security Management Process

**Standard:** Required. Implement policies and procedures to prevent, detect, contain, and
correct security violations.

### Implementation Specifications

| Spec | Designation | What it requires |
|---|---|---|
| Risk Analysis | Required | Accurate and thorough assessment of risks/vulnerabilities to ePHI confidentiality, integrity, availability |
| Risk Management | Required | Implement security measures to reduce risks to a reasonable and appropriate level |
| Sanction Policy | Required | Apply appropriate sanctions against workforce members who fail to comply |
| Information System Activity Review | Required | Implement procedures to regularly review records of information system activity (audit logs, access reports, security incident reports) |

### Code-audit implications

**Risk analysis** is a document-level requirement, but a complete risk analysis must enumerate
specific systems. If the system you are auditing is not in scope of an existing risk analysis,
flag it — uncovered systems are themselves a finding. Confirm with the team.

**Information system activity review** is the administrative counterpart to § 164.312(b)
(Audit Controls). Audit logs must exist AND be reviewed. A log that is never reviewed satisfies
neither requirement. The Montefiore Medical Center case ($4.75M, 2024) demonstrates that
failing to review audit logs allows insider threats to persist for years undetected.

**How to check:**
- Does an audit log exist for ePHI access? (§ 164.312(b) check)
- Is there evidence in the codebase or configuration of scheduled log review? (alert rules,
  SIEM config, monitoring dashboards covering ePHI access)
- Is there anomaly detection — e.g., alerts when a user accesses records outside their normal
  patient panel, or accesses an unusually high volume of records?

---

## § 164.308(a)(4) — Information Access Management

**Standard:** Required. Implement policies and procedures for authorizing access to ePHI that
are consistent with the applicable requirements of the Privacy Rule.

### Implementation Specifications

| Spec | Designation | What it requires |
|---|---|---|
| Isolating clearinghouse functions | Required (if applicable) | Health care clearinghouses must isolate their functions from the rest of the organization |
| Access Authorization | Addressable | Policies and procedures for granting access to ePHI — e.g., by workstation, transaction, program, or process |
| Access Establishment and Modification | Addressable | Policies to establish, document, review, and modify a user's right of access |

**Note on Addressable:** Both Access Authorization and Access Establishment and Modification are
addressable — but the BayCare Health System settlement ($800,000, 2024) demonstrates that OCR
will pursue enforcement when access authorization policies are not implemented or enforced. The
"addressable" designation does not make these optional in practice.

### Code-audit implications

**Access Authorization** → Every ePHI access should require a prior authorization decision. In
code, this means role-based access control (RBAC) or attribute-based access control (ABAC) is
applied at the data layer, not just at the UI layer.

**Access Establishment and Modification** → User provisioning and deprovisioning flows. When a
staff member changes roles or leaves the organization, is their ePHI access updated or revoked?
Over-provisioned accounts (accounts with more access than the job function requires) violate
both this standard and the minimum necessary principle (§ 164.502(b)).

### How to check in code

```
1. Find all routes and functions that return or modify ePHI.
2. Verify that each enforces a role or permission check — not just authentication.
3. Find the user provisioning/deprovisioning flow:
   - Is there a function to disable/remove a user's ePHI access?
   - Is it called when employment terminates?
4. Find the role assignment logic — can a user self-escalate roles?
   Or does role assignment require an admin action with an audit trail?
5. Check for over-broad roles: does a billing role have access to clinical notes?
   Does a read-only role have write access?
6. Grep for any "super user", "bypass", or "admin override" code paths that skip
   access checks — flag each one.
```

**Minimum necessary linkage:** Access authorization must be consistent with the minimum
necessary standard (§ 164.502(b) / § 164.514(d)). A final rule requirement is that covered
entities must establish policies that identify the *types* of persons who have access to
*designated categories* of information — meaning role-level access categorization, not
individual per-record decisions. See `violation-patterns.md` section 7 for API design
implications.

---

## § 164.308(a)(6) — Security Incident Procedures

**Standard:** Required. Implement policies and procedures to address security incidents.

### Implementation Specification

| Spec | Designation | What it requires |
|---|---|---|
| Response and Reporting | Required | Identify and respond to suspected or known security incidents; mitigate harmful effects to the extent practicable; document security incidents and their outcomes |

### Code-audit implications

Security incidents must be **identified** (requires monitoring/detection), **responded to**
(requires a process), **mitigated** (requires incident response capability), and **documented**
(requires an incident log that is separate from general application logs).

In code, "identification" depends on the audit controls in § 164.312(b). If audit logs don't
exist or aren't reviewed, security incidents cannot be identified — which cascades into a
§ 164.308(a)(6) violation.

"Documentation" requires that incidents be recorded with their outcomes — not just that they
occurred. This means an incident record must include: what happened, when it was detected, what
ePHI was affected, what remediation was taken, and the outcome.

### How to check in code

```
1. Is there an incident logging mechanism separate from application error logs?
   (Application error logs are not incident records — they capture runtime errors,
   not the narrative of what happened and how it was resolved.)
2. Does the incident record include: type of incident, systems affected,
   ePHI involved, detection timestamp, response actions, outcome?
3. Is there an alerting path from the audit log to incident response? (e.g., alert
   rules that fire on anomalous ePHI access patterns, failed auth spikes, etc.)
4. Is the incident log stored in a write-once or append-only storage?
   (Same integrity requirement as audit logs)
```

---

## § 164.308(a)(7) — Contingency Plan

**Standard:** Required. Establish and implement policies and procedures for responding to an
emergency or other occurrence (fire, vandalism, system failure, natural disaster) that damages
systems containing ePHI.

### Implementation Specifications

| Spec | Designation | What it requires |
|---|---|---|
| Data Backup Plan | Required | Create and maintain retrievable exact copies of ePHI |
| Disaster Recovery Plan | Required | Establish procedures to restore any loss of ePHI |
| Emergency Mode Operation Plan | Required | Maintain security of ePHI while operating in emergency mode |
| Testing and Revision Procedures | Addressable | Implement procedures for periodic testing and revision of contingency plans |
| Applications and Data Criticality Analysis | Addressable | Assess relative criticality of specific applications and data in support of other contingency plan components |

### Code-audit implications

**Data Backup Plan (Required):** Backups of ePHI must exist and must be retrievable.
Retrievable = tested. An untested backup may not actually restore.

**Disaster Recovery Plan (Required):** A documented procedure for restoring ePHI from backup.
In code review, look for: backup configuration (frequency, retention, storage location), restore
procedures, and evidence the restore process has been tested.

**Ransomware note:** Multiple OCR cases (Comstar, BST & Co., TWRTC, numerous others) involve
ransomware encrypting ePHI. An offline or immutable backup is the technical control that
limits the impact of a ransomware attack. A backup stored on the same network segment as the
primary data is likely to be encrypted along with it.

### How to check in code

```
1. Find backup configuration — what systems are backed up? How often?
   Are backups stored in a separate account, region, or offline location?
2. Is there a backup for every system that stores ePHI?
   Map PHI-bearing tables/services to their backup coverage.
3. Are backups tested (restore drill)? This is not visible in code — flag as INFO
   for human confirmation.
4. Is the backup storage immutable or write-once? (Protects against ransomware
   encrypting or deleting backups.)
5. Is the retention period defined? HIPAA requires 6 years for security documentation;
   best practice is to apply the same to ePHI backups.
6. In emergency mode: are access controls maintained even when running from backup
   infrastructure? Or does emergency mode bypass normal auth?
```

---

## § 164.308(a)(8) — Evaluation

**Standard:** Required. Perform a periodic technical and nontechnical evaluation that establishes
the extent to which the entity's security policies and procedures meet the requirements of
the Security Rule.

**When:** Initially upon implementing the Security Rule; subsequently in response to
environmental or operational changes affecting the security of ePHI.

### Code-audit implications

The Evaluation standard is what makes security audits like this one a HIPAA requirement, not
a best practice. A covered entity that has never commissioned a technical evaluation of its
ePHI systems is not meeting this standard.

Environmental or operational changes that trigger re-evaluation include: new system deployments,
significant software changes, vendor changes, workforce changes, new PHI data types handled.

### How to check

- This is primarily a documentation/process finding — flag as INFO if there is no evidence of
  prior technical evaluations.
- In code: look for `HIPAA*.md`, `compliance*.md`, `security-audit*.md` or similar in the
  repository. Prior audit documents are evidence of prior evaluation.
- Flag if the last evaluation predates a significant system change found in git history.

---

## § 164.308(a)(5) — Security Awareness and Training

**Standard:** Required. Implement a security awareness and training program for all members of
the workforce.

**Implementation Specifications (all Addressable):**
- Security reminders
- Protection from malicious software
- Log-in monitoring
- Password management

### Code-audit implications

Training is a process control, not a code control — but the TWRTC case (2026, phishing attack)
illustrates that technical controls (MFA) and training work together. When a phishing attack
succeeds, it often indicates both a lack of MFA and inadequate phishing awareness training.

In code, "log-in monitoring" (addressable spec under training) and "protection from malicious
software" have technical analogs: login failure alerting, endpoint detection. Flag their absence
as LOW/INFO depending on context.

---

## Quick Reference: § 164.308 Code-Audit Checklist

```
Security Management Process
[ ] Audit log exists for all ePHI access events
[ ] Audit log is reviewed periodically (evidence: alerts, reports, dashboards)
[ ] Anomaly detection on ePHI access patterns

Information Access Management
[ ] Role-based access control enforced at data layer (not just UI)
[ ] User provisioning flow documented and code-verified
[ ] User deprovisioning flow exists and is called on termination/role change
[ ] No self-escalation of roles without admin approval
[ ] Access is scoped to minimum necessary for each role

Security Incident Procedures
[ ] Incident log exists (separate from application error logs)
[ ] Incident records include: type, affected systems, PHI involved, resolution
[ ] Alert path from audit anomaly to incident response exists

Contingency Plan
[ ] Backups exist for all ePHI-bearing systems
[ ] Backups stored in separate location (offline, immutable, or separate account)
[ ] Restore procedure documented and tested
[ ] Backup retention period defined (6+ years recommended)
[ ] Emergency mode maintains access controls

Evaluation
[ ] Prior technical evaluation of ePHI systems exists (check docs/)
[ ] Evaluation was updated after significant system changes
```
