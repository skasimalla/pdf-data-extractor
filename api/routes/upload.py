"""
PDF upload endpoint — extracts patient First Name, Last Name, and Date of Birth.

Extraction pipeline (in priority order):
  1. pdfplumber text layer  → OpenAI GPT-4o-mini text extraction
  2. pdfplumber text layer  → regex heuristics (no OpenAI key needed)
  3. pypdfium2 image render → OpenAI GPT-4o-mini Vision  (scanned / fax PDFs)
  4. No-key fallback        → returns a clear error asking for OPENAI_API_KEY

The sample document is a multi-page scanned fax (Boston Orthotics & Prosthetics).
Patient data appears on page 1 ("Patient Name and Address" / "Patient Date of Birth")
and page 2 ("Patient Name:" / "DOB:" in a Clinical Summary header).
"""
from __future__ import annotations

import base64
import io
import json
import re
import uuid
import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..dependencies import verify_api_key
from ..models import Order
from ..schemas import ExtractedPatientInfo, OrderResponse, UploadResponse

logger = logging.getLogger("medorders.upload")
router = APIRouter(prefix="/v1/upload", tags=["Upload"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
# Only render the first N pages — patient demographics always appear early
MAX_VISION_PAGES = 2


# ─── Image rendering ─────────────────────────────────────────────────────────


def _render_pdf_pages(pdf_bytes: bytes, max_pages: int = MAX_VISION_PAGES) -> List[str]:
    """
    Render the first `max_pages` pages of a PDF to base64-encoded JPEG strings
    using pypdfium2 (no Poppler dependency).

    Returns a list of base64 strings, one per page.
    """
    try:
        import pypdfium2 as pdfium  # type: ignore
    except ImportError:
        raise RuntimeError(
            "pypdfium2 is not installed. Add it to requirements.txt and redeploy."
        )

    doc = pdfium.PdfDocument(pdf_bytes)
    pages_b64: List[str] = []

    for i in range(min(max_pages, len(doc))):
        bitmap = doc[i].render(scale=2.0)  # 2× gives ~1224×1584 px — enough for Vision
        pil_img = bitmap.to_pil()
        buf = io.BytesIO()
        pil_img.convert("RGB").save(buf, format="JPEG", quality=88)
        pages_b64.append(base64.b64encode(buf.getvalue()).decode())

    return pages_b64


# ─── OpenAI Vision extraction (scanned / image-only PDFs) ────────────────────


async def _extract_with_vision(pages_b64: List[str], api_key: str) -> ExtractedPatientInfo:
    """Send rendered page images to GPT-4o-mini Vision and return structured patient info."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)

    content: list = [
        {
            "type": "text",
            "text": (
                "You are a medical document parser. The images below are pages from a medical "
                "fax or prescription document. Extract the patient's demographics.\n\n"
                "Return ONLY a JSON object with these exact keys:\n"
                '  "first_name": string | null\n'
                '  "last_name":  string | null\n'
                '  "date_of_birth": "YYYY-MM-DD" | null  (convert any date format to ISO)\n'
                '  "confidence": float 0.0–1.0\n\n'
                "Look for labels such as: 'Patient Name', 'Patient Name and Address', "
                "'First Name', 'Last Name', 'DOB', 'Date of Birth', 'Birth Date', 'Born'.\n"
                "The patient name is typically the FIRST non-address line below a "
                "'Patient Name' heading. Do NOT return the prescriber's name."
            ),
        }
    ]

    for b64 in pages_b64:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": "high",
                },
            }
        )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"},
        temperature=0,
        timeout=30,
    )

    data = json.loads(response.choices[0].message.content)
    return ExtractedPatientInfo(
        first_name=data.get("first_name") or "",
        last_name=data.get("last_name") or "",
        date_of_birth=data.get("date_of_birth") or "",
        confidence=float(data.get("confidence", 0.9)),
    )


# ─── OpenAI text extraction (PDFs with a text layer) ─────────────────────────


async def _extract_with_openai_text(text: str, api_key: str) -> ExtractedPatientInfo:
    """Use GPT-4o-mini to extract patient info from already-extracted PDF text."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a medical document parser. Extract patient demographics from text.\n"
                    "Return ONLY valid JSON with keys: first_name, last_name, date_of_birth (YYYY-MM-DD), confidence (0.0–1.0).\n"
                    "Look for: Patient Name, First Name, Last Name, DOB, Date of Birth, Born.\n"
                    "Do NOT return the prescriber or physician name."
                ),
            },
            {"role": "user", "content": f"Extract patient info:\n\n{text[:8000]}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        timeout=20,
    )
    data = json.loads(response.choices[0].message.content)
    return ExtractedPatientInfo(
        first_name=data.get("first_name") or "",
        last_name=data.get("last_name") or "",
        date_of_birth=data.get("date_of_birth") or "",
        confidence=float(data.get("confidence", 0.85)),
    )


# ─── Regex fallback (text layer only) ────────────────────────────────────────


def _extract_with_regex(text: str) -> ExtractedPatientInfo:
    """
    Best-effort regex extraction for PDFs that have a text layer but no OpenAI key.
    Covers common DME / prescription fax layouts.
    """
    first = last = dob_str = ""

    # "Last, First" layout
    m = re.search(
        r"(?:patient[\s_]*name(?:\s+and\s+address)?|name)\s*[:\-]?\s*"
        r"([A-Za-z\-']+)\s*,\s*([A-Za-z\-']+)",
        text, re.IGNORECASE,
    )
    if m:
        last, first = m.group(1).strip(), m.group(2).strip()
    else:
        # "First Last" layout
        m = re.search(
            r"(?:patient[\s_]*name(?:\s+and\s+address)?|name)\s*[:\-]?\s*"
            r"([A-Za-z\-']+)\s+([A-Za-z\-']+)",
            text, re.IGNORECASE,
        )
        if m:
            first, last = m.group(1).strip(), m.group(2).strip()

    if not first:
        m = re.search(r"(?:first[\s_]*name|given[\s_]*name)\s*[:\-]?\s*([A-Za-z\-']+)", text, re.IGNORECASE)
        if m:
            first = m.group(1).strip()

    if not last:
        m = re.search(r"(?:last[\s_]*name|surname|family[\s_]*name)\s*[:\-]?\s*([A-Za-z\-']+)", text, re.IGNORECASE)
        if m:
            last = m.group(1).strip()

    for pat in [
        r"(?:DOB|Date[\s_]*of[\s_]*Birth|Birth[\s_]*Date|Born)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
        r"(?:DOB|Date[\s_]*of[\s_]*Birth|Birth[\s_]*Date|Born)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        r"(?:DOB|Date[\s_]*of[\s_]*Birth|Birth[\s_]*Date|Born)\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            dob_str = m.group(1).strip()
            break

    confidence = 0.3
    if first and last:
        confidence += 0.4
    elif first or last:
        confidence += 0.2
    if dob_str:
        confidence += 0.3

    return ExtractedPatientInfo(
        first_name=first,
        last_name=last,
        date_of_birth=dob_str,
        confidence=min(confidence, 1.0),
    )


# ─── Date parsing ─────────────────────────────────────────────────────────────


def _parse_dob(dob_str: str) -> date:
    if not dob_str:
        return date.today()
    for fmt in (
        "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y",
        "%B %d, %Y", "%b %d, %Y", "%m/%d/%y",
    ):
        try:
            return datetime.strptime(dob_str.strip(), fmt).date()
        except ValueError:
            continue
    try:
        from dateutil import parser as dp
        return dp.parse(dob_str, dayfirst=False).date()
    except Exception:
        return date.today()


# ─── Route ───────────────────────────────────────────────────────────────────


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Upload a PDF (including scanned faxes with no text layer) and extract:
      - Patient First Name
      - Patient Last Name
      - Date of Birth

    An Order record is automatically created from the extracted data.

    When OPENAI_API_KEY is set, GPT-4o-mini Vision is used for scanned documents.
    Text-layer PDFs also benefit from GPT-4o-mini for accurate parsing.
    Without an API key, regex fallback handles text-layer PDFs only.
    """
    settings = get_settings()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are accepted")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    # ── Step 1: Try text-layer extraction ────────────────────────────────────
    pdf_text = ""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pdf_text = "\n".join(p.extract_text() or "" for p in pdf.pages).strip()
    except Exception as exc:
        logger.warning("pdfplumber failed: %s", exc)

    has_text_layer = bool(pdf_text)
    patient_info: Optional[ExtractedPatientInfo] = None

    if has_text_layer:
        logger.info("PDF has text layer (%d chars). Using text extraction.", len(pdf_text))
        if settings.OPENAI_API_KEY:
            try:
                patient_info = await _extract_with_openai_text(pdf_text, settings.OPENAI_API_KEY)
            except Exception as exc:
                logger.warning("OpenAI text extraction failed, trying regex: %s", exc)
                patient_info = _extract_with_regex(pdf_text)
        else:
            patient_info = _extract_with_regex(pdf_text)

    # ── Step 2: Scanned / image-only PDF → Vision API ────────────────────────
    if not has_text_layer or (patient_info and not patient_info.first_name and not patient_info.last_name):
        logger.info("No usable text layer. Rendering pages for Vision extraction.")

        if not settings.OPENAI_API_KEY:
            raise HTTPException(
                status_code=422,
                detail=(
                    "This PDF has no text layer (it is a scanned image or fax). "
                    "Set the OPENAI_API_KEY environment variable to enable Vision-based extraction."
                ),
            )

        try:
            pages_b64 = _render_pdf_pages(content, max_pages=MAX_VISION_PAGES)
        except RuntimeError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:
            logger.error("PDF rendering failed: %s", exc)
            raise HTTPException(status_code=422, detail=f"Could not render PDF pages: {exc}")

        if not pages_b64:
            raise HTTPException(status_code=422, detail="PDF produced no renderable pages")

        try:
            patient_info = await _extract_with_vision(pages_b64, settings.OPENAI_API_KEY)
        except Exception as exc:
            logger.error("Vision extraction failed: %s", exc)
            raise HTTPException(
                status_code=422,
                detail=f"Vision-based extraction failed: {exc}",
            )

    # ── Validate extraction result ────────────────────────────────────────────
    if not patient_info or (not patient_info.first_name and not patient_info.last_name):
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not extract patient name from the document. "
                "Ensure the document contains readable patient demographic fields."
            ),
        )

    # ── Persist order ─────────────────────────────────────────────────────────
    dob = _parse_dob(patient_info.date_of_birth)
    order = Order(
        id=str(uuid.uuid4()),
        patient_first_name=patient_info.first_name or "Unknown",
        patient_last_name=patient_info.last_name or "Unknown",
        patient_dob=dob,
        status="pending",
        document_filename=file.filename,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)

    logger.info(
        "Extracted: %s %s DOB=%s (confidence=%.2f) from %s [%s]",
        patient_info.first_name,
        patient_info.last_name,
        patient_info.date_of_birth,
        patient_info.confidence,
        file.filename,
        "vision" if not has_text_layer else "text",
    )

    return UploadResponse(
        extracted_info=patient_info,
        order=OrderResponse.model_validate(order),
        message="Document processed and order created successfully",
    )
