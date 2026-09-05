"""Financial API endpoints — scheme listing and standalone financial calculation."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.scheme import SchemeRule
from app.schemas.financial import (
    FinancialCalculationRequest,
    FinancialCalculationResponse,
    SchemeResponse,
    SchemesListResponse,
)
from app.services.financial_engine import FinancialEngine

logger = logging.getLogger(__name__)
router = APIRouter()
engine = FinancialEngine()


@router.get("/schemes", response_model=SchemesListResponse, tags=["Financial"])
async def list_schemes(db: AsyncSession = Depends(get_db)):
    """List all active loan schemes (NBCFDC + SCA)."""
    schemes = await engine.get_all_schemes(db)
    return SchemesListResponse(
        schemes=[
            SchemeResponse(
                scheme_id=str(s.scheme_id),
                scheme_code=s.scheme_code,
                scheme_name=s.scheme_name,
                category=s.category,
                loan_percentage=float(s.loan_percentage),
                max_loan_amount=float(s.max_loan_amount),
                annual_interest_rate=float(s.annual_interest_rate),
                tenure_months=s.tenure_months,
                tenure_years=round(s.tenure_months / 12, 1),
                moratorium_months=s.moratorium_months,
                repayment_frequency=s.repayment_frequency,
            )
            for s in schemes
        ],
        total=len(schemes),
    )


@router.post("/calculate", response_model=FinancialCalculationResponse, tags=["Financial"])
async def calculate_financial(
    request: FinancialCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Standalone financial calculation endpoint.
    Given a margin capital amount, returns:
    - Project cost, eligible loan, scheme
    - EMI (monthly + quarterly)
    - Full amortization schedule
    """
    try:
        return await engine.calculate(
            margin_capital=request.margin_capital,
            db=db,
            village_lgd_code=request.village_lgd_code,
            user_id=request.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Financial calculation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Calculation failed. Please retry.")


@router.get("/categories", tags=["Financial"])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """List all active business categories with display names."""
    from app.models.business import CategoryConfig
    result = await db.execute(
        select(CategoryConfig)
        .where(CategoryConfig.is_active == True)  # noqa: E712
        .order_by(CategoryConfig.display_name)
    )
    categories = result.scalars().all()
    return {
        "categories": [
            {
                "code": c.category_code,
                "name": c.display_name,
                "target_segments": c.target_segments,
            }
            for c in categories
        ],
        "total": len(categories),
    }
