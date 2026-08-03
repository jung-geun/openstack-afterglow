-- 016: GPU PCI 장치 카탈로그 (관리자 추가 alias, 내장 기본값/afterglow.conf 위에 overlay)

CREATE TABLE IF NOT EXISTS gpu_device_catalog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vendor_id CHAR(4) NOT NULL,
    device_id CHAR(4) NOT NULL,
    name VARCHAR(128) NOT NULL,
    is_audio TINYINT(1) NOT NULL DEFAULT 0,
    aliases JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_gpu_device_vendor_device (vendor_id, device_id)
);
