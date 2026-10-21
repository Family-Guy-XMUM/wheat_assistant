"""Team-created synthetic fixtures, generated as real input files."""
import csv
import io
from copy import deepcopy
from datetime import date, timedelta
from openpyxl import Workbook

PRODUCTS = [
    {"sku": "TEA-001", "name": "Jasmine tea 500 g", "base_unit": "piece", "unit_factors": {"piece": "1", "box": "12", "pack": "6"}},
    {"sku": "SOAP-002", "name": "Dish soap 1 L", "base_unit": "piece", "unit_factors": {"piece": "1", "box": "6", "pack": "3"}},
    {"sku": "RICE-003", "name": "Rice 5 kg", "base_unit": "piece", "unit_factors": {"piece": "1", "box": "4"}},
]
CHANNELS = {
    "channel-a": {"label": "Channel A", "headers": ["Order ID", "Line", "Item Code", "Qty", "Unit", "Order Status", "Date"],
                  "known": {"Confirmed": "include", "Cancelled": "exclude", "Shipped": "exclude"}},
    "channel-b": {"label": "Channel B", "headers": ["OrderNo", "DetailNo", "Product", "Quantity", "UOM", "Status", "PlacedOn"],
                  "known": {"Paid": "include", "Cancelled": "exclude", "Dispatched": "exclude"}},
    "manual": {"label": "Manual orders", "headers": ["Ref", "LineNo", "Item", "Count", "Pack", "State", "OrderDate"],
               "known": {"ready": "include", "void": "exclude", "shipped": "exclude"}},
}

def csv_bytes(headers, rows):
    target = io.StringIO()
    writer = csv.writer(target)
    writer.writerow(headers)
    writer.writerows(rows)
    return target.getvalue().encode("utf-8-sig")

def workbook_bytes(headers, rows=()):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet.append(headers)
    for row in rows:
        sheet.append(list(row))
    workbook.properties.creator = "MaiZi"
    workbook.properties.lastModifiedBy = "MaiZi"
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()

def demo_files(week):
    if week not in (1, 2, 3):
        raise ValueError("Choose demo week 1, 2 or 3")
    day = (date(2026, 10, 5) + timedelta(days=(week - 1) * 7)).isoformat()
    prefix = "W" + str(week)
    output = []
    for channel, settings in CHANNELS.items():
        rows = []
        eligible = next(key for key, action in settings["known"].items() if action == "include")
        for index in range(1, 9):
            sku = PRODUCTS[(index - 1) % 3]["sku"]
            unit = "carton" if channel == "channel-b" and index == 2 else ("box" if index % 3 == 0 else "piece")
            if channel == "manual" and index == 1:
                sku = "Jasmine500"
            rows.append([prefix + "-" + channel + "-" + str(index).zfill(3), "1", sku, str(index % 4 + 1), unit, eligible, day])
        if week < 3:
            excluded = next(key for key, action in settings["known"].items() if action == "exclude")
            rows.append([prefix + "-" + channel + "-C01", "1", "", "", "", excluded, day])
            rows.append(deepcopy(rows[0]))
        if channel == "channel-a" and week < 3:
            rows.extend([
                [prefix + "-A-CONFLICT", "1", "TEA-001", "1", "piece", eligible, day],
                [prefix + "-A-CONFLICT", "1", "TEA-001", "2", "piece", eligible, day],
                [prefix + "-A-MISSING", "", "TEA-001", "1", "piece", eligible, day],
            ])
        if channel == "manual" and week < 3:
            rows.extend([
                [prefix + "-M-UNKNOWN", "1", "NOT-IN-MASTER", "2", "piece", eligible, day],
                [prefix + "-M-UNIT", "1", "SOAP-002", "2", "bundle", eligible, day],
                [prefix + "-M-QTY", "1", "RICE-003", "0.5", "piece", eligible, day],
            ])
        if channel == "channel-b" and week == 2:
            rows.extend([[prefix + "-B-PART-" + str(i), "1", "SOAP-002", "2", "piece", "Partially shipped", day] for i in range(1, 4)])
        headers = settings["headers"]
        if week == 3:
            # Same names, different positions and a new unused column.
            permutation = [5, 0, 2, 1, 4, 3, 6]
            rows = [[row[i] for i in permutation] + ["Synthetic note"] for row in rows]
            headers = [headers[i] for i in permutation] + ["Notes"]
        output.append({"name": prefix + "_" + channel + ".csv", "role": "orders", "channel_id": channel,
                       "content": csv_bytes(headers, rows)})
    master_rows = [[x["sku"], x["name"], x["base_unit"], x["unit_factors"].get("box", ""), x["unit_factors"].get("pack", "")] for x in PRODUCTS]
    output.append({"name": "Synthetic_product_master.xlsx", "role": "master", "channel_id": "",
                   "content": workbook_bytes(["SKU", "Name", "Base unit", "Box size", "Pack size"], master_rows)})
    output.append({"name": "Warehouse_template.xlsx", "role": "template", "channel_id": "",
                   "content": workbook_bytes(["SKU", "Description", "Pick quantity", "Unit"])})
    return output
