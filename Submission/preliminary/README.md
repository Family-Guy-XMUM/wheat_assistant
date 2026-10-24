# Preliminary submission checklist / 初赛缺项清单

Checked against the local project requirements and build repository on **2026-10-24 MYT**. Deadline: **2026-10-25 07:59:59 MYT (UTC+8)**. This checklist records missing work; it is not a completed PRD, declaration or official submission receipt.

## Required before official submission

| Item | Remaining work | Destination / acceptance |
|---|---|---|
| Team identity | Confirm the formal competition team name and use approved team identity consistently. | Root README, final documents, deck, video and portal. |
| Official templates | Obtain and check the actual Submission Template and Technical Tools Declaration fields, naming, combined-PDF requirements and portal fields. Existing internal folder conventions do not confirm those details. | Edit a downloaded copy, preserve the shared original, then export final documents to PDF. |
| PRD / submission document | Complete the problem, SME users, scope, human control, synthetic data, SDG 8 (8.2 / 8.3), relevant SDG 9, implementation limits and expected impact. Distinguish estimates from measurements. | `PRD.pdf`, or the actual combined submission PDF with page/section links in the [submission index](../README.md). Currently absent. |
| Pitch deck | Create the actual PPTX explaining problem, solution, technology and expected impact. Keep it consistent with the current live product and video. No fixed preliminary slide limit was recorded, but the talk must remain concise. | `Pitch_Deck.pptx`. Currently absent. A PDF preview does not replace the PPTX. |
| Technical & Tools Declaration | Complete the official declaration of actual models/providers, AI assistants, dependencies, data, existing materials and sponsor platforms. Update Replit usage to include full hosting plus PostgreSQL, in addition to Status Guard development. Earlier filling guides are reference material. | `Technical_Tools_Declaration.pdf`, or the template's actual combined-file location. Currently absent. Link the [Replit proof](evidence/README.md). |
| Public YouTube video | Record/edit/upload a **5–7 minute public** pitch including actual prototype operation. Confirm processing and playback, then record the real URL. | Root README and [submission index](../README.md). No URL exists in the current repository. |
| Source delivery | Review and commit this directory reorganization, push the selected version, confirm public access and record the final full commit SHA. Keep the demonstrated runtime and submitted behavior aligned. | Existing [public GitHub repository](https://github.com/Family-Guy-XMUM/wheat_assistant). Its existing history has identity markers that need review; none are reproduced here. |
| Final access and portal receipt | Check prototype, video, documents and source from another device. Verify any required reviewer permissions, submit the actual repository link in the portal and retain the receipt/version. | Formal submission and receipt are not yet verified. |

## Verification and declaration items still open

These are separate from the six deliverables; the project requirements do not make a Windows executable an additional seventh deliverable.

| Item | Current boundary / next step |
|---|---|
| Windows v0.2.1 | The [hosted CI run for base commit `8b16d957`](https://github.com/Family-Guy-XMUM/wheat_assistant/actions/runs/40077140352) completed on 2026-10-24: macOS passed; Windows setup and launcher prerequisites passed, but versioned acceptance failed during `python_tests`. Resolve that failure and obtain new Windows source/native, restart, performance and separate human Excel receipts before claiming Windows verification. Use [the Windows handoff](../../docs/validation/WINDOWS_VALIDATION.md). The public web prototype remains the available demonstration route. |
| Live-model quality | The six recorded cases consumed twelve authorized requests: one passed after repair, five failed; there were no first-attempt passes. Declare this limitation. Further provider evaluation requires separately authorized request budget; no extra model calls are part of this directory task. Deterministic editable setup remains usable. |
| RunPod applicability | No team-run GPU training/fine-tuning or RunPod job is recorded. The sponsor requirement's application to hosted third-party inference APIs is still unconfirmed. Check the actual requirement before finalizing the declaration and do not invent platform proof. |
| Replit evidence | A public live deployment URL is already available as one of the recorded accepted proof options; an additional account screenshot is not automatically required. Keep the deployment and reviewed proof accessible during review. See [evidence](evidence/README.md). |
| Privacy | Existing Git history contains non-anonymous identity markers. Resolve the permitted public team identity and any required remediation with the repository owner; this task does not rewrite history. Check final Office/PDF metadata and screenshots before upload. Keep credentials and unrelated account data out. |

Local `.env`, runtime data, caches and earlier release/verification artifacts remain excluded from Git. Earlier successful test counts belong to their recorded candidates; document preparation or a directory move does not establish new model quality, Windows acceptance or competition submission.
