import asyncio
from datetime import UTC, datetime, timedelta
import os
from uuid import uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import LatestVehicleLocation, Preference
from app.tracking import tracking_state


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://transitops:transitops@localhost:5433/transitops").replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def auth(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": "demo"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def location_payload(*, captured_at: datetime | None = None, key: str | None = None) -> dict:
    return {"idempotency_key": key or f"test-{uuid4().hex}", "latitude": 22.55, "longitude": 72.91, "accuracy_meters": 9, "speed_mps": 8.2, "captured_at": (captured_at or datetime.now(UTC)).isoformat(), "vehicle_id": "v-car02", "driver_id": "d-samir", "trip_id": "TR-1039"}


def test_driver_start_derives_own_assignment_and_ignores_forged_trip(client: TestClient) -> None:
    headers = auth(client, "driver@transitops.demo")
    response = client.post("/api/tracking/sessions/start", headers=headers, json={"consent": True, "trip_id": "TR-1051", "driver_id": "d-vikram"})
    assert response.status_code in (200, 201)
    assert response.json()["driver_id"] == "d-rahul"
    assert response.json()["vehicle_id"] == "v-truck11"
    assert response.json()["trip_id"] == "TR-1042"


def test_financial_analyst_cannot_view_or_subscribe_to_locations(client: TestClient) -> None:
    headers = auth(client, "finance@transitops.demo")
    assert client.get("/api/tracking/fleet/latest", headers=headers).status_code == 403
    assert client.get("/api/tracking/events", headers=headers).status_code == 403


def test_manager_can_view_authorized_active_fleet(client: TestClient) -> None:
    headers = auth(client, "fleet@transitops.demo")
    response = client.get("/api/tracking/fleet/latest", headers=headers)
    assert response.status_code == 200
    vehicle_ids = {item["vehicle_id"] for item in response.json()}
    assert {"v-truck11", "v-van12", "v-truck15"}.issubset(vehicle_ids)


def test_location_associations_are_server_derived_and_idempotent(client: TestClient) -> None:
    driver_headers = auth(client, "driver@transitops.demo")
    client.post("/api/tracking/sessions/start", headers=driver_headers, json={"consent": True})
    payload = location_payload()
    first = client.post("/api/tracking/locations", headers=driver_headers, json=payload)
    duplicate = client.post("/api/tracking/locations", headers=driver_headers, json=payload)
    assert first.status_code == 202
    assert duplicate.status_code == 202 and duplicate.json()["duplicate"] is True
    manager_headers = auth(client, "fleet@transitops.demo")
    latest = client.get("/api/tracking/vehicles/v-truck11/latest", headers=manager_headers)
    assert latest.status_code == 200
    assert latest.json()["driver_id"] == "d-rahul"
    assert latest.json()["trip_id"] == "TR-1042"


def test_ended_session_rejects_points_and_can_restart_for_active_trip(client: TestClient) -> None:
    headers = auth(client, "driver.meera@transitops.demo")
    started = client.post("/api/tracking/sessions/start", headers=headers, json={"consent": True})
    ended = client.post(f"/api/tracking/sessions/{started.json()['id']}/end", headers=headers)
    assert ended.status_code == 200
    assert client.post("/api/tracking/locations", headers=headers, json=location_payload()).status_code == 409
    restarted = client.post("/api/tracking/sessions/start", headers=headers, json={"consent": True})
    assert restarted.status_code == 201 and restarted.json()["status"] == "ACTIVE"


def test_offline_batch_is_persisted_in_chronological_order(client: TestClient) -> None:
    headers = auth(client, "driver@transitops.demo")
    client.post("/api/tracking/sessions/start", headers=headers, json={"consent": True})
    base = datetime.now(UTC) - timedelta(minutes=3)
    points = [location_payload(captured_at=base + timedelta(seconds=offset), key=f"batch-{uuid4().hex}") for offset in (40, 0, 20)]
    response = client.post("/api/tracking/locations/batch", headers=headers, json={"points": points})
    assert response.status_code == 202
    history = client.get("/api/tracking/trips/TR-1042/history?limit=20", headers=headers).json()
    relevant = [item["captured_at"] for item in history if item["id"] in {result["id"] for result in response.json()["results"]}]
    assert relevant == sorted(relevant)


def test_driver_visibility_defaults_to_own_vehicle(client: TestClient) -> None:
    fleet_headers = auth(client, "fleet@transitops.demo")
    original = client.get("/api/settings", headers=fleet_headers).json()
    configured = {**original, "driver_fleet_visibility": "OWN_VEHICLE_ONLY", "allow_driver_nearby_vehicles": False}
    assert client.put("/api/settings", headers=fleet_headers, json=configured).status_code == 200
    try:
        driver_headers = auth(client, "driver@transitops.demo")
        visible = client.get("/api/tracking/my-visible-fleet", headers=driver_headers)
        assert visible.status_code == 200
        assert {item["vehicle_id"] for item in visible.json()} == {"v-truck11"}
        assert all(item["driver_name"] in (None, "Rahul Patel") for item in visible.json())
    finally:
        client.put("/api/settings", headers=fleet_headers, json=original)


def test_cross_region_history_is_blocked(client: TestClient) -> None:
    headers = auth(client, "dispatcher@transitops.demo")
    assert client.get("/api/tracking/vehicles/v-mini03/history", headers=headers).status_code == 403


def test_freshness_status_calculation() -> None:
    settings = Preference(id=1, depot_name="Demo", currency="INR", distance_unit="Kilometres", tracking_stale_seconds=60, tracking_offline_seconds=180)
    online = LatestVehicleLocation(vehicle_id="v", trip_id="t", driver_id="d", tracking_session_id="s", latitude=1, longitude=1, speed_mps=5, accuracy_meters=10, captured_at=datetime.now(UTC).replace(tzinfo=None), received_at=datetime.now(UTC).replace(tzinfo=None), freshness_status="ONLINE")
    stale = LatestVehicleLocation(vehicle_id="v", trip_id="t", driver_id="d", tracking_session_id="s", latitude=1, longitude=1, speed_mps=5, accuracy_meters=10, captured_at=datetime.now(UTC).replace(tzinfo=None), received_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=90), freshness_status="STALE")
    offline = LatestVehicleLocation(vehicle_id="v", trip_id="t", driver_id="d", tracking_session_id="s", latitude=1, longitude=1, speed_mps=5, accuracy_meters=10, captured_at=datetime.now(UTC).replace(tzinfo=None), received_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=300), freshness_status="OFFLINE")
    assert tracking_state(online, settings) == ("ONLINE", "MOVING")
    assert tracking_state(stale, settings) == ("STALE", "STOPPED")
    assert tracking_state(offline, settings) == ("OFFLINE", "STOPPED")


async def _restore_trip_1051() -> None:
    connection = await asyncpg.connect(DATABASE_URL)
    try:
        await connection.execute("UPDATE trips SET status='In Progress', completed_at=NULL WHERE id='TR-1051'")
        await connection.execute("UPDATE vehicles SET status='On Trip' WHERE id='v-truck15'")
        await connection.execute("UPDATE drivers SET status='On Trip' WHERE id='d-vikram'")
    finally:
        await connection.close()


def test_completed_trip_ends_tracking_and_rejects_new_points(client: TestClient) -> None:
    driver_headers = auth(client, "driver.vikram@transitops.demo")
    client.post("/api/tracking/sessions/start", headers=driver_headers, json={"consent": True})
    dispatcher_headers = auth(client, "dispatcher@transitops.demo")
    completed = client.post("/api/trips/TR-1051/complete", headers=dispatcher_headers)
    assert completed.status_code == 200
    assert client.post("/api/tracking/locations", headers=driver_headers, json=location_payload()).status_code == 409
    asyncio.run(_restore_trip_1051())
    restarted = client.post("/api/tracking/sessions/start", headers=driver_headers, json={"consent": True})
    assert restarted.status_code == 201
