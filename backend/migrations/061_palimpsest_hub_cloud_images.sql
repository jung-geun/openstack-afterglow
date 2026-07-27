-- Palimpsest 허브에 베이스 cloud image 종류 추가.
--
-- 배경: 로컬 KVM 은 "사용자가 로컬에서 빌드해 허브에 올리는" 환경이다. 그러려면 빌드의
-- 출발점인 **베이스 cloud image(qcow2)도 허브에서 받을 수 있어야** 한다. 지금까지 허브는
-- squashfs 레이어 blob 만 다뤘다.
--
-- 왜 별도 테이블이 아닌가: 업로드 세션·digest 재검증·Range 스트리밍·삭제 로직이 레이어와
-- 완전히 같다. 테이블을 나누면 그 machinery 를 통째로 복제하게 된다. `kind='cloud-image'` 로
-- 구분하고 레이어 전용 컬럼(parent_digest / chain_id / python_version)은 NULL 로 둔다.
--
-- 멱등: 컬럼 존재를 information_schema 로 확인 후 분기.

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'palimpsest_hub_layers'
    AND column_name = 'disk_format'
);
SET @ddl := IF(
  @col_exists = 0,
  'ALTER TABLE palimpsest_hub_layers
     ADD COLUMN disk_format VARCHAR(16) NULL AFTER media_type,
     ADD COLUMN arch        VARCHAR(16) NULL AFTER disk_format,
     ADD COLUMN os_variant  VARCHAR(64) NULL AFTER arch',
  'SELECT 1'
);
PREPARE palimpsest_hub_image_stmt FROM @ddl;
EXECUTE palimpsest_hub_image_stmt;
DEALLOCATE PREPARE palimpsest_hub_image_stmt;

-- kind 로 목록을 뽑는 조회(`/hub/images`)가 생기므로 인덱스를 둔다.
SET @idx_exists := (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'palimpsest_hub_layers'
    AND index_name = 'idx_palimpsest_hub_layers_kind'
);
SET @ddl := IF(
  @idx_exists = 0,
  'ALTER TABLE palimpsest_hub_layers ADD KEY idx_palimpsest_hub_layers_kind (kind)',
  'SELECT 1'
);
PREPARE palimpsest_hub_kind_idx_stmt FROM @ddl;
EXECUTE palimpsest_hub_kind_idx_stmt;
DEALLOCATE PREPARE palimpsest_hub_kind_idx_stmt;
