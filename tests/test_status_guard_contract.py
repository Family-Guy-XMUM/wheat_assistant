"""Independent contract tests for ``maizi.status_guard.check_status_coverage``.

Written from CONTRACT.md only. All rows and channels are synthetic. The tests
cover known include/exclude statuses, trimmed matching, unknown and missing
values, unconfigured channels, empty input, channel isolation and the no-mutation
guarantee. If ``maizi.status_guard`` is missing the import must fail; there is
no skip and no replacement implementation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from maizi.status_guard import check_status_coverage

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "golden_cases.json"

MISSING = object()
STATUS_FIELD = "订单状态"


@pytest.fixture(scope="module")
def golden() -> dict:
    with FIXTURES.open(encoding="utf-8") as handle:
        return json.load(handle)


def guard_row(
    source_row_id: str,
    status,
    *,
    channel: str = "shop-a",
    row_number: int = 2,
) -> dict:
    data = {}
    if status is not MISSING:
        data[STATUS_FIELD] = status
    return {
        "source_id": channel,
        "source_row_id": source_row_id,
        "source_name": f"synthetic-{channel}-export",
        "sheet": "Orders",
        "row_number": row_number,
        "data": data,
    }


def issue_codes(result: dict) -> list[str]:
    return [issue["code"] for issue in result["issues"]]


def assert_issue_shape(issue: dict) -> None:
    assert set(issue) >= {"row_id", "channel_id", "field", "value", "code"}
    assert isinstance(issue["code"], str) and issue["code"]
    assert isinstance(issue["row_id"], str) and issue["row_id"]
    assert isinstance(issue["channel_id"], str) and issue["channel_id"]


def test_known_include_and_exclude_statuses_are_covered(golden: dict) -> None:
    case = golden["guard"]["cases"]["known_statuses"]
    result = check_status_coverage(
        copy.deepcopy(golden["guard"]["channels"]),
        copy.deepcopy(case["rows"]),
    )

    expected = case["expected"]
    assert result["rows_checked"] == expected["rows_checked"] == len(case["rows"])
    assert result["covered"] is expected["covered"] is True
    assert result["affected_row_ids"] == expected["affected_row_ids"] == []
    assert result["issues"] == []
    assert result["unknown_values"] == []


def test_unknown_status_reports_issue_and_groups_unknown_values(golden: dict) -> None:
    case = golden["guard"]["cases"]["unknown_status"]
    result = check_status_coverage(
        copy.deepcopy(golden["guard"]["channels"]),
        copy.deepcopy(case["rows"]),
    )
    expected = case["expected"]

    assert result["rows_checked"] == expected["rows_checked"]
    assert result["covered"] is False
    assert set(result["affected_row_ids"]) == set(expected["affected_row_ids"])
    assert len(result["issues"]) == 2
    for issue in result["issues"]:
        assert_issue_shape(issue)
        assert issue["code"] == "UNKNOWN_STATUS"
        assert issue["channel_id"] == "shop-a"
        assert issue["field"] == STATUS_FIELD
        assert issue["value"] == "已发货"
        assert issue["row_id"] in expected["affected_row_ids"]
    assert result["unknown_values"] == expected["unknown_values"]


@pytest.mark.parametrize(
    "status",
    [
        pytest.param("", id="empty-string"),
        pytest.param("   ", id="whitespace-only"),
        pytest.param(None, id="none"),
        pytest.param(MISSING, id="missing-key"),
    ],
)
def test_missing_or_blank_status_reports_missing_status(
    golden: dict, status
) -> None:
    row = guard_row("synthetic-guard-missing", status)
    result = check_status_coverage(
        copy.deepcopy(golden["guard"]["channels"]),
        [row],
    )

    assert result["rows_checked"] == 1
    assert result["covered"] is False
    assert result["affected_row_ids"] == ["synthetic-guard-missing"]
    assert issue_codes(result) == ["MISSING_STATUS"]
    assert_issue_shape(result["issues"][0])
    assert result["issues"][0]["row_id"] == "synthetic-guard-missing"
    assert result["issues"][0]["channel_id"] == "shop-a"


def test_unconfigured_channel_reports_channel_rule_missing(golden: dict) -> None:
    row = guard_row("synthetic-guard-no-channel", "待处理", channel="shop-z")
    result = check_status_coverage(
        copy.deepcopy(golden["guard"]["channels"]),
        [row],
    )

    assert result["rows_checked"] == 1
    assert result["covered"] is False
    assert result["affected_row_ids"] == ["synthetic-guard-no-channel"]
    assert issue_codes(result) == ["CHANNEL_RULE_MISSING"]
    assert_issue_shape(result["issues"][0])
    assert result["issues"][0]["row_id"] == "synthetic-guard-no-channel"
    assert result["issues"][0]["channel_id"] == "shop-z"


def test_empty_rows_are_covered(golden: dict) -> None:
    result = check_status_coverage(copy.deepcopy(golden["guard"]["channels"]), [])

    assert result["rows_checked"] == 0
    assert result["covered"] is True
    assert result["affected_row_ids"] == []
    assert result["issues"] == []
    assert result["unknown_values"] == []


def test_check_does_not_mutate_channels_or_rows(golden: dict) -> None:
    channels = copy.deepcopy(golden["guard"]["channels"])
    rows = [
        guard_row("synthetic-nomutate-known", "待处理"),
        guard_row("synthetic-nomutate-unknown", "已发货", row_number=3),
        guard_row("synthetic-nomutate-missing", "", row_number=4),
        guard_row("synthetic-nomutate-channel", "待处理", channel="shop-z", row_number=5),
    ]
    channels_snapshot = copy.deepcopy(channels)
    rows_snapshot = copy.deepcopy(rows)

    check_status_coverage(channels, rows)

    assert channels == channels_snapshot
    assert rows == rows_snapshot


def test_channel_rules_are_isolated(golden: dict) -> None:
    rows = [
        guard_row("synthetic-isolated-a", "待处理", channel="shop-a"),
        guard_row("synthetic-isolated-b", "待处理", channel="shop-b", row_number=3),
    ]
    result = check_status_coverage(
        copy.deepcopy(golden["guard"]["channels"]),
        rows,
    )

    assert result["rows_checked"] == 2
    assert result["covered"] is False
    assert set(result["affected_row_ids"]) == {"synthetic-isolated-b"}
    assert len(result["issues"]) == 1
    issue = result["issues"][0]
    assert issue["code"] == "UNKNOWN_STATUS"
    assert issue["row_id"] == "synthetic-isolated-b"
    assert issue["channel_id"] == "shop-b"
    assert issue["field"] == STATUS_FIELD
    assert issue["value"] == "待处理"

    assert len(result["unknown_values"]) == 1
    group = result["unknown_values"][0]
    assert group["channel_id"] == "shop-b"
    assert group["field"] == STATUS_FIELD
    assert group["value"] == "待处理"
    assert group["count"] == 1
    assert group["row_ids"] == ["synthetic-isolated-b"]


def test_status_matching_trims_outer_whitespace_only(golden: dict) -> None:
    rows = [
        guard_row("synthetic-trim-known", "  待处理  "),
        guard_row("synthetic-trim-internal", "待 处理", row_number=3),
    ]
    result = check_status_coverage(
        copy.deepcopy(golden["guard"]["channels"]),
        rows,
    )

    assert result["rows_checked"] == 2
    assert result["covered"] is False
    assert result["affected_row_ids"] == ["synthetic-trim-internal"]
    assert issue_codes(result) == ["UNKNOWN_STATUS"]
    issue = result["issues"][0]
    assert issue["row_id"] == "synthetic-trim-internal"
    assert issue["value"] == "待 处理"
    assert issue["field"] == STATUS_FIELD
