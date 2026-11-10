import io
import logging
from dataclasses import dataclass

import cv2
from PIL import Image, UnidentifiedImageError
from pytesseract import TesseractError, TesseractNotFoundError
from sqlalchemy.orm import Session
from starlette import status

from app.core.config import settings
from app.core.errors import AppError
from app.models import MedicationList, MedicationListItem, OcrExtractionResult, PrescriptionImage, User
from app.models.enums import ConfirmationFlag, ConfirmationStatus, ListSource, OcrStatus
from app.ocr.tesseract_engine import Tesseract_engine
from app.models.medication_list import random_file_reference
from app.schemas.medication_list import MedicationListOut, OCRLineOut
from app.services.medication_list_service import _load, to_detail
from app.services.normalization import resolve_term

logger = logging.getLogger(__name__)
MAX_IMAGE_PIXELS = 20_000_000
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


@dataclass
class OCRListResult:
    image_id: int
    medication_list: MedicationListOut
    extracted_lines: list[OCRLineOut]


def _validate_image(image_bytes: bytes) -> str:
    if not image_bytes:
        raise AppError(status.HTTP_400_BAD_REQUEST, "empty_image", "Choose an image to upload.")
    if len(image_bytes) > settings.MAX_IMAGE_BYTES:
        raise AppError(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "image_too_large",
            f"The image must be no larger than {settings.MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
        )

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image_format = image.format
            width, height = image.size
            if image_format not in SUPPORTED_IMAGE_FORMATS:
                raise AppError(
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    "unsupported_image",
                    "Upload a JPEG, PNG, or WebP image.",
                )
            if width * height > MAX_IMAGE_PIXELS:
                raise AppError(
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    "image_too_large",
                    "The image dimensions are too large to process.",
                )
            image.verify()
    except AppError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise AppError(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_image", "The uploaded file is not a valid image.") from exc

    return image_format


def create_list_from_image(db: Session, user: User, image_bytes: bytes) -> OCRListResult:
    image_format = _validate_image(image_bytes)
    try:
        lines = Tesseract_engine().extract_lines(image_bytes)
    except TesseractNotFoundError as exc:
        logger.exception("Tesseract executable is unavailable")
        raise AppError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ocr_unavailable",
            "OCR is unavailable. Install Tesseract or configure TESSERACT_CMD.",
        ) from exc
    except TesseractError as exc:
        logger.exception("Tesseract failed to process an uploaded image")
        raise AppError(
            status.HTTP_502_BAD_GATEWAY,
            "ocr_failed",
            "OCR could not read this image. Try a clearer image.",
        ) from exc
    except cv2.error as exc:
        raise AppError(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_image", "The uploaded image could not be decoded.") from exc

    if not lines:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "no_text_detected",
            "No readable text was found. Try a clearer image.",
        )
    if len(lines) > settings.MAX_MEDS_PER_LIST:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "too_many_ocr_lines",
            f"OCR found {len(lines)} text lines; a list can contain at most {settings.MAX_MEDS_PER_LIST} items. "
            "Try a closer crop around the medicine names.",
        )

    med_list = MedicationList(
        user_id=user.id,
        source=ListSource.OCR,
        confirmation_status=ConfirmationStatus.DRAFT,
    )
    db.add(med_list)
    db.flush()

    image_record = PrescriptionImage(
        list_id=med_list.id,
        file_reference=random_file_reference(image_format.lower()),
        ocr_status=OcrStatus.COMPLETED,
    )
    db.add(image_record)
    db.flush()

    extracted_lines: list[OCRLineOut] = []
    extraction_candidates: list[dict] = []
    for line in lines:
        candidates = resolve_term(db, line.text)
        item = MedicationListItem(
            list_id=med_list.id,
            raw_text=line.text,
            medication_id=candidates[0]["medication_id"] if candidates else None,
            match_score=candidates[0]["match_score"] if candidates else None,
            confirmation_flag=ConfirmationFlag.UNRESOLVED,
        )
        db.add(item)
        db.flush()
        extracted_lines.append(
            OCRLineOut(
                item_id=item.id,
                text=line.text,
                confidence=line.confidence,
                candidates=candidates,
            )
        )
        extraction_candidates.append(
            {
                "text": line.text,
                "confidence": line.confidence,
                "item_id": item.id,
                "candidates": candidates,
            }
        )

    db.add(
        OcrExtractionResult(
            image_id=image_record.id,
            raw_text="\n".join(line.text for line in lines),
            candidates=extraction_candidates,
            confidence=round(sum(line.confidence for line in lines) / len(lines)),
        )
    )
    db.commit()
    loaded_list = _load(db, med_list.id)
    if loaded_list is None:
        raise RuntimeError("The OCR-created medication list could not be reloaded after commit.")

    return OCRListResult(
        image_id=image_record.id,
        medication_list=to_detail(loaded_list),
        extracted_lines=extracted_lines,
    )
