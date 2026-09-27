"""Read-only WHOOP cycle metadata. Calories stay on /timeseries."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes.v1.whoop_cycles import cycles_to_metadata

START = "2026-09-17T02:04:24.410000Z"
CLOSED = {
    "id": 456,
    "start": "2026-09-21T11:00:00Z",
    "end": "2026-09-22T03:00:00Z",
    "timezone_offset": "-04:00",
    "score_state": "SCORED",
    "updated_at": "2026-09-22T12:00:00Z",
    "score": {"kilojoule": 12000, "strain": 10.2},
}
OPEN = {
    "id": "123",
    "start": START,
    "end": None,
    "timezone_offset": "-04:00",
    "score_state": "SCORED",
    "updated_at": "2026-09-17T06:00:00Z",
}
LONG = {
    "id": "long",
    "start": "2026-09-21T12:00:00Z",
    "end": "2026-09-23T00:00:00Z",
    "timezone_offset": "-04:00",
    "score_state": "SCORED",
    "updated_at": "2026-09-23T01:00:00Z",
}


def test_closed_cycle_keeps_bounds_and_sets_energy_recorded_at() -> None:
    record = cycles_to_metadata([CLOSED])[0]
    assert record.cycle_id == "456"
    assert record.end is not None
    assert record.timezone_offset == "-04:00"
    assert record.score_state == "SCORED"
    assert record.energy_recorded_at == record.start
    assert not hasattr(record, "kilojoule")
    dumped = record.model_dump()
    assert "kilojoule" not in dumped
    assert "value" not in dumped


def test_open_cycle_is_kept_with_null_end() -> None:
    record = cycles_to_metadata([OPEN])[0]
    assert record.cycle_id == "123"
    assert record.end is None
    assert record.score_state == "SCORED"
    assert record.energy_recorded_at == datetime(2026, 9, 17, 2, 4, 24, 410000, tzinfo=timezone.utc)


def test_long_cycle_bounds_are_unchanged() -> None:
    record = cycles_to_metadata([LONG])[0]
    assert record.end is not None
    hours = (record.end - record.start).total_seconds() / 3600
    assert hours == pytest.approx(36)
    assert "unaligned" not in record.model_dump().values()


def test_multiple_cycles_keep_the_open_one() -> None:
    records = cycles_to_metadata([CLOSED, OPEN])
    assert [row.cycle_id for row in records] == ["456", "123"]


def test_malformed_cycle_is_dropped_without_dropping_valid_ones() -> None:
    records = cycles_to_metadata([{"score_state": "SCORED"}, "nope", CLOSED])
    assert [row.cycle_id for row in records] == ["456"]


def test_join_instant_matches_cycle_start() -> None:
    record = cycles_to_metadata([{"id": "join", "start": START}])[0]
    assert record.energy_recorded_at.isoformat() == "2026-09-17T02:04:24.410000+00:00"


def _url(prefix: str, user_id: str) -> str:
    return (
        f"{prefix}/users/{user_id}/providers/whoop/cycles?start_time=2026-09-01T00:00:00Z&end_time=2026-09-30T00:00:00Z"
    )


def test_route_requires_api_key(client: TestClient, api_v1_prefix: str) -> None:
    response = client.get(_url(api_v1_prefix, str(uuid4())))
    assert response.status_code == 401


def test_invalid_user_id_is_rejected(client: TestClient, api_v1_prefix: str, api_key_header: dict[str, str]) -> None:
    response = client.get(_url(api_v1_prefix, "not-a-uuid"), headers=api_key_header)
    assert response.status_code == 400


def test_route_returns_metadata_without_secrets(
    client: TestClient,
    api_v1_prefix: str,
    api_key_header: dict[str, str],
) -> None:
    with patch("app.services.providers.whoop.data_247.Whoop247Data.get_cycle_data", return_value=[CLOSED, OPEN]):
        response = client.get(_url(api_v1_prefix, str(uuid4())), headers=api_key_header)
    assert response.status_code == 200
    body = response.json()
    assert [row["cycle_id"] for row in body["data"]] == ["456", "123"]
    assert body["data"][1]["end"] is None
    blob = response.text.lower()
    assert "access_token" not in blob
    assert "refresh_token" not in blob
    assert "kilojoule" not in blob


def test_empty_cycles(client: TestClient, api_v1_prefix: str, api_key_header: dict[str, str]) -> None:
    with patch("app.services.providers.whoop.data_247.Whoop247Data.get_cycle_data", return_value=[]):
        response = client.get(_url(api_v1_prefix, str(uuid4())), headers=api_key_header)
    assert response.status_code == 200
    assert response.json() == {"data": []}


def test_provider_failure_hides_credentials(
    client: TestClient,
    api_v1_prefix: str,
    api_key_header: dict[str, str],
) -> None:
    with patch(
        "app.services.providers.whoop.data_247.Whoop247Data.get_cycle_data",
        side_effect=RuntimeError("boom access_token=secret-token"),
    ):
        response = client.get(_url(api_v1_prefix, str(uuid4())), headers=api_key_header)
    assert response.status_code == 502
    assert "secret-token" not in response.text
    assert response.json()["detail"] == "WHOOP cycle request failed"
