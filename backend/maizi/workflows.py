"""Workflow identity and review diffs, separate from immutable FlowSpec hashes."""
from maizi.store import digest


def metadata(flow):
    return {**flow, "workflow_id": flow.get("workflow_id", flow["id"]),
            "rule_version": flow.get("rule_version", 1), "parent_flow_id": flow.get("parent_flow_id")}


def table_identity(table):
    return {"headers": table["headers"], "sheet": table["sheet"],
            "blank_rows": table.get("blank_rows", 0),
            "records": [{key: row.get(key, [] if key == "formula_fields" else None)
                         for key in ("row_number", "data", "formula_fields")} for row in table["records"]]}


def review_diff(source, current, assets, old_assets):
    keys = {"fields": lambda spec: {name: {"fields": rule["fields"], "date_format": rule.get("date_format", "%Y-%m-%d")}
                                  for name, rule in spec["channels"].items()},
            "statuses": lambda spec: {name: rule["status_actions"] for name, rule in spec["channels"].items()},
            "products": lambda spec: {"aliases": spec.get("aliases", {}), "master": spec.get("master_fields", {})},
            "units": lambda spec: {"aliases": spec.get("unit_aliases", {}), "master": spec.get("master_fields", {})},
            "duplicates": lambda spec: {name: rule.get("dedup_mode") for name, rule in spec["channels"].items()},
            "output": lambda spec: {key: spec.get(key) for key in ("output_columns", "date_from", "date_to")}}
    previous = source["spec"] if source else None
    groups = [{"group": name, "changed": previous is None or digest(getter(previous)) != digest(getter(current)),
               "before": getter(previous) if previous else None, "after": getter(current)} for name, getter in keys.items()]
    inputs = []
    if source:
        for role, affected in (("master", ("products", "units")), ("template", ("output",))):
            before = [x["hash"] for x in old_assets if x["role"] == role]
            after = [x["hash"] for x in assets if x["role"] == role]
            if before != after:
                inputs.append({"kind": role, "message": "Product master changed" if role == "master" else "Warehouse template changed"})
                for group in groups:
                    if group["group"] in affected:
                        group["changed"] = True
        def structures(collection):
            result = {}
            for asset in collection:
                if asset["role"] == "orders":
                    result.setdefault(asset["channel_id"], set()).add(tuple(asset["table"]["headers"]))
            return result
        before_sources, after_sources = structures(old_assets), structures(assets)
        for channel in sorted(before_sources.keys() | after_sources.keys()):
            if channel not in before_sources:
                inputs.append({"kind": "new_source", "message": "New source: " + channel})
            elif channel not in after_sources:
                inputs.append({"kind": "removed_source", "message": "Source removed from this batch: " + channel})
            elif before_sources[channel] != after_sources[channel]:
                inputs.append({"kind": "structure", "message": "Columns changed in source: " + channel})
            previous_files = [x for x in old_assets if x["role"] == "orders" and x["channel_id"] == channel]
            current_files = [x for x in assets if x["role"] == "orders" and x["channel_id"] == channel]
            if previous_files and current_files and sorted(x["hash"] for x in previous_files) != sorted(x["hash"] for x in current_files):
                previous_rows = sum(len(x["table"].get("records", [])) for x in previous_files)
                current_rows = sum(len(x["table"].get("records", [])) for x in current_files)
                inputs.append({"kind": "source_inputs", "message": f"Inputs changed in {channel}: {len(previous_files)} files / {previous_rows} rows → {len(current_files)} files / {current_rows} rows"})
    return {"groups": groups, "inputs": inputs, "source_flow_id": source["id"] if source else None}
