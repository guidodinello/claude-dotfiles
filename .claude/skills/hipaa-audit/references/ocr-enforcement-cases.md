# OCR Enforcement Cases

Real-world resolution agreements from HHS Office for Civil Rights (OCR). Each case maps the
technical failure to the violated CFR section, showing what the breach actually was and what
remediation was required.

Source: https://www.hhs.gov/hipaa/for-professionals/compliance-enforcement/agreements/index.html

---

## Pattern Summary

Failure to conduct an accurate and thorough risk analysis (§ 164.308(a)(1)(ii)(A)) appears in
virtually every settlement. It is the most common basis for OCR enforcement action. A stale or
missing risk analysis is not a documentation problem — it is the technical predicate OCR uses to
establish that all downstream failures were foreseeable and unaddressed.

Second most common: failure to review information system activity logs (§ 164.308(a)(1)(ii)(D))
— meaning audit logs either did not exist, were not reviewed, or were insufficient to detect
intrusion or insider misuse.

---

## Cases (2021–2026, reverse chronological)

---

### Top of the World Ranch Treatment Center (TWRTC)
**Date:** February 19, 2026
**Settlement:** $103,000 + 2-year corrective action plan (CAP)
**Entity type:** Substance use disorder treatment provider (Illinois)
**Individuals affected:** 1,980

**What happened:** An unauthorized third party accessed ePHI through a workforce member's email
account following a successful phishing attack. Reported to OCR via breach notification filed
March 2023.

**HIPAA violations found:**
- Failed to conduct an accurate and thorough risk analysis (§ 164.308(a)(1)(ii)(A))

**Technical failure:** Workforce member email account had no MFA or equivalent control; phishing
attack succeeded and went undetected until after the breach. No evidence of a risk analysis that
would have identified email account takeover as a foreseeable risk vector.

**CAP required:**
- Complete an accurate and thorough risk analysis
- Develop and implement a risk management plan
- Develop/maintain written HIPAA policies and procedures
- Annual HIPAA workforce training

**Auditor takeaway:** Email accounts of any workforce member who can access ePHI must be covered
in the risk analysis. MFA on email is a foreseeable control gap. Phishing simulation and training
are not sufficient without technical controls.

---

### Deer Oaks — The Behavioral Health Solution
**Date:** July 2025
**Settlement:** $225,000 + 2-year CAP
**Entity type:** Behavioral health provider
**Rule:** HIPAA Privacy Rule and Security Rule

**What happened:** OCR investigation resolved potential violations of both Privacy and Security
Rules.

**HIPAA violations found:**
- Failed to conduct an accurate and thorough risk analysis (§ 164.308(a)(1)(ii)(A))

**Technical failure:** No adequate risk analysis existed to identify risks and vulnerabilities to
the ePHI held by the organization.

**CAP required:** Corrective action plan monitored for two years.

**Auditor takeaway:** Privacy Rule and Security Rule violations often travel together. An
inadequate risk analysis affects both because the Privacy Rule's administrative requirements and
the Security Rule's administrative safeguards draw on the same foundational risk assessment.

---

### Northeast Radiology (NERAD)
**Date:** April 2025
**Settlement:** $350,000 + 2-year CAP
**Entity type:** Professional corporation providing clinical services at medical imaging centers
(New York, Connecticut)

**What happened:** OCR initiated investigation into HIPAA Security Rule violations.

**HIPAA violations found:**
- Failed to conduct an accurate and thorough risk analysis (§ 164.308(a)(1)(ii)(A))

**Technical failure:** Risk analysis for ePHI systems was absent or insufficient to identify
potential risks and vulnerabilities across information systems.

**CAP required:** Corrective action plan monitored for two years.

**Auditor takeaway:** Imaging and radiology practices often have ePHI in PACS systems and
DICOM storage that are outside the scope of their general IT risk analysis. Scope your risk
analysis to include all systems that store, process, or transmit ePHI — including legacy imaging
infrastructure.

---

### Comstar, LLC
**Date:** May 30, 2025
**Settlement:** $75,000 + 2-year CAP
**Entity type:** Business associate — provides billing, collection, and related services to
emergency ambulance services (Massachusetts)
**Individuals affected:** 585,621

**What happened:** On March 19, 2022, an unknown actor gained unauthorized access to Comstar's
network servers. Comstar did not detect the intrusion until March 26, 2022 (seven days later).
Ransomware was used to encrypt the network servers and the ePHI of ~585,621 individuals.
Breach notification filed May 26, 2022.

**HIPAA violations found:**
- Failed to conduct an accurate and thorough risk analysis (§ 164.308(a)(1)(ii)(A))

**Technical failure:** No adequate risk analysis; the seven-day gap between intrusion and
detection suggests absence of network activity monitoring or intrusion detection controls.
Ransomware encrypted ePHI — no evidence of controls to detect unauthorized access before
encryption completed.

**CAP required:** Corrective action plan monitored for two years.

**Auditor takeaway:** Business associates are directly liable under HIPAA. A BA that lacks a
risk analysis for the ePHI systems it operates on behalf of covered entities faces the same
enforcement exposure as those covered entities. Intrusion detection lag is itself evidence of
missing information system activity review (§ 164.308(a)(1)(ii)(D)).

---

### Montefiore Medical Center
**Date:** February 6, 2024
**Settlement:** $4,750,000 + 2-year CAP
**Entity type:** Non-profit hospital system (New York City)

**What happened:** A malicious insider (employee) accessed and stole patient PHI over an
extended period. OCR's investigation revealed that Montefiore was unable to prevent or even
detect the attack until years after it occurred.

**HIPAA violations found:**
- Failed to analyze and identify potential risks and vulnerabilities to PHI
  (§ 164.308(a)(1)(ii)(A))
- Failed to monitor and safeguard information systems' activity
  (§ 164.308(a)(1)(ii)(D) — information system activity review)
- Failed to implement policies and procedures to record and examine activity in information
  systems containing or using PHI (§ 164.312(b) — Audit Controls)

**Technical failure:** No audit controls that would detect insider access anomalies. No
information system activity review process. Years passed between the insider's first unauthorized
access and its detection — demonstrating that audit logs either did not exist or were never
reviewed.

**CAP required:**
- Workforce training on HIPAA policies and procedures
- OCR monitoring for two years

**Auditor takeaway:** This is the canonical insider threat case. The $4.75M penalty reflects
simultaneous failures of risk analysis, audit controls, and activity monitoring. An audit log
that is never reviewed provides no protection. Automated anomaly detection (e.g., alert when
a user accesses records outside their normal patient panel) is the control that would have
caught this earlier.

---

### BayCare Health System
**Date:** 2024
**Settlement:** $800,000 + 2-year CAP
**Entity type:** Florida health care provider
**Trigger:** Complaint received concerning impermissible access to a complainant's ePHI

**HIPAA violations found:**
- Failed to implement policies and procedures for authorizing access to ePHI consistent with
  the Privacy Rule (§ 164.308(a)(4)(ii)(A) — Access Authorization)
- Failed to reduce risks and vulnerabilities to ePHI to a reasonable and appropriate level
  (§ 164.308(a)(1)(ii)(B) — Risk Management)
- Failed to regularly review records of information system activity
  (§ 164.308(a)(1)(ii)(D) — Information System Activity Review)

**Technical failure:** Access authorization policies not implemented or enforced — a user was
able to access a patient's ePHI without authorization. Activity logs not regularly reviewed —
the impermissible access was detected via complaint, not internal monitoring.

**CAP required:** Corrective action plan monitored for two years.

**Auditor takeaway:** This case directly pairs access authorization failures with audit log
review failures. Access logs that are never reviewed don't catch unauthorized access until a
patient complains. Both controls must exist and both must be operative.

---

### BST & Co. CPAs, LLP
**Date:** Settlement announced post-2020 (breach report filed February 16, 2020)
**Settlement:** Paid to OCR + 2-year CAP
**Entity type:** Business associate — public accounting and management consulting firm (New York)
**Incident date:** December 7, 2019 (ransomware discovered)

**What happened:** BST discovered part of its network was infected with ransomware on December 7,
2019, affecting the PHI of its covered entity client.

**HIPAA violations found:**
- Failed to conduct an accurate and thorough risk analysis to determine the potential risks and
  vulnerabilities to the confidentiality, integrity, and availability of ePHI
  (§ 164.308(a)(1)(ii)(A))

**Technical failure:** No adequate risk analysis; ransomware succeeded because risks were not
identified and mitigated in advance.

**CAP required:**
- Augment existing HIPAA and security training program
- Provide annual training for all workforce members with access to PHI

**Auditor takeaway:** Ransomware is a foreseeable risk. A risk analysis that does not identify
ransomware as a risk to ePHI confidentiality and availability is inadequate. Business associates
face direct enforcement without needing to go through the covered entity.

---

## Common Corrective Action Plan Requirements

Across nearly all settlements, OCR requires:

1. **Accurate and thorough risk analysis** — covering all ePHI systems, documenting threats,
   vulnerabilities, likelihood, and impact
2. **Risk management plan** — documenting how identified risks will be mitigated to a reasonable
   and appropriate level
3. **Written HIPAA policies and procedures** — developed, maintained, and revised
4. **Annual workforce training** — on HIPAA policies, procedures, and individual role
   responsibilities
5. **OCR monitoring** — typically two years of oversight

## Technical Controls Implicitly Validated by Enforcement

The pattern of these cases validates the following as controls OCR expects to exist in ePHI
systems:

| Control | CFR Basis | Why it matters |
|---|---|---|
| Risk analysis covering all ePHI systems | § 164.308(a)(1)(ii)(A) | Absent in virtually every case |
| Information system activity review (log review) | § 164.308(a)(1)(ii)(D) | Absent in insider and access violation cases |
| Audit controls (ePHI access logs) | § 164.312(b) | Absent in Montefiore; required to detect access |
| Access authorization enforcement | § 164.308(a)(4)(ii)(A) | BayCare — policies not enforced |
| MFA or equivalent on email accounts | § 164.308(a)(1) (risk management) | TWRTC — phishing succeeded due to absence |
| Intrusion detection / anomaly alerting | § 164.308(a)(1)(ii)(D) | Comstar — 7-day gap before detection |
