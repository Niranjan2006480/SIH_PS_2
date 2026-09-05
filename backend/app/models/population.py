"""
Population & Economic ORM models
Covers: PopulationStats, StateEconomicProfile, PurchasingPowerBands
"""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class PopulationStats(Base):
    __tablename__ = "population_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_lgd_code = Column(String(15), ForeignKey("villages.village_lgd_code"), nullable=True)
    district_lgd_code = Column(String(10), ForeignKey("districts.district_lgd_code"), nullable=True)
    geographic_level = Column(Text, nullable=False)  # village | subdistrict | district | state
    source = Column(Text, nullable=False)
    source_year = Column(Integer, nullable=False)
    total_population = Column(Integer, nullable=True)
    male_population = Column(Integer, nullable=True)
    female_population = Column(Integer, nullable=True)
    total_households = Column(Integer, nullable=True)
    sex_ratio = Column(Numeric(6, 2), nullable=True)
    data_quality = Column(Text, default="medium")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StateEconomicProfile(Base):
    __tablename__ = "state_economic_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_code = Column(String(2), ForeignKey("states.state_code"), nullable=False)
    district_lgd_code = Column(String(10), ForeignKey("districts.district_lgd_code"), nullable=True)
    geographic_level = Column(Text, nullable=False)
    total_households = Column(Integer, nullable=True)
    deprived_households_pct = Column(Numeric(5, 2), nullable=True)
    income_lt_5000_pct = Column(Numeric(5, 2), nullable=True)
    income_5k_10k_pct = Column(Numeric(5, 2), nullable=True)
    income_gt_10k_pct = Column(Numeric(5, 2), nullable=True)
    literacy_rate_pct = Column(Numeric(5, 2), nullable=True)
    land_ownership_pct = Column(Numeric(5, 2), nullable=True)
    source = Column(Text, default="SECC 2011")
    source_year = Column(Integer, default=2011)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PurchasingPowerBand(Base):
    __tablename__ = "purchasing_power_bands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_code = Column(String(2), ForeignKey("states.state_code"), nullable=False)
    rural_urban = Column(Text, nullable=False)
    monthly_pcc_expenditure = Column(Numeric(10, 2), nullable=True)
    band_classification = Column(Text, nullable=True)
    source = Column(Text, default="HCES 2023-24")
    survey_year = Column(Integer, default=2024)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
