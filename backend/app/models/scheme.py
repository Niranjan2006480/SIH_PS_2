"""
Scheme ORM models — SchemeRules, FinancialCalculations, RepaymentSchedule
Uses the module2_schema.sql definitions (the more complete version).
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class SchemeRule(Base):
    __tablename__ = "scheme_rules"

    scheme_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scheme_code = Column(String(50), unique=True, nullable=False)
    scheme_name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)  # Term Loan | Micro Finance
    min_project_cost = Column(Numeric(14, 2), nullable=False, default=0)
    max_project_cost = Column(Numeric(14, 2), nullable=False)
    loan_percentage = Column(Numeric(5, 2), nullable=False)
    max_loan_amount = Column(Numeric(14, 2), nullable=False)
    annual_interest_rate = Column(Numeric(6, 4), nullable=False)
    tenure_months = Column(Integer, nullable=False)
    moratorium_months = Column(Integer, nullable=False, default=0)
    repayment_frequency = Column(String(20), default="monthly")
    moratorium_interest_policy = Column(String(50), default="paid_separately")
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    calculations = relationship("FinancialCalculation", back_populates="scheme")


class FinancialCalculation(Base):
    __tablename__ = "financial_calculations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=True)       # Firebase UID or null
    location_id = Column(String(255), nullable=True)   # village_lgd_code
    scheme_id = Column(UUID(as_uuid=True), ForeignKey("scheme_rules.scheme_id"), nullable=False)
    available_margin = Column(Numeric(14, 2), nullable=False)
    raw_project_cost = Column(Numeric(14, 2), nullable=False)
    project_cost = Column(Numeric(14, 2), nullable=False)
    theoretical_loan = Column(Numeric(14, 2), nullable=False)
    eligible_loan = Column(Numeric(14, 2), nullable=False)
    required_margin = Column(Numeric(14, 2), nullable=False)
    funding_gap = Column(Numeric(14, 2), nullable=False)
    annual_interest_rate = Column(Numeric(6, 4), nullable=False)
    tenure_months = Column(Integer, nullable=False)
    moratorium_months = Column(Integer, nullable=False)
    moratorium_interest_mode = Column(String(50), nullable=False)
    monthly_emi = Column(Numeric(14, 2), nullable=True)
    quarterly_payment = Column(Numeric(14, 2), nullable=True)
    rules_version = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    scheme = relationship("SchemeRule", back_populates="calculations")
    repayment_schedule = relationship("RepaymentScheduleEntry", back_populates="calculation", cascade="all, delete-orphan")


class RepaymentScheduleEntry(Base):
    __tablename__ = "repayment_schedule"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calculation_id = Column(UUID(as_uuid=True), ForeignKey("financial_calculations.id", ondelete="CASCADE"), nullable=False)
    period_number = Column(Integer, nullable=False)
    period_type = Column(String(20), nullable=False)  # month | quarter
    opening_balance = Column(Numeric(14, 2), nullable=False)
    payment = Column(Numeric(14, 2), nullable=False)
    principal_component = Column(Numeric(14, 2), nullable=False)
    interest_component = Column(Numeric(14, 2), nullable=False)
    closing_balance = Column(Numeric(14, 2), nullable=False)

    calculation = relationship("FinancialCalculation", back_populates="repayment_schedule")
