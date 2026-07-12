import asyncio
import os

import asyncpg
import pytest
from fastapi.testclient import TestClient


async def can_connect() -> bool:
    database_url = os.getenv("DATABASE_URL", "postgresql://transitops:transitops@localhost:5433/transitops").replace("postgresql+asyncpg://", "postgresql://")
    try:
        connection = await asyncpg.connect(database_url, timeout=0.5)
        await connection.close()
        return True
    except (OSError, asyncpg.PostgresError):
        return False


if not asyncio.run(can_connect()):
    pytest.skip("PostgreSQL is required for database integration tests. Start `docker compose up --build` first.", allow_module_level=True)

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def auth(client: TestClient, email: str = "dispatcher@transitops.demo") -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": "demo"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_dashboard_requires_sign_in(client: TestClient) -> None:
    assert client.get("/api/dashboard").status_code == 401


def test_dispatch_and_complete_release_resources(client: TestClient) -> None:
    headers = auth(client)
    payload = {"source": "Ahmedabad", "destination": "Gandhinagar", "vehicle_id": "v-van05", "driver_id": "d-alex", "cargo_kg": 250, "planned_distance_km": 30, "revenue": 2500}
    created = client.post("/api/trips", headers=headers, json=payload)
    assert created.status_code == 201
    trip_id = created.json()["id"]

    assert client.post(f"/api/trips/{trip_id}/dispatch", headers=headers).status_code == 200
    vehicle = next(item for item in client.get("/api/vehicles", headers=headers).json() if item["id"] == "v-van05")
    driver = next(item for item in client.get("/api/drivers", headers=headers).json() if item["id"] == "d-alex")
    assert (vehicle["status"], driver["status"]) == ("On Trip", "On Trip")

    assert client.post(f"/api/trips/{trip_id}/complete", headers=headers).status_code == 200
    vehicle = next(item for item in client.get("/api/vehicles", headers=headers).json() if item["id"] == "v-van05")
    driver = next(item for item in client.get("/api/drivers", headers=headers).json() if item["id"] == "d-alex")
    assert (vehicle["status"], driver["status"]) == ("Available", "Available")


def test_expired_driver_is_blocked_at_dispatch(client: TestClient) -> None:
    headers = auth(client)
    payload = {"source": "Ahmedabad", "destination": "Surat", "vehicle_id": "v-van05", "driver_id": "d-neha", "cargo_kg": 250, "planned_distance_km": 265, "revenue": 10000}
    draft = client.post("/api/trips", headers=headers, json=payload)
    assert draft.status_code == 201
    response = client.post(f"/api/trips/{draft.json()['id']}/dispatch", headers=headers)
    assert response.status_code == 409
    assert "expired" in response.json()["detail"]


def test_active_maintenance_blocks_vehicle(client: TestClient) -> None:
    headers = auth(client, "fleet@transitops.demo")
    created = client.post("/api/maintenance", headers=headers, json={"vehicle_id": "v-van05", "service_type": "Tyre check", "cost": 950, "notes": "Safety inspection"})
    assert created.status_code == 201
    assert client.post(f"/api/maintenance/{created.json()['id']}/close", headers=headers).status_code == 200
    vehicle = next(item for item in client.get("/api/vehicles", headers=headers).json() if item["id"] == "v-van05")
    assert vehicle["status"] == "Available"


def test_fleet_manager_can_save_preferences_and_export_analytics(client: TestClient) -> None:
    headers = auth(client, "fleet@transitops.demo")
    saved = client.put("/api/settings", headers=headers, json={"depot_name": "Ahmedabad Depot", "currency": "INR", "distance_unit": "Kilometres"})
    assert saved.status_code == 200
    exported = client.get("/api/analytics/export", headers=headers)
    assert exported.status_code == 200
    assert "vehicle,operational_cost" in exported.text


def test_retirement_is_blocked_for_active_maintenance(client: TestClient) -> None:
    headers = auth(client, "fleet@transitops.demo")
    response = client.post("/api/vehicles/v-mini03/retire", headers=headers)
    assert response.status_code == 409
