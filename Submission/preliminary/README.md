# Preliminary submission checklist / 初赛材料与缺项

Reviewed through **2026-10-25 MYT**, including the final PDF corrections and supplied video URL. All six deliverable types have a local file or URL, and the final six-document/two-PDF batch is pushed to public main. Deadline: **2026-10-25 07:59:59 MYT (UTC+8)**. The earlier three attachment versions were not filed in this repository and are superseded by these revised inputs.

## Materials now present

| Material | File and status |
|---|---|
| Team name | **Family Guy**, consistent in both revised PDFs and the revised deck. The approved official identity fields remain in the PDFs. |
| Combined preliminary proposal / PRD | [SDC2026_FamilyGuy_Preliminary.pdf](SDC2026_FamilyGuy_Preliminary.pdf), 11 pages; the local copy now includes the requested contact, implemented-stack and licence/tool corrections. It follows the supplied template's single-PDF naming; no separate `PRD.pdf` is required. |
| Technical & Tools Declaration | [SDC2026_FamilyGuy_TechDeclaration.pdf](SDC2026_FamilyGuy_TechDeclaration.pdf), 13 pages; the local copy now includes the deadline, Python/VM details, dependency/licence table, current validation status and the corrected p9 Replit Agent scope. |
| Pitch deck | [Pitch_Deck.pptx](Pitch_Deck.pptx), 12 slides, with the requested storage correction on slide 8 and its speaker note. |
| Public prototype and Replit proof | [Live prototype](https://wheat-assistant.replit.app), [evidence index](evidence/README.md) and [standalone Replit POU](evidence/replit_pou/SDC2026_FamilyGuy_Replit_POU.pdf). The app loaded in a signed-out browser, showed its independent cloud workspace / configured API, and `/healthz` returned `{"status":"ok"}` during this review. |
| Source repository and run instructions | [Public GitHub repository](https://github.com/Family-Guy-XMUM/wheat_assistant), [source setup](../../README.md), [Apache-2.0 license](../../LICENSE), backend/frontend source and dependency locks are present. The final documentation/material status commit is pushed to public main; runtime code and the three formal materials are unchanged by that commit. |
| Pitch video | [Wheat Assistant by Family Guy](https://youtu.be/Fh8PB-QlRbw), displayed duration **7:00**. Signed-out playback and an actual prototype-demo segment were sampled. The video is **Public**; a fresh signed-out watch page was checked. |

Both supplied PDFs visibly contain signature images and the date 2026/10/24. This task does not authenticate signatures. The requested PDF corrections are now in the final local copies; all non-target pages and the signature pages are pixel-identical after the corrections. The existing signature images are preserved; this batch does not impose a new approval gate or claim that a signature authenticates the revised text.

## Remaining before official submission

| Item | Concrete next step |
|---|---|
| Proposal consistency | Completed: the proposal now uses CSV / openpyxl, cloud PostgreSQL and local SQLite, with the corrected licence and tool declarations. The existing signature image is preserved; no signature authentication is claimed. |
| Declaration completeness | Completed: the declaration now includes the submission deadline, Python/VM details, dependency/licence table and current validation status; the p9 Replit Agent row attributes only Status Guard development, correction and testing. The existing signature image is preserved; no signature authentication is claimed. |
| Final source / material version | Public main contains the final six-document/two-PDF status commit after `43d1fd3` (two-parent merge of `8d42152` and `9f20677`; tree identical to `8d42152`). Runtime code and the three formal materials are unchanged by that documentation commit. Live Replit release `a37ccc68` was published from the verified 60-file package; runtime manifest `d8871eb76a49f93019e5dd0cd4aa1a13e0b20e49a19ef34486b62c7b0928fa21`, planner `8d1a9137029ff70d2f0c482f3ec854f73e6911fb31d3c283efd35ba22428cf0c`. The pre-publication ZIP `031c...e013` contains the runtime and three materials, not the final six Markdown bytes. |
| Portal and cross-device access | The logged-in portal shows the existing repository submission with the correct GitHub link, **Your submission**, **API integration confirmed** and **Edit**. No exact submission time or receipt number is displayed, and none is invented here. Do not duplicate the existing submission; a separate-device link/access check remains prudent. |

The revised files resolve the earlier team-name mismatch and the claim that Replit hosting was only a future plan. The verified repair code is included in main's `43d1fd3` merge tree and live release `a37ccc68`; the earlier Windows/model-quality failures remain recorded. The 30% time-saving target remains an explicit planning target, not a measured customer result.

## Verification and declaration items still open

These are separate from the six deliverables; the project requirements do not make a Windows executable an additional seventh deliverable.

| Item | Current boundary / next step |
|---|---|
| Windows v0.2.1 | The [latest CI](https://github.com/Family-Guy-XMUM/wheat_assistant/actions/runs/40106221040) at `9f20677` completed successfully on Windows and macOS. Recorded Windows evidence: 178 tests, all eight automatic stages, source/native three-week journeys, restarts / graceful stops, and 8.774-second export median within the unchanged 10-second target. Separate human launch, Ctrl+C and Excel checks remain pending. `9f20677` is the second parent of `43d1fd3`; the tree is identical to `8d42152` and contains the verified code. Live release `a37ccc68` was published from the verified 60-file package. See [the Windows handoff](../../docs/validation/WINDOWS_VALIDATION.md); historical failures remain recorded. |
| Live-model quality | The repair batch used 13 of 14 authorized requests in total. Its final six synthetic cases passed on their first attempts in three subsets with identical planner / fixture hashes; prior 12-request and diagnostic failures remain recorded. Six cases are bounded evidence. The planner code is included in main's `43d1fd3` tree and live release `a37ccc68` (planner `8d1a9137029ff70d2f0c482f3ec854f73e6911fb31d3c283efd35ba22428cf0c`). The 2026-10-25 public probe made no provider calls; deterministic editable setup remains usable. See [acceptance evidence](../../docs/validation/ACCEPTANCE.md). |
| RunPod applicability | No team-run GPU training/fine-tuning or RunPod job is recorded. The sponsor requirement's application to hosted third-party inference APIs is still unconfirmed. Check the actual requirement before finalizing the declaration and do not invent platform proof. |
| Replit evidence | The public live deployment is Replit release `a37ccc68` (five stages succeeded; Current status Live, Public; Asia/0.5 vCPU/2 GiB). It is the selected proof option; an additional account screenshot is not automatically required. See [evidence](evidence/README.md). |
| Privacy | The existing Git history retains 8 commits with personal author identity and 6 with tool identity; this batch only counts the categories and does not rewrite history. The final source/docs, the two PDFs/PPTX and the 60-file upload archive were scanned; the PDF/PPTX metadata is sanitized, and the formal PDFs keep only the authorized identity fields. Keep credentials and unrelated account data out. |

Local `.env`, runtime data, caches and earlier release/verification artifacts remain excluded from Git. Earlier successful test counts belong to their recorded candidates; document preparation or a directory move does not establish new model quality, Windows acceptance or competition submission.
