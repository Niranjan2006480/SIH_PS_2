"""
Geography ORM models — States, Districts, Subdistricts, Villages, Locations
Mirrors the schema.sql geography layer exactly.
"""

import uuid

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, Double, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class State(Base):
    __tablename__ = "states"

    state_code = Column(String(2), primary_key=True)
    census_2011_code = Column(String(2), nullable=True)
    state_name = Column(Text, nullable=False)
    state_name_normalized = Column(Text, nullable=False)
    is_union_territory = Column(Boolean, default=False)
    region = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    districts = relationship("District", back_populates="state")


class District(Base):
    __tablename__ = "districts"

    district_lgd_code = Column(String(10), primary_key=True)
    district_census_code = Column(String(10), nullable=True)
    state_code = Column(String(2), ForeignKey("states.state_code"), nullable=False)
    district_name = Column(Text, nullable=False)
    district_name_normalized = Column(Text, nullable=False)
    is_pilot_active = Column(Boolean, default=False)
    data_completeness_pct = Column(Double, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    state = relationship("State", back_populates="districts")
    subdistricts = relationship("Subdistrict", back_populates="district")


class Subdistrict(Base):
    __tablename__ = "subdistricts"

    subdistrict_lgd_code = Column(String(10), primary_key=True)
    district_lgd_code = Column(String(10), ForeignKey("districts.district_lgd_code"), nullable=False)
    subdistrict_name = Column(Text, nullable=False)
    subdistrict_name_normalized = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    district = relationship("District", back_populates="subdistricts")
    villages = relationship("Village", back_populates="subdistrict")


class Village(Base):
    __tablename__ = "villages"

    village_lgd_code = Column(String(15), primary_key=True)
    village_census_2011_code = Column(String(15), nullable=True)
    subdistrict_lgd_code = Column(String(10), ForeignKey("subdistricts.subdistrict_lgd_code"), nullable=False)
    district_lgd_code = Column(String(10), ForeignKey("districts.district_lgd_code"), nullable=False)
    state_code = Column(String(2), ForeignKey("states.state_code"), nullable=False)
    village_name = Column(Text, nullable=False)
    village_name_normalized = Column(Text, nullable=False)
    local_body_code = Column(String(15), nullable=True)
    local_body_name = Column(Text, nullable=True)
    is_pilot_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    subdistrict = relationship("Subdistrict", back_populates="villages")
    location = relationship("Location", back_populates="village", uselist=False)


class Location(Base):
    __tablename__ = "locations"

    location_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_lgd_code = Column(String(15), ForeignKey("villages.village_lgd_code"), unique=True)
    latitude = Column(Double, nullable=False)
    longitude = Column(Double, nullable=False)
    geom = Column(Geometry("Point", srid=4326), nullable=False)
    coordinate_source = Column(Text, nullable=False)
    coordinate_accuracy = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    village = relationship("Village", back_populates="location")
