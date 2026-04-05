from pydantic import BaseModel
from typing import Optional


class ClusterTemplateInfo(BaseModel):
    id: str
    name: str
    coe: str              # kubernetes, swarm, mesos
    image_id: str | None = None
    flavor_id: str | None = None
    master_flavor_id: str | None = None
    network_driver: str | None = None
    public: bool = False
    hidden: bool = False
    created_at: str | None = None


class ClusterInfo(BaseModel):
    id: str
    name: str
    status: str
    status_reason: str | None = None
    cluster_template_id: str | None = None
    master_count: int = 1
    node_count: int = 1
    api_address: str | None = None
    coe_version: str | None = None
    keypair: str | None = None
    create_timeout: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CreateClusterRequest(BaseModel):
    name: str
    cluster_template_id: str
    node_count: int = 1
    master_count: int = 1
    keypair: str | None = None
    create_timeout: int | None = None


class ZunContainerInfo(BaseModel):
    uuid: str
    name: str
    status: str
    status_reason: str | None = None
    image: str | None = None
    command: str | None = None
    cpu: float | None = None
    memory: str | None = None
    created_at: str | None = None
    addresses: dict | None = None


class CreateZunContainerRequest(BaseModel):
    name: str
    image: str
    command: str | None = None
    cpu: float | None = None
    memory: str | None = None
    environment: dict | None = None
    auto_remove: bool = False
