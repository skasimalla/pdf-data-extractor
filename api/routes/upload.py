"""
PDF upload endpoint — extracts patient First Name, Last Name, and Date of Birth.

Extraction pipeline (in priority order):
  1. pdfplumber text layer  → regex heuristics  (fast, no API key)
  2. pdfplumber text layer  → OpenAI GPT-4o-mini (optional, better accuracy)
  3. pypdfium2 image render → rapidocr-onnxruntime OCR → regex  (scanned/fax, no API key)
  4. pypdfium2 image render → OpenAI GPT-4o-mini Vision            (optional, best accuracy)

Steps 2 and 4 only run when OPENAI_API_KEY is set.
Steps 3 and 4 handle scanned/fax PDFs that have no text layer.
rapidocr-onnxruntime uses bundled ONNX models — no internet access required at runtime.
"""
from __future__ import annotations

import base64
import io
import json
import re
import uuid
import logging
from datetime import date, datetime
from typing import Any, List, Optional

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
MAX_PAGES = 2

# ─── Lazy OCR engine singleton ────────────────────────────────────────────────

_ocr_engine: Optional[Any] = None
_ocr_available: Optional[bool] = None
_ocr_init_error: str = ""


def _get_ocr_engine() -> Optional[Any]:
    """
    Lazily initialise a RapidOCR ONNX engine (models loaded once per process).

    rapidocr-onnxruntime >= 1.4.0 bundles the ONNX model files inside the
    Python wheel (site-packages/rapidocr_onnxruntime/models/*.onnx).
    We resolve those paths explicitly so the engine works even when Vercel's
    working directory differs from the package install directory.
    """
    global _ocr_engine, _ocr_available, _ocr_init_error
    if _ocr_available is not None:
        return _ocr_engine if _ocr_available else None

    try:
        import os
        import rapidocr_onnxruntime as _rapi_pkg  # type: ignore
        from rapidocr_onnxruntime import RapidOCR  # type: ignore

        models_dir = os.path.join(os.path.dirname(_rapi_pkg.__file__), "models")

        # Resolve bundled model paths (>= 1.4.0 ships them in the wheel)
        def _find(prefix: str) -> Optional[str]:
            if not os.path.isdir(models_dir):
                return None
            for name in os.listdir(models_dir):
                if name.endswith(".onnx") and prefix in name.lower():
                    return os.path.join(models_dir, name)
            return None

        det = _find("det")
        cls = _find("cls")
        rec = _find("rec")

        kwargs: dict = {}
        if det:
            kwargs["det_model_path"] = det
        if cls:
            kwargs["cls_model_path"] = cls
        if rec:
            kwargs["rec_model_path"] = rec

        logger.info(
            "RapidOCR model paths — det=%s cls=%s rec=%s",
            det, cls, rec,
        )

        # Limit onnxruntime to single-threaded CPU to avoid libgomp/OpenMP
        # issues in Lambda / Vercel serverless containers.
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")

        _ocr_engine = RapidOCR(**kwargs)
        _ocr_available = True
        logger.info("RapidOCR (ONNX) engine ready")

    except Exception as exc:
        import traceback
        _ocr_init_error = f"{type(exc).__name__}: {exc}"
        logger.error(
            "RapidOCR init failed — OCR disabled.\n%s",
            traceback.format_exc(),
        )
        _ocr_available = False

    return _ocr_engine if _ocr_available else None


# ─── PDF rendering helpers ────────────────────────────────────────────────────


def _render_pages_pil(pdf_bytes: bytes, max_pages: int = MAX_PAGES) -> list:
    """Render first `max_pages` pages of a PDF to PIL Images (2× scale for OCR quality)."""
    try:
        import pypdfium2 as pdfium  # type: ignore
    except ImportError:
        raise RuntimeError(
            "pypdfium2 is not installed. Add it to requirements.txt and redeploy."
        )
    doc = pdfium.PdfDocument(pdf_bytes)
    images = []
    for i in range(min(max_pages, len(doc))):
        bitmap = doc[i].render(scale=2.0)
        images.append(bitmap.to_pil().convert("RGB"))
    return images


def _render_pages_b64(pdf_bytes: bytes, max_pages: int = MAX_PAGES) -> List[str]:
    """Render pages to base64-encoded JPEG strings (used for OpenAI Vision)."""
    pages_b64: List[str] = []
    for img in _render_pages_pil(pdf_bytes, max_pages):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        pages_b64.append(base64.b64encode(buf.getvalue()).decode())
    return pages_b64


# ─── OCR extraction ───────────────────────────────────────────────────────────


def _tesseract_ocr_page(img: Any) -> str:
    """Run pytesseract on a single PIL Image. Returns '' if tesseract is not installed."""
    try:
        import pytesseract  # type: ignore
        return pytesseract.image_to_string(img, lang="eng")
    except Exception:
        return ""


def _ocr_pdf_to_text(pdf_bytes: bytes) -> str:
    """
    Render a scanned PDF and extract text via OCR.

    Strategy (in order):
      1. RapidOCR (ONNX) — bundled models, no system binary, works everywhere.
      2. pytesseract — fallback for local development (requires brew/apt tesseract).

    Returns the concatenated raw text, or '' if both engines are unavailable.
    """
    try:
        page_images = _render_pages_pil(pdf_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("PDF rendering failed: %s", exc)
        return ""

    if not page_images:
        return ""

    # ── Strategy 1: RapidOCR ─────────────────────────────────────────────────
    ocr = _get_ocr_engine()
    if ocr:
        try:
            import numpy as np  # type: ignore
            texts: List[str] = []
            for img in page_images:
                result, _ = ocr(np.array(img))
                if result:
                    texts.append("\n".join(item[1] for item in result if item[1]))
            combined = "\n\n".join(texts)
            logger.info(
                "RapidOCR produced %d chars from %d page(s)",
                len(combined), len(page_images),
            )
            if combined.strip():
                return combined
        except Exception as exc:
            logger.warning("RapidOCR inference failed: %s", exc)

    # ── Strategy 2: pytesseract (local fallback) ─────────────────────────────
    tess_texts: List[str] = []
    for img in page_images:
        t = _tesseract_ocr_page(img)
        if t.strip():
            tess_texts.append(t)

    if tess_texts:
        combined = "\n\n".join(tess_texts)
        logger.info(
            "pytesseract produced %d chars from %d page(s)",
            len(combined), len(page_images),
        )
        return combined

    logger.warning(
        "Both OCR strategies produced no text. "
        "RapidOCR init error: %s", _ocr_init_error or "none",
    )
    return ""


# ─── OpenAI Vision extraction (scanned / image-only PDFs) ────────────────────


async def _extract_with_vision(pages_b64: List[str], api_key: str) -> ExtractedPatientInfo:
    """Send rendered page images to GPT-4o-mini Vision and return structured patient info."""
    from openai import AsyncOpenAI  # type: ignore

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
    from openai import AsyncOpenAI  # type: ignore

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


# ─── Regex extraction (works on both native text and OCR output) ──────────────


def _extract_with_regex(text: str) -> ExtractedPatientInfo:
    """
    Best-effort regex extraction for text-layer or OCR'd content.
    Handles common DME / CPAP / prescription fax layouts, including
    'Last, First', 'First Last', and labelled-field ('First Name: ...') forms.

    OCR output is noisier than native text, so patterns are intentionally
    permissive (allow extra whitespace / punctuation between label and value).
    """
    first = last = dob_str = ""

    # Normalise runs of whitespace while preserving line structure
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    flat = "\n".join(lines)

    # ── Name extraction ──────────────────────────────────────────────────────
    #
    # Priority order:
    #   A) Inline same-line label  "Patient Name: First Last"  (page 2 of CPAP fax)
    #   B) Inline with comma       "Patient Name: Last, First"
    #   C) Next-line layout        "Patient Name and Address\n<junk>\nFirst Last\n"
    #      (page 1 of CPAP fax — OCR merges column headers into prev line)
    #   D) Explicit separate labels "First Name: X" / "Last Name: Y"

    # A) Inline "Patient Name: First Last" — separator is only horizontal space, NOT newlines
    m = re.search(
        r"patient[\s_]*name\s*[:\-][ \t]*([A-Za-z][A-Za-z\-'\.]+)[ \t]+([A-Za-z][A-Za-z\-'\.]+)",
        flat, re.IGNORECASE,
    )
    if m:
        first, last = m.group(1).strip(), m.group(2).strip()

    # B) Inline "Last, First"
    if not first and not last:
        m = re.search(
            r"patient[\s_]*name\s*[:\-][ \t]*([A-Za-z][A-Za-z\-'\.]+)\s*,\s*([A-Za-z][A-Za-z\-'\.]+)",
            flat, re.IGNORECASE,
        )
        if m:
            last, first = m.group(1).strip(), m.group(2).strip()

    # C) Next-line layout — scan up to 5 lines after any "Patient Name…" heading
    if not first and not last:
        _SKIP_LINE = re.compile(
            r"(?:date|birth|prescriber|address|phone|fax|npi|diagnosis|"
            r"authorization|page|server|insurance|provider|sex|gender|age)",
            re.IGNORECASE,
        )
        for i, line in enumerate(lines):
            if re.search(r"patient[\s_]*name", line, re.IGNORECASE):
                for j in range(i + 1, min(i + 6, len(lines))):
                    if _SKIP_LINE.search(lines[j]) or not lines[j]:
                        continue
                    name_m = re.search(
                        r"([A-Za-z][A-Za-z\-'\.]+)\s+([A-Za-z][A-Za-z\-'\.]+)",
                        lines[j],
                    )
                    if name_m:
                        first, last = name_m.group(1), name_m.group(2)
                        break
                if first:
                    break

    # D) Explicit separate fields
    if not first:
        m = re.search(
            r"(?:first[\s_]*name|given[\s_]*name|fname)\s*[:\-]?\s*([A-Za-z][A-Za-z\-'\.]+)",
            flat, re.IGNORECASE,
        )
        if m:
            first = m.group(1).strip()

    if not last:
        m = re.search(
            r"(?:last[\s_]*name|surname|family[\s_]*name|lname)\s*[:\-]?\s*([A-Za-z][A-Za-z\-'\.]+)",
            flat, re.IGNORECASE,
        )
        if m:
            last = m.group(1).strip()

    # ── DOB extraction ───────────────────────────────────────────────────────

    dob_patterns = [
        # ISO  2024-01-15
        r"(?:DOB|Date[\s_]*of[\s_]*Birth|Birth[\s_]*Date|Born|Birthdate)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
        # US   01/15/2024  or  01-15-2024
        r"(?:DOB|Date[\s_]*of[\s_]*Birth|Birth[\s_]*Date|Born|Birthdate)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        # Verbose  January 15, 2024
        r"(?:DOB|Date[\s_]*of[\s_]*Birth|Birth[\s_]*Date|Born|Birthdate)\s*[:\-]?\s*([A-Za-z]+\.?\s+\d{1,2},?\s+\d{4})",
        # ISO without label — as last resort
        r"\b(\d{4}-\d{2}-\d{2})\b",
        # US without label — only when we already have a name to reduce false positives
        r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
    ]
    for pat in dob_patterns:
        m = re.search(pat, flat, re.IGNORECASE)
        if m:
            dob_str = m.group(1).strip()
            break

    # ── Confidence score ─────────────────────────────────────────────────────
    confidence = 0.2
    if first and last:
        confidence += 0.5
    elif first or last:
        confidence += 0.25
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
        "%B %d, %Y", "%b %d, %Y", "%m/%d/%y", "%b. %d, %Y",
    ):
        try:
            return datetime.strptime(dob_str.strip(), fmt).date()
        except ValueError:
            continue
    try:
        from dateutil import parser as dp  # type: ignore
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

    **No API key required** — OCR is performed locally using rapidocr-onnxruntime
    (ONNX models, no internet access needed at runtime).
    Set OPENAI_API_KEY for higher-accuracy extraction via GPT-4o-mini Vision.
    """
    settings = get_settings()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are accepted")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    # ── Step 1: Native text layer (pdfplumber) ───────────────────────────────
    pdf_text = ""
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pdf_text = "\n".join(p.extract_text() or "" for p in pdf.pages).strip()
    except Exception as exc:
        logger.warning("pdfplumber failed: %s", exc)

    has_text_layer = bool(pdf_text)
    extraction_method = "unknown"
    patient_info: Optional[ExtractedPatientInfo] = None

    if has_text_layer:
        logger.info("PDF has native text layer (%d chars)", len(pdf_text))
        if settings.OPENAI_API_KEY:
            try:
                patient_info = await _extract_with_openai_text(pdf_text, settings.OPENAI_API_KEY)
                extraction_method = "openai-text"
            except Exception as exc:
                logger.warning("OpenAI text extraction failed, falling back to regex: %s", exc)
                patient_info = _extract_with_regex(pdf_text)
                extraction_method = "regex-text"
        else:
            patient_info = _extract_with_regex(pdf_text)
            extraction_method = "regex-text"

    # ── Step 2: Scanned / image PDF → local OCR (no API key required) ────────
    needs_ocr = not has_text_layer or (
        patient_info and not patient_info.first_name and not patient_info.last_name
    )

    if needs_ocr:
        logger.info("Attempting local OCR (RapidOCR / ONNX) on rendered pages")
        ocr_text = _ocr_pdf_to_text(content)

        if ocr_text.strip():
            patient_info = _extract_with_regex(ocr_text)
            extraction_method = "ocr-regex"
            logger.info(
                "OCR extracted text (%d chars), regex confidence=%.2f",
                len(ocr_text), patient_info.confidence,
            )

            # ── Step 3: Optionally refine with OpenAI Vision (higher accuracy) ──
            if settings.OPENAI_API_KEY and patient_info.confidence < 0.7:
                logger.info("Confidence low (%.2f), trying OpenAI Vision", patient_info.confidence)
                try:
                    pages_b64 = _render_pages_b64(content)
                    if pages_b64:
                        patient_info = await _extract_with_vision(pages_b64, settings.OPENAI_API_KEY)
                        extraction_method = "openai-vision"
                except Exception as exc:
                    logger.warning("OpenAI Vision failed, keeping OCR result: %s", exc)
        else:
            # OCR produced nothing (engine unavailable or totally blank page)
            if settings.OPENAI_API_KEY:
                logger.info("OCR produced no text, falling back to OpenAI Vision")
                try:
                    pages_b64 = _render_pages_b64(content)
                    if not pages_b64:
                        raise HTTPException(status_code=422, detail="PDF produced no renderable pages")
                    patient_info = await _extract_with_vision(pages_b64, settings.OPENAI_API_KEY)
                    extraction_method = "openai-vision"
                except HTTPException:
                    raise
                except Exception as exc:
                    logger.error("Vision extraction failed: %s", exc)
                    raise HTTPException(
                        status_code=422,
                        detail=f"OCR and Vision extraction both failed: {exc}",
                    )
            else:
                diag = f" Init error: {_ocr_init_error}" if _ocr_init_error else ""
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "This PDF has no text layer and local OCR produced no output."
                        f"{diag} "
                        "Ensure rapidocr-onnxruntime>=1.4.0 and numpy are installed, "
                        "or set OPENAI_API_KEY to enable Vision-based extraction."
                    ),
                )

    # ── Validate final result ─────────────────────────────────────────────────
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
        "Extracted: %s %s DOB=%s (confidence=%.2f, method=%s) from '%s'",
        patient_info.first_name,
        patient_info.last_name,
        patient_info.date_of_birth,
        patient_info.confidence,
        extraction_method,
        file.filename,
    )

    return UploadResponse(
        extracted_info=patient_info,
        order=OrderResponse.model_validate(order),
        message=f"Document processed via {extraction_method} and order created successfully",
    )
