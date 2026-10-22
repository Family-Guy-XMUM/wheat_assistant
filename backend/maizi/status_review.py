"""Explicit per-batch Hold decisions, separate from FlowSpec v1 rules."""
from collections import Counter

from maizi.store import digest


class StatusReviewRequired(ValueError):
    code = "STATUS_REVIEW_REQUIRED"


def hold_review(batch_id, input_hash, spec, source_flow_id, guard):
    counts = Counter((item["channel_id"], item["field"], str(item["value"]))
                     for item in guard["issues"]
                     if item["code"] in {"UNKNOWN_STATUS", "MISSING_STATUS"})
    groups = [{"channel_id": channel, "field": field, "value": value, "count": count}
              for (channel, field, value), count in sorted(counts.items())]
    return {"required": bool(groups), "groups": groups, "snapshot_hash": digest({
        "batch_id": batch_id, "input_hash": input_hash, "spec": spec,
        "source_flow_id": source_flow_id, "groups": groups})}


def confirm_holds(review, held_statuses, review_hash):
    keys = [(x["channel_id"], x["field"], x["value"]) for x in held_statuses]
    expected = [(x["channel_id"], x["field"], x["value"]) for x in review["groups"]]
    wanted_hash = review["snapshot_hash"] if expected else None
    if len(keys) != len(set(keys)) or sorted(keys) != sorted(expected) or review_hash != wanted_hash:
        raise StatusReviewRequired("Review every unconfirmed status. Explicitly hold it as an exception, include or exclude it, then check this batch again.")
    return [{"channel_id": channel, "field": field, "value": value}
            for channel, field, value in sorted(keys)]
