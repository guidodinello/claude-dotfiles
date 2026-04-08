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
- **Stripe** — does not receive PHI directly, but linking payment records to patient IDs creates a combined record that may be PHI. Stripe has a BAA program.

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
