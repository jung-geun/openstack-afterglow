-- 006_k3s_plugin_status.sql
-- k3s 클러스터에 플러그인 적용 결과 및 cloud-config secret 상태 컬럼 추가
-- plugin_status: {"occm": {"status": "deployed"|"failed"|"not_deployed", "error": "..."}}
-- secret_cloud_config_status: "ok" | "failed" | NULL (cloud_conf 없는 경우)
ALTER TABLE k3s_clusters ADD COLUMN plugin_status JSON DEFAULT NULL;
ALTER TABLE k3s_clusters ADD COLUMN secret_cloud_config_status VARCHAR(20) DEFAULT NULL;
