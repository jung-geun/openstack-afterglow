-- 013: 셀프서비스 프로젝트 생성 + 이메일 초대 시스템
-- afterglow 자체 프로젝트 관리자 역할 추적 (Keystone과 별개)
CREATE TABLE IF NOT EXISTS project_roles (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  project_id  VARCHAR(64)  NOT NULL,
  user_id     VARCHAR(64)  NOT NULL,
  role        VARCHAR(32)  NOT NULL DEFAULT 'manager',
  granted_by  VARCHAR(64)  NOT NULL,
  created_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uq_project_user_role (project_id, user_id, role),
  KEY idx_project_roles_project (project_id),
  KEY idx_project_roles_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 이메일 초대 수명주기 관리
CREATE TABLE IF NOT EXISTS project_invitations (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  project_id       VARCHAR(64)   NOT NULL,
  invited_email    VARCHAR(255)  NOT NULL,
  invited_user_id  VARCHAR(64),
  invited_by       VARCHAR(64)   NOT NULL,
  invited_by_name  VARCHAR(255)  NOT NULL DEFAULT '',
  token_hash       VARCHAR(64)   NOT NULL UNIQUE,
  status           VARCHAR(16)   NOT NULL DEFAULT 'pending',
  keystone_role    VARCHAR(64)   NOT NULL DEFAULT 'member',
  expires_at       DATETIME(6)   NOT NULL,
  accepted_at      DATETIME(6),
  created_at       DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at       DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  KEY idx_project_invitations_status (project_id, status),
  KEY idx_project_invitations_email (invited_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
