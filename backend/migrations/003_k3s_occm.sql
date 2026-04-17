-- OCCM (OpenStack Cloud Controller Manager) 활성화 플래그 추가
ALTER TABLE k3s_clusters ADD COLUMN occm_enabled BOOLEAN NOT NULL DEFAULT FALSE;
