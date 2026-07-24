"""SQLAlchemy ORM 모델 — k3s 클러스터 및 Notion 설정 영속화."""

from datetime import UTC, datetime

from sqlalchemy import (
    BIGINT,
    BOOLEAN,
    CHAR,
    INT,
    JSON,
    TEXT,
    VARCHAR,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import MEDIUMBLOB, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class K3sCluster(Base):
    __tablename__ = "k3s_clusters"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(VARCHAR(63), nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="CREATING")
    status_reason: Mapped[str | None] = mapped_column(TEXT)

    # OpenStack 리소스 ID
    server_vm_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    server_flavor_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    agent_flavor_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    network_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    security_group_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    # API LB (K3s API 서버 앞단 Octavia LB + Floating IP)
    api_lb_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    api_lb_pool_id: Mapped[str | None] = mapped_column(VARCHAR(64))  # LB-first 방식: 클러스터 생성 시 pool 저장
    api_fip_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    api_fip_address: Mapped[str | None] = mapped_column(VARCHAR(45))

    # k3s 정보
    server_ip: Mapped[str | None] = mapped_column(VARCHAR(45))
    api_address: Mapped[str | None] = mapped_column(VARCHAR(255))
    k3s_version: Mapped[str | None] = mapped_column(VARCHAR(32))
    node_token: Mapped[str | None] = mapped_column(VARCHAR(512))  # 에이전트 join용

    # SSH / 접근
    key_name: Mapped[str | None] = mapped_column(VARCHAR(255))
    ssh_public_key: Mapped[str | None] = mapped_column(TEXT)

    # kubeconfig (AES-256-GCM 암호화 상태로 저장)
    kubeconfig_encrypted: Mapped[str | None] = mapped_column(TEXT)

    # 생성자 정보
    created_by_user_id: Mapped[str | None] = mapped_column(VARCHAR(64), index=True)
    created_by_username: Mapped[str | None] = mapped_column(VARCHAR(255))

    # 설정
    agent_count: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    occm_enabled: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    plugins_enabled: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"occm": true, ...}
    plugin_status: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # {"occm": {"status": "deployed", "error": ""}}
    secret_cloud_config_status: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)
    os_type: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="ubuntu")
    # Octavia Ingress Application Credential (per-cluster, managed by per-project manager user)
    app_credential_id: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    # soft-delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by_user_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    deleted_reason: Mapped[str | None] = mapped_column(VARCHAR(255))

    # HA 멀티 마스터 (1 | 3)
    master_count: Mapped[int] = mapped_column(INT, nullable=False, default=1)

    # Template 추적 (생성 시 사용한 템플릿)
    template_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    template_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Stampede 오토스케일 모드
    stampede_enabled: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)

    # 인증서 회전 추적
    last_rotation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_rotation_initiated_by: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)

    # 관계
    agent_vms: Mapped[list["K3sAgentVM"]] = relationship(
        "K3sAgentVM", back_populates="cluster", cascade="all, delete-orphan"
    )
    nodegroups: Mapped[list["K3sNodegroup"]] = relationship(
        "K3sNodegroup", back_populates="cluster", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_k3s_cluster_project_created", "project_id", "created_at"),)


class K3sAgentVM(Base):
    __tablename__ = "k3s_agent_vms"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    cluster_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("k3s_clusters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vm_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(VARCHAR(255))
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="CREATING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    cluster: Mapped["K3sCluster"] = relationship("K3sCluster", back_populates="agent_vms")


class GpuQuota(Base):
    """프로젝트별 GPU 타입 quota. limit=-1 은 무제한."""

    __tablename__ = "gpu_quotas"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    gpu_type: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)  # PCI alias (예: "RTX3090")
    limit: Mapped[int] = mapped_column(INT, nullable=False, default=-1)  # -1 = 무제한
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (Index("idx_gpu_quota_project_type", "project_id", "gpu_type", unique=True),)


class GpuDeviceCatalog(Base):
    """관리자가 추가한 GPU PCI 장치 카탈로그. 내장 기본값 + config.toml 위에 overlay된다."""

    __tablename__ = "gpu_device_catalog"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    vendor_id: Mapped[str] = mapped_column(CHAR(4), nullable=False)  # PCI vendor (예: "10DE")
    device_id: Mapped[str] = mapped_column(CHAR(4), nullable=False)  # PCI product (예: "2204")
    name: Mapped[str] = mapped_column(VARCHAR(128), nullable=False)
    is_audio: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # pci_passthrough alias 목록
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (Index("idx_gpu_device_vendor_device", "vendor_id", "device_id", unique=True),)


class NotionTarget(Base):
    """Notion 다중 연동 대상. API key는 AES-256-GCM 암호화 저장."""

    __tablename__ = "notion_targets"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, default="기본")

    # 민감 정보 — AES-256-GCM 암호화
    api_key_encrypted: Mapped[str] = mapped_column(TEXT, nullable=False)

    # 데이터베이스 ID (인스턴스 DB 필수, 나머지 선택)
    database_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, default="")
    users_database_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    hypervisors_database_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    gpu_spec_database_id: Mapped[str | None] = mapped_column(VARCHAR(64))

    # 동기화 설정
    enabled: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)
    interval_minutes: Mapped[int] = mapped_column(INT, nullable=False, default=30)

    # 마지막 동기화 시각
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hypervisors_last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gpu_spec_last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class ProjectDefaultNetwork(Base):
    """프로젝트별 기본 네트워크 설정. 자동 생성 또는 사용자가 직접 지정."""

    __tablename__ = "project_default_networks"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(64), unique=True, nullable=False, index=True)
    network_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    subnet_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    router_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    auto_created: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class NotionConfig(Base):
    """Notion 연동 설정 (싱글톤, id=1 고정). API key는 AES-256-GCM 암호화 저장."""

    __tablename__ = "notion_config"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)

    # 민감 정보 — AES-256-GCM 암호화
    api_key_encrypted: Mapped[str] = mapped_column(TEXT, nullable=False)

    # 데이터베이스 ID
    database_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, default="")
    users_database_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    hypervisors_database_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    gpu_spec_database_id: Mapped[str | None] = mapped_column(VARCHAR(64))

    # 동기화 설정
    enabled: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    interval_minutes: Mapped[int] = mapped_column(INT, nullable=False, default=30)

    # 마지막 동기화 시각
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hypervisors_last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gpu_spec_last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class LibraryRecipe(Base):
    """라이브러리별 빌드 레시피 — cloud-init ephemeral 빌드에 사용."""

    __tablename__ = "library_recipes"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    library_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(INT, nullable=False, default=1)

    # [{step: str, progress_pct: int, script: str}]
    commands: Mapped[list | None] = mapped_column(JSON, nullable=True)
    apt_packages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pip_packages: Mapped[list | None] = mapped_column(JSON, nullable=True)

    base_image_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    share_size_gb: Mapped[int] = mapped_column(INT, nullable=False, default=20)
    share_proto: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="NFS")
    cloud_init_template_version: Mapped[int] = mapped_column(INT, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (Index("idx_library_recipes_lib_ver", "library_id", "version", unique=True),)


class LibraryBuild(Base):
    """라이브러리 사전빌드 작업 추적 — Manila share + 빌더 VM 상태를 DB에 기록."""

    __tablename__ = "library_builds"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    library_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    file_storage_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    server_id: Mapped[str | None] = mapped_column(VARCHAR(64))

    # ephemeral 빌드 추가 필드
    recipe_id: Mapped[int | None] = mapped_column(INT, nullable=True)
    port_id: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)
    build_token: Mapped[str | None] = mapped_column(CHAR(32), nullable=True, unique=True)
    console_log_excerpt: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    # queued/booting/installing/finalizing/success/failure/indeterminate
    cloud_init_status: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)

    # 상태: pending, creating_share, creating_access, creating_vm, building, verifying, cleanup, complete, error, timeout
    status: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="pending")
    progress_step: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, default="")
    progress_pct: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(TEXT)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


# ---------------------------------------------------------------------------
# squashfs NFS 레이어 빌드/소비 추적
# ---------------------------------------------------------------------------


class LayerBuild(Base):
    """squashfs 레이어 빌드 작업 추적 — NFS Manila share에 .sqsh 파일 생성."""

    __tablename__ = "layer_builds"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    layer_name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, server_default="python")
    python_version: Mapped[str | None] = mapped_column(VARCHAR(16))
    profile_name: Mapped[str | None] = mapped_column(VARCHAR(64))
    pip_packages: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    apt_packages: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    ubuntu_base: Mapped[str] = mapped_column(
        VARCHAR(255),
        nullable=False,
        default="ubuntu-24.04-server-2026-04-15",
        server_default="ubuntu-24.04-server-2026-04-15",
    )
    base_image_id: Mapped[str | None] = mapped_column(VARCHAR(128), nullable=True)
    base_image_name: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    base_image_checksum: Mapped[str | None] = mapped_column(VARCHAR(128), nullable=True)
    base_image_os_hash_algo: Mapped[str | None] = mapped_column(VARCHAR(32), nullable=True)
    base_image_os_hash_value: Mapped[str | None] = mapped_column(VARCHAR(128), nullable=True)
    base_image_min_disk: Mapped[int | None] = mapped_column(INT, nullable=True)
    base_image_visibility: Mapped[str | None] = mapped_column(VARCHAR(32), nullable=True)
    base_image_owner: Mapped[str | None] = mapped_column(VARCHAR(128), nullable=True)
    source_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parent_artifact_id: Mapped[int | None] = mapped_column(
        INT,
        ForeignKey("layer_artifacts.id", name="fk_layer_builds_parent_artifact", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    share_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)

    # 빌더 VM 추적
    server_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    port_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    build_token: Mapped[str | None] = mapped_column(CHAR(32), nullable=True, unique=True)
    console_log_excerpt: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    # queued/booting/installing/finalizing/success/failure/indeterminate
    cloud_init_status: Mapped[str | None] = mapped_column(VARCHAR(20), nullable=True)

    # 상태: queued/creating_access/creating_vm/building/verifying/complete/error/cancelled
    status: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="pending")
    progress_step: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, default="")
    progress_pct: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(TEXT)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class LayerConsume(Base):
    """squashfs 레이어 소비 인스턴스 추적 — 관리자가 생성한 레이어 소비 VM."""

    __tablename__ = "layer_consumes"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    profile_name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    server_id: Mapped[str | None] = mapped_column(VARCHAR(64), index=True)
    port_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    share_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    project_id: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True, index=True)
    artifact_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    server_name: Mapped[str | None] = mapped_column(VARCHAR(128))

    # 상태: creating/active/error
    status: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="creating")
    error_message: Mapped[str | None] = mapped_column(TEXT)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LayerArtifact(Base):
    """squashfs 레이어 빌드 성공 시 생성되는 아티팩트 레코드.

    레이어별 동적 Manila NFS share 방식(per-layer-share):
    빌드 시 자기 share를 생성하고 RW access rule로 `.sqsh`를 기록한 뒤 RO로 봉인(is_sealed=True).
    소비 시 프로필 레이어 체인의 N개 share를 각각 RO 마운트한다.

    기존 `layer_artifacts` 테이블에 행이 있는 경우 신규 컬럼을 수동 ALTER해야 한다:
      ALTER TABLE layer_artifacts
        ADD COLUMN parent_id INT NULL,
        ADD COLUMN is_sealed TINYINT(1) NOT NULL DEFAULT 0,
        ADD CONSTRAINT fk_layer_artifacts_parent
          FOREIGN KEY (parent_id) REFERENCES layer_artifacts(id) ON DELETE SET NULL;
    """

    __tablename__ = "layer_artifacts"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    # "uv" | "python" | 기타 사용자 정의 kind
    kind: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, index=True)
    python_version: Mapped[str | None] = mapped_column(VARCHAR(16))
    pip_packages: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    apt_packages: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    ubuntu_base: Mapped[str] = mapped_column(
        VARCHAR(255),
        nullable=False,
        default="ubuntu-24.04-server-2026-04-15",
        server_default="ubuntu-24.04-server-2026-04-15",
    )
    base_image_id: Mapped[str | None] = mapped_column(VARCHAR(128), nullable=True)
    base_image_name: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    base_image_checksum: Mapped[str | None] = mapped_column(VARCHAR(128), nullable=True)
    base_image_os_hash_algo: Mapped[str | None] = mapped_column(VARCHAR(32), nullable=True)
    base_image_os_hash_value: Mapped[str | None] = mapped_column(VARCHAR(128), nullable=True)
    base_image_min_disk: Mapped[int | None] = mapped_column(INT, nullable=True)
    base_image_visibility: Mapped[str | None] = mapped_column(VARCHAR(32), nullable=True)
    base_image_owner: Mapped[str | None] = mapped_column(VARCHAR(128), nullable=True)
    source_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sqsh_filename: Mapped[str] = mapped_column(VARCHAR(256), nullable=False)
    # 이 레이어 전용 Manila NFS share ID (동적 생성, 봉인 후 RO)
    share_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    build_id: Mapped[int | None] = mapped_column(INT, ForeignKey("layer_builds.id", ondelete="SET NULL"))
    size_bytes: Mapped[int | None] = mapped_column(BIGINT)
    # 단일 부모 체인: child → parent → grandparent → ... → base(parent_id=NULL)
    parent_id: Mapped[int | None] = mapped_column(
        INT, ForeignKey("layer_artifacts.id", ondelete="SET NULL"), nullable=True
    )
    # 봉인 여부: 빌드 성공 후 RW rule 회수 완료 = True (소비 가능 상태)
    is_sealed: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    is_published: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)


class LayerImportJob(Base):
    """GitHub Dockerfile → squashfs layer chain import job."""

    __tablename__ = "layer_import_jobs"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(
        VARCHAR(32), nullable=False, default="github_dockerfile", server_default="github_dockerfile"
    )
    status: Mapped[str] = mapped_column(
        VARCHAR(32), nullable=False, default="queued", server_default="queued", index=True
    )
    progress_step: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)
    progress_pct: Mapped[int] = mapped_column(INT, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(TEXT, nullable=True)

    github_url: Mapped[str] = mapped_column(VARCHAR(512), nullable=False)
    repo_owner: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    repo_name: Mapped[str] = mapped_column(VARCHAR(128), nullable=False)
    commit_sha: Mapped[str] = mapped_column(CHAR(40), nullable=False)
    dockerfile_path: Mapped[str] = mapped_column(
        VARCHAR(255), nullable=False, default="Dockerfile", server_default="Dockerfile"
    )

    layer_prefix: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    profile_name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    ubuntu_base: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    base_image_id: Mapped[str] = mapped_column(VARCHAR(128), nullable=False)
    base_image_name: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    base_image_checksum: Mapped[str | None] = mapped_column(VARCHAR(128), nullable=True)
    base_image_os_hash_algo: Mapped[str | None] = mapped_column(VARCHAR(32), nullable=True)
    base_image_os_hash_value: Mapped[str | None] = mapped_column(VARCHAR(128), nullable=True)
    base_image_min_disk: Mapped[int | None] = mapped_column(INT, nullable=True)

    planned_layers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    artifact_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    build_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LayerProfile(Base):
    """레이어 프로필 — 여러 레이어를 순서 있는 리스트로 묶어 DB에 저장.

    소비 VM cloud-init에서 이 레이어 리스트를 주입해 OverlayFS를 구성한다.
    NFS /profiles/*.conf 파일을 대체하는 DB-based source of truth.
    """

    __tablename__ = "layer_profiles"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, unique=True, index=True)
    # JSON 배열: ["uv-latest", "python-latest"]  순서 = OverlayFS lowerdir 위→아래
    layers: Mapped[list] = mapped_column(JSON, nullable=False)
    is_published: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False, server_default="0", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


# ---------------------------------------------------------------------------
# Union Mount 레이어 시스템
# ---------------------------------------------------------------------------


class UnionLayer(Base):
    """Content-addressable 불변 레이어. id = 'sha256:<64hex>'."""

    __tablename__ = "union_layers"

    id: Mapped[str] = mapped_column(VARCHAR(71), primary_key=True)  # sha256:<64hex>
    name: Mapped[str] = mapped_column(VARCHAR(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    created_by: Mapped[str] = mapped_column(VARCHAR(128), nullable=False)
    sealed: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)

    # 단일 상속: 부모 0개(최상위) 또는 1개
    parent_id: Mapped[str | None] = mapped_column(
        VARCHAR(71), ForeignKey("union_layers.id", ondelete="RESTRICT"), index=True
    )
    # 다중 상속(실험, opt-in): parent_ids 가 NOT NULL 이면 multi 모드, parent_id 는 NULL.
    # 단일/다중은 mutually exclusive (둘 중 하나만 사용).
    parent_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # 최상위 레이어에만 있음: 어느 Ubuntu base 위에서 빌드됐는지
    ubuntu_base: Mapped[str | None] = mapped_column(VARCHAR(255))

    # 재현/재빌드용 메타데이터
    build_recipe: Mapped[dict] = mapped_column(JSON, nullable=False)
    installed_packages: Mapped[dict] = mapped_column(JSON, nullable=False)

    # 검증용
    content_hash: Mapped[str] = mapped_column(VARCHAR(71), nullable=False)  # sha256:<64hex>
    size_bytes: Mapped[int | None] = mapped_column(BIGINT)
    file_count: Mapped[int | None] = mapped_column(INT)

    # 프로젝트 격리 (NULL = 공유/시스템 레이어, 값 있음 = 해당 프로젝트 전용)
    project_id: Mapped[str | None] = mapped_column(VARCHAR(64), index=True)
    # 봉인 시각 (sealed=True 로 변경된 시점)
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 라이선스 메타데이터 (None = 제한 없음)
    license_type: Mapped[str | None] = mapped_column(VARCHAR(64))
    max_concurrent_mounts: Mapped[int | None] = mapped_column(INT)

    # 관계
    parent: Mapped["UnionLayer | None"] = relationship("UnionLayer", remote_side="UnionLayer.id")
    templates: Mapped[list["UnionTemplate"]] = relationship("UnionTemplate", back_populates="leaf_layer")

    __table_args__ = (
        Index("idx_union_layers_name_version", "name", "version"),
        Index("idx_union_layers_parent", "parent_id"),
    )


class UnionTemplate(Base):
    """이름 붙은 레이어 조합 (leaf layer + ubuntu base 지정)."""

    __tablename__ = "union_templates"

    name: Mapped[str] = mapped_column(VARCHAR(128), primary_key=True)
    version: Mapped[int] = mapped_column(INT, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    created_by: Mapped[str] = mapped_column(VARCHAR(128), nullable=False)
    parent_version: Mapped[int | None] = mapped_column(INT)
    ubuntu_base: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    leaf_layer_id: Mapped[str] = mapped_column(
        VARCHAR(71), ForeignKey("union_layers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    note: Mapped[str | None] = mapped_column(TEXT)

    # 관계
    leaf_layer: Mapped["UnionLayer"] = relationship("UnionLayer", back_populates="templates")


class UnionUserMount(Base):
    """사용자 VM 마운트 추적 (GC 판단 및 운영 가시성)."""

    __tablename__ = "union_user_mounts"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(VARCHAR(128), nullable=False, index=True)
    vm_hostname: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    leaf_layer_id: Mapped[str] = mapped_column(
        VARCHAR(71), ForeignKey("union_layers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    mounted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    unmounted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class K3sNodegroup(Base):
    """k3s 노드그룹. 클러스터 내 동일 role/flavor VM 집합."""

    __tablename__ = "k3s_nodegroups"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    cluster_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("k3s_clusters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(VARCHAR(63), nullable=False)
    role: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="agent")  # "server" | "agent"
    node_count: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    flavor_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    image_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    taints: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_default: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    # Stampede 오토스케일
    stampede_enabled: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    min_size: Mapped[int] = mapped_column(INT, nullable=False, default=0)
    max_size: Mapped[int] = mapped_column(INT, nullable=False, default=5)
    stampede_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cluster: Mapped["K3sCluster"] = relationship("K3sCluster", back_populates="nodegroups")
    vms: Mapped[list["K3sNodegroupVM"]] = relationship(
        "K3sNodegroupVM", back_populates="nodegroup", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_ng_cluster_role", "cluster_id", "role"),)


class K3sNodegroupVM(Base):
    """노드그룹 내 개별 VM 추적."""

    __tablename__ = "k3s_nodegroup_vms"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    nodegroup_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("k3s_nodegroups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cluster_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("k3s_clusters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vm_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(VARCHAR(255))
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="CREATING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    nodegroup: Mapped["K3sNodegroup"] = relationship("K3sNodegroup", back_populates="vms")


class K3sClusterTemplate(Base):
    """k3s 클러스터 프리셋. 운영자가 정의하고 사용자가 클러스터 생성 시 선택."""

    __tablename__ = "k3s_cluster_templates"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(63), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(TEXT)
    k3s_version: Mapped[str | None] = mapped_column(VARCHAR(32))
    default_node_count: Mapped[int] = mapped_column(INT, nullable=False, default=1)
    default_agent_flavor_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    default_image_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    plugins_enabled: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    os_type: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="ubuntu")
    public_visible: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProjectRole(Base):
    """afterglow 자체 프로젝트 관리자 역할 (Keystone role과 별개)."""

    __tablename__ = "project_roles"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="manager")
    granted_by: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)

    from sqlalchemy import UniqueConstraint

    __table_args__ = (UniqueConstraint("project_id", "user_id", "role", name="uq_project_user_role"),)


class ProjectInvitation(Base):
    """프로젝트 이메일 초대 수명주기."""

    __tablename__ = "project_invitations"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    invited_email: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    invited_user_id: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)
    invited_by: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    invited_by_name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False, default="")
    token_hash: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="pending")
    keystone_role: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, default="member")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_project_invitations_status", "project_id", "status"),
        Index("idx_project_invitations_email", "invited_email"),
    )


class LibraryCatalog(Base):
    """라이브러리 카탈로그 — 선택 가능한 라이브러리 정의 (이전: 코드 하드코딩)."""

    __tablename__ = "library_catalog"

    library_id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(128), nullable=False)
    version: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    packages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    depends_on: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    share_proto: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="CEPHFS")
    ubuntu_versions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    visibility: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="public")
    license_type: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)
    max_concurrent_mounts: Mapped[int | None] = mapped_column(INT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class SiteBrandingAsset(Base):
    """DB-backed public branding asset for login-page logo variants."""

    __tablename__ = "site_branding_assets"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    slot: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, unique=True, index=True)
    filename: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    content_type: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(INT, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    content: Mapped[bytes] = mapped_column(
        LargeBinary(length=1_048_576).with_variant(MEDIUMBLOB, "mysql", "mariadb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    updated_by_user_id: Mapped[str | None] = mapped_column(VARCHAR(64), nullable=True)


class UserTutorialStatus(Base):
    """사용자별 튜토리얼(투어) 진행 이력. (user_id, tour_id) 복합 PK.

    status='completed'(완주) | 'dismissed'(무시/패스). 기록이 없으면 미체험 상태로,
    프론트엔드가 해당 페이지의 튜토리얼 버튼을 강조한다. 완료·무시 어느 쪽이든 기록되면 강조 해제.
    user_id 는 항상 서버가 token_info 로 계산하며 클라이언트 입력을 신뢰하지 않는다(IDOR 방지).
    """

    __tablename__ = "user_tutorial_statuses"

    user_id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    tour_id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    status: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


# ---------------------------------------------------------------------------
# Waygate (WireGuard 게이트웨이 — Phase 1 서버 프로비저닝 + 클라이언트 관리)
# ---------------------------------------------------------------------------


class WaygateServer(Base):
    """Waygate 게이트웨이 인스턴스 1개.

    테넌트 프로젝트에 부팅되는 bastion VM. 서버 private key는 VM 내부에서만
    생성되고 백엔드 DB에는 절대 저장하지 않는다(마이그레이션 요구사항 ③ 자연 충족).
    """

    __tablename__ = "waygate_servers"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(VARCHAR(63), nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="CREATING")
    status_reason: Mapped[str | None] = mapped_column(TEXT)

    # OpenStack 리소스 ID
    server_vm_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    flavor_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    provider_network_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    provider_port_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    security_group_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    fip_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    endpoint_ip: Mapped[str | None] = mapped_column(VARCHAR(45))  # FIP 또는 provider fixed IP
    key_name: Mapped[str | None] = mapped_column(VARCHAR(255))

    # 에이전트 제어채널 자격증명 — AES-256-GCM 암호화 저장(도메인 wg_agent_token).
    # Redis(휘발성)가 아니라 여기에 durable 하게 보관해, Redis eviction/재시작이나 이전
    # 7일 TTL 만료 후에도 에이전트 register/desired-state/status 채널이 유지된다.
    agent_token_encrypted: Mapped[str | None] = mapped_column(TEXT)

    # WireGuard 설정
    server_public_key: Mapped[str | None] = mapped_column(VARCHAR(64))  # 에이전트 register가 채움
    listen_port: Mapped[int] = mapped_column(INT, nullable=False, default=51820)
    tunnel_cidr: Mapped[str] = mapped_column(VARCHAR(43), nullable=False, default="10.8.0.0/24")
    dns: Mapped[str | None] = mapped_column(VARCHAR(255))
    mtu: Mapped[int | None] = mapped_column(INT)

    # 생성자 정보
    created_by_user_id: Mapped[str | None] = mapped_column(VARCHAR(64), index=True)
    created_by_username: Mapped[str | None] = mapped_column(VARCHAR(255))

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    # soft-delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by_user_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    deleted_reason: Mapped[str | None] = mapped_column(VARCHAR(255))

    # 관계
    clients: Mapped[list["WaygateClient"]] = relationship(
        "WaygateClient", back_populates="server", cascade="all, delete-orphan"
    )
    network_attachments: Mapped[list["WaygateNetworkAttachment"]] = relationship(
        "WaygateNetworkAttachment", back_populates="server", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_waygate_server_project_created", "project_id", "created_at"),)


class WaygateClient(Base):
    """WireGuard peer(=wg-easy client). 클라이언트 private key는 AES-256-GCM 암호화 저장.

    private key는 백엔드가 X25519로 생성하며 서버 VM에는 절대 전송하지 않는다
    (서버는 peer의 public key만 필요).
    """

    __tablename__ = "waygate_clients"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("waygate_servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    # NOTE: soft-delete 시 NULL로 비워 uq_waygate_client_server_name 슬롯을 해제한다(아래 참고).
    name: Mapped[str | None] = mapped_column(VARCHAR(63))
    enabled: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)

    public_key: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    private_key_encrypted: Mapped[str] = mapped_column(TEXT, nullable=False)
    preshared_key_encrypted: Mapped[str | None] = mapped_column(TEXT)

    # NOTE: soft-delete 시 NULL로 비워 uq_waygate_client_server_tunnel_ip 슬롯을 해제한다.
    # MySQL/MariaDB는 partial/filtered unique index를 지원하지 않으므로, 활성 클라이언트만
    # unique 제약을 갖도록 하려면 값 자체를 NULL로 비우는 방법뿐이다(NULL은 unique index에서
    # 여러 번 허용됨). list_clients/list_all_active_clients 등 조회 경로는 전부
    # deleted_at IS NULL 필터를 거치므로, 활성 클라이언트의 name/tunnel_ip는 항상 non-null이다.
    tunnel_ip: Mapped[str | None] = mapped_column(VARCHAR(45))
    allowed_ips: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 클라이언트→서버 방향 route 대상
    dns: Mapped[str | None] = mapped_column(VARCHAR(255))

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    # soft-delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by_user_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    deleted_reason: Mapped[str | None] = mapped_column(VARCHAR(255))

    server: Mapped["WaygateServer"] = relationship("WaygateServer", back_populates="clients")

    __table_args__ = (
        UniqueConstraint("server_id", "tunnel_ip", name="uq_waygate_client_server_tunnel_ip"),
        UniqueConstraint("server_id", "name", name="uq_waygate_client_server_name"),
        Index("idx_waygate_client_project_created", "project_id", "created_at"),
    )


class WaygateNetworkAttachment(Base):
    """Waygate VM에 붙은 테넌트 네트워크 (Phase 2용 스키마 — Phase 1 API는 이 테이블을 사용하지 않음).

    다중 테넌트 네트워크 연결(요구사항 ②) 시 nova.attach_interface로 생성된 포트를 기록한다.
    """

    __tablename__ = "waygate_network_attachments"

    id: Mapped[int] = mapped_column(INT, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("waygate_servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    network_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    subnet_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    port_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    cidr: Mapped[str | None] = mapped_column(VARCHAR(43))  # NAT 대상
    nat_mode: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="snat")
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="CREATING")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    server: Mapped["WaygateServer"] = relationship("WaygateServer", back_populates="network_attachments")

    __table_args__ = (Index("idx_waygate_netattach_server", "server_id"),)


# ActivityLog 모델을 Base.metadata 에 등록 (create_tables 자동 감지)
from app.models.activity import ActivityLog  # noqa: E402,F401

# Announcement/AnnouncementRead 모델을 Base.metadata 에 등록 (create_tables 자동 감지)
from app.models.announcement import Announcement, AnnouncementRead  # noqa: E402,F401
from app.models.chat_assets import ChatAsset, ChatMessageAsset, ChatRunAsset  # noqa: E402,F401

# 빌트인 AI 채팅 모델을 Base.metadata 에 등록 (create_tables 자동 감지)
from app.models.chat_db import (  # noqa: E402,F401
    ChatConversation,
    ChatCustomTool,
    ChatMcpServer,
    ChatMessage,
    ChatUsageLog,
    LlmModel,
    LlmProvider,
    UserWallet,
)
from app.models.chat_jobs import ChatInputDerivation, ChatJob, ChatMemoryOutbox, ChatMemoryProvenance  # noqa: E402,F401
from app.models.chat_runs import (  # noqa: E402,F401
    ChatRun,
    ChatRunEventRow,
    ChatRunProvider,
    ChatRunSegment,
    ChatRunTurn,
    ChatSchedulerLease,
    ChatTempThread,
    ChatToolApproval,
)


class VmCloudInitSnippet(Base):
    """사용자별 VM cloud-init 실행 이력과 명명된 재사용 프리셋."""

    __tablename__ = "vm_cloud_init_snippets"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)  # history | preset
    name: Mapped[str | None] = mapped_column(VARCHAR(100))
    content_encrypted: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_vm_cloud_init_snippets_user_kind_created", "user_id", "kind", "created_at"),
        UniqueConstraint("user_id", "kind", "name", name="uq_vm_cloud_init_snippet_user_kind_name"),
    )


class ResourcePolicy(Base):
    """Global admin-owned selection of a discovered OpenStack resource."""

    __tablename__ = "resource_policies"

    policy_key: Mapped[str] = mapped_column(VARCHAR(100), primary_key=True)
    resource_kind: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(VARCHAR(128))
    resource_name: Mapped[str | None] = mapped_column(VARCHAR(255))
    constraints: Mapped[dict | None] = mapped_column(JSON)
    updated_by_user_id: Mapped[str | None] = mapped_column(VARCHAR(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    __table_args__ = (Index("idx_resource_policies_kind", "resource_kind"),)
