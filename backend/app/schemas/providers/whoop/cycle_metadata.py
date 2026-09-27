"""Safe WHOOP physiological-cycle metadata for external consumers.

Numeric burn stays on ``/timeseries``. This schema never carries kilojoules or kcal.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WhoopCycleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_id: str
    start: datetime
    end: datetime | None = None
    timezone_offset: str | None = None
    score_state: str | None = None
    updated_at: datetime | None = None
    energy_recorded_at: datetime


class WhoopCycleMetadataResponse(BaseModel):
    data: list[WhoopCycleMetadata]
