"""Analysis API endpoints — generate and retrieve feasibility reports."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.report import FeasibilityReport
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.report_composer import ReportComposer
from app.services.pdf_generator import PDFGenerator

logger = logging.getLogger(__name__)
router = APIRouter()
composer = ReportComposer()
pdf_gen = PDFGenerator()


@router.post("/generate", response_model=AnalysisResponse, tags=["Analysis"])
async def generate_analysis(
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Core endpoint — generates a full AI feasibility report.

    Pipeline:
    1. PostGIS market context (population, competitors, pricing, infrastructure)
    2. Financial calculation (scheme selection, EMI, amortization)
    3. Gemini AI analysis (SWOT, risks, opportunity, recommendation)
    4. Assembly + DB persistence + Redis caching

    Cached responses return immediately (~50ms). Fresh analysis: ~5-8 seconds.
    """
    try:
        return await composer.compose(request, db)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Analysis generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis generation failed. Please retry.")


@router.get("/{report_id}", response_model=AnalysisResponse, tags=["Analysis"])
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a previously generated feasibility report by ID."""
    try:
        uid = UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid report ID format")

    result = await db.execute(
        select(FeasibilityReport).where(FeasibilityReport.report_id == uid)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    response = AnalysisResponse(**report.report_json)
    response.is_cached = True
    return response


@router.get("/{report_id}/pdf", tags=["Analysis"])
async def download_report_pdf(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download a feasibility report as PDF."""
    try:
        uid = UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid report ID format")

    result = await db.execute(
        select(FeasibilityReport).where(FeasibilityReport.report_id == uid)
    )
    db_report = result.scalar_one_or_none()

    if not db_report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    report = AnalysisResponse(**db_report.report_json)
    pdf_bytes = pdf_gen.generate(report)

    filename = f"udyamai-report-{report_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
