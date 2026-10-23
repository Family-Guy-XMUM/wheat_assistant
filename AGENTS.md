# wheat_assistant build workspace

This is the user-authorized build workspace. Shared resource rules are maintained separately in SDC_Resource. Never copy that resource library into this project.

- Current hardening coordinator: Codex / agent-audit (user-authorized 2026-10-22); owns API/models/store/frontend/scripts/packaging/shared contracts and central records. Earlier contributions retain their original attribution.
- DeepSeek Harness hardening unit 1 may edit only backend/wheat_assistant/files.py, backend/wheat_assistant/exporter.py, tests/test_io_hardening.py and tests/fixtures/io_hardening/. Unit 2 may add tests/test_hardening_acceptance.py after coordinator handoff. No other shared files, original tests, configuration or Git writes. Read the hardening contract first and report actual tool/model identity and hashes.
- Replit Free develops wheat_assistant_status_guard.py; coordinator integrates the verified source unchanged and records provenance.
- All business inputs must be team-created synthetic data. Do not upload private developer information, credentials, local paths, raw account logs or unrelated files.
- Store API keys only in ignored local configuration. Never include them in frontend code, logs, test fixtures, screenshots or release bundles.
- AI proposes a constrained JSON workflow; Python validates and executes. No arbitrary model-generated code or SQL.
- Preserve every accepted input row and its disposition; unknown states and conversions cannot silently enter picking results.
- Before any real modification, follow the resource HISTORY/taskbuild recording rules. The coordinator serializes central records; each contributor supplies their own signed engineering notes and exact contribution.
- Do not publish, push, change repository permissions or fabricate platform evidence.

## Windows v0.2.1 batch (2026-10-22)

User approved the Windows receipt remediation plan. Codex / agent-winfix is the sole writer of production code, shared contracts, configuration, existing tests, packaging and central records for this batch. DeepSeek Harness / agent-contract-tests may only add tests/test_windows_v021.py and tests/test_windows_v021_review.py and provide its own signed handoff. No changes to production code, existing tests, fixtures, shared records or Git by Harness. Read the v0.2.1 contract before writing. No .env reads or provider calls. Coordinator freezes candidate writes before final review; Windows results require a new actual Windows receipt.

## Application rename (2026-10-23)

The user authorized renaming the application, its own packages, launchers and GitHub repository to `wheat_assistant`; the resource directory remains `SDC_Resource`. Codex / agent-rename is the sole writer for this batch. Existing contributor attribution, Replit source provenance and Git history remain intact. Local compatibility references to the former name preserve existing databases, locks and environment settings. No model requests, source push or visibility change are included.
