# SDC 2026 submission index

Project: **wheat** (`wheat_assistant`) · Team: **Family Guy** · Domain 2: Orbyte Smart SME Challenge.

**Reviewed on 2026-10-24 MYT: all six preliminary deliverable types have a local file or URL. Final readiness is still open: the PDFs need content corrections and signer review, and local materials/link updates have not reached public main. No official portal receipt is recorded.** The recorded preliminary deadline is **2026-10-25 07:59:59 MYT (UTC+8)**.

## Six preliminary deliverables

| Deliverable | Current status and entry |
|---|---|
| PRD / official preliminary submission PDF | [SDC2026_FamilyGuy_Preliminary.pdf](preliminary/SDC2026_FamilyGuy_Preliminary.pdf), 11 pages. The team's revised single proposal PDF contains the problem, solution, architecture, SDG, IP and declaration sections. Remaining consistency checks are in the checklist. |
| Pitch deck, PPTX | [Pitch_Deck.pptx](preliminary/Pitch_Deck.pptx), 12 slides, based on the team's revised deck, with its requested cloud/local storage correction in slide 8 and the matching speaker note. |
| Technical & Tools Declaration, PDF | [SDC2026_FamilyGuy_TechDeclaration.pdf](preliminary/SDC2026_FamilyGuy_TechDeclaration.pdf), 13 pages. The requested PostgreSQL cloud / SQLite local storage correction is included on pages 3 and 5; remaining completeness checks are in the checklist. |
| Interactive live prototype | [Open wheat](https://wheat-assistant.replit.app). See [Replit evidence](preliminary/evidence/README.md) and the [source setup / review path](../README.md). |
| Complete public GitHub source repository | [Public repository](https://github.com/Family-Guy-XMUM/wheat_assistant), with [README](../README.md), [Apache-2.0 license](../LICENSE), source, locks and tests. Public main was checked at `84b0c474`: its preliminary directory currently contains only the checklist and evidence directory, without the locally filed PDFs/PPTX. These materials and link updates still require reviewed commit and push. Git-history identity review remains separate. |
| Public YouTube pitch, 5–7 minutes, with actual prototype demonstration | [Wheat Assistant by Family Guy](https://youtu.be/Fh8PB-QlRbw), displayed duration **7:00**. Signed-out playback and a prototype-demo segment were checked. **The uploader has confirmed Public visibility; signed-out playback was rechecked and the Unlisted marker is no longer shown.** |

Use the [preliminary checklist](preliminary/README.md) for remaining checks and the [evidence index](preliminary/evidence/README.md) for existing Replit proof. Receiving a material file is not a claim that every statement has passed final review or that the official portal submission has occurred.

## Source version and deployment

The [latest repair-branch CI](https://github.com/Family-Guy-XMUM/wheat_assistant/actions/runs/40106221040) passed both Windows and macOS at `9f20677af3e9934a87a6e7e02985eda05ec0c942` on `codex/ci-model-fixes`. Its automatic Windows checks and final six synthetic model cases have passed within their recorded scope; separate human Windows/Excel checks remain pending. These fixes have not been merged into public main or redeployed. Finalize the selected source version and verify that the public demo, documents and repository describe it consistently.

## File naming and preservation

The two supplied templates explicitly request `SDC2026_TeamName_Preliminary.pdf` and `SDC2026_TeamName_TechDeclaration.pdf`. Their `TeamName` filename value here is `FamilyGuy`. The preliminary proposal is one combined PDF; no duplicate standalone `PRD.pdf` is needed. The deck remains an actual PPTX.

The proposal PDF is an exact byte copy of the team's revised file. At the team's further request, the declaration's pages 3 and 5 and deck slide 8 / its speaker note were corrected to distinguish PostgreSQL cloud storage from local SQLite. All other PDF pages and slide visuals are unchanged; unrelated note content is preserved, with minor blank-line normalization during export. The original supplied files remain intact. Existing signature images are preserved, and the signers must review the corrected declaration before submission. The team explicitly authorized retaining and publishing the official templates' required identity fields. This permission is limited to formal material fields; it does not authorize unrelated developer identities, credentials, local paths or Git metadata. The local formal materials and link updates have not yet been committed or pushed to main, and no official portal submission is verified.

Create `final/` only when entry to the finals and permission to resume development are confirmed. Keep the project resource library, raw recordings, private configuration, databases, caches and original account logs outside the submission repository.

## Demonstration boundaries

Only team-created synthetic business data belongs in the demo. Human rule approval and export confirmation are required; Orbyte handoff is simulated. Cloud mode uses PostgreSQL and anonymous browser workspaces; desktop mode uses SQLite. The remaining source/material storage inconsistency is identified in the [checklist](preliminary/README.md). See the [deployment guide](../docs/deployment/REPLIT_DEPLOYMENT.md) and existing [model-quality / Windows limitations](../docs/validation/ACCEPTANCE.md).

Before the deadline, complete final content and link review, verify access from a separate device, select the final source version and preserve the official portal receipt. Follow the applicable submission freeze rules afterward.
