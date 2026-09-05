"""
Report & User ORM models
Covers: Users, FeasibilityReports, FieldObservations
"""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(Text, unique=True, nullable=True)
    name = Column(Text, nullable=True)
    preferred_language = Column(Text, default="en")
    role = Column(Text, default="entrepreneur")
    home_village_lgd_code = Column(String(15), ForeignKey("villages.village_lgd_code"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), nullable=True)


class FeasibilityReport(Base):
    __tablename__ = "feasibility_reports"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    village_lgd_code = Column(String(15), ForeignKey("villages.village_lgd_code"), nullable=False)
    business_category = Column(Text, ForeignKey("category_config.category_code"), nullable=False)
    radius_km = Column(Numeric(5, 2), default=10)
    margin_capital = Column(Numeric(12, 2), nullable=True)
    input_hash = Column(Text, nullable=False)
    report_json = Column(JSONB, nullable=False)
    overall_feasibility_score = Column(Numeric(5, 2), nullable=True)
    confidence_score = Column(Numeric(5, 2), nullable=True)
    status = Column(Text, default="completed")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
