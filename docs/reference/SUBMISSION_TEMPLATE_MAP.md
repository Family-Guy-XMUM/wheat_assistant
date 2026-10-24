# Submission template map

This map keeps the reviewer-facing repository aligned with the example submission project while preserving the actual `wheat_assistant` architecture. It is a navigation aid; it does not replace the official submission forms.

| Example repository concern | `wheat_assistant` location | Status and boundary |
|---|---|---|
| Project overview and reviewer links | [`README.md`](../../README.md) | Complete: product, live prototype, source repository, pitch video, SDG scope and limitations are stated at the root. |
| Source code | [`backend/`](../../backend/) and [`frontend/`](../../frontend/) | Complete: the real FastAPI/Python and React/TypeScript layout is retained instead of adding a wrapper `src/` directory. |
| Tests and reproducibility | [`tests/`](../../tests/), [`frontend/e2e/`](../../frontend/e2e/), [`pyproject.toml`](../../pyproject.toml), [`uv.lock`](../../uv.lock), [`frontend/package-lock.json`](../../frontend/package-lock.json) | Complete: unit, contract, browser and packaging checks are kept with their lockfiles. |
| Documentation | [`docs/`](../) | Complete: reference contract, deployment instructions and validation records are indexed from [`docs/README.md`](../README.md). |
| Submission materials | [`Submission/`](../../Submission/) | Complete for the preliminary package: combined proposal PDF, Technical & Tools Declaration PDF, editable PPTX and evidence index. The capitalized path is retained so existing public links remain stable. |
| Platform evidence | [`Submission/preliminary/evidence/`](../../Submission/preliminary/evidence/) | Replit proof and sanitized provenance are kept. No RunPod directory or proof is added because this project records no team-run GPU training, fine-tuning or inference job. |
| Runtime configuration | [`.env.example`](../../.env.example), [`.replit`](../../.replit), launch/setup scripts | Complete: examples contain placeholders only; local `.env`, databases, caches, logs and native build output stay ignored. |
| License | [`LICENSE`](../../LICENSE) | Complete: Apache License 2.0 is present at the repository root. |

## Public repository boundary

The public tree identifies the team as **Family Guy** and the project as `wheat_assistant`. Individual developer names, personal email addresses, local absolute paths, credentials, runtime databases, logs and resource-library records are not part of the reviewer-facing submission. Required identity fields remain only where the official submission forms require them.

Internal build-workspace rules are maintained outside the public submission repository. No `AGENTS.md` or other private collaboration instructions are included in the reviewer-facing tree.

## Reviewer path

1. Start at [`README.md`](../../README.md) for the live prototype, source link, pitch video and source run instructions.
2. Open [`Submission/README.md`](../../Submission/README.md) for the six preliminary deliverable links and current status.
3. Use [`Submission/preliminary/README.md`](../../Submission/preliminary/README.md) and [`evidence/README.md`](../../Submission/preliminary/evidence/README.md) for material-specific boundaries and Replit proof.
4. Use [`docs/README.md`](../README.md) for the technical contract, deployment and validation details.
