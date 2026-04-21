import re
import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..services import query as query_service
from .helpers import wrap as _wrap

router = APIRouter(prefix="/api/asset-framework")

_SLUG_RE = re.compile(r"^[a-z0-9_]+$")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AssetCreate(BaseModel):
    asset_id: str = Field(min_length=1, max_length=100)
    asset_name: str = Field(min_length=1, max_length=200)
    asset_type: str
    parent_asset_id: str | None = None
    template_id: str | None = None
    site_name: str | None = None
    description: str | None = None
    capacity_mw: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    tag_count: int | None = None

    @field_validator("asset_id")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("asset_id must be lowercase alphanumeric with underscores")
        return v


class AssetUpdate(BaseModel):
    asset_name: str | None = None
    asset_type: str | None = None
    template_id: str | None = None
    site_name: str | None = None
    description: str | None = None
    capacity_mw: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    tag_count: int | None = None


class AssetMove(BaseModel):
    new_parent_id: str | None = None


class ApplyTemplate(BaseModel):
    template_id: str


class AttributeValueUpdate(BaseModel):
    attribute_id: str
    value: str | None = None


class AttributeValuesUpdate(BaseModel):
    values: list[AttributeValueUpdate]


class TemplateCreate(BaseModel):
    template_id: str = Field(min_length=1, max_length=100)
    template_name: str = Field(min_length=1, max_length=200)
    base_asset_type: str
    description: str | None = None

    @field_validator("template_id")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("template_id must be lowercase alphanumeric with underscores")
        return v


class TemplateUpdate(BaseModel):
    template_name: str | None = None
    description: str | None = None
    base_asset_type: str | None = None


class AttributeCreate(BaseModel):
    attribute_id: str = Field(min_length=1, max_length=100)
    attribute_name: str = Field(min_length=1, max_length=200)
    data_type: str = Field(pattern=r"^(DOUBLE|STRING|BOOLEAN|INT|TIMESTAMP)$")
    unit: str | None = None
    default_value: str | None = None
    is_required: bool = False
    sort_order: int = 0
    tag_pattern: str | None = None

    @field_validator("attribute_id")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("attribute_id must be lowercase alphanumeric with underscores")
        return v


class AttributeUpdate(BaseModel):
    attribute_name: str | None = None
    data_type: str | None = Field(default=None, pattern=r"^(DOUBLE|STRING|BOOLEAN|INT|TIMESTAMP)$")
    unit: str | None = None
    default_value: str | None = None
    is_required: bool | None = None
    sort_order: int | None = None
    tag_pattern: str | None = None


# ---------------------------------------------------------------------------
# Hierarchy routes
# ---------------------------------------------------------------------------

@router.get("/hierarchy")
async def get_hierarchy() -> dict:
    start = time.monotonic()
    data = await query_service.execute("hierarchy")
    return _wrap(data, start)


@router.post("/hierarchy", status_code=201)
async def create_asset(body: AssetCreate) -> dict:
    start = time.monotonic()
    await query_service.execute(
        "hierarchyCreate",
        asset_id=body.asset_id,
        asset_name=body.asset_name,
        asset_type=body.asset_type,
        parent_asset_id=body.parent_asset_id,
        template_id=body.template_id,
        site_name=body.site_name,
        description=body.description,
        capacity_mw=body.capacity_mw,
        latitude=body.latitude,
        longitude=body.longitude,
        tag_count=body.tag_count,
    )
    data = await query_service.execute("hierarchyAsset", asset_id=body.asset_id)
    if not data:
        raise HTTPException(status_code=500, detail="Failed to create asset")
    return _wrap(data[0], start)


@router.get("/hierarchy/tag-summary")
async def get_hierarchy_tag_summary(
    minutes: int = Query(default=60, ge=1, le=1440),
) -> dict:
    start = time.monotonic()
    data = await query_service.execute("hierarchyAssetTagSummary", minutes=minutes)
    return _wrap(data, start)


@router.get("/hierarchy/{asset_id}")
async def get_asset(asset_id: str) -> dict:
    start = time.monotonic()
    data = await query_service.execute("hierarchyAsset", asset_id=asset_id)
    if not data:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _wrap(data[0], start)


@router.get("/hierarchy/{asset_id}/tags")
async def get_asset_tags(
    asset_id: str,
    minutes: int = Query(default=60, ge=1, le=1440),
    include_unmapped: bool = Query(default=True),
) -> dict:
    start = time.monotonic()
    data = await query_service.execute(
        "hierarchyAssetTags",
        asset_id=asset_id,
        minutes=minutes,
        include_unmapped=include_unmapped,
    )
    return _wrap(data, start)


@router.put("/hierarchy/{asset_id}")
async def update_asset(asset_id: str, body: AssetUpdate) -> dict:
    start = time.monotonic()
    await query_service.execute(
        "hierarchyUpdate",
        asset_id=asset_id,
        asset_name=body.asset_name,
        asset_type=body.asset_type,
        template_id=body.template_id,
        site_name=body.site_name,
        description=body.description,
        capacity_mw=body.capacity_mw,
        latitude=body.latitude,
        longitude=body.longitude,
        tag_count=body.tag_count,
    )
    data = await query_service.execute("hierarchyAsset", asset_id=asset_id)
    if not data:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _wrap(data[0], start)


@router.delete("/hierarchy/{asset_id}")
async def delete_asset(asset_id: str) -> dict:
    start = time.monotonic()
    await query_service.execute("hierarchyDelete", asset_id=asset_id)
    return _wrap({"deleted": asset_id}, start)


@router.put("/hierarchy/{asset_id}/move")
async def move_asset(asset_id: str, body: AssetMove) -> dict:
    start = time.monotonic()
    await query_service.execute("hierarchyMove", asset_id=asset_id, new_parent_id=body.new_parent_id)
    data = await query_service.execute("hierarchyAsset", asset_id=asset_id)
    if not data:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _wrap(data[0], start)


@router.post("/hierarchy/{asset_id}/apply-template")
async def apply_template(asset_id: str, body: ApplyTemplate) -> dict:
    start = time.monotonic()
    # Update asset's template_id
    await query_service.execute("hierarchyUpdate", asset_id=asset_id, template_id=body.template_id)
    # Copy default attribute values
    await query_service.execute("applyTemplate", asset_id=asset_id, template_id=body.template_id)
    data = await query_service.execute("assetAttrValues", asset_id=asset_id)
    return _wrap(data, start)


@router.get("/hierarchy/{asset_id}/attributes")
async def get_asset_attributes(asset_id: str) -> dict:
    start = time.monotonic()
    data = await query_service.execute("assetAttrValues", asset_id=asset_id)
    return _wrap(data, start)


@router.put("/hierarchy/{asset_id}/attributes")
async def update_asset_attributes(asset_id: str, body: AttributeValuesUpdate) -> dict:
    start = time.monotonic()
    for av in body.values:
        await query_service.execute(
            "assetAttrValuesUpdate",
            asset_id=asset_id,
            attribute_id=av.attribute_id,
            value=av.value,
        )
    data = await query_service.execute("assetAttrValues", asset_id=asset_id)
    return _wrap(data, start)


# ---------------------------------------------------------------------------
# Template routes
# ---------------------------------------------------------------------------

@router.get("/templates")
async def list_templates() -> dict:
    start = time.monotonic()
    data = await query_service.execute("templatesList")
    return _wrap(data, start)


@router.post("/templates", status_code=201)
async def create_template(body: TemplateCreate) -> dict:
    start = time.monotonic()
    await query_service.execute(
        "templateCreate",
        template_id=body.template_id,
        template_name=body.template_name,
        base_asset_type=body.base_asset_type,
        description=body.description,
    )
    data = await query_service.execute("templateById", template_id=body.template_id)
    return _wrap(data, start)


@router.get("/templates/{template_id}")
async def get_template(template_id: str) -> dict:
    start = time.monotonic()
    data = await query_service.execute("templateById", template_id=template_id)
    if not data:
        raise HTTPException(status_code=404, detail="Template not found")
    assets = await query_service.execute("templateAssets", template_id=template_id)
    return _wrap({"template": data, "assets": assets}, start)


@router.put("/templates/{template_id}")
async def update_template(template_id: str, body: TemplateUpdate) -> dict:
    start = time.monotonic()
    await query_service.execute(
        "templateUpdate",
        template_id=template_id,
        template_name=body.template_name,
        description=body.description,
        base_asset_type=body.base_asset_type,
    )
    data = await query_service.execute("templateById", template_id=template_id)
    return _wrap(data, start)


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str) -> dict:
    start = time.monotonic()
    # Check if any assets reference this template
    assets = await query_service.execute("templateAssets", template_id=template_id)
    if assets:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete template: {len(assets)} asset(s) still reference it",
        )
    await query_service.execute("templateDelete", template_id=template_id)
    return _wrap({"deleted": template_id}, start)


@router.post("/templates/{template_id}/attributes", status_code=201)
async def create_attribute(template_id: str, body: AttributeCreate) -> dict:
    start = time.monotonic()
    await query_service.execute(
        "templateAttrCreate",
        attribute_id=body.attribute_id,
        template_id=template_id,
        attribute_name=body.attribute_name,
        data_type=body.data_type,
        unit=body.unit,
        default_value=body.default_value,
        is_required=body.is_required,
        sort_order=body.sort_order,
        tag_pattern=body.tag_pattern,
    )
    data = await query_service.execute("templateById", template_id=template_id)
    return _wrap(data, start)


@router.put("/templates/{template_id}/attributes/{attribute_id}")
async def update_attribute(template_id: str, attribute_id: str, body: AttributeUpdate) -> dict:
    start = time.monotonic()
    await query_service.execute(
        "templateAttrUpdate",
        attribute_id=attribute_id,
        attribute_name=body.attribute_name,
        data_type=body.data_type,
        unit=body.unit,
        default_value=body.default_value,
        is_required=body.is_required,
        sort_order=body.sort_order,
        tag_pattern=body.tag_pattern,
    )
    data = await query_service.execute("templateById", template_id=template_id)
    return _wrap(data, start)


@router.get("/hierarchy/{asset_id}/live-attributes")
async def get_live_attributes(asset_id: str) -> dict:
    start = time.monotonic()
    data = await query_service.execute("assetLiveAttrValues", asset_id=asset_id)
    return _wrap(data, start)


@router.get("/hierarchy/{asset_id}/aggregation")
async def get_child_aggregation(asset_id: str, minutes: int = 10) -> dict:
    start = time.monotonic()
    data = await query_service.execute(
        "hierarchyChildAggregation", asset_id=asset_id, minutes=minutes,
    )
    return _wrap(data, start)


@router.delete("/templates/{template_id}/attributes/{attribute_id}")
async def delete_attribute(template_id: str, attribute_id: str) -> dict:
    start = time.monotonic()
    await query_service.execute("templateAttrDelete", attribute_id=attribute_id)
    data = await query_service.execute("templateById", template_id=template_id)
    return _wrap(data, start)
