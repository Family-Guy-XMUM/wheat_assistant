# MaiZi — weekly order preparation (0.2.1)

A local web prototype for small wholesalers: combine channel order files, confirm business rules, prepare warehouse picking data, and reuse the flow next week. Only team-created synthetic business data is used in the demo.

## Run from source

Requires Python 3.12+, uv, and Node.js 22+. Commands run from this repository:

```sh
uv sync --frozen
npm --prefix frontend ci
npm --prefix frontend run build
uv run python -m maizi.launcher
```

The browser opens at `http://127.0.0.1:8765`. If that port is busy the launcher chooses another local port. Close the terminal to stop. After initial setup, use `Start_MaiZi.command` on macOS or `Start_MaiZi.bat` on Windows. Python source mode is the reproducible fallback for unsigned development binaries.

### Windows: first setup, start and stop

Use a clean source checkout on the Windows computer. Do not copy the Mac `.venv`, `node_modules`, runtime database, or private `.env`; the macOS ZIP is a separate native build.

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Node.js 22+ including npm](https://nodejs.org/en/download). Reopen your terminal after installation. Network access is required for first setup; uv may download Python 3.12.
2. Double-click **`Setup_Windows.bat`** once. It prepares the Windows Python environment from `uv.lock`, installs frontend packages from the lockfile and builds the interface. It copies `.env.example` only when `.env` does not exist; your existing key configuration is preserved.
3. Double-click **`Start_MaiZi.bat`** for daily use. Keep its console open. The browser opens automatically; use the address printed there if port 8765 is occupied.
4. To **stop**, press **Ctrl+C in that console**. If Windows asks whether to terminate the batch job, enter **Y**. Closing the browser tab alone does not stop the server. Start again with the same BAT file.

Equivalent commands from Command Prompt in this folder:

```bat
Setup_Windows.bat
Start_MaiZi.bat
```

In PowerShell, use `./Setup_Windows.bat` and `./Start_MaiZi.bat`. If Windows hides file extensions, look for the Windows Batch File type rather than opening the script in a text editor. No administrator privileges are requested by these scripts.

For a non-interactive setup check, use `Setup_Windows.bat --no-pause`, then `Start_MaiZi.bat --check`. The latter checks source-launch prerequisites without starting the server. Windows CI is configured to run these commands; **The v0.2.0 Windows receipt failed overall; this v0.2.1 candidate still needs its own Windows receipt**. The app's synthetic demos work without an API key; configure live AI only in your own local `.env`.

For the Windows operator handoff, run `Validate_Windows.bat` after setup and follow [WINDOWS_VALIDATION.md](WINDOWS_VALIDATION.md). It builds a Windows native ZIP on that computer and verifies source and independently extracted native applications over real local HTTP. Each attempt writes eight-stage and source/native/performance receipts under `output/verification/v0.2.1/<attempt-id>/`; previous receipts stay intact. Share only the sanitized JSON reports and manual checklist; keep the detailed local log private. A source ZIP is not a tested Windows executable.

Optional live AI: copy `.env.example` to `.env` and configure `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`. It uses the OpenAI-compatible chat-completions protocol, through the local backend. Keys never go to the frontend or the Replit module. No key is distributed. Header-name suggestions and all deterministic processing work without a model; that mode is explicitly labeled. Live planning sends bounded file profiles and samples to your configured provider. Default limit: 60 requests/day, 45-second timeout, at most one JSON repair attempt. Provider usage and availability depend on your own account.

Data persists in the operating system's MaiZi application-data directory, or `MAIZI_DATA_DIR` when configured. Input files remain intact; results are separate. Stop the app before backing up that directory. Before the first v0.2 opening of an existing database, the app creates a verified SQLite backup and copies original files and artifacts under that directory's `backups/`; it retains old payloads and approval hashes. To restore, stop all MaiZi processes, copy the chosen backup's `maizi.sqlite`, `files/` and `artifacts/` to a new empty data directory, and launch with `--data-dir` pointing there. Preserve the original directory. `scripts/verify_backup.py <backup-folder>` validates a temporary restored copy without modifying the backup. This is a single-operator local prototype, with no multi-user authentication or production tenant isolation; run only one app process for a given data directory.

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

React/TypeScript frontend → FastAPI → validated FlowSpec → deterministic Python subprocess. SQLite stores immutable flow approvals, input hashes, run snapshots and activity. Rows retain source file/sheet/row and each transformation. Resource limits bound the child process; it executes only bundled operations and receives no model credentials. This is process separation, not a hardened arbitrary-code sandbox; arbitrary generated code is never accepted.

`backend/maizi/status_guard.py` was developed and tested in a real Replit Free project, downloaded, hash-checked and integrated unchanged. `REPLIT_MODULE.json` records its sanitized provenance. Replit is not hosting the full app. Orbyte identity/task handoff is simulated and labeled. No fine-tuning or GPU training has been performed.

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

The build script creates an OS-native `dist/MaiZi-<OS>-<architecture>-v0.2.1.zip` with a source manifest. Run it on each target OS; it is not a cross-compiler. `.github/workflows/check.yml` prepares macOS/Windows checks and artifacts when run in your repository. A prepared workflow is not evidence that either hosted job has run. Development binaries are unsigned/not notarized. This foundation does not include submission documents, a public deployment or a completed competition submission.

See [ACCEPTANCE.md](ACCEPTANCE.md) for the measured v0.2 results and remaining gates. The six live-model cases used all twelve authorized requests: one succeeded after structural repair and five were rejected as invalid output. No first-attempt successes were observed. Those failures remain recorded; deterministic editable setup works without a key. Schema and repair guidance were subsequently strengthened and mock-tested, but have not received another live verification within this budget.

AI-assisted contributions: Codex coordinated architecture/core/UI/integration and final acceptance; DeepSeek Harness authored independent contract/API/security tests and v0.2 CSV/template-export hardening with 26 additional tests; Replit Agent developed Status Guard. Independent expected results, not the planning model, verify the transformations.

License: Apache-2.0. Dependencies retain their own licenses in their distributions. Never upload `.env`, runtime files, caches, private developer metadata or unreviewed screenshots.
