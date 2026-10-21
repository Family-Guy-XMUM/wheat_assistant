"""Pure status-coverage checks for order spreadsheet rows.

This module has no web-framework or third-party dependencies and can be copied
into a local spreadsheet workflow as-is.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any, Mapping, Sequence


def _json_safe(value: Any) -> Any:
    """Convert common Python values to JSON-safe equivalents."""
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _row_id(row: Mapping[str, Any]) -> Any:
    """Return the already globally unique source row ID without modification."""
    return row.get("source_row_id")


def _value_key(value: Any) -> str:
    """Return a stable key for grouping JSON-safe status values."""
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def check_status_coverage(
    channels: Mapping[Any, Any], rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Check every row against the status rule for its source channel.

    Status strings are trimmed at their edges only. Their case and meaning are
    never inferred. A recognized ``include`` or ``exclude`` value is covered;
    coverage does not imply eligibility for picking.

    Result row IDs are the exact ``source_row_id`` values from the input. Those
    IDs are already globally unique and are never prefixed or otherwise changed.
    """
    issues: list[dict[str, Any]] = []
    affected_row_ids: list[Any] = []
    affected_seen: set[str] = set()
    unknown_by_key: dict[tuple[Any, str, str], dict[str, Any]] = {}
    unknown_row_ids_seen: dict[tuple[Any, str, str], set[str]] = {}

    def add_issue(
        row_id: Any,
        channel_id: Any,
        field: Any,
        value: Any,
        code: str,
    ) -> None:
        issue = {
            "row_id": _json_safe(row_id),
            "channel_id": _json_safe(channel_id),
            "field": _json_safe(field),
            "value": _json_safe(value),
            "code": code,
        }
        issues.append(issue)
        row_id_key = _value_key(row_id)
        if row_id_key not in affected_seen:
            affected_seen.add(row_id_key)
            affected_row_ids.append(_json_safe(row_id))

    for row in rows:
        channel_id = row.get("source_id")
        row_id = _row_id(row)
        channel = channels.get(channel_id)

        if not isinstance(channel, Mapping):
            add_issue(row_id, channel_id, None, None, "CHANNEL_RULE_MISSING")
            continue

        fields = channel.get("fields")
        status_actions = channel.get("status_actions")
        field = fields.get("status") if isinstance(fields, Mapping) else None
        if not isinstance(field, str) or not isinstance(status_actions, Mapping):
            add_issue(row_id, channel_id, field, None, "CHANNEL_RULE_MISSING")
            continue

        data = row.get("data")
        raw_value = data.get(field) if isinstance(data, Mapping) else None
        if raw_value is None:
            add_issue(row_id, channel_id, field, "", "MISSING_STATUS")
            continue

        value = raw_value.strip() if isinstance(raw_value, str) else raw_value
        if value == "":
            add_issue(row_id, channel_id, field, "", "MISSING_STATUS")
            continue

        action = status_actions.get(value) if isinstance(value, str) else None
        if action == "include" or action == "exclude":
            continue

        add_issue(row_id, channel_id, field, value, "UNKNOWN_STATUS")
        group_key = (_value_key(channel_id), field, _value_key(value))
        group = unknown_by_key.get(group_key)
        if group is None:
            group = {
                "channel_id": _json_safe(channel_id),
                "field": field,
                "value": _json_safe(value),
                "count": 0,
                "row_ids": [],
            }
            unknown_by_key[group_key] = group
            unknown_row_ids_seen[group_key] = set()
        group["count"] += 1
        row_id_key = _value_key(row_id)
        if row_id_key not in unknown_row_ids_seen[group_key]:
            unknown_row_ids_seen[group_key].add(row_id_key)
            group["row_ids"].append(_json_safe(row_id))

    return {
        "rows_checked": len(rows),
        "covered": not issues,
        "affected_row_ids": affected_row_ids,
        "issues": issues,
        "unknown_values": list(unknown_by_key.values()),
    }
