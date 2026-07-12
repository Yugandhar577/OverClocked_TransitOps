from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, UploadFile

from ..controllers.fuel_ocr_controller import scan_fuel_receipt
from ..main import CurrentUser, require


router = APIRouter(tags=["fuel"])


@router.post("/api/fuel/scan")
async def scan_fuel(
    image: Annotated[UploadFile, File(description="Fuel receipt or odometer image")],
    user: CurrentUser,
    scan_type: Annotated[Literal["receipt", "odometer"], Form()] = "receipt",
) -> dict[str, Any]:
    require(user, "Financial Analyst", "Fleet Manager", "Administrator")
    return await scan_fuel_receipt(image, scan_type)
