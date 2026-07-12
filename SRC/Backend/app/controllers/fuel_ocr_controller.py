from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..services.ocr_service import OCRServiceError, ScanType, parse_fuel_receipt, read_receipt


ALLOWED_CONTENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}
MAX_RECEIPT_SIZE = 10 * 1024 * 1024
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"


async def scan_fuel_receipt(file: UploadFile, scan_type: ScanType) -> dict[str, object]:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        return {"success": False, "extractedData": {}, "rawText": "", "imageUrl": None, "receiptImage": None, "error": "Upload a JPG, PNG, or PDF image under 10 MB."}

    contents = await file.read()
    if not contents or len(contents) > MAX_RECEIPT_SIZE:
        return {"success": False, "extractedData": {}, "rawText": "", "imageUrl": None, "receiptImage": None, "error": "Upload a non-empty JPG, PNG, or PDF image under 10 MB."}

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{ALLOWED_CONTENT_TYPES[file.content_type]}"
    (UPLOAD_DIR / stored_name).write_bytes(contents)
    image_url = f"/uploads/{stored_name}"
    receipt_image = image_url if scan_type == "receipt" else None

    try:
        raw_text = await read_receipt(contents, file.filename or stored_name, file.content_type, os.getenv("OCR_SPACE_API_KEY", ""))
    except OCRServiceError as error:
        return {"success": False, "extractedData": {}, "rawText": "", "imageUrl": image_url, "receiptImage": receipt_image, "error": str(error)}

    return {"success": True, "extractedData": parse_fuel_receipt(raw_text, scan_type), "rawText": raw_text, "imageUrl": image_url, "receiptImage": receipt_image, "error": None}
