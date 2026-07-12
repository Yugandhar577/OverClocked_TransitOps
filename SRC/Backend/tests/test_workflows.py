from fastapi.testclient import TestClient

from app.main import app, store


client = TestClient(app)


def auth(email: str = "dispatcher@transitops.demo") -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": "demo"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_dashboard_requires_sign_in() -> None:
    assert client.get("/api/dashboard").status_code == 401


def test_dispatch_and_complete_release_resources() -> None:
    headers = auth()
    trip = next(item for item in store.trips if item["id"] == "TR-1043")
    vehicle = next(item for item in store.vehicles if item["id"] == trip["vehicle_id"])
    driver = next(item for item in store.drivers if item["id"] == trip["driver_id"])
    trip["status"], vehicle["status"], driver["status"] = "Draft", "Available", "Available"

    assert client.post("/api/trips/TR-1043/dispatch", headers=headers).status_code == 200
    assert (trip["status"], vehicle["status"], driver["status"]) == ("Dispatched", "On Trip", "On Trip")

    assert client.post("/api/trips/TR-1043/complete", headers=headers).status_code == 200
    assert (trip["status"], vehicle["status"], driver["status"]) == ("Completed", "Available", "Available")


def test_expired_driver_is_blocked_at_dispatch() -> None:
    headers = auth()
    payload = {
        "source": "Ahmedabad", "destination": "Surat", "vehicle_id": "v-van05", "driver_id": "d-neha",
        "cargo_kg": 250, "planned_distance_km": 265, "revenue": 10000,
    }
    draft = client.post("/api/trips", headers=headers, json=payload)
    assert draft.status_code == 201
    response = client.post(f"/api/trips/{draft.json()['id']}/dispatch", headers=headers)
    assert response.status_code == 409
    assert "expired" in response.json()["detail"]


def test_active_maintenance_blocks_vehicle() -> None:
    headers = auth("fleet@transitops.demo")
    vehicle = next(item for item in store.vehicles if item["id"] == "v-van05")
    vehicle["status"] = "Available"
    created = client.post("/api/maintenance", headers=headers, json={"vehicle_id": "v-van05", "service_type": "Tyre check", "cost": 950, "notes": "Safety inspection"})
    assert created.status_code == 201
    assert vehicle["status"] == "In Shop"
    closed = client.post(f"/api/maintenance/{created.json()['id']}/close", headers=headers)
    assert closed.status_code == 200
    assert vehicle["status"] == "Available"


def test_fleet_manager_can_save_preferences_and_export_analytics() -> None:
    headers = auth("fleet@transitops.demo")
    saved = client.put("/api/settings", headers=headers, json={"depot_name": "Ahmedabad Depot", "currency": "INR", "distance_unit": "Kilometres"})
    assert saved.status_code == 200
    assert saved.json()["depot_name"] == "Ahmedabad Depot"
    exported = client.get("/api/analytics/export", headers=headers)
    assert exported.status_code == 200
    assert "vehicle,operational_cost" in exported.text


def test_retirement_is_blocked_for_active_maintenance() -> None:
    headers = auth("fleet@transitops.demo")
    response = client.post("/api/vehicles/v-mini03/retire", headers=headers)
    assert response.status_code == 409
