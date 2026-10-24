# Platform evidence

## Replit public deployment

**Live Prototype URL: [https://wheat-assistant.replit.app](https://wheat-assistant.replit.app)**

This is the project's public interactive prototype; a Replit login is not required. The recorded organizer proof options allow a live Replit deployment URL, an accessible project-history link, or a credit-finished screenshot. The live deployment URL is the selected proof option here; there is no need to spend the remaining credits just to create a screenshot. Actual official template fields still require checking.

The deployment acceptance on **2026-10-24 MYT** recorded the following for the real production deployment:

- Three synthetic weekly flows, with input / included / excluded / duplicate / exception counts of `36 / 24 / 3 / 3 / 6`, `39 / 24 / 6 / 3 / 6` and `24 / 24 / 0 / 0 / 0`.
- Human rule approvals, eight-sheet Excel downloads and explicitly simulated Orbyte task creation.
- Persistence across an actual redeployment: old inputs and three downloads retained identical SHA-256 values; another browser workspace could not access those records.
- Replit Reserved VM hosting with managed PostgreSQL for records and immutable file bytes; no provider model requests were made during that deployment acceptance.

These are the prior deployment acceptance results. During this repository review on 2026-10-24, read-only requests to `/` and `/healthz` both returned HTTP 200 with the expected app shell / healthy response; the full public three-week journey was not repeated. [Deployment and reproduction instructions](../../../docs/deployment/REPLIT_DEPLOYMENT.md) describe the runtime and its limits. Model configuration does not establish model quality.

## Original Replit-developed module

[REPLIT_MODULE.json](REPLIT_MODULE.json) is the original sanitized provenance record for `backend/wheat_assistant/status_guard.py`, developed in a real Replit Starter / Free project on **2026-10-21 MYT** and integrated unchanged. Its historical project name is preserved for accurate attribution. The source hash in that record can be compared with the current module. It supports the development history; it is not the completed Technical & Tools Declaration.

If the official template additionally requires screenshots or account fields, add only reviewed evidence here. Preserve required project/runtime facts and remove unrelated personal identity, other projects, billing details, credentials and local paths. Raw account logs, private keys and unreviewed screenshots are not evidence for public upload.
