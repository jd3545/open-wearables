"""Read-only WHOOP physiological-cycle metadata.

The numeric burn source remains ``GET /users/{user_id}/timeseries`` ``active_energy``.
This route only returns the period facts Calyx needs to align that daily total.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.database import DbSession
from app.schemas.providers.whoop.cycle_metadata import WhoopCycleMetadata, WhoopCycleMetadataResponse
from app.services import ApiKeyDep
from app.services.providers.factory import ProviderFactory
from app.services.providers.whoop.data_247 import Whoop247Data
from app.utils.dates import DateTimeQueryParam, parse_query_datetime, parse_query_end_datetime

logger = logging.getLogger(__name__)

router = APIRouter()


def cycles_to_metadata(raw_cycles: list[Any]) -> list[WhoopCycleMetadata]:
    """Map raw WHOOP cycle objects. Skip rows missing id or start."""
    records: list[WhoopCycleMetadata] = []
    for raw in raw_cycles:
        if not isinstance(raw, dict):
            logger.warning("Skipping non-object WHOOP cycle payload")
            continue
        cycle_id = raw.get("id")
        start_raw = raw.get("start")
        if cycle_id is None or not start_raw:
            logger.warning("Skipping WHOOP cycle missing id or start")
            continue
        start = _parse_dt(start_raw)
        if start is None:
            logger.warning("Skipping WHOOP cycle %s with unparseable start", cycle_id)
            continue
        records.append(
            WhoopCycleMetadata(
                cycle_id=str(cycle_id),
                start=start,
                end=_parse_dt(raw.get("end")),
                timezone_offset=raw.get("timezone_offset"),
                score_state=raw.get("score_state"),
                updated_at=_parse_dt(raw.get("updated_at")),
                energy_recorded_at=start,
            )
        )
    return records


def _parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


@router.get("/users/{user_id}/providers/whoop/cycles")
def get_whoop_cycles(
    user_id: UUID,
    start_time: DateTimeQueryParam,
    end_time: DateTimeQueryParam,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> WhoopCycleMetadataResponse:
    """Return WHOOP cycle bounds already fetched by the provider. No calorie fields."""
    provider = ProviderFactory().get_provider("whoop")
    data_247 = provider.data_247
    if not isinstance(data_247, Whoop247Data):
        raise HTTPException(status_code=502, detail="WHOOP cycle request failed")
    try:
        raw = data_247.get_cycle_data(
            db,
            user_id,
            parse_query_datetime(start_time),
            parse_query_end_datetime(end_time),
        )
    except Exception:
        logger.exception("WHOOP cycle metadata request failed for user %s", user_id)
        raise HTTPException(status_code=502, detail="WHOOP cycle request failed") from None
    return WhoopCycleMetadataResponse(data=cycles_to_metadata(raw or []))
