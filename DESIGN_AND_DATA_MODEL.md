# Miraflores — Evidence Graph Workpaper

## Core idea
A tax workpaper should be a navigable **chain of proof**, not a grid of numbers. A reviewer begins with a return line or an exception and can traverse upstream to computation inputs, extracted fields, and the precise simulated source-document page. Every human judgment lives beside the evidence that justified it. Corrections and new documents trigger fresh review, without erasing previous decisions.

## Data model
- **Case:** household, filing period, jurisdiction, firm, and roles.
- **Documents / Pages:** 74 immutable document records, with issuer, dates, correction status, and `printed_content` used for simulated source rendering.
- **Extracted values:** 3,012 field-level evidence records keyed by `ev-NNNN`, linked to document ID, page, field label, original text, and extraction confidence.
- **Return versions and lines:** v1, v2, and v3 computed snapshots. Each line contains a stable key, value, jurisdiction, rule, `inputs` for upstream calculations, and `sources` for source links.
- **Exceptions / decisions:** independently derived controls, severity, source document, assignee, status, user reason, author, timestamp. Decisions never silently replace extracted facts.
- **Review actions / sign-offs:** actor role, action, affected object, timestamp, version; changes reopen sign-offs.
- **Scenarios:** supplied `what_if.alternatives` only; no unsanctioned recomputation is claimed.

## UX and workflow
1. **Overview:** high-signal triage, open critical issues, and computation snapshot.
2. **Lineage explorer:** searchable line → calculation rule → upstream lines → extracted values → simulated page.
3. **Evidence library:** page rendering, extracted fields, confidence, and reverse links to the return.
4. **Exceptions:** independent checks for corrected and duplicate documents, conflicting IDs, and book-to-tax questions. Reviewers document rationale before resolution.
5. **Versions / scenarios:** cross-version line differences and reference-provided what-if tax effects.
6. **People / filing:** role switcher, staged sign-offs blocked by open critical exceptions, case timeline.

## Technical choices and honest limitations
The artifact is a self-contained static web prototype with embedded case JSON and browser `localStorage` persistence. This supports immediate offline exploration with no account setup. It is **not** a production collaborative backend: authorization is a demo role gate; edit/audit state is local and not tamper-proof; there is no true multi-user synchronization, server-side encryption, notification delivery, new file upload or e-filing integration. Real deployment would use a relational store with append-only event history, server-side RBAC, privacy-safe audit logs, object storage for source documents, and a calculation engine with event-driven invalidation and reconciliation. A hosted URL and recorded walkthrough remain to be created.

## AI use disclosure
AI assistance was used to interpret the case requirements, build the static prototype, design review workflows, and identify candidate anomalies. Every tax judgment requires professional verification; exception flags are not assertions of final tax liability.
