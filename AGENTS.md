# MaiZi build workspace

This is the user-authorized build workspace. Shared resource rules are maintained separately in SDC_Resource. Never copy that resource library into this project.

- Coordinator: Codex / agent-handoff; owns backend/, frontend/, scripts/, packaging and shared contracts.
- DeepSeek Harness may edit only tests/test_engine_contract.py, tests/test_status_guard_contract.py, tests/test_api_journey.py, tests/test_ingestion_security.py, tests/fixtures/golden_cases.json after receiving the contract. No shared files or Git writes.
- Replit Free develops maizi_status_guard.py; coordinator integrates the verified source unchanged and records provenance.
- All business inputs must be team-created synthetic data. Do not upload private developer information, credentials, local paths, raw account logs or unrelated files.
- Store API keys only in ignored local configuration. Never include them in frontend code, logs, test fixtures, screenshots or release bundles.
- AI proposes a constrained JSON workflow; Python validates and executes. No arbitrary model-generated code or SQL.
- Preserve every accepted input row and its disposition; unknown states and conversions cannot silently enter picking results.
- Before any real modification, follow the resource HISTORY/taskbuild recording rules. The coordinator serializes central records; each contributor supplies their own signed engineering notes and exact contribution.
- Do not publish, push, change repository permissions or fabricate platform evidence.
