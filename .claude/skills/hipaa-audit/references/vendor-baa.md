# Vendor / BAA Checklist

For each vendor integration found in the codebase, answer these questions:

1. **Does this vendor receive PHI?** (even partial data — email alone, or an order ID that can be correlated back to a patient, counts)
2. **Is there a BAA?** Flag as INFO — you cannot verify this from code, but it must be confirmed by the team.
3. **Is the integration authenticated?** For outbound: are API keys stored securely? For inbound (webhooks): is the signature verified before trusting the payload?
4. **What's the blast radius if the API key is compromised?** Can an attacker query patient records? Download a list?

---

## High-Risk Vendor Categories

### Error Monitoring (CRITICAL to check)
- **Sentry** — check for `beforeSend` hook that scrubs PHI from error events. Patient objects in errors are common.
- **Datadog APM** — check span/trace attributes for PHI. DB query parameters in traces can contain PHI.
- **Rollbar, Bugsnag** — same pattern as Sentry; check for filtering configuration.

### Analytics (HIGH risk)
- **Mixpanel, Segment, Amplitude, Heap** — check every `.track()` / `.identify()` call. Email, name, or health-related properties in event payloads are violations.
- **Google Analytics** — PHI in URL parameters will be captured. Flag any PHI in tracked URLs.
- **Intercom** — often receives email and name for support. Must have BAA if it handles PHI.

### Communication (require BAA)
- **SendGrid, Mailgun, Postmark** — email providers that handle PHI must have a BAA. Check what data is in email bodies/templates.
- **Twilio** — SMS/voice provider. If PHI is sent via SMS, BAA required. Check message templates.
- **Vonage, Bandwidth** — same as Twilio.

### Infrastructure (flag for human review)
- **AWS, GCP, Azure** — major cloud providers offer BAAs. Flag if region or service selection could affect compliance.
- **Cloudflare** — handles TLS termination and may log request details. Check what's logged.
- **Vercel, Railway, Render** — hosting providers with access to environment variables and logs.

### Healthcare-Specific (usually have BAA programs)
- Pharmacy APIs (e.g., Belmar, PioneerRx, Surescripts) — always receive PHI; BAA required.
- Lab APIs (LabCorp, Quest) — always PHI.
- EHR connectors (Epic, Athena, Elation) — always PHI; check OAuth scopes.
- Prior auth services — receive diagnosis and medication data.

### Payment (careful with combination data)
- **Payment processors (Stripe, Braintree, etc.)** — typically do not receive clinical PHI, but any vendor that receives data linkable to a patient's health record may require a BAA. The key question: does the integration pass patient name, diagnosis, medication, or other PHI fields into payment metadata or descriptions? If yes, a BAA is required regardless of the vendor's primary purpose.

---

---

## BAA Program URLs

Direct links to the BAA or HIPAA compliance program pages for major vendors. These should be confirmed with the vendor's current documentation at time of audit, as terms and covered services change.

### Infrastructure

| Vendor | BAA / HIPAA program URL | Notes |
|---|---|---|
| **AWS** | https://aws.amazon.com/compliance/hipaa-compliance/ | BAA available via AWS Artifact in the console. List of HIPAA-eligible services: https://aws.amazon.com/compliance/services-in-scope/HIPAA_BAA/ — only process ePHI on eligible services. |
| **Cloudflare** | https://www.cloudflare.com/trust-hub/compliance-resources/ | BAA only available to Enterprise customers with a minimum spend threshold. Not available on self-serve or Pro/Business plans. Contact enterprise sales. |
| **GCP** | https://cloud.google.com/security/compliance/hipaa | BAA available to all customers who accept the Google Cloud HIPAA BAA in the console. |
| **Azure** | https://learn.microsoft.com/en-us/azure/compliance/offerings/offering-hipaa-us | BAA included in Microsoft Online Services Terms (OST) for eligible services. |

### Communication

| Vendor | BAA / HIPAA program URL | Notes |
|---|---|---|
| **Twilio (voice/SMS/video)** | https://www.twilio.com/en-us/hipaa | BAA available on Security Edition or Enterprise Edition only. Covered services: Programmable SMS, Voice, Video, SIP, and runtime tools. Not all Twilio products are covered — verify each service used. |
| **Twilio SendGrid (email)** | https://www.twilio.com/docs/sendgrid/ui/account-and-settings/hipaa-compliant | SendGrid does NOT sign a BAA and is not HIPAA compliant for ePHI transmission. Do not send ePHI via SendGrid. Use an alternative HIPAA-compliant email provider if email must contain PHI — see HIPAA-compliant email alternatives below. |
| **Mailgun** | Contact Mailgun enterprise sales | Mailgun offers BAAs for enterprise customers. Verify coverage before transmitting ePHI. |
| **Paubox** | https://www.paubox.com/hipaa | BAA available; verify current scope and terms at the link. Designed specifically for healthcare; encrypts email end-to-end without requiring the recipient to use a portal. Confirm BAA coverage before transmitting ePHI. |
| **AWS SES** | https://aws.amazon.com/compliance/hipaa-compliance/ | AWS SES is a HIPAA-eligible service under the AWS BAA (sign via AWS Artifact). Requires the organization to already have an AWS BAA in place. |

### Payment

Payment processors generally do not have documented BAA programs because they are not designed to handle PHI. If the integration passes PHI (including patient name, DOB, or clinical data in metadata fields), the team must contact the vendor's legal team to arrange a BAA or redesign the integration to exclude PHI.

### Healthcare-Specific

| Vendor | Notes |
|---|---|
| Pharmacy APIs (Belmar, PioneerRx, Surescripts) | These vendors are healthcare-specific and routinely handle ePHI. BAA should already be in place per their standard contracts. Verify. |
| EHR connectors (Epic, Athena, Elation) | Standard BAA in vendor contracts. Confirm scope covers the specific integration (OAuth scopes, HL7/FHIR endpoints). |
| Lab APIs (LabCorp, Quest) | BAA in standard contracts. Verify coverage for API integrations specifically, not just the broader service agreement. |

### NIST SP 800-66r2 Reference

NIST SP 800-66 Rev. 2 (February 2024) provides implementation guidance for the HIPAA Security Rule including mappings to NIST SP 800-53r5 controls and NIST Cybersecurity Framework subcategories.
- PDF: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-66r2.pdf
- DOI: https://doi.org/10.6028/NIST.SP.800-66r2
- Interactive CPRT: https://csrc.nist.gov/Projects/cprt/catalog#/cprt/framework/version/SP800_66_2_0_0/home

---

## How to Find Vendor Integrations in Code

```bash
# Find HTTP client usage
grep -r "fetch(" --include="*.ts" --include="*.js" -l
grep -r "axios" --include="*.ts" --include="*.js" -l

# Find SDK instantiations
grep -rE "new (Sentry|Datadog|Mixpanel|Segment|Twilio|SendGrid|Stripe)" --include="*.ts" -l

# Find API key env vars
grep -rE "(API_KEY|API_SECRET|WEBHOOK_SECRET|AUTH_TOKEN)" .env* --include="*.env*"
grep -rE "process\.env\.(.*)(KEY|SECRET|TOKEN)" --include="*.ts" -l
```

For each match, trace what data flows to that vendor.
