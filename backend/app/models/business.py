"""
Business & Market ORM models
Covers: CategoryConfig, DistrictBusinessSummary, Businesses, MarketPrices, PriceIndex
"""

import uuid
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class CategoryConfig(Base):
    __tablename__ = "category_config"

    category_code = Column(Text, primary_key=True)
    display_name = Column(Text, nullable=False)
    target_segments = Column(JSONB, nullable=True)
    relevant_commodities = Column(JSONB, nullable=True)
    required_facilities = Column(JSONB, nullable=True)
    risk_factors = Column(JSONB, nullable=True)
    competitor_categories = Column(JSONB, nullable=True)
    pricing_method = Column(Text, nullable=True)
    demand_formula_params = Column(JSONB, nullable=True)
    threat_thresholds = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class DistrictBusinessSummary(Base):
    __tablename__ = "district_business_summary"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district_lgd_code = Column(String(10), ForeignKey("districts.district_lgd_code"), nullable=False)
    sector = Column(Text, nullable=True)
    micro_count = Column(Integer, default=0)
    small_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    manufacturing_count = Column(Integer, default=0)
    service_count = Column(Integer, default=0)
    trading_count = Column(Integer, default=0)
    total_registered = Column(Integer, default=0)
    reference_date = Column(Date, nullable=True)
    source = Column(Text, default="Udyam Registration")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Business(Base):
    __tablename__ = "businesses"

    business_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=True)
    category = Column(Text, ForeignKey("category_config.category_code"), nullable=False)
    village_lgd_code = Column(String(15), ForeignKey("villages.village_lgd_code"), nullable=True)
    district_lgd_code = Column(String(10), ForeignKey("districts.district_lgd_code"), nullable=True)
    latitude = Column(Double, nullable=True)
    longitude = Column(Double, nullable=True)
    geom = Column(Geometry("Point", srid=4326), nullable=True)
    registration_type = Column(Text, nullable=True)
    confidence = Column(Text, default="medium")
    source = Column(Text, nullable=False)
    source_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MarketPrice(Base):
    __tablename__ = "market_prices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_code = Column(String(2), ForeignKey("states.state_code"), nullable=True)
    district_lgd_code = Column(String(10), ForeignKey("districts.district_lgd_code"), nullable=True)
    market_name = Column(Text, nullable=True)
    commodity = Column(Text, nullable=False)
    variety = Column(Text, nullable=True)
    price_date = Column(Date, nullable=False)
    min_price = Column(Numeric(10, 2), nullable=True)
    max_price = Column(Numeric(10, 2), nullable=True)
    modal_price = Column(Numeric(10, 2), nullable=True)
    arrival_quantity = Column(Numeric(12, 2), nullable=True)
    source = Column(Text, default="AGMARKNET")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PriceIndex(Base):
    __tablename__ = "price_index"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_code = Column(String(2), ForeignKey("states.state_code"), nullable=True)
    division = Column(Text, nullable=True)
    month_year = Column(Date, nullable=False)
    general_index = Column(Numeric(8, 2), nullable=True)
    inflation_rate_pct = Column(Numeric(6, 2), nullable=True)
    rural_urban_combined = Column(Text, default="combined")
    source = Column(Text, default="MoSPI CPI")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
