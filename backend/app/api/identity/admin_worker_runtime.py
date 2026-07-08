"""Admin worker runtime manager endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models.worker_runtime import WorkerDesiredPatch, WorkerRuntimeStatus
from app.services.worker_runtime import get_runtime_status, patch_desired_counts, reconcile_once_with_lock

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/worker-runtime/status", response_model=WorkerRuntimeStatus)
async def get_worker_runtime_status() -> WorkerRuntimeStatus:
    """Return adapter capability plus desired/observed replicas for known workers."""
    return await get_runtime_status()


@router.patch("/worker-runtime/desired", response_model=WorkerRuntimeStatus)
async def patch_worker_runtime_desired(payload: WorkerDesiredPatch) -> WorkerRuntimeStatus:
    """Store shared desired replica overrides, then let the elected reconciler apply them."""
    updates = {item.name: item.desired_replicas for item in payload.workers}
    return await patch_desired_counts(updates)


@router.post("/worker-runtime/reconcile", response_model=WorkerRuntimeStatus | None)
async def reconcile_worker_runtime_now() -> WorkerRuntimeStatus | None:
    """Best-effort immediate reconcile using the same distributed lock as the background loop."""
    return await reconcile_once_with_lock()
