from fastapi.testclient import TestClient

from app.main import app


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": "demo"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_every_demo_role_receives_scoped_dashboard_shape() -> None:
    expected = {
        "fleet@transitops.demo": ("Fleet Manager", "fleet.read"),
        "dispatcher@transitops.demo": ("Dispatcher", "trip.dispatch"),
        "safety@transitops.demo": ("Safety Officer", "safety.manage"),
        "finance@transitops.demo": ("Financial Analyst", "finance.read"),
        "admin@transitops.demo": ("Administrator", "users.manage"),
        "driver@transitops.demo": ("Driver", "driver.home"),
    }
    with TestClient(app) as client:
        dashboard_keys: dict[str, tuple[str, ...]] = {}
        for email, (role, permission) in expected.items():
            response = client.get("/api/dashboard", headers=login(client, email))
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["role"] == role
            assert payload["generated_at"]
            assert set(payload) == {"role", "generated_at", "scope", "filter_options", "permissions", "kpis", "tasks", "alerts", "widgets"}
            assert permission in payload["permissions"]
            assert 2 <= len(payload["kpis"]) <= 5
            dashboard_keys[role] = tuple(item["key"] for item in payload["kpis"])
        assert len(set(dashboard_keys.values())) == len(expected)


def test_cross_role_read_permissions_are_enforced() -> None:
    with TestClient(app) as client:
        dispatcher = login(client, "dispatcher@transitops.demo")
        safety = login(client, "safety@transitops.demo")
        finance = login(client, "finance@transitops.demo")
        driver = login(client, "driver@transitops.demo")
        assert client.get("/api/finance", headers=dispatcher).status_code == 403
        assert client.get("/api/analytics", headers=safety).status_code == 403
        assert client.get("/api/vehicles", headers=safety).status_code == 403
        assert client.get("/api/drivers", headers=finance).status_code == 403
        assert client.get("/api/trips", headers=finance).status_code == 403
        assert client.get("/api/maintenance", headers=driver).status_code == 403


def test_list_and_detail_vehicle_permissions_are_consistent() -> None:
    with TestClient(app) as client:
        finance = login(client, "finance@transitops.demo")
        assert client.get("/api/vehicles", headers=finance).status_code == 403
        assert client.get("/api/vehicles/v-van05", headers=finance).status_code == 403


def test_dashboard_filter_validation_and_region_scope() -> None:
    with TestClient(app) as client:
        dispatcher = login(client, "dispatcher@transitops.demo")
        assert client.get("/api/dashboard?region=x", headers=dispatcher).status_code == 422
        payload = client.get("/api/dashboard?region=Ahmedabad", headers=dispatcher).json()
        assert payload["scope"]["region"] == "Ahmedabad"
        assert client.get("/api/dashboard?region=Mumbai", headers=dispatcher).status_code == 403
        filtered = client.get("/api/dashboard?vehicle_type=Truck", headers=dispatcher)
        assert filtered.status_code == 200
        assert filtered.json()["scope"]["vehicle_type"] == "Truck"


def test_role_scoped_alert_visibility() -> None:
    with TestClient(app) as client:
        finance = login(client, "finance@transitops.demo")
        safety = login(client, "safety@transitops.demo")
        assert client.get("/api/alerts", headers=finance).json()["alerts"] == []
        assert all(item["entity_type"] == "driver" for item in client.get("/api/alerts", headers=safety).json()["alerts"])


def test_permission_summary_uses_effective_backend_policy() -> None:
    with TestClient(app) as client:
        safety = login(client, "safety@transitops.demo")
        payload = client.get("/api/auth/permissions", headers=safety).json()
        assert payload["role"] == "Safety Officer"
        assert "safety.manage" in payload["permissions"]
        assert "finance.read" not in payload["permissions"]


def test_analytics_filters_export_and_cost_definition_are_consistent() -> None:
    with TestClient(app) as client:
        finance_headers = login(client, "finance@transitops.demo")
        finance = client.get("/api/finance", headers=finance_headers).json()
        analytics = client.get("/api/analytics", headers=finance_headers).json()
        assert analytics["metrics"]["operationalCost"] == finance["operationalCost"]
        assert analytics["generated_at"]
        assert all(item["month"].count("-") == 1 for item in analytics["revenue"])
        vehicle_id = analytics["filterOptions"]["vehicles"][0]["id"]
        filtered = client.get(f"/api/analytics?vehicle_id={vehicle_id}", headers=finance_headers)
        assert filtered.status_code == 200
        assert filtered.json()["scope"]["vehicle_id"] == vehicle_id
        assert len(filtered.json()["costliestVehicles"]) == 1
        assert len(filtered.json()["filterOptions"]["vehicles"]) == len(analytics["filterOptions"]["vehicles"])
        exported = client.get(f"/api/analytics/export?vehicle_id={vehicle_id}", headers=finance_headers)
        assert exported.status_code == 200
        assert exported.headers["content-type"].startswith("text/csv")
        assert len(exported.text.strip().splitlines()) == 2
        assert client.get("/api/analytics?date_from=2026-07-12&date_to=2026-01-01", headers=finance_headers).status_code == 422


def test_licence_expiry_windows_are_configurable_and_validated() -> None:
    with TestClient(app) as client:
        fleet = login(client, "fleet@transitops.demo")
        settings = client.get("/api/settings", headers=fleet).json()
        assert settings["license_expiry_warning_days"] >= settings["license_expiry_critical_days"]
        settings["license_expiry_warning_days"] = 7
        settings["license_expiry_critical_days"] = 14
        assert client.put("/api/settings", headers=fleet, json=settings).status_code == 422
