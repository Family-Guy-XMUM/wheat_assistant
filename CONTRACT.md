# Foundation contracts v1

All examples are synthetic. Coordinator owns this contract; tests may depend on it but must not edit it.

## Pure engine

`from maizi.engine import process_orders`

`process_orders(rows, products, flow) -> dict`

rows: list of `{source_id: channel ID, source_row_id: globally unique string, source_name: string, sheet: string, row_number: integer, data: raw column/value dict}`.

products: list of `{sku: string, name: string, base_unit: string, unit_factors: {unit: positive decimal string}}`. Base unit always has factor 1. Duplicate SKU is invalid master data and raises ValueError.

flow: `{channels: {channel: {fields: {order_id, line_id, product, quantity, unit, status, date}, status_actions: {exact trimmed value: include|exclude}, dedup_mode: business_key|source_row}}, aliases: {exact trimmed alias: sku}, date_from: ISO date or null, date_to: ISO date or null}`. Values in fields are raw column names; line_id/date may be null. Date range requires mapped ISO date. Unknown operations are never executed.

result: `{rows: [...], summary: {input,included,excluded,duplicate,exception,totals_match}, sku_summary: [{sku,name,quantity,unit}]}`. Each row result contains source_row_id, source_id, raw, disposition (included|excluded|duplicate|exception), sku (nullable), quantity (decimal string or null), reasons (list of code/message dicts), events (list), duplicate_of (nullable). sku_summary quantities are decimal strings.

Rules: unknown/missing status -> exception. Known excluded status -> excluded, without product/quantity follow-up. Default business key = channel/order/line. Same key identical data -> one representative and duplicate pointer. Same key conflicting content -> all group members exceptions, never keep one automatically. Same SKU with different line IDs is legal. Missing line ID -> exception unless source_row mode is explicitly selected. Exact SKU or confirmed alias only. Unknown product/unit, missing or non-positive quantity, fractional base-piece result -> exception. Integer piece conversion uses Decimal and never rounds. Cross-week batches are independent. Every input row has one disposition and aggregate totals reconcile. Errors need stable reason codes but tests should not depend on prose.

## Replit status guard

`from maizi.status_guard import check_status_coverage`

`check_status_coverage(channels, rows) -> {rows_checked,covered,affected_row_ids,issues,unknown_values}`.

Uses the same channel/row shapes as above. known include AND exclude statuses are covered. Trim whitespace only. Issue codes UNKNOWN_STATUS, MISSING_STATUS, CHANNEL_RULE_MISSING. Issue fields row_id,channel_id,field,value,code. unknown_values entries channel_id,field,value,count,row_ids. No mutation. Empty rows are covered. Covered does not mean eligible for picking.

## Historical foundation test ownership

DeepSeek Harness owns only tests/test_engine_contract.py, tests/test_status_guard_contract.py, tests/test_api_journey.py, tests/test_ingestion_security.py and tests/fixtures/golden_cases.json. Write independent expected examples, no engine implementation. If modules do not yet exist, tests may temporarily fail import; do not skip tests or create replacement production modules. Do not write config, shared files, Git history or secrets. Report exact files, test command/results and actual model/tool identity.

## User-authorized local hardening contract (2026-10-22)

This section supersedes the old file whitelist for this hardening batch only. Coordinator Codex / agent-audit owns shared/API/frontend work. DeepSeek Harness owns only files.py, exporter.py, tests/test_io_hardening.py and tests/fixtures/io_hardening/ for unit 1. Original tests and status_guard.py stay unchanged. No Git writes, real model calls, .env reads or secret access by Harness. All inputs are synthetic. Supply a self-signed handoff with exact files, SHA-256, red/green evidence, limitations and actual identity; coordinator transcribes central records.

Parser: retain parse_table(content, filename, role, sheet_name=None), profile(table), extract_products(table,mapping) and existing return keys. Add PARSER_VERSION=2 and table.parser_version=2. Every new record has row_number=start physical line and row_end_number=end physical line (same for XLSX). Strict CSV must reject malformed quotes while accepting valid embedded newline/delimiter/escaped quotes. MAX_CELL_CHARS=32767 applies to CSV/XLSX; overlong cells or serialized raw data beyond Excel's single-cell limit raise ValueError with safe filename and physical row. Wrap csv.Error as ValueError; optional exception attributes code and line_number may carry structured details. Retain UTF-8/BOM and existing file/row/column/decompression limits. Do not truncate any input. Profile retains its bounded samples; coordinator derives complete status/unit options separately. Never add local paths to errors.

Exporter: retain export_workbook(result,flow,snapshot,target,template_content=None) positional compatibility; add optional template_sheet_name=None and on_stage=None keyword parameters. Add EXPORTER_VERSION=2. Use selected worksheet; copy public style attributes (font/fill/border/alignment/protection/number_format), column widths and header height; do not overwrite chosen template header formatting with default finish formatting. Untrusted strings remain data_type='s'; large integers stay exact. Exactly eight existing sheets and all data/lineage preserved. Avoid repeated max_row scans per appended row. Write to a unique temporary sibling, load and verify sheet names/counts/styles/no formulas, then os.replace to target only after verification. Existing target unchanged on failure; close and clean only own temporary file. Call on_stage('writing') and on_stage('verifying') at the actual stages if provided. Return str(target). No arbitrary formula/code execution. Tests use temporary directories and no provider calls.

Coordinator API extensions: optional source_flow_id on plan/approve and preflight query; flow envelope adds workflow_id/rule_version/parent_flow_id without changing FlowSpec v1 or old hashes. GET /api/runs/{id}/sku-summary and /api/history/{kind} use {total,rows,offset,limit}; existing rows endpoint gains optional reason_code/source_row_id filters and keeps old fields. GET run adds export_state/export_stage/export_error/export_id; original execute/export-approval synchronous interfaces remain compatible. Source records/results/approvals remain immutable. Unchanged rules keep a version, new content increments within workflow, every batch keeps its own approval. Unknown statuses/units/products remain held. Six review groups are required after every edit.
## v0.2 final additive recovery interfaces

FlowSpec remains schema_version=1; the existing spec/snapshot digest algorithm is unchanged. Approval envelopes add workflow_id, rule_version, parent_flow_id and optional draft_id. Older flows without lineage remain independent version 1 records. Reapproval of identical input/spec within one batch is idempotent; each different batch still has its own approval. BatchRequest optionally accepts idempotency_key (1..100 characters); without it, creating a new batch retains its original behavior. Reusing a key with different file IDs or label is rejected.

- `GET /api/flows/{id}` reads the canonical saved flow.
- `POST /api/batches/{id}/approval-status` accepts the approve body and reads `{flow: saved-or-null}` without approving or executing.
- `GET /api/batches/by-key/{key}` reads `{batch: saved-or-null}` for a keyed import.
- `GET /api/history/{batches|flows|runs|activity}` returns `{rows,total,offset,limit}`; default20, maximum200; optional query, run_id (activity), workflow_id (flows), flow_id (runs).
- `GET /api/runs/{id}/sku-summary` returns all SKU totals through paged `{rows,total,offset,limit}`; default50, maximum200. Existing full summary in the run response remains compatible.
- Rows retain original defaults and add reason_code/source_row_id filtering; all paging clamps offset to >=0 and limit to1..200.
- Runs use ready/running/completed/failed/interrupted. Export status is not_started/building/ready/failed/interrupted; stage records validating/writing/verifying/ready. pending_export_id is distinct from the last verified export_id. A failed new export keeps prior verified downloads usable.
- `GET /api/runs/{id}/exports` lists versions; download optionally accepts export_id and validates file existence plus SHA-256. The legacy download URL remains unchanged. A historical file without an original checksum is registered on first v2 observation; earlier tampering cannot be inferred retroactively.
- Native/source desktop launchers hold an OS lock per data directory. Arbitrary direct API hosting and multiple operators are outside this local prototype.

On transport failures the frontend queries persisted status. A recovered approval/run requires an explicit start; a timeout does not cancel server execution. The existing deterministic worker has a 30-second wall/20-second CPU/512-MiB RSS boundary; export verification continues in the server until completion or restart.
