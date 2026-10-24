# Platform evidence

## Replit public deployment

**Live Prototype URL: [https://wheat-assistant.replit.app](https://wheat-assistant.replit.app)**

**Standalone reviewer attachment: [SDC2026_FamilyGuy_Replit_POU.pdf](replit_pou/SDC2026_FamilyGuy_Replit_POU.pdf)**

This one-page POU attachment repeats the public deployment URL and the minimum Replit use and verification facts, so a reviewer can identify the proof without interpreting the full evidence index.

This is the project's public interactive prototype; a Replit login is not required. The recorded organizer proof options allow a live Replit deployment URL, an accessible project-history link, or a credit-finished screenshot. The live deployment URL is the selected proof option here; there is no need to spend the remaining credits just to create a screenshot. The logged-in portal shows the existing repository submission with the correct GitHub link, **Your submission**, **API integration confirmed** and **Edit**; it displays no receipt number or exact submission time, so none is invented. Do not duplicate the existing submission.

The deployment acceptance on **2026-10-24 MYT** recorded the following for the real production deployment:

- Three synthetic weekly flows, with input / included / excluded / duplicate / exception counts of `36 / 24 / 3 / 3 / 6`, `39 / 24 / 6 / 3 / 6` and `24 / 24 / 0 / 0 / 0`.
- Human rule approvals, eight-sheet Excel downloads and explicitly simulated Orbyte task creation.
- Persistence across an actual redeployment: old inputs and three downloads retained identical SHA-256 values; another browser workspace could not access those records.
- Replit Reserved VM hosting with managed PostgreSQL for records and immutable file bytes; no provider model requests were made during that deployment acceptance.

**Final publication and public probe (2026-10-25 MYT).** Replit's Published record is `a37ccc68` with five successful stages, Current status **Live**, visibility **Public**, URL [https://wheat-assistant.replit.app](https://wheat-assistant.replit.app), and configuration Asia/0.5 vCPU/2 GiB. The deployment used the verified 60-file ZIP `031c44091097316047d887dad9ac103e3caa3ff1286522ca954ef6be1ccee013` (62 entries); its runtime manifest is `d8871eb76a49f93019e5dd0cd4aa1a13e0b20e49a19ef34486b62c7b0928fa21` (28 files) and its planner SHA-256 is `8d1a9137029ff70d2f0c482f3ec854f73e6911fb31d3c283efd35ba22428cf0c`. No plan, credit or Secret was changed. The interface's existing free Agent scan still shows 0 issues; this batch did not run a new scan and does not claim a new full security review.

An independent anonymous HTTP probe created its own workspace (no browser cookie), ran the three synthetic weeks, approved all six rule groups each week, exported and reopened all eight worksheets, checked the exact XLSX MIME type, proved second-session isolation, and rejected wrong-origin, missing-CSRF-header and cross-site requests. Result: **200 checks passed, 61 HTTP requests, zero provider calls**. Workbook SHA-256 values were `97db40275e3e602c235fcdf3cfd60cf34832db4c7a76df394223e4990204fb36`, `7fbbe711eeb6b860939460ac99606f236c167228c82a4c68bb462a1ad84e26d5` and `1859440a077bde5c3c2c9fb9bb6a053212e34f3da24a660059fc1793a59d8166`.

These 2026-10-24 results describe the prior build. The live build is now release `a37ccc68`, and the 2026-10-25 probe above is its current-build verification. The earlier redeployment/persistence test remains a prior-build result and was not repeated here. [Deployment and reproduction instructions](../../../docs/deployment/REPLIT_DEPLOYMENT.md) describe the runtime and its limits. Model configuration does not establish model quality.

## Original Replit-developed module

[REPLIT_MODULE.json](REPLIT_MODULE.json) is the original sanitized provenance record for `backend/wheat_assistant/status_guard.py`, developed in a real Replit Starter / Free project on **2026-10-21 MYT** and integrated unchanged. Its historical project name is preserved for accurate attribution. The source hash in that record can be compared with the current module. It supports the development history; it is not the completed Technical & Tools Declaration.

If the official template additionally requires screenshots or account fields, add only reviewed evidence here. Preserve required project/runtime facts and remove unrelated personal identity, other projects, billing details, credentials and local paths. Raw account logs, private keys and unreviewed screenshots are not evidence for public upload.
