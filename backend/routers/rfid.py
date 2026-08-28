"""RFID router (Fase 5 — SIMULATOR).

Endpoint prefix /api. Perizinan:
- GET (baca)            → wms:view
- encode/retire/scan    → wms:scan  (warehouse/manager/admin)
- device write & seed   → role admin (infra)
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from dependencies import require_permission, require_role, audit
from entity_scope import entity_ctx, resolve_scope_ids
import services.rfid_service as rfid

router = APIRouter(prefix="/api")


# ─── Payloads ────────────────────────────────────────────────────────────────
class EncodePayload(BaseModel):
    roll_id: str
    epc: Optional[str] = None


class AutoEncodePayload(BaseModel):
    warehouse_id: Optional[str] = None


class DevicePayload(BaseModel):
    code: Optional[str] = None
    name: str
    type: str                      # gate | fixed_reader | handheld
    direction: Optional[str] = None  # in | out (gate saja)
    warehouse_id: str
    location: Optional[str] = None
    status: Optional[str] = None


class DevicePatch(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    direction: Optional[str] = None
    type: Optional[str] = None


class GateSimPayload(BaseModel):
    device_id: str
    roll_id: str


class ReaderScanPayload(BaseModel):
    device_id: str


class PrintJobPayload(BaseModel):
    roll_ids: list[str]


class VerifyScanPayload(BaseModel):
    epcs: list[str]


class RoutingPayload(BaseModel):
    roll_ids: list[str]
    routing: str  # store | cross_dock


# ─── Summary ─────────────────────────────────────────────────────────────────
@router.get("/rfid/summary")
async def get_summary(request: Request, warehouse_id: Optional[str] = None,
                      entity_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    scope = resolve_scope_ids(ctx, entity_id)
    return await rfid.rfid_summary(scope, warehouse_id)


# ─── Tags ────────────────────────────────────────────────────────────────────
@router.get("/rfid/tags")
async def get_tags(request: Request, warehouse_id: Optional[str] = None,
                   status: Optional[str] = None, entity_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    scope = resolve_scope_ids(ctx, entity_id)
    tags = await rfid.list_tags(scope, warehouse_id, status)
    return {"count": len(tags), "tags": tags}


@router.get("/rfid/untagged-rolls")
async def get_untagged(request: Request, warehouse_id: Optional[str] = None,
                       entity_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    scope = resolve_scope_ids(ctx, entity_id)
    rolls = await rfid.untagged_rolls(scope, warehouse_id)
    return {"count": len(rolls), "rolls": rolls}


@router.post("/rfid/tags/encode")
async def post_encode(payload: EncodePayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "scan")
    ctx = await entity_ctx(request)
    scope = resolve_scope_ids(ctx, None)
    tag = await rfid.encode_tag(payload.roll_id, scope, payload.epc, actor["name"])
    await audit(actor["name"], "rfid_tag_encoded", "rfid_tag", tag["id"],
                {"epc": tag["epc"], "roll_id": payload.roll_id})
    return tag


@router.post("/rfid/tags/auto-encode")
async def post_auto_encode(payload: AutoEncodePayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "scan")
    ctx = await entity_ctx(request)
    scope = resolve_scope_ids(ctx, None)
    res = await rfid.auto_encode(scope, payload.warehouse_id, actor["name"])
    await audit(actor["name"], "rfid_auto_encode", "rfid_tag", "batch", {"encoded": res["encoded"]})
    return res


@router.delete("/rfid/tags/{tag_id}")
async def delete_tag(tag_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "scan")
    ctx = await entity_ctx(request)
    scope = resolve_scope_ids(ctx, None)
    res = await rfid.retire_tag(tag_id, scope)
    await audit(actor["name"], "rfid_tag_retired", "rfid_tag", tag_id, {})
    return res


# ─── Devices ─────────────────────────────────────────────────────────────────
@router.get("/rfid/devices")
async def get_devices(request: Request, warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    devs = await rfid.list_devices(warehouse_id)
    return {"count": len(devs), "devices": devs}


@router.post("/rfid/devices")
async def post_device(payload: DevicePayload, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["admin"])
    dev = await rfid.create_device(payload.model_dump(), actor["name"])
    await audit(actor["name"], "rfid_device_created", "rfid_device", dev["id"], {"code": dev["code"]})
    return dev


@router.patch("/rfid/devices/{device_id}")
async def patch_device(device_id: str, payload: DevicePatch, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["admin"])
    dev = await rfid.update_device(device_id, payload.model_dump(exclude_none=True))
    await audit(actor["name"], "rfid_device_updated", "rfid_device", device_id, {})
    return dev


@router.delete("/rfid/devices/{device_id}")
async def del_device(device_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["admin"])
    res = await rfid.delete_device(device_id)
    await audit(actor["name"], "rfid_device_deleted", "rfid_device", device_id, {})
    return res


@router.post("/rfid/devices/seed-defaults")
async def post_seed_devices(request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["admin"])
    res = await rfid.seed_default_devices(actor["name"])
    await audit(actor["name"], "rfid_devices_seeded", "rfid_device", "batch", {"created": res["created"]})
    return res


# ─── Reads / Gate / Scan ─────────────────────────────────────────────────────
@router.get("/rfid/reads")
async def get_reads(request: Request, device_id: Optional[str] = None, result: Optional[str] = None,
                    read_type: Optional[str] = None, warehouse_id: Optional[str] = None,
                    limit: int = 100) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    reads = await rfid.list_reads(device_id, result, read_type, warehouse_id, min(limit, 300))
    return {"count": len(reads), "reads": reads}


@router.post("/rfid/gate/simulate")
async def post_gate_simulate(payload: GateSimPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "scan")
    ctx = await entity_ctx(request)
    scope = resolve_scope_ids(ctx, None)
    read = await rfid.gate_simulate(payload.device_id, payload.roll_id, scope)
    if read.get("result") == "red":
        await audit(actor["name"], "rfid_gate_alert", "rfid_read", read["id"],
                    {"reason": read.get("reason"), "roll_id": payload.roll_id})
    return read


@router.post("/rfid/reader/scan")
async def post_reader_scan(payload: ReaderScanPayload, request: Request) -> Dict[str, Any]:
    await require_permission(request, "wms", "scan")
    ctx = await entity_ctx(request)
    scope = resolve_scope_ids(ctx, None)
    return await rfid.reader_scan(payload.device_id, scope)


# ─── Locations ───────────────────────────────────────────────────────────────
@router.get("/rfid/locations")
async def get_locations(request: Request, warehouse_id: Optional[str] = None,
                        entity_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    scope = resolve_scope_ids(ctx, entity_id)
    items = await rfid.rfid_locations(scope, warehouse_id)
    return {"count": len(items), "items": items}


# ─── FASE R1 — Print Jobs & Verifikasi ───────────────────────────────────────
@router.get("/rfid/print-jobs")
async def get_print_jobs(request: Request, warehouse_id: Optional[str] = None,
                         status: Optional[str] = None, entity_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    from services import rfid_print_service as rps
    jobs = await rps.list_print_jobs(resolve_scope_ids(ctx, entity_id), warehouse_id, status)
    return {"count": len(jobs), "jobs": jobs}


@router.post("/rfid/print-jobs")
async def post_print_job(payload: PrintJobPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "scan")
    ctx = await entity_ctx(request)
    from services import rfid_print_service as rps
    job = await rps.create_print_job(payload.roll_ids, resolve_scope_ids(ctx, None), actor["name"])
    await audit(actor["name"], "rfid_print_job_created", "rfid_print_job", job["id"],
                {"job_number": job["job_number"], "items": job["item_count"]})
    return job


@router.get("/rfid/print-jobs/{job_id}")
async def get_print_job(job_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    from services import rfid_print_service as rps
    return await rps.get_print_job(job_id, resolve_scope_ids(ctx, None))


@router.get("/rfid/print-jobs/{job_id}/zpl")
async def get_print_job_zpl(job_id: str, request: Request):
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    from fastapi.responses import PlainTextResponse
    from services import rfid_print_service as rps
    job = await rps.get_print_job(job_id, resolve_scope_ids(ctx, None))
    return PlainTextResponse(rps.job_zpl(job), headers={
        "Content-Disposition": f"attachment; filename={job.get('job_number', job_id)}.zpl"})


@router.post("/rfid/print-jobs/{job_id}/mark-printed")
async def post_mark_printed(job_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "scan")
    ctx = await entity_ctx(request)
    from services import rfid_print_service as rps
    job = await rps.mark_printed(job_id, resolve_scope_ids(ctx, None))
    await audit(actor["name"], "rfid_print_job_printed", "rfid_print_job", job_id, {})
    return job


@router.post("/rfid/print-jobs/{job_id}/verify/start")
async def post_verify_start(job_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "scan")
    ctx = await entity_ctx(request)
    from services import rfid_print_service as rps
    return await rps.start_verify(job_id, resolve_scope_ids(ctx, None), actor["name"])


@router.post("/rfid/verify-sessions/{session_id}/scan")
async def post_verify_scan(session_id: str, payload: VerifyScanPayload, request: Request) -> Dict[str, Any]:
    await require_permission(request, "wms", "scan")
    ctx = await entity_ctx(request)
    from services import rfid_print_service as rps
    return await rps.scan_verify(session_id, payload.epcs, resolve_scope_ids(ctx, None))


@router.post("/rfid/verify-sessions/{session_id}/complete")
async def post_verify_complete(session_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "scan")
    ctx = await entity_ctx(request)
    from services import rfid_print_service as rps
    sess = await rps.complete_verify(session_id, resolve_scope_ids(ctx, None))
    await audit(actor["name"], "rfid_verify_completed", "rfid_verify_session", session_id,
                {"result": sess.get("result"), "missing": len(sess.get("missing", [])),
                 "extra": len(sess.get("extra", []))})
    return sess


@router.post("/rfid/rolls/set-routing")
async def post_set_routing(payload: RoutingPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "update")
    ctx = await entity_ctx(request)
    from services import rfid_print_service as rps
    res = await rps.set_routing(payload.roll_ids, payload.routing,
                                resolve_scope_ids(ctx, None), actor["name"])
    await audit(actor["name"], "roll_routing_set", "inventory_roll", "bulk",
                {"routing": payload.routing, "rolls": len(payload.roll_ids)})
    return res
