from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Fields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: str
    line_id: str | None = None
    product: str
    quantity: str
    unit: str
    status: str
    date: str | None = None

class ChannelRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: Fields
    status_actions: dict[str, Literal["include", "exclude"]]
    dedup_mode: Literal["business_key", "source_row"] = "business_key"
    date_format: Literal["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"] = "%Y-%m-%d"

class OutputColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    header: str = Field(min_length=1, max_length=100)
    field: Literal["sku", "name", "quantity", "unit"]

class FlowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    name: str = Field(default="Weekly picking preparation", min_length=1, max_length=100)
    channels: dict[str, ChannelRule]
    aliases: dict[str, str] = Field(default_factory=dict)
    unit_aliases: dict[str, str] = Field(default_factory=dict)
    master_fields: dict[str, str] = Field(default_factory=lambda: {
        "sku": "SKU", "name": "Name", "base_unit": "Base unit",
        "box": "Box size", "pack": "Pack size"
    })
    output_columns: list[OutputColumn] = Field(default_factory=lambda: [
        OutputColumn(header="SKU", field="sku"),
        OutputColumn(header="Description", field="name"),
        OutputColumn(header="Pick quantity", field="quantity"),
        OutputColumn(header="Unit", field="unit"),
    ])
    date_from: str | None = None
    date_to: str | None = None

    @model_validator(mode="after")
    def check_dates(self):
        from datetime import date
        start = date.fromisoformat(self.date_from) if self.date_from else None
        end = date.fromisoformat(self.date_to) if self.date_to else None
        if start and end and start > end:
            raise ValueError("Start date must not be after end date")
        if not self.channels:
            raise ValueError("At least one channel is required")
        if not self.output_columns or len({x.header for x in self.output_columns}) != len(self.output_columns):
            raise ValueError("Output headers must be non-empty and unique")
        return self

class PlanRequest(BaseModel):
    instructions: str = Field(default="", max_length=8000)
    mode: Literal["suggested", "live"] = "suggested"
    flow: FlowSpec | None = None
    source_flow_id: str | None = None

class HeldStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel_id: str
    field: str
    value: str

class ApproveRequest(BaseModel):
    flow: FlowSpec
    reviewed: list[str]
    expected_input_hash: str
    source_flow_id: str | None = None
    draft_id: str | None = None
    held_statuses: list[HeldStatus] = Field(default_factory=list, max_length=10000)
    hold_review_hash: str | None = None

class RunRequest(BaseModel):
    batch_id: str
    flow_id: str
    expected_snapshot: str | None = None

class ExportApproval(BaseModel):
    result_hash: str
    acknowledge_exceptions: bool = False

REVIEW_GROUPS = {"fields", "statuses", "products", "units", "duplicates", "output"}
