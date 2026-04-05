import openstack

from app.models.containers import ClusterTemplateInfo, ClusterInfo


def list_cluster_templates(conn: openstack.connection.Connection) -> list[ClusterTemplateInfo]:
    result = []
    for t in conn.container_infrastructure_management.cluster_templates():
        result.append(ClusterTemplateInfo(
            id=t.id,
            name=t.name or "",
            coe=t.coe or "",
            image_id=getattr(t, 'image_id', None),
            flavor_id=getattr(t, 'flavor_id', None),
            master_flavor_id=getattr(t, 'master_flavor_id', None),
            network_driver=getattr(t, 'network_driver', None),
            public=bool(getattr(t, 'public', False)),
            hidden=bool(getattr(t, 'hidden', False)),
            created_at=str(t.created_at) if getattr(t, 'created_at', None) else None,
        ))
    return result


def list_clusters(conn: openstack.connection.Connection) -> list[ClusterInfo]:
    result = []
    for c in conn.container_infrastructure_management.clusters():
        result.append(_cluster_to_info(c))
    return result


def get_cluster(conn: openstack.connection.Connection, cluster_id: str) -> ClusterInfo:
    c = conn.container_infrastructure_management.get_cluster(cluster_id)
    return _cluster_to_info(c)


def create_cluster(
    conn: openstack.connection.Connection,
    name: str,
    cluster_template_id: str,
    node_count: int = 1,
    master_count: int = 1,
    keypair: str | None = None,
    create_timeout: int | None = None,
) -> ClusterInfo:
    kwargs: dict = {
        "name": name,
        "cluster_template_id": cluster_template_id,
        "node_count": node_count,
        "master_count": master_count,
    }
    if keypair:
        kwargs["keypair"] = keypair
    if create_timeout is not None:
        kwargs["create_timeout"] = create_timeout
    c = conn.container_infrastructure_management.create_cluster(**kwargs)
    return _cluster_to_info(c)


def delete_cluster(conn: openstack.connection.Connection, cluster_id: str) -> None:
    conn.container_infrastructure_management.delete_cluster(cluster_id, ignore_missing=True)


def _cluster_to_info(c) -> ClusterInfo:
    return ClusterInfo(
        id=c.id,
        name=c.name or "",
        status=c.status or "",
        status_reason=getattr(c, 'status_reason', None),
        cluster_template_id=getattr(c, 'cluster_template_id', None),
        master_count=getattr(c, 'master_count', 1) or 1,
        node_count=getattr(c, 'node_count', 1) or 1,
        api_address=getattr(c, 'api_address', None),
        coe_version=getattr(c, 'coe_version', None),
        keypair=getattr(c, 'keypair', None),
        create_timeout=getattr(c, 'create_timeout', None),
        created_at=str(c.created_at) if getattr(c, 'created_at', None) else None,
        updated_at=str(c.updated_at) if getattr(c, 'updated_at', None) else None,
    )
