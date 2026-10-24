"""Provider shape, repair, accounting and redaction boundaries without real requests."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from wheat_assistant.models import FlowSpec
from wheat_assistant import planner
from wheat_assistant.store import Store


def materials():
    fields = dict(order_id="Order", line_id="Line", product="SKU", quantity="Qty", unit="Unit", status="Status", date=None)
    flow = FlowSpec.model_validate({"channels": {"source": {"fields": fields, "status_actions": {"Confirmed": "include"}}}}).model_dump()
    assets = [{"role": "orders", "channel_id": "source", "profile": {}, "table": {"headers": [x for x in fields.values() if x]}}]
    return assets, flow


def completion(content, **choice):
    return {"choices": [{"message": {"content": json.dumps(content) if isinstance(content, dict) else content}, **choice}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 3, "total_tokens": 11}}


def install_provider(monkeypatch, responses):
    for key, value in {"LLM_BASE_URL": "https://synthetic.invalid/v1", "LLM_MODEL": "synthetic-model", "LLM_API_KEY": "synthetic-private-key"}.items():
        monkeypatch.setenv(key, value)
    calls = []

    class Response:
        status_code = 200
        def __init__(self, body): self.body = body
        def json(self): return self.body

    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            calls.append(copy.deepcopy(kwargs["json"]))
            return Response(responses[min(len(calls) - 1, len(responses) - 1)])

    monkeypatch.setattr(planner.httpx, "Client", Client)
    return calls


@pytest.mark.parametrize("bad,code", [
    ({"choices": []}, "missing_choices"),
    (completion(None), "empty_or_non_text_output"),
    (completion([{"text": "not plain text"}]), "empty_or_non_text_output"),
    (completion("{", finish_reason="length"), "truncated_output"),
    ({"choices": [{"message": {"tool_calls": [{"function": {"name": "do_not_execute"}}]}}]}, "unexpected_tool_call"),
])
def test_invalid_shapes_are_repaired_once_with_accounting(tmp_path, monkeypatch, bad, code):
    assets, flow = materials()
    calls = install_provider(monkeypatch, [bad, completion({"flow": flow}, finish_reason="stop")])
    with Store(tmp_path) as store:
        result = planner.propose_live(store, {"id": "synthetic"}, assets, "Synthetic instruction", flow)
        usage = list(reversed(store.list("usage")))
    assert result["flow"] == flow and result["origin"] == "live_ai"
    assert len(calls) == 2
    assert [entry["status"] for entry in usage] == ["invalid_output", "succeeded"]
    assert usage[0]["validation_issues"][0]["type"] == code
    assert usage[1]["finish_reason"] == "stop" and usage[1]["tokens"]["total_tokens"] == 11
    assert all(entry["duration_ms"] >= 0 and entry["prompt_hash"] and entry["schema_hash"] for entry in usage)


def test_repair_does_not_retry_forever_or_publish_unknown_keys(tmp_path, monkeypatch):
    assets, flow = materials()
    private = "SYNTHETIC_PRIVATE_FIELD_9271"
    bad = completion({"flow": flow, private: "synthetic private value"}, finish_reason="stop")
    calls = install_provider(monkeypatch, [bad])
    with Store(tmp_path) as store:
        with pytest.raises(ValueError, match="JSON structure"):
            planner.propose_live(store, {"id": "synthetic"}, assets, "", flow)
        usage = store.list("usage")
    assert len(calls) == 2 and len(usage) == 2
    assert all(entry["status"] == "invalid_output" for entry in usage)
    assert private not in json.dumps(usage) and "synthetic-private-key" not in json.dumps(usage)
    assert all(entry["tokens"]["total_tokens"] == 11 for entry in usage)


def test_refusal_is_visible_and_not_retried(tmp_path, monkeypatch):
    assets, flow = materials()
    calls = install_provider(monkeypatch, [{"choices": [{"message": {"refusal": "synthetic private refusal", "content": None}}]}])
    with Store(tmp_path) as store:
        with pytest.raises(ValueError, match="declined"):
            planner.propose_live(store, {"id": "synthetic"}, assets, "", flow)
        usage = store.list("usage")
    assert len(calls) == 1 and usage[0]["status"] == "invalid_output"
    assert "synthetic private refusal" not in json.dumps(usage)


@pytest.mark.parametrize("problem", ["missing_channel", "unknown_column", "hold_action"])
def test_bad_workflow_references_cannot_be_accepted(tmp_path, monkeypatch, problem):
    assets, flow = materials()
    bad = copy.deepcopy(flow)
    if problem == "missing_channel":
        assets.append({**assets[0], "channel_id": "second"})
        good = {**flow, "channels": {**flow["channels"], "second": copy.deepcopy(flow["channels"]["source"])}}
    else:
        good = flow
        if problem == "unknown_column": bad["channels"]["source"]["fields"]["quantity"] = "Invented"
        else: bad["channels"]["source"]["status_actions"]["Unconfirmed"] = "hold"
    calls = install_provider(monkeypatch, [completion({"flow": bad}), completion({"flow": good})])
    with Store(tmp_path) as store:
        result = planner.propose_live(store, {"id": "synthetic"}, assets, "", flow)
    assert len(calls) == 2 and result["flow"] == good


def test_experiment_budget_survives_reopening_and_dates(tmp_path):
    path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_planner.py"
    spec = importlib.util.spec_from_file_location("synthetic_planner_evaluation", path)
    evaluation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluation)
    with evaluation.EvaluationStore(tmp_path, 1) as store:
        item = store.add("usage", {"status": "invalid_output"})
        store.put("usage", item["id"], {**item, "created_at": "2000-01-01T00:00:00Z"})
    with evaluation.EvaluationStore(tmp_path, 1) as store:
        with pytest.raises(ValueError, match="experiment request budget"):
            store.add("usage", {"status": "requested"})
        assert len(store.list("usage")) == 1


@pytest.mark.parametrize("action", ["include", "exclude"])
def test_unconfirmed_status_must_stay_held_even_when_model_says_exclude(tmp_path, monkeypatch, action):
    assets, flow = materials()
    flow["channels"]["source"]["status_actions"] = {}
    bad = copy.deepcopy(flow)
    bad["channels"]["source"]["status_actions"] = {"Partially shipped": action}
    calls = install_provider(monkeypatch, [completion({"flow": bad}), completion({"flow": flow})])
    with Store(tmp_path) as store:
        value = planner.propose_live(store, {"id": "synthetic"}, assets, "Hold partially shipped", flow)
        usage = list(reversed(store.list("usage")))
    assert len(calls) == 2 and value["flow"]["channels"]["source"]["status_actions"] == {}
    assert usage[0]["validation_issues"][0]["type"] == "unconfirmed_status_requires_hold"


def test_existing_explicit_unknown_status_decision_is_preserved(tmp_path, monkeypatch):
    assets, flow = materials()
    flow["channels"]["source"]["status_actions"]["Partially shipped"] = "exclude"
    calls = install_provider(monkeypatch, [completion({"flow": flow})])
    with Store(tmp_path) as store:
        value = planner.propose_live(store, {"id": "synthetic"}, assets, "Reuse the approved draft", flow)
    assert len(calls) == 1 and value["flow"] == flow
