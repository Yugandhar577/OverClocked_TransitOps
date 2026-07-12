from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

import httpx


OCR_SPACE_URL = "https://api.ocr.space/parse/image"
ScanType = Literal["receipt", "odometer"]


@dataclass
class ExtractedFuelData:
    stationName: str | None = None
    liters: float | None = None
    pricePerLiter: float | None = None
    totalAmount: float | None = None
    date: str | None = None
    receiptNumber: str | None = None
    odometerKm: float | None = None
    sourceType: str | None = None

    def value(self) -> dict[str, Any]:
        return asdict(self)


class OCRServiceError(Exception):
    """A recoverable OCR provider error that should not block manual entry."""


def _number(value: str) -> float:
    return float(value.replace(",", "").replace(" ", ""))


def _first_number(patterns: list[str], text: str) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return _number(match.group(1))
            except ValueError:
                continue
    return None


def _parse_date(text: str) -> str | None:
    patterns = [
        (r"\b(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\b", "%Y-%m-%d"),
        (r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", "%d-%m-%Y"),
    ]
    for pattern, date_format in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            return datetime.strptime("-".join(match.groups()), date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _station_name(text: str) -> str | None:
    for line in (line.strip(" :-") for line in text.splitlines()):
        if re.search(r"\b(petrol|fuel|filling station|service station|indian oil|bharat petroleum|hindustan petroleum|hpcl|iocl|bpcl|shell)\b", line, re.IGNORECASE):
            return line[:80] or None
    return None

def _odometer_reading(text: str, allow_fallback: bool) -> float | None:
    value = _first_number([
        r"(?:odometer|odo(?:meter)?|mileage|km\s*reading|kilomet(?:er|re)s?)\D{0,20}(\d[\d, ]{2,8})",
        r"\b(\d[\d, ]{3,8})\s*(?:km|kms)\b",
    ], text)
    if value is not None and 0 <= value <= 9_999_999:
        return value
    if not allow_fallback:
        return None

    candidates = [
        _number(match.group(0))
        for match in re.finditer(r"\b\d[\d, ]{3,8}\b", text)
        if not (1900 <= _number(match.group(0)) <= 2100)
    ]
    return max(candidates, default=None)


def _complete_fuel_values(liters: float | None, price_per_liter: float | None, total_amount: float | None) -> tuple[float | None, float | None, float | None]:
    if liters is not None and liters <= 0:
        liters = None
    if price_per_liter is not None and price_per_liter <= 0:
        price_per_liter = None
    if total_amount is not None and total_amount <= 0:
        total_amount = None

    if liters is None and price_per_liter and total_amount:
        liters = round(total_amount / price_per_liter, 3)
    if price_per_liter is None and liters and total_amount:
        price_per_liter = round(total_amount / liters, 2)
    if total_amount is None and liters and price_per_liter:
        total_amount = round(liters * price_per_liter, 2)
    return liters, price_per_liter, total_amount




def parse_fuel_receipt(raw_text: str, scan_type: ScanType = "receipt") -> dict[str, Any]:
    """Extract fuel values, deriving one missing value when the other two are available."""
    text = raw_text.replace("\u20b9", "Rs ")
    liters = _first_number([
        r"(?:qty|quantity|volume|vol(?:ume)?|lit(?:re|er)s?|ltr?s?)\s*[:=-]?\s*(\d+(?:[,.]\d+)?)",
        r"\b(\d+(?:[,.]\d+)?)\s*(?:lit(?:re|er)s?|ltr?s?|l)\b",
    ], text)
    price_per_liter = _first_number([
        r"(?:rate|price\s*per\s*lit(?:re|er)|unit\s*price|per\s*lit(?:re|er))\s*[:=-]?\s*(?:rs\.?\s*)?(\d+(?:[,.]\d+)?)",
        r"\b(\d+(?:[,.]\d+)?)\s*/\s*(?:lit(?:re|er)|l)\b",
    ], text)
    total_amount = _first_number([
        r"(?:grand\s*total|total\s*(?:amount|sale)?|amount\s*payable|net\s*amount|amount\s*due|paid)\D{0,18}(\d+(?:[,.]\d+)?)",
    ], text)
    if total_amount is None:
        currency_values = [
            _number(match.group(1))
            for match in re.finditer(r"(?:rs\.?|inr)\s*(\d+(?:[,.]\d+)?)", text, flags=re.IGNORECASE)
        ]
        total_amount = max(currency_values, default=None)
    liters, price_per_liter, total_amount = _complete_fuel_values(liters, price_per_liter, total_amount)

    receipt_match = re.search(r"(?:receipt|bill|invoice|txn|transaction)\s*(?:no|number|#)?\s*[:#-]?\s*([A-Z0-9/-]{3,})", text, re.IGNORECASE)
    source_type = "odometer" if scan_type == "odometer" else ("meter" if re.search(r"\b(meter|nozzle|dispensed|volume)\b", text, re.IGNORECASE) else "receipt")
    return ExtractedFuelData(
        stationName=_station_name(text),
        liters=liters,
        pricePerLiter=price_per_liter,
        totalAmount=total_amount,
        date=_parse_date(text),
        receiptNumber=receipt_match.group(1) if receipt_match else None,
        odometerKm=_odometer_reading(text, allow_fallback=scan_type == "odometer"),
        sourceType=source_type,
    ).value()


async def read_receipt(file_bytes: bytes, filename: str, content_type: str, api_key: str) -> str:
    if not api_key:
        raise OCRServiceError("Receipt was saved, but OCR is not configured. Add OCR_SPACE_API_KEY to scan it.")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0)) as client:
            response = await client.post(
                OCR_SPACE_URL,
                data={"apikey": api_key, "language": "eng", "isOverlayRequired": "false", "OCREngine": "2"},
                files={"file": (filename, file_bytes, content_type)},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise OCRServiceError("OCR service could not scan this file. You can still enter the fuel log manually.") from error

    if payload.get("IsErroredOnProcessing"):
        message = payload.get("ErrorMessage") or "OCR could not read this file."
        if isinstance(message, list):
            message = " ".join(str(item) for item in message)
        raise OCRServiceError(str(message))

    raw_text = "\n".join(
        str(result.get("ParsedText", ""))
        for result in payload.get("ParsedResults", [])
        if result.get("ParsedText")
    ).strip()
    if not raw_text:
        raise OCRServiceError("No readable text was found. You can still enter the fuel log manually.")
    return raw_text
