"""Deterministic order processing. No model calls, arbitrary code, or file writes."""
from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from maizi.numbers import positive_decimal

def text(value):
    return "" if value is None else str(value).strip()

def decimal_text(value: Decimal):
    return format(value, "f").rstrip("0").rstrip(".") if "." in format(value, "f") else format(value, "f")

def process_orders(rows: list[dict], products: list[dict], flow: dict) -> dict:
    master = {}
    for product in products:
        sku = text(product.get("sku"))
        if not sku or sku in master:
            raise ValueError("Product master has a missing or duplicate SKU")
        factors = {}
        for unit, factor in product.get("unit_factors", {}).items():
            try:
                amount = positive_decimal(factor, Decimal("1000000000"))
            except (InvalidOperation, ValueError):
                raise ValueError("Invalid product conversion")
            if not amount.is_finite() or amount <= 0:
                raise ValueError("Product conversion must be positive")
            factors[text(unit)] = amount
        base = text(product.get("base_unit", "piece"))
        if base in factors and factors[base] != 1:
            raise ValueError("Base unit conversion must be one")
        factors[base] = Decimal(1)
        master[sku] = {**product, "base_unit": base, "factors": factors}

    identifiers = [x["source_row_id"] for x in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Source row identifiers must be unique")
    channels = flow.get("channels", {})
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        rule = channels.get(row["source_id"], {})
        fields = rule.get("fields", {})
        order = text(row["data"].get(fields.get("order_id", "")))
        line = text(row["data"].get(fields.get("line_id", "")))
        if rule.get("dedup_mode", "business_key") == "business_key" and order and line:
            groups[(row["source_id"], order, line)].append(index)
    conflicts, duplicates = set(), {}
    for indices in groups.values():
        if len(indices) < 2:
            continue
        signatures = {json.dumps(rows[i]["data"], sort_keys=True, ensure_ascii=False, default=str) for i in indices}
        if len(signatures) > 1:
            conflicts.update(indices)
        else:
            for i in indices[1:]:
                duplicates[i] = rows[indices[0]]["source_row_id"]

    results, totals = [], {}
    for index, row in enumerate(rows):
        raw = copy.deepcopy(row["data"])
        result = {
            "source_row_id": row["source_row_id"], "source_id": row["source_id"],
            "source_name": row.get("source_name", row["source_id"]),
            "sheet": row.get("sheet", ""), "row_number": row.get("row_number"),
            "row_end_number": row.get("row_end_number", row.get("row_number")),
            "raw": raw, "disposition": "exception", "sku": None, "quantity": None,
            "reasons": [], "events": [], "duplicate_of": None,
        }
        def fail(code, message):
            result["reasons"].append({"code": code, "message": message})
        def event(stage, before, after, rule_name, evidence=None):
            result["events"].append({
                "stage": stage, "before": before, "after": after, "rule": rule_name,
                "evidence": evidence,
            })
        rule = channels.get(row["source_id"])
        if not rule:
            fail("CHANNEL_RULE_MISSING", "Confirm a rule for this channel")
        elif index in conflicts:
            fail("CONFLICTING_DUPLICATE", "Same business key has conflicting contents; review the entire group")
        elif index in duplicates:
            result["disposition"] = "duplicate"
            result["duplicate_of"] = duplicates[index]
            event("deduplicate", raw, duplicates[index], "channel + order + line; identical payload")
        else:
            fields = rule["fields"]
            get = lambda name: text(raw.get(fields.get(name, "")))
            status = get("status")
            action = rule.get("status_actions", {}).get(status)
            event("status", status, action or "exception", "confirmed exact status mapping")
            if action == "exclude":
                result["disposition"] = "excluded"
                fail("STATUS_EXCLUDED", "Excluded by confirmed channel status rule")
            elif action != "include":
                fail("MISSING_STATUS" if not status else "UNKNOWN_STATUS", "Confirm the missing or new status")
            else:
                formulas = set(row.get("formula_fields", []))
                if formulas.intersection(x for x in fields.values() if x):
                    fail("FORMULA_NOT_SUPPORTED", "Replace mapped formulas with confirmed values")
                if not get("order_id"):
                    fail("MISSING_ORDER_ID", "Provide an order identifier")
                if rule.get("dedup_mode", "business_key") == "business_key" and not get("line_id"):
                    fail("MISSING_LINE_ID", "Provide a line ID or explicitly select source-row handling")

                if flow.get("date_from") or flow.get("date_to"):
                    try:
                        day = datetime.strptime(get("date"), rule.get("date_format", "%Y-%m-%d")).date()
                        start = date.fromisoformat(flow["date_from"]) if flow.get("date_from") else None
                        end = date.fromisoformat(flow["date_to"]) if flow.get("date_to") else None
                        if (start and day < start) or (end and day > end):
                            result["disposition"] = "excluded"
                            result["reasons"] = [{"code": "DATE_EXCLUDED", "message": "Outside the approved date range"}]
                            event("date", get("date"), "excluded", "approved date range")
                            results.append(result)
                            continue
                    except (ValueError, TypeError):
                        fail("INVALID_DATE", "Confirm the date field and format")

                value = get("product")
                sku = value if value in master else flow.get("aliases", {}).get(value)
                product = master.get(sku)
                if not product:
                    fail("UNKNOWN_PRODUCT", "Provide a master SKU or confirm an alias")
                else:
                    result["sku"] = sku
                    result["product_name"] = product["name"]
                    event("product", value, sku, "exact SKU" if value == sku else "confirmed alias", {"master_sku": sku})
                quantity = None
                try:
                    quantity = positive_decimal(get("quantity"), Decimal("1000000000000"))
                    if not quantity.is_finite() or quantity <= 0:
                        raise ValueError()
                except (InvalidOperation, ValueError, TypeError):
                    fail("INVALID_QUANTITY", "Quantity must be positive, at most 1e12, with at most six decimal places")

                unit = get("unit")
                canonical_unit = flow.get("unit_aliases", {}).get(unit, unit)
                if product:
                    factor = product["factors"].get(canonical_unit)
                    if factor is None:
                        fail("UNKNOWN_UNIT", "Provide a master conversion or confirm the unit mapping")
                    elif quantity is not None and quantity.is_finite() and quantity > 0:
                        converted = quantity * factor
                        if converted != converted.to_integral_value():
                            fail("FRACTIONAL_BASE_QUANTITY", "Base-piece quantity must be an integer; no rounding is applied")
                        else:
                            result["quantity"] = decimal_text(converted)
                            result["unit"] = product["base_unit"]
                            event("quantity", {"quantity": get("quantity"), "unit": unit},
                                  {"quantity": result["quantity"], "unit": product["base_unit"]},
                                  "confirmed product master conversion",
                                  {"sku": sku, "unit": canonical_unit, "factor": decimal_text(factor)})
                if not result["reasons"]:
                    result["disposition"] = "included"
                    key = (sku, product["base_unit"])
                    if key not in totals:
                        totals[key] = {"sku": sku, "name": product["name"], "unit": product["base_unit"], "quantity": Decimal(0)}
                    totals[key]["quantity"] += Decimal(result["quantity"])
        results.append(result)
    counts = Counter(x["disposition"] for x in results)
    summary = {"input": len(rows), **{key: counts[key] for key in ("included", "excluded", "duplicate", "exception")}}
    summary["totals_match"] = len(rows) == sum(summary[x] for x in ("included", "excluded", "duplicate", "exception"))
    if not summary["totals_match"]:
        raise RuntimeError("Row accounting failed")
    sku_summary = [{**item, "quantity": decimal_text(item["quantity"])} for _, item in sorted(totals.items())]
    if sum(Decimal(x["quantity"]) for x in results if x["disposition"] == "included") != sum(Decimal(x["quantity"]) for x in sku_summary):
        raise RuntimeError("Aggregate quantity accounting failed")
    return {"rows": results, "summary": summary, "sku_summary": sku_summary}
