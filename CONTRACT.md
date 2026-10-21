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

## Test ownership

DeepSeek Harness owns only tests/test_engine_contract.py, tests/test_status_guard_contract.py, tests/test_api_journey.py, tests/test_ingestion_security.py and tests/fixtures/golden_cases.json. Write independent expected examples, no engine implementation. If modules do not yet exist, tests may temporarily fail import; do not skip tests or create replacement production modules. Do not write config, shared files, Git history or secrets. Report exact files, test command/results and actual model/tool identity.
