"""
Location Schemas — Request/Response models for location resolution.
"""


from pydantic import BaseModel, Field


class LocationSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Village/district name to search")
    state_code: str | None = Field(None, description="Optional 2-digit state code to narrow search")
    limit: int = Field(10, ge=1, le=50)


class VillageResult(BaseModel):
    village_lgd_code: str
    village_name: str
    subdistrict_name: str
    district_name: str
    state_name: str
    state_code: str
    latitude: float | None = None
    longitude: float | None = None
    has_coordinates: bool = False

    model_config = {"from_attributes": True}


class LocationSearchResponse(BaseModel):
    results: list[VillageResult]
    total: int
    query: str


class VillageDetail(BaseModel):
    village_lgd_code: str
    village_name: str
    subdistrict_lgd_code: str
    subdistrict_name: str
    district_lgd_code: str
    district_name: str
    state_code: str
    state_name: str
    latitude: float | None = None
    longitude: float | None = None
    coordinate_source: str | None = None
    has_coordinates: bool = False

    model_config = {"from_attributes": True}


class HierarchyNode(BaseModel):
    code: str
    name: str
    children: list["HierarchyNode"] = []


class StateHierarchyResponse(BaseModel):
    state_code: str
    state_name: str
    districts: list[dict]
