"""Independent contract tests for ``maizi.engine.process_orders``.

These tests are written from CONTRACT.md only. Every row, product, channel and
value below is synthetic. Assertions use stable disposition names and reason
shape, never human-readable reason prose. If ``maizi.engine`` is missing the
module import must fail; this file deliberately does not skip or ship a stub.
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

from maizi.engine import process_orders

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "golden_cases.json"

BASE_FIELDS = {
    "order_id": "订单号",
    "line_id": "明细号",
    "product": "商品",
    "quantity": "数量",
    "unit": "单位",
    "status": "订单状态",
    "date": "日期",
}

DEFAULT_STATUS_ACTIONS = {"待处理": "include", "已取消": "exclude"}


@pytest.fixture(scope="module")
def golden() -> dict:
    with FIXTURES.open(encoding="utf-8") as handle:
        return json.load(handle)


def products_from(golden: dict) -> list[dict]:
    return copy.deepcopy(golden["engine"]["products"])


def make_row(
    source_row_id: str,
    data: dict,
    *,
    channel: str = "shop-a",
    row_number: int = 2,
) -> dict:
    return {
        "source_id": channel,
        "source_row_id": source_row_id,
        "source_name": f"synthetic-{channel}-export",
        "sheet": "Orders",
        "row_number": row_number,
        "data": dict(data),
    }


def make_data(
    order_id: str,
    *,
    line: str | None = "1",
    product: str = "SKU-BLUE-001",
    quantity: str = "2",
    unit: str = "瓶",
    status: str | None = "待处理",
    date: str = "2026-10-06",
) -> dict:
    data = {
        "订单号": order_id,
        "商品": product,
        "数量": quantity,
        "单位": unit,
        "订单状态": status,
        "日期": date,
    }
    if line is not None:
        data["明细号"] = line
    return data


def make_flow(
    *,
    status_actions: dict | None = None,
    aliases: dict | None = None,
    dedup_mode: str | None = "business_key",
    date_from: str | None = None,
    date_to: str | None = None,
    channel: str = "shop-a",
) -> dict:
    rule = {
        "fields": dict(BASE_FIELDS),
        "status_actions": dict(DEFAULT_STATUS_ACTIONS) if status_actions is None else dict(status_actions),
    }
    if dedup_mode is not None:
        rule["dedup_mode"] = dedup_mode
    return {
        "channels": {channel: rule},
        "aliases": dict(aliases or {}),
        "date_from": date_from,
        "date_to": date_to,
    }


def without_key(payload: dict, key: str) -> dict:
    copied = dict(payload)
    copied.pop(key)
    return copied


def result_map(result: dict) -> dict[str, dict]:
    return {row["source_row_id"]: row for row in result["rows"]}


def sku_quantities(result: dict) -> dict[str, str]:
    return {entry["sku"]: entry["quantity"] for entry in result["sku_summary"]}


def assert_exception_row(row: dict) -> None:
    assert row["disposition"] == "exception"
    assert isinstance(row["reasons"], list) and row["reasons"]
    for reason in row["reasons"]:
        assert isinstance(reason, dict)
        assert isinstance(reason.get("code"), str) and reason["code"]
        assert isinstance(reason.get("message"), str)


def test_reconciliation_dispositions_counts_and_totals(golden: dict) -> None:
    case = golden["engine"]["cases"]["reconciliation"]
    input_rows = copy.deepcopy(case["rows"])
    result = process_orders(
        input_rows,
        products_from(golden),
        copy.deepcopy(case["flow"]),
    )

    rows = result_map(result)
    assert len(result["rows"]) == len(input_rows)
    assert set(rows) == {row["source_row_id"] for row in input_rows}

    summary = result["summary"]
    for key, value in case["expected"]["summary"].items():
        assert summary[key] == value
    assert summary["input"] == len(input_rows)
    assert summary["included"] + summary["excluded"] + summary["duplicate"] + summary["exception"] == summary["input"]
    assert summary["totals_match"] is True

    for input_row in input_rows:
        output_row = rows[input_row["source_row_id"]]
        for key in (
            "source_row_id",
            "source_id",
            "raw",
            "disposition",
            "sku",
            "quantity",
            "reasons",
            "events",
            "duplicate_of",
        ):
            assert key in output_row
        assert output_row["source_id"] == input_row["source_id"]
        assert output_row["raw"] == input_row["data"]
        assert output_row["disposition"] in {"included", "excluded", "duplicate", "exception"}
        assert isinstance(output_row["events"], list)

    for source_row_id, disposition in case["expected"]["dispositions"].items():
        assert rows[source_row_id]["disposition"] == disposition, source_row_id

    for output_row in result["rows"]:
        if output_row["disposition"] == "exception":
            assert_exception_row(output_row)

    assert sku_quantities(result) == case["expected"]["sku_quantities"]

    included_total = sum(
        Decimal(row["quantity"])
        for row in result["rows"]
        if row["disposition"] == "included"
    )
    sku_total = sum(Decimal(entry["quantity"]) for entry in result["sku_summary"])
    assert included_total == sku_total == Decimal("2")


def test_same_sku_with_different_line_ids_is_legal(golden: dict) -> None:
    rows = [
        make_row("synthetic-lines-1", make_data("SYN-4001", line="1", quantity="2")),
        make_row("synthetic-lines-2", make_data("SYN-4001", line="2", quantity="3")),
    ]
    result = process_orders(rows, products_from(golden), make_flow())

    output = result_map(result)
    assert output["synthetic-lines-1"]["disposition"] == "included"
    assert output["synthetic-lines-2"]["disposition"] == "included"
    assert output["synthetic-lines-1"]["quantity"] == "2"
    assert output["synthetic-lines-2"]["quantity"] == "3"
    assert result["summary"]["included"] == 2
    assert result["summary"]["duplicate"] == 0
    assert sku_quantities(result) == {"SKU-BLUE-001": "5"}
    assert result["summary"]["totals_match"] is True


def test_exact_duplicate_rows_collapse_to_one_representative(golden: dict) -> None:
    payload = make_data("SYN-4101", line="1", quantity="4")
    rows = [
        make_row("synthetic-dup-a", payload, row_number=2),
        make_row("synthetic-dup-b", payload, row_number=3),
        make_row("synthetic-dup-c", payload, row_number=4),
    ]
    result = process_orders(rows, products_from(golden), make_flow())

    output = result_map(result)
    included = [row for row in result["rows"] if row["disposition"] == "included"]
    duplicates = [row for row in result["rows"] if row["disposition"] == "duplicate"]
    assert len(included) == 1
    assert len(duplicates) == 2
    representative_id = included[0]["source_row_id"]
    assert included[0]["duplicate_of"] is None
    for duplicate in duplicates:
        assert duplicate["duplicate_of"] == representative_id
    assert result["summary"]["input"] == 3
    assert result["summary"]["included"] == 1
    assert result["summary"]["excluded"] == 0
    assert result["summary"]["duplicate"] == 2
    assert result["summary"]["exception"] == 0
    assert result["summary"]["totals_match"] is True
    assert sku_quantities(result) == {"SKU-BLUE-001": "4"}
    assert set(output) == {"synthetic-dup-a", "synthetic-dup-b", "synthetic-dup-c"}


def test_conflicting_business_key_marks_every_member_exception(golden: dict) -> None:
    rows = [
        make_row("synthetic-conflict-1", make_data("SYN-4201", line="1", quantity="2")),
        make_row("synthetic-conflict-2", make_data("SYN-4201", line="1", quantity="3")),
    ]
    result = process_orders(rows, products_from(golden), make_flow())

    output = result_map(result)
    for source_row_id in ("synthetic-conflict-1", "synthetic-conflict-2"):
        assert_exception_row(output[source_row_id])
        assert output[source_row_id]["duplicate_of"] is None
    assert result["summary"]["input"] == 2
    assert result["summary"]["included"] == 0
    assert result["summary"]["duplicate"] == 0
    assert result["summary"]["exception"] == 2
    assert result["summary"]["totals_match"] is True
    assert result["sku_summary"] == []


def test_excluded_status_skips_product_and_quantity_follow_up(golden: dict) -> None:
    rows = [
        make_row(
            "synthetic-excluded-blank",
            make_data(
                "SYN-4301",
                line="1",
                product="",
                quantity="",
                unit="",
                status="已取消",
            ),
        ),
        make_row(
            "synthetic-excluded-invalid",
            make_data(
                "SYN-4301",
                line="2",
                product="SKU-NOT-IN-MASTER",
                quantity="-5",
                unit="箱",
                status="  已取消  ",
            ),
        ),
        make_row(
            "synthetic-excluded-peer",
            make_data("SYN-4301", line="3", quantity="2"),
        ),
    ]
    result = process_orders(rows, products_from(golden), make_flow())

    output = result_map(result)
    assert output["synthetic-excluded-blank"]["disposition"] == "excluded"
    assert output["synthetic-excluded-invalid"]["disposition"] == "excluded"
    assert output["synthetic-excluded-peer"]["disposition"] == "included"
    assert result["summary"]["included"] == 1
    assert result["summary"]["excluded"] == 2
    assert result["summary"]["exception"] == 0
    assert sku_quantities(result) == {"SKU-BLUE-001": "2"}


@pytest.mark.parametrize(
    ("payload", "case_id"),
    [
        (make_data("SYN-4401", status="已发货"), "unknown"),
        (make_data("SYN-4402", status="   "), "blank"),
        (make_data("SYN-4403", status=None), "none"),
        (without_key(make_data("SYN-4404"), "订单状态"), "missing"),
    ],
    ids=["unknown", "blank", "none", "missing"],
)
def test_unknown_or_empty_status_is_exception(
    golden: dict, payload: dict, case_id: str
) -> None:
    row = make_row(f"synthetic-status-{case_id}", payload)
    result = process_orders([row], products_from(golden), make_flow())

    output = result["rows"][0]
    assert_exception_row(output)
    assert result["summary"]["input"] == 1
    assert result["summary"]["included"] == 0
    assert result["summary"]["excluded"] == 0
    assert result["summary"]["exception"] == 1
    assert result["sku_summary"] == []


def test_exact_alias_maps_to_sku_and_unknown_alias_is_exception(golden: dict) -> None:
    case = golden["engine"]["cases"]["alias"]
    result = process_orders(
        copy.deepcopy(case["rows"]),
        products_from(golden),
        copy.deepcopy(case["flow"]),
    )

    output = result_map(result)
    assert output["synthetic-alias-1"]["disposition"] == "included"
    assert output["synthetic-alias-1"]["sku"] == "SKU-BLUE-001"
    assert_exception_row(output["synthetic-alias-2"])
    assert result["summary"]["included"] == 1
    assert result["summary"]["exception"] == 1
    assert sku_quantities(result) == {"SKU-BLUE-001": "1"}


def test_unit_conversion_aggregates_in_base_units(golden: dict) -> None:
    rows = [
        make_row("synthetic-unit-1", make_data("SYN-4501", line="1", quantity="2", unit="箱")),
        make_row(
            "synthetic-unit-2",
            make_data("SYN-4502", line="1", product="SKU-TEA-002", quantity="1.5", unit="包"),
        ),
        make_row(
            "synthetic-unit-3",
            make_data("SYN-4503", line="1", product="SKU-TEA-002", quantity="0.5", unit="包"),
        ),
    ]
    result = process_orders(rows, products_from(golden), make_flow())

    assert all(row["disposition"] == "included" for row in result["rows"])
    assert result["summary"]["included"] == 3
    assert sku_quantities(result) == {
        "SKU-BLUE-001": "24",
        "SKU-TEA-002": "12",
    }

    by_sku = {entry["sku"]: entry for entry in result["sku_summary"]}
    products = {product["sku"]: product for product in products_from(golden)}
    for sku, entry in by_sku.items():
        assert entry["unit"] == products[sku]["base_unit"]
        assert entry["name"] == products[sku]["name"]
        assert Decimal(entry["quantity"]) > 0
    assert result["summary"]["totals_match"] is True


def test_decimal_conversion_never_rounds(golden: dict) -> None:
    # 0.29 * 100 is 28.999999999999996 in binary float; Decimal gives exactly 29.
    row = make_row(
        "synthetic-decimal-1",
        make_data(
            "SYN-4601",
            line="1",
            product="SKU-NUT-003",
            quantity="0.29",
            unit="箱",
        ),
    )
    result = process_orders([row], products_from(golden), make_flow())

    assert result["rows"][0]["disposition"] == "included"
    assert sku_quantities(result) == {"SKU-NUT-003": "29"}
    assert result["sku_summary"][0]["unit"] == "罐"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(make_data("SYN-4701", quantity="2.5"), id="fractional-base-piece"),
        pytest.param(
            make_data("SYN-4702", product="SKU-NUT-003", quantity="0.255", unit="箱"),
            id="fractional-conversion",
        ),
        pytest.param(make_data("SYN-4703", quantity="-2"), id="negative"),
        pytest.param(make_data("SYN-4704", quantity="0"), id="zero"),
        pytest.param(without_key(make_data("SYN-4705"), "数量"), id="missing"),
    ],
)
def test_fractional_non_positive_or_missing_quantity_is_exception(
    golden: dict, payload: dict
) -> None:
    row = make_row(f"synthetic-quantity-{payload['订单号']}", payload)
    result = process_orders([row], products_from(golden), make_flow())

    assert_exception_row(result["rows"][0])
    assert result["summary"]["exception"] == 1
    assert result["summary"]["included"] == 0
    assert result["sku_summary"] == []


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            make_data("SYN-4801", product="SKU-UNKNOWN-999"),
            id="unknown-sku",
        ),
        pytest.param(make_data("SYN-4802", unit="桶"), id="unknown-unit"),
        pytest.param(make_data("SYN-4803", product=""), id="blank-product"),
    ],
)
def test_unknown_product_or_unit_is_exception(golden: dict, payload: dict) -> None:
    row = make_row(f"synthetic-lookup-{payload['订单号']}", payload)
    result = process_orders([row], products_from(golden), make_flow())

    assert_exception_row(result["rows"][0])
    assert result["summary"]["exception"] == 1
    assert result["sku_summary"] == []


@pytest.mark.parametrize("line", [None, ""], ids=["missing-key", "blank-value"])
def test_missing_line_id_is_exception_in_default_business_key_mode(
    golden: dict, line: str | None
) -> None:
    row = make_row(
        "synthetic-missing-line",
        make_data("SYN-4901", line=line, quantity="2"),
    )
    result = process_orders(
        [row],
        products_from(golden),
        make_flow(dedup_mode=None),
    )

    assert_exception_row(result["rows"][0])
    assert result["summary"]["exception"] == 1
    assert result["summary"]["included"] == 0
    assert result["sku_summary"] == []


def test_source_row_mode_allows_missing_line_and_keeps_rows_separate(golden: dict) -> None:
    payload = make_data("SYN-5001", line=None, quantity="2")
    rows = [
        make_row("synthetic-source-row-1", payload, row_number=2),
        make_row("synthetic-source-row-2", payload, row_number=3),
    ]
    result = process_orders(
        rows,
        products_from(golden),
        make_flow(dedup_mode="source_row"),
    )

    output = result_map(result)
    assert output["synthetic-source-row-1"]["disposition"] == "included"
    assert output["synthetic-source-row-2"]["disposition"] == "included"
    assert output["synthetic-source-row-1"]["duplicate_of"] is None
    assert output["synthetic-source-row-2"]["duplicate_of"] is None
    assert result["summary"]["included"] == 2
    assert result["summary"]["duplicate"] == 0
    assert sku_quantities(result) == {"SKU-BLUE-001": "4"}


def test_duplicate_master_sku_raises_value_error(golden: dict) -> None:
    products = products_from(golden)
    products.append(copy.deepcopy(products[0]))
    rows = [make_row("synthetic-master-dup", make_data("SYN-5101"))]

    with pytest.raises(ValueError):
        process_orders(rows, products, make_flow())


def test_date_range_is_inclusive_and_outside_rows_are_excluded(golden: dict) -> None:
    case = golden["engine"]["cases"]["date_range"]
    result = process_orders(
        copy.deepcopy(case["rows"]),
        products_from(golden),
        copy.deepcopy(case["flow"]),
    )

    output = result_map(result)
    for source_row_id, disposition in case["expected"]["dispositions"].items():
        assert output[source_row_id]["disposition"] == disposition, source_row_id
    for key, value in case["expected"]["summary"].items():
        assert result["summary"][key] == value
    assert sku_quantities(result) == case["expected"]["sku_quantities"]
    assert result["summary"]["totals_match"] is True


def test_cross_batch_calls_are_independent(golden: dict) -> None:
    products = products_from(golden)
    flow = make_flow()
    week_one = make_row(
        "synthetic-batch-week-1",
        make_data("SYN-5201", line="1", quantity="2", date="2026-10-06"),
    )
    week_two = make_row(
        "synthetic-batch-week-2",
        make_data("SYN-5201", line="1", quantity="2", date="2026-10-13"),
    )

    first = process_orders([week_one], products, copy.deepcopy(flow))
    snapshot = copy.deepcopy(first)
    second = process_orders([week_two], products, copy.deepcopy(flow))

    assert first == snapshot
    for result in (first, second):
        assert result["rows"][0]["disposition"] == "included"
        assert result["rows"][0]["duplicate_of"] is None
        assert result["summary"]["included"] == 1
        assert result["summary"]["duplicate"] == 0
        assert sku_quantities(result) == {"SKU-BLUE-001": "2"}
