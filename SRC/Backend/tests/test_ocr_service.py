from app.services.ocr_service import parse_fuel_receipt
from app.main import app
from fastapi.testclient import TestClient


def auth(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": "finance@transitops.demo", "password": "demo"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_parse_receipt_extracts_fuel_fields() -> None:
    parsed = parse_fuel_receipt(
        "Indian Oil Petrol Pump\n"
        "Receipt No: IOCL-12345\n"
        "Qty 5.42 L\n"
        "Rate 112.69/L\n"
        "Total Rs. 610.80\n"
        "12/07/2026"
    )

    assert parsed == {
        "stationName": "Indian Oil Petrol Pump",
        "liters": 5.42,
        "pricePerLiter": 112.69,
        "totalAmount": 610.8,
        "date": "2026-07-12",
        "receiptNumber": "IOCL-12345",
        "odometerKm": None,
        "sourceType": "receipt",
    }


def test_parse_meter_derives_rate_when_missing() -> None:
    parsed = parse_fuel_receipt("PETROL DISPENSED\nVolume 20.0 L\nTotal Amount Rs. 1500")

    assert parsed["sourceType"] == "meter"
    assert parsed["liters"] == 20
    assert parsed["totalAmount"] == 1500
    assert parsed["pricePerLiter"] == 75


def test_parse_receipt_derives_missing_liters_and_total() -> None:
    missing_liters = parse_fuel_receipt("Rate Rs. 100/L\nTotal Amount Rs. 1250")
    missing_total = parse_fuel_receipt("Qty 15.5 L\nRate 96/L")

    assert missing_liters["liters"] == 12.5
    assert missing_liters["pricePerLiter"] == 100
    assert missing_liters["totalAmount"] == 1250
    assert missing_total["liters"] == 15.5
    assert missing_total["pricePerLiter"] == 96
    assert missing_total["totalAmount"] == 1488


def test_parse_odometer_photo_prefers_labelled_kilometres() -> None:
    parsed = parse_fuel_receipt("ODO METER\n128,450 km\nTrip 2026", scan_type="odometer")

    assert parsed["odometerKm"] == 128450
    assert parsed["sourceType"] == "odometer"


def test_receipt_scan_gracefully_falls_back_when_ocr_is_not_configured() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/fuel/scan",
            headers=auth(client),
            data={"scan_type": "receipt"},
            files={"image": ("receipt.jpg", b"not-a-real-image", "image/jpeg")},
        )
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["receiptImage"].startswith("/uploads/")
