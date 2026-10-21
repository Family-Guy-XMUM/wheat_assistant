# MaiZi — weekly order preparation

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

For a non-interactive setup check, use `Setup_Windows.bat --no-pause`, then `Start_MaiZi.bat --check`. The latter checks source-launch prerequisites without starting the server. Windows CI is configured to run these commands; **Windows runtime verification has not yet been performed**. The app's synthetic demos work without an API key; configure live AI only in your own local `.env`.

Optional live AI: copy `.env.example` to `.env` and configure `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_KEY`. It uses the OpenAI-compatible chat-completions protocol, through the local backend. Keys never go to the frontend or the Replit module. No key is distributed. Header-name suggestions and all deterministic processing work without a model; that mode is explicitly labeled. Live planning sends bounded file profiles and samples to your configured provider. Default limit: 60 requests/day, 45-second timeout, at most one JSON repair attempt. Provider usage and availability depend on your own account.

Data persists in the operating system's MaiZi application-data directory, or `MAIZI_DATA_DIR` when configured. Input files remain intact; results are separate. Stop the app before backing up that directory. This is a single-operator local prototype, with no multi-user authentication or production tenant isolation.

## Interactive review path

1. Click **01 Configure**, then **Propose a plan with AI** or **Review editable setup**. Inspect channel fields, statuses and duplicate policy.
2. Confirm `Jasmine500 → TEA-001` and `carton → box`. These are synthetic demo business decisions, not universal mappings.
3. **Check changes**, review the six concrete rule groups, and **Approve rules & run**. Week 1: 36 rows = 24 included + 3 excluded + 3 duplicate + 6 exception. SKU quantities: TEA-001 21, SOAP-002 33, RICE-003 84.
4. Inspect rows and their provenance. Acknowledge retained exceptions, export the workbook, then create the explicitly simulated Orbyte preparation task.
5. Return to **Files & flows**, click **02 Catch a change**. The saved flow is reused. Three new `Partially shipped` rows stay held. Explicitly choose **Exclude** for that status, review again, and rerun. Week 2 after confirmation: 39 = 24 + 6 + 3 + 6.
6. Click **03 Reuse**. Reordered columns and an added unused Notes field retain the mappings. Week 3: 24 rows, all included, same SKU quantities. Every batch still requires review before execution.

These counts are fixture expectations, not measured customer benefits. Live model proposals may differ and must be inspected. A partially shipped order is excluded in this demo because remaining-quantity handling is outside the first version.

## Input and output boundary

- Up to five order files, 10,000 total order lines, 5,000 product-master rows, 5 MB/file, 100 columns. UTF-8/BOM CSV and clear XLSX tables only. Headers on the first row; choose a worksheet explicitly for multi-sheet workbooks.
- Supported: mappings, exact status filters, SKU/confirmed aliases, master-based unit conversions, conservative duplicate checks, date scope, aggregation. Unknowns stay in Exceptions. No rounding of fractional base quantities. Quantities are bounded to 1e12, conversion factors to 1e9, both with at most six decimal places; larger values require a separate reviewed workflow.
- The workbook contains Warehouse_Picklist, Order_Detail, Exceptions, Excluded, Duplicates, SKU_Summary, Lineage and Run_Summary. Basic header style is reused; complex workbook formatting and macros are unsupported. Formula cells are not executed. Exported untrusted text remains text.
- All source rows receive a disposition; blank physical rows are counted separately in input profiles. No actual inventory movement, payment or external warehouse write.

## Implementation and verification

React/TypeScript frontend → FastAPI → validated FlowSpec → deterministic Python subprocess. SQLite stores immutable flow approvals, input hashes, run snapshots and activity. Rows retain source file/sheet/row and each transformation. Resource limits bound the child process; it executes only bundled operations and receives no model credentials. This is process separation, not a hardened arbitrary-code sandbox; arbitrary generated code is never accepted.

`backend/maizi/status_guard.py` was developed and tested in a real Replit Free project, downloaded, hash-checked and integrated unchanged. `REPLIT_MODULE.json` records its sanitized provenance. Replit is not hosting the full app. Orbyte identity/task handoff is simulated and labeled. No fine-tuning or GPU training has been performed.

```sh
uv run pytest -q
npm --prefix frontend run build
uv run python scripts/check_api.py   # optional; makes one real configured-provider call
uv run python scripts/build_bundle.py
```

The build script creates an OS-native `dist/MaiZi-<OS>-<architecture>.zip`. Run it on each target OS; it is not a cross-compiler. `.github/workflows/check.yml` prepares macOS/Windows checks and artifacts when run in your repository. A prepared workflow is not evidence that either hosted job has run. Development binaries are unsigned/not notarized. This foundation does not include submission documents, a public deployment or a completed competition submission.

AI-assisted contributions: Codex coordinated architecture/core/UI/integration; DeepSeek Harness authored independent contract/API/security tests; Replit Agent developed Status Guard. Independent expected results, not the planning model, verify the transformations.

License: Apache-2.0. Dependencies retain their own licenses in their distributions. Never upload `.env`, runtime files, caches, private developer metadata or unreviewed screenshots.
