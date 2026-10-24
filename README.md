# wheat — weekly order preparation (0.2.1)

The interface brand is `wheat`; the repository, source package and executable use `wheat_assistant`.

A web prototype for small wholesalers: combine channel order files, confirm business rules, prepare warehouse picking data, and reuse the flow next week. Only team-created synthetic business data is used in the demo.

**Live Prototype URL: [https://wheat-assistant.replit.app](https://wheat-assistant.replit.app)** — no Replit login required. The public three-week workflow and actual Excel download were verified on 2026-10-24 MYT. Each browser gets a separate synthetic demo workspace; keep its cookies to return to saved history. The online AI entry is configured; source-version and verification boundaries are described below.

**Pitch video: [Wheat Assistant by Family Guy](https://youtu.be/Fh8PB-QlRbw)** — displayed duration **7:00**. Signed-out playback and a prototype-demo segment were checked on 2026-10-24 MYT. **The uploader has confirmed Public visibility; signed-out playback was rechecked and the Unlisted marker is no longer shown.**

For the separate Replit cloud entry point, browser-private workspaces and PostgreSQL persistence, see [Replit deployment](docs/deployment/REPLIT_DEPLOYMENT.md). The desktop entry point remains available locally. The public app and its `/healthz` response were checked again on 2026-10-24 MYT.

The application and source package were renamed from MaiZi to `wheat_assistant` on 2026-10-23. Earlier verification receipts retain their original names and hashes. Rebuilt artifacts use the new name. Historical receipts and the later repair-branch results must be read against their actual source versions.

## Competition and deliverables

SDC Hackathon 2026 · Domain 2: Orbyte Smart SME Challenge. Team: **Family Guy**, as named consistently in the revised submission documents and pitch deck supplied by the team. The project supports SDG 8 (8.2 and 8.3), with SDG 9 relevant to its reusable workflow capability; no measured customer impact is claimed.

- [Public source repository](https://github.com/Family-Guy-XMUM/wheat_assistant)
- [Submission index and current readiness](Submission/README.md)
- [Preliminary checklist and remaining checks](Submission/preliminary/README.md)
- [Replit evidence and provenance](Submission/preliminary/evidence/README.md)
- [Engineering documentation](docs/README.md)

All six preliminary deliverable types now have a local file or access link: the combined proposal PDF, Technical & Tools Declaration PDF, 12-slide PPTX, live prototype, public source repository and pitch video. This is **not yet a complete public submission**: the PDFs have remaining content corrections, and the local materials/link updates have not been committed or pushed to main. See the [submission index](Submission/README.md) and [remaining checks](Submission/preliminary/README.md); the official portal receipt is still unverified. The recorded preliminary deadline is **2026-10-25 07:59:59 MYT (UTC+8)**.

## Repository layout

```text
wheat_assistant/
├── README.md, LICENSE              # reviewer entry and Apache-2.0
├── backend/wheat_assistant/        # FastAPI, workflows, SQLite / cloud storage
├── frontend/                      # React / TypeScript and browser tests
├── tests/                         # independent contracts and regression tests
├── scripts/                       # build, package, verify and Replit commands
├── docs/
│   ├── README.md                  # technical document index
│   ├── reference/CONTRACT.md
│   ├── deployment/REPLIT_DEPLOYMENT.md
│   └── validation/                # local acceptance and Windows handoff
├── Submission/
│   ├── README.md                  # six-deliverable status and access links
│   └── preliminary/
│       ├── README.md              # material status and remaining checks
│       ├── SDC2026_FamilyGuy_Preliminary.pdf
│       ├── SDC2026_FamilyGuy_TechDeclaration.pdf
│       ├── Pitch_Deck.pptx
│       └── evidence/              # Replit proof URL and original provenance
├── Start_wheat_assistant.*        # daily desktop launchers
├── Setup_Windows.bat, Validate_Windows.bat
└── pyproject.toml, uv.lock, .replit, .env.example
```

The supplied official templates require one preliminary proposal PDF and one Technical & Tools Declaration PDF, named with the team name as shown above. `FamilyGuy` is the filename form of Family Guy. Directory names remain the team's convention, and the final portal fields still require checking. No finals directory has been created. Local `.env`, databases, `state/`, `.runtime/`, `.venv/`, `node_modules/`, `build/`, `dist/` and `output/` are excluded from Git. Generated local files remain in place.

## Run from source

Requires Python 3.12+, uv, and Node.js 22+. Commands run from this repository:

```sh
uv sync --frozen
npm --prefix frontend ci
npm --prefix frontend run build
uv run python -m wheat_assistant.launcher
```

The browser opens at `http://127.0.0.1:8765`. If that port is busy the launcher chooses another local port. Close the terminal to stop. After initial setup, use `Start_wheat_assistant.command` on macOS or `Start_wheat_assistant.bat` on Windows. Python source mode is the reproducible fallback for unsigned development binaries.

### Windows: first setup, start and stop

Use a clean source checkout on the Windows computer. Do not copy the Mac `.venv`, `node_modules`, runtime database, or private `.env`; the macOS ZIP is a separate native build.

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Node.js 22+ including npm](https://nodejs.org/en/download). Reopen your terminal after installation. Network access is required for first setup; uv may download Python 3.12.
2. Double-click **`Setup_Windows.bat`** once. It prepares the Windows Python environment from `uv.lock`, installs frontend packages from the lockfile and builds the interface. It copies `.env.example` only when `.env` does not exist; your existing key configuration is preserved.
3. Double-click **`Start_wheat_assistant.bat`** for daily use. Keep its console open. The browser opens automatically; use the address printed there if port 8765 is occupied.
4. To **stop**, press **Ctrl+C in that console**. If Windows asks whether to terminate the batch job, enter **Y**. Closing the browser tab alone does not stop the server. Start again with the same BAT file.

Equivalent commands from Command Prompt in this folder:

```bat
Setup_Windows.bat
Start_wheat_assistant.bat
```

In PowerShell, use `./Setup_Windows.bat` and `./Start_wheat_assistant.bat`. If Windows hides file extensions, look for the Windows Batch File type rather than opening the script in a text editor. No administrator privileges are requested by these scripts.

For a non-interactive setup check, use `Setup_Windows.bat --no-pause`, then `Start_wheat_assistant.bat --check`. The latter checks source-launch prerequisites without starting the server. The separate `codex/ci-model-fixes` branch has since passed Windows and macOS automatic acceptance at commit `9f20677`; it has not been merged into main or deployed. The earlier Windows failures remain documented. Separate operator launch, Ctrl+C and Excel checks are still pending. The app's synthetic demos work without an API key; configure live AI only in your own local `.env`.

For the Windows operator handoff, run `Validate_Windows.bat` after setup and follow [Windows validation](docs/validation/WINDOWS_VALIDATION.md). It builds a Windows native ZIP on that computer and verifies source and independently extracted native applications over real local HTTP. Each attempt writes eight-stage and source/native/performance receipts under `output/verification/v0.2.1/<attempt-id>/`; previous receipts stay intact. Share only the sanitized JSON reports and manual checklist; keep the detailed local log private. A source ZIP is not a tested Windows executable.

Optional live AI: copy `.env.example` to `.env` and configure `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`. It uses the OpenAI-compatible chat-completions protocol, through the local backend. Keys never go to the frontend or the Replit module. No key is distributed. Header-name suggestions and all deterministic processing work without a model; that mode is explicitly labeled. Live planning sends bounded file profiles and samples to your configured provider. Default limit: 60 requests/day, 45-second timeout, at most one JSON repair attempt. Provider usage and availability depend on your own account.

New data persists in the operating system's `wheat_assistant` application-data directory, or `WHEAT_ASSISTANT_DATA_DIR` when configured. Existing installations continue to use their original `MaiZi` data directory and `maizi.sqlite` database when no current database exists, so renaming does not hide saved work. Legacy `MAIZI_DATA_DIR` and `MAIZI_PORT` remain accepted; the corresponding `WHEAT_ASSISTANT_` settings take precedence. Input files remain intact; results are separate. Stop the app before backing up that directory. Before the first v0.2 opening of an existing database, the app creates a verified SQLite backup and copies original files and artifacts under that directory's `backups/`; it retains old payloads and approval hashes. To restore, stop all wheat_assistant processes, copy the chosen backup's database (`wheat_assistant.sqlite`, or legacy `maizi.sqlite`), `files/` and `artifacts/` to a new empty data directory, and launch with `--data-dir` pointing there. Preserve the original directory. `scripts/verify_backup.py <backup-folder>` validates a temporary restored copy without modifying the backup. This is a single-operator local prototype, with no multi-user authentication or production tenant isolation; run only one app process for a given data directory.

## Interactive review path

1. Click **01 Configure**, select **Create a new workflow**, then **Propose a plan with AI** or **Review editable setup**. Inspect channel fields, statuses and duplicate policy. Ordinary uploads use the same controls: assign a stable source ID and choose the template worksheet when it has multiple sheets.
2. Confirm `Jasmine500 → TEA-001` and `carton → box`. These are synthetic demo business decisions, not universal mappings.
3. **Check changes**, review the six concrete rule groups, and **Approve rules & run**. Week 1: 36 rows = 24 included + 3 excluded + 3 duplicate + 6 exception. SKU quantities: TEA-001 21, SOAP-002 33, RICE-003 84.
4. Inspect rows and their provenance. Acknowledge retained exceptions, export the workbook, then create the explicitly simulated Orbyte preparation task.
5. Return to **Files & flows**, explicitly select the approved version in **Workflow to use**, then click **02 Catch a change**. Three new `Partially shipped` rows in channel-b start as **Unreviewed** and block approval until you explicitly hold, include or exclude them. Explicitly choose **Exclude** for that status, review again, and rerun. Week 2 after confirmation: 39 = 24 + 6 + 3 + 6.
6. Click **03 Reuse**. Reordered columns and an added unused Notes field retain the mappings. Week 3: 24 rows, all included, same SKU quantities. Every batch still requires review before execution.

These counts are fixture expectations, not measured customer benefits. Live model proposals may differ and must be inspected. A partially shipped order is excluded in this demo because remaining-quantity handling is outside the first version.

The selector shows saved versions rather than silently choosing the globally newest flow. Workflow identity, rule version and per-batch approval are separate: unchanged rules keep their version, while every batch receives an independent immutable approval. **Check changes** shows six rule-group differences and input changes. Missing source mappings, missing columns and incompatible templates block approval. Status observations include all files in each source, including more than 60 distinct values; unit options come from the actual product master.

Order lines default to 100 per page (50/100/200); SKU totals use 50, history uses 20. Search and **Last** reach every result. Activity starts with the current run and can be switched to global. Exception reason groups link to alias, unit or status edits; confirm the new draft again to produce a new run. Old approvals and results stay available. A deliberate **Hold as exception** stays separate from the reusable rules: confirm each held status for this batch, then review all six groups. Changing inputs, rules or source version clears those confirmations. Missing statuses can only be explicitly held or corrected in a new input.

Failed or interrupted runs can be retried with the same run ID and approved snapshot. After a connection error, refresh actual status before retrying. Export shows writing, verification, ready, failure and interruption states; an unchanged result with the same exporter version reuses a verified artifact. Failed exports can be retried, while old exports remain separately downloadable.

## Input and output boundary

- Up to five order files, 10,000 total order lines, 5,000 product-master rows, 5 MB/file, 100 columns. UTF-8/BOM CSV and clear XLSX tables only. Headers on the first row; choose a worksheet explicitly for multi-sheet workbooks. Strict CSV accepts quoted multiline fields, quoted delimiters and escaped quotes; malformed quoting is rejected with a filename and physical line. Single cells and serialized per-row original data must each fit Excel's 32,767-character limit; rejected content is never truncated. Original row start/end lines remain visible.
- Supported: mappings, exact status filters, SKU/confirmed aliases, master-based unit conversions, conservative duplicate checks, date scope, aggregation. Unknowns stay in Exceptions. No rounding of fractional base quantities. Quantities are bounded to 1e12, conversion factors to 1e9, both with at most six decimal places; larger values require a separate reviewed workflow.
- The workbook contains Warehouse_Picklist, Order_Detail, Exceptions, Excluded, Duplicates, SKU_Summary, Lineage and Run_Summary. The selected template sheet's basic public header styles, column widths and header height are reused; complex workbook formatting and macros are unsupported. Formula cells are not executed. Exported untrusted text and integers exceeding Excel's numeric precision remain text. Each new export is written to a temporary file, reopened and checked before publication.
- All source rows receive a disposition; blank physical rows are counted separately in input profiles. No actual inventory movement, payment or external warehouse write.

## Implementation and verification

React/TypeScript frontend → FastAPI → validated FlowSpec → deterministic Python subprocess. Desktop mode uses SQLite; the Replit cloud entry point stores scoped approvals, inputs, results and export bytes in PostgreSQL. Rows retain source file/sheet/row and each transformation. Resource limits bound the child process; it executes only bundled operations and receives no model credentials. This is process separation, not a hardened arbitrary-code sandbox; arbitrary generated code is never accepted.

`backend/wheat_assistant/status_guard.py` was developed and tested in a real Replit Free project, downloaded, hash-checked and integrated unchanged. [REPLIT_MODULE.json](Submission/preliminary/evidence/REPLIT_MODULE.json) records its sanitized provenance. The complete public prototype now runs on a Replit Reserved VM with Replit PostgreSQL. The cloud deployment batch recorded fourteen additional tests, including a real PostgreSQL three-week journey and loss of the temporary file cache, with 148 local tests passing on that snapshot. The later repair-branch CI results are described below. Orbyte identity/task handoff is simulated and labeled. No team-run fine-tuning, GPU training or RunPod job is recorded; the sponsor requirement for hosted third-party inference still needs organizer confirmation.

```sh
uv run pytest -q
npm --prefix frontend run build
cd frontend && npm test  # requires Playwright Chromium, or Google Chrome on macOS
# Return to the repository root for the following commands.
uv run python scripts/verify_release.py --output output/verification/source-release.json
uv run python scripts/benchmark_release.py
uv run python scripts/check_api.py   # optional; makes one real configured-provider call
uv run python scripts/build_bundle.py
```

The build script creates an OS-native `dist/wheat_assistant-<OS>-<architecture>-v0.2.1.zip` with a source manifest. Run it on each target OS; it is not a cross-compiler. `.github/workflows/check.yml` prepares macOS/Windows checks and artifacts when run in your repository. The [earlier base-commit CI](https://github.com/Family-Guy-XMUM/wheat_assistant/actions/runs/40077140352) failed Windows acceptance. The [latest repair-branch CI](https://github.com/Family-Guy-XMUM/wheat_assistant/actions/runs/40106221040), at `9f20677af3e9934a87a6e7e02985eda05ec0c942`, passed both Windows and macOS. Its Windows evidence records 178 Python tests, all eight automatic stages, source/native journeys, restarts and an 8.774-second export median against the unchanged 10-second target. These results belong to `codex/ci-model-fixes`; main remains `84b0c474`, and the public Replit deployment has not been updated with that branch. The locally filed PDFs/PPTX and these README changes are also still awaiting commit and push. Development binaries are unsigned/not notarized. Submission documents and the official competition submission are separate from the live prototype.

See [acceptance evidence](docs/validation/ACCEPTANCE.md) for version-specific results and remaining gates. The historical model evaluation used twelve requests and passed one of six cases after repair. A later authorized evaluation on the repair branch used 13 of 14 requests in total; its final six synthetic cases passed on their first attempts, run in three subsets with identical planner and fixture hashes. The earlier failures remain recorded, and six cases are bounded evidence. That planner is not yet in main or the public deployment. Deterministic editable setup remains available without a key.

AI-assisted contributions: Codex coordinated architecture/core/UI/integration and final acceptance; DeepSeek Harness authored independent contract/API/security tests and v0.2 CSV/template-export hardening with 26 additional tests; Replit Agent developed Status Guard. Independent expected results, not the planning model, verify the transformations.

License: Apache-2.0. Dependencies retain their own licenses in their distributions. Never upload `.env`, runtime files, caches, private developer metadata or unreviewed screenshots.
