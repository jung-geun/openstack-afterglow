"""Background worker runtime manager API models."""

from typing import Literal

from pydantic import BaseModel, Field

WorkerRuntimeMode = Literal["static", "docker", "kubernetes"]
WorkerName = Literal["notion_worker"]


class WorkerRuntimeWorkerStatus(BaseModel):
    """Observed and desired state for one known background worker."""

    name: WorkerName
    enabled: bool
    module: str
    desired_replicas: int = Field(ge=0)
    max_replicas: int = Field(ge=0)
    observed_replicas: int | None = Field(default=None, ge=0)
    mode: WorkerRuntimeMode
    capable: bool
    reason: str | None = None


class WorkerRuntimeStatus(BaseModel):
    """Runtime-manager capability and per-worker state."""

    mode: WorkerRuntimeMode
    capable: bool
    reason: str | None = None
    workers: list[WorkerRuntimeWorkerStatus]


class WorkerDesiredItem(BaseModel):
    """Desired replica override for one worker."""

    name: WorkerName
    desired_replicas: int = Field(ge=0)


class WorkerDesiredPatch(BaseModel):
    """Shared desired replica overrides stored outside the API process."""

    workers: list[WorkerDesiredItem] = Field(min_length=1, max_length=1)
