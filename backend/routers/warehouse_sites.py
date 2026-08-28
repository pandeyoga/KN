"""FASE R0 — Router lokasi gudang (sites) + seed blueprint peta gudang user."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from dependencies import require_permission, audit
from services import warehouse_profile_service as whp

router = APIRouter(prefix="/api")


class SitePayload(BaseModel):
    name: str
    city: Optional[str] = ""


class SitePatch(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None


@router.get("/warehouse-sites")
async def get_sites(request: Request) -> Dict[str, Any]:
    await require_permission(request, "warehouse", "view")
    return {"sites": await whp.list_sites()}


@router.post("/warehouse-sites")
async def post_site(payload: SitePayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "create")
    site = await whp.create_site(payload.name, payload.city or "", actor["name"])
    await audit(actor["name"], "warehouse_site_created", "warehouse_site", site["id"], site)
    return site


@router.patch("/warehouse-sites/{site_id}")
async def patch_site(site_id: str, payload: SitePatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "update")
    site = await whp.update_site(site_id, payload.model_dump(exclude_none=True))
    await audit(actor["name"], "warehouse_site_updated", "warehouse_site", site_id, site)
    return site


@router.delete("/warehouse-sites/{site_id}")
async def del_site(site_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "delete")
    res = await whp.delete_site(site_id)
    await audit(actor["name"], "warehouse_site_deleted", "warehouse_site", site_id, {})
    return res


@router.post("/warehouse-sites/seed-blueprint")
async def post_seed_blueprint(request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "create")
    res = await whp.seed_blueprint(actor["name"])
    await audit(actor["name"], "warehouse_blueprint_seeded", "warehouse_site", "blueprint", res)
    return res
