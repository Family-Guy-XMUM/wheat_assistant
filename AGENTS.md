# MaiZi build workspace

This is the user-authorized build workspace. Shared resource rules are maintained separately in SDC_Resource. Never copy that resource library into this project.

- Current hardening coordinator: Codex / agent-audit (user-authorized 2026-10-22); owns API/models/store/frontend/scripts/packaging/shared contracts and central records. Earlier contributions retain their original attribution.
- DeepSeek Harness hardening unit 1 may edit only backend/maizi/files.py, backend/maizi/exporter.py, tests/test_io_hardening.py and tests/fixtures/io_hardening/. Unit 2 may add tests/test_hardening_acceptance.py after coordinator handoff. No other shared files, original tests, configuration or Git writes. Read the hardening contract first and report actual tool/model identity and hashes.
- Replit Free develops maizi_status_guard.py; coordinator integrates the verified source unchanged and records provenance.
- All business inputs must be team-created synthetic data. Do not upload private developer information, credentials, local paths, raw account logs or unrelated files.
- Store API keys only in ignored local configuration. Never include them in frontend code, logs, test fixtures, screenshots or release bundles.
- AI proposes a constrained JSON workflow; Python validates and executes. No arbitrary model-generated code or SQL.
- Preserve every accepted input row and its disposition; unknown states and conversions cannot silently enter picking results.
- Before any real modification, follow the resource HISTORY/taskbuild recording rules. The coordinator serializes central records; each contributor supplies their own signed engineering notes and exact contribution.
- Do not publish, push, change repository permissions or fabricate platform evidence.
