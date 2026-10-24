# Preliminary submission checklist / 初赛材料与缺项

Reviewed on **2026-10-24 MYT**, including the team's revised material files and supplied video URL. All six deliverable types have a local file or URL; the items below still prevent a final readiness claim. Deadline: **2026-10-25 07:59:59 MYT (UTC+8)**. The earlier three attachment versions were not filed in this repository and are superseded by these revised inputs.

## Materials now present

| Material | File and status |
|---|---|
| Team name | **Family Guy**, consistent in both revised PDFs and the revised deck. The approved official identity fields remain in the PDFs. |
| Combined preliminary proposal / PRD | [SDC2026_FamilyGuy_Preliminary.pdf](SDC2026_FamilyGuy_Preliminary.pdf), 11 pages, received and preserved unchanged. It follows the supplied template's single-PDF naming; no separate `PRD.pdf` is required. |
| Technical & Tools Declaration | [SDC2026_FamilyGuy_TechDeclaration.pdf](SDC2026_FamilyGuy_TechDeclaration.pdf), 13 pages, with the requested storage correction on pages 3 and 5. |
| Pitch deck | [Pitch_Deck.pptx](Pitch_Deck.pptx), 12 slides, with the requested storage correction on slide 8 and its speaker note. |
| Public prototype and Replit proof | [Live prototype](https://wheat-assistant.replit.app) and [evidence index](evidence/README.md). The app loaded in a signed-out browser, showed its independent cloud workspace / configured API, and `/healthz` returned `{"status":"ok"}` during this review. |
| Source repository and run instructions | [Public GitHub repository](https://github.com/Family-Guy-XMUM/wheat_assistant), [source setup](../../README.md), [Apache-2.0 license](../../LICENSE), backend/frontend source and dependency locks are present. Formal-file and final-version synchronization remain pending. |
| Pitch video | [Wheat Assistant by Family Guy](https://youtu.be/Fh8PB-QlRbw), displayed duration **7:00**. Signed-out playback and an actual prototype-demo segment were sampled. The uploader has confirmed **Public** visibility; a fresh signed-out watch page no longer shows the Unlisted marker. |

Both supplied PDFs visibly contain signature images and the date 2026/10/24. This task does not authenticate signatures. At the team's request, the declaration's storage wording has now been corrected; the existing signature page is visually unchanged. Its signers must review the corrected statements again before submission.

## Remaining before official submission

| Item | Concrete next step |
|---|---|
| Proposal consistency | Physical page 5 still describes pandas and SQLite as the planned stack while also saying the prototype is deployed. The current implementation uses CSV / openpyxl processing, **PostgreSQL in the cloud and SQLite locally**; pandas is not in the application dependencies. Revise this page to match the submitted implementation, then obtain the signers' review. The declaration and deck already distinguish cloud/local storage. |
| Declaration completeness | Physical page 2 visibly retains `Submission Deadline: [Insert date]`; replace it with **2026-10-25 07:59:59 MYT (UTC+8)**. The §2.2 table on physical pages 3–4 lists Python, TypeScript, React/react-dom, Vite/plugin-react, FastAPI and Uvicorn, but omits used libraries such as Pydantic, SQLAlchemy, openpyxl, HTTPX and the cloud psycopg driver, plus other direct dependencies. Complete their versions / licenses from `pyproject.toml`, `uv.lock` and `frontend/package-lock.json`; account for PostgreSQL and the actual hosting configuration, then obtain signer review. |
| Final source / material version | Public main was checked at `84b0c474ebf47e778f20279db796076cc5e1e420`; it still lacks the two local PDFs and PPTX. The validated fixes are separately on `codex/ci-model-fixes` at `9f20677af3e9934a87a6e7e02985eda05ec0c942`. Review and integrate the selected final code and corrected materials, commit/push the README/video updates, and record the full final SHA. Check the demonstrated behavior against that exact source and redeploy any selected runtime changes. No merge, push or deployment was performed by this link review. |
| Portal and cross-device access | Verify the prototype, video, source and PDFs/PPTX from another device; check actual portal fields and any required reviewer access, submit the repository link and preserve the receipt. Portal submission has not been verified. |

The revised files resolve the earlier team-name mismatch and the claim that Replit hosting was only a future plan. The later repair-branch successes below retain their source boundary and do not erase the earlier Windows or model-quality failures. The 30% time-saving target remains an explicit planning target, not a measured customer result.

## Verification and declaration items still open

These are separate from the six deliverables; the project requirements do not make a Windows executable an additional seventh deliverable.

| Item | Current boundary / next step |
|---|---|
| Windows v0.2.1 | The [latest CI](https://github.com/Family-Guy-XMUM/wheat_assistant/actions/runs/40106221040) at repair-branch commit `9f20677` completed successfully on Windows and macOS. Recorded Windows evidence: 178 tests, all eight automatic stages, source/native three-week journeys, restarts / graceful stops, and 8.774-second export median within the unchanged 10-second target. Separate human launch, Ctrl+C and Excel checks remain pending. These fixes are not yet in main or the public deployment. See [the Windows handoff](../../docs/validation/WINDOWS_VALIDATION.md); historical failures remain recorded. |
| Live-model quality | The repair batch used 13 of 14 authorized requests in total. Its final six synthetic cases passed on their first attempts in three subsets with identical planner / fixture hashes; prior 12-request and diagnostic failures remain recorded. Six cases are bounded evidence, and the improved planner has not reached main or the public deployment. See [acceptance evidence](../../docs/validation/ACCEPTANCE.md). This link review made no provider calls; deterministic editable setup remains usable. |
| RunPod applicability | No team-run GPU training/fine-tuning or RunPod job is recorded. The sponsor requirement's application to hosted third-party inference APIs is still unconfirmed. Check the actual requirement before finalizing the declaration and do not invent platform proof. |
| Replit evidence | A public live deployment URL is already available as one of the recorded accepted proof options; an additional account screenshot is not automatically required. Keep the deployment and reviewed proof accessible during review. See [evidence](evidence/README.md). |
| Privacy | Existing Git history contains non-anonymous identity markers. Resolve the permitted public team identity and any required remediation with the repository owner; this task does not rewrite history. Check final Office/PDF metadata and screenshots before upload. Keep credentials and unrelated account data out. |

Local `.env`, runtime data, caches and earlier release/verification artifacts remain excluded from Git. Earlier successful test counts belong to their recorded candidates; document preparation or a directory move does not establish new model quality, Windows acceptance or competition submission.
