-- 004_k3s_plugins.sql
-- k3s 클러스터에 활성 플러그인 목록 저장 컬럼 추가
-- plugins_enabled IS NULL이면 레거시 행 (occm_enabled 컬럼으로 폴백)
ALTER TABLE k3s_clusters ADD COLUMN plugins_enabled JSON DEFAULT NULL;
