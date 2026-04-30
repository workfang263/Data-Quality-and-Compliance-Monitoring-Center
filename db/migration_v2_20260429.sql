-- ============================================
-- Migration v2: 数据库增量更新
-- Date: 2026-04-29
-- 兼容 MySQL 8.0+，全部使用 ALTER TABLE MODIFY/ADD，
-- 确保服务器已有表列类型与代码完全一致，可重复执行。
--
-- 执行方式：
--   mysql -u root -p shoplazza_dashboard < db/migration_v2_20260429.sql
-- ============================================

-- ============================================
-- 0. 辅助存储过程（执行完清理）
-- ============================================

-- 安全添加列：不存在才加
DROP PROCEDURE IF EXISTS add_col_if_missing;
DELIMITER //
CREATE PROCEDURE add_col_if_missing(
    IN tbl VARCHAR(128), IN col VARCHAR(128), IN def VARCHAR(1024)
)
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = tbl AND COLUMN_NAME = col
    ) THEN
        SET @s = CONCAT('ALTER TABLE `', tbl, '` ADD COLUMN `', col, '` ', def);
        PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;
    END IF;
END //
DELIMITER ;

-- 安全创建索引：不存在才加
DROP PROCEDURE IF EXISTS add_idx_if_missing;
DELIMITER //
CREATE PROCEDURE add_idx_if_missing(
    IN tbl VARCHAR(128), IN idx VARCHAR(128), IN cols VARCHAR(512)
)
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = tbl AND INDEX_NAME = idx
    ) THEN
        SET @s = CONCAT('CREATE INDEX `', idx, '` ON `', tbl, '` (', cols, ')');
        PREPARE st FROM @s; EXECUTE st; DEALLOCATE PREPARE st;
    END IF;
END //
DELIMITER ;


-- ============================================
-- A. 已有表 - 新增字段（ALTER TABLE ADD COLUMN）
-- ============================================

CALL add_col_if_missing('shoplazza_stores', 'display_name',
    "varchar(255) DEFAULT NULL COMMENT '店铺具体名称（可为空，用于运营页面展示）' AFTER `is_active`");

CALL add_col_if_missing('store_owner_mapping', 'display_name',
    "varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '店铺显示名称' AFTER `owner`");

CALL add_col_if_missing('users', 'can_view_store_ops',
    "tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否可查看店铺运营/员工归因报表' AFTER `can_edit_mappings`");


-- ============================================
-- B. 新表 - CREATE IF NOT EXISTS + 逐列 MODIFY 修正类型
-- ============================================

-- B1. mapping_resource_audit
CREATE TABLE IF NOT EXISTS `mapping_resource_audit` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `action` varchar(50) NOT NULL,
  `resource_type` varchar(50) NOT NULL,
  `resource_id` varchar(255) NOT NULL,
  `owner` varchar(255) DEFAULT NULL,
  `operator_user_id` int DEFAULT NULL,
  `operator_username` varchar(64) DEFAULT NULL,
  `request_payload` json DEFAULT NULL,
  `result_status` varchar(20) DEFAULT 'success',
  `result_message` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `mapping_resource_audit`
  MODIFY COLUMN `action`            varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `resource_type`     varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `resource_id`       varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `owner`             varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  MODIFY COLUMN `operator_user_id`  int DEFAULT NULL,
  MODIFY COLUMN `operator_username` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  MODIFY COLUMN `request_payload`   json DEFAULT NULL,
  MODIFY COLUMN `result_status`     varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'success',
  MODIFY COLUMN `result_message`    text COLLATE utf8mb4_unicode_ci,
  MODIFY COLUMN `created_at`        timestamp NULL DEFAULT CURRENT_TIMESTAMP;

CALL add_idx_if_missing('mapping_resource_audit', 'idx_resource_type', '`resource_type`');
CALL add_idx_if_missing('mapping_resource_audit', 'idx_action',        '`action`');
CALL add_idx_if_missing('mapping_resource_audit', 'idx_created_at',    '`created_at`');


-- B2. store_ops_shop_whitelist
CREATE TABLE IF NOT EXISTS `store_ops_shop_whitelist` (
  `id` int NOT NULL AUTO_INCREMENT,
  `shop_domain` varchar(255) NOT NULL,
  `is_enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `shop_domain` (`shop_domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `store_ops_shop_whitelist`
  MODIFY COLUMN `shop_domain` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `is_enabled` tinyint(1) NOT NULL DEFAULT 1,
  MODIFY COLUMN `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY COLUMN `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;


-- B3. store_ops_shop_ad_whitelist
CREATE TABLE IF NOT EXISTS `store_ops_shop_ad_whitelist` (
  `id` int NOT NULL AUTO_INCREMENT,
  `shop_domain` varchar(255) NOT NULL,
  `ad_account_id` varchar(64) NOT NULL,
  `is_enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ad_account_id` (`ad_account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `store_ops_shop_ad_whitelist`
  MODIFY COLUMN `shop_domain`   varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `ad_account_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `is_enabled`    tinyint(1) NOT NULL DEFAULT 1,
  MODIFY COLUMN `created_at`    timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY COLUMN `updated_at`    timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

CALL add_idx_if_missing('store_ops_shop_ad_whitelist', 'idx_shop_domain', '`shop_domain`');


-- B4. store_ops_employee_config
CREATE TABLE IF NOT EXISTS `store_ops_employee_config` (
  `id` int NOT NULL AUTO_INCREMENT,
  `employee_slug` varchar(32) NOT NULL,
  `display_name` varchar(64) NOT NULL,
  `utm_keyword` varchar(64) NOT NULL,
  `campaign_keyword` varchar(64) NOT NULL,
  `status` enum('active','blocked') NOT NULL DEFAULT 'active',
  `sort_order` int NOT NULL DEFAULT 100,
  `deleted_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `store_ops_employee_config`
  MODIFY COLUMN `employee_slug`    varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `display_name`     varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `utm_keyword`      varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `campaign_keyword` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `status`           enum('active','blocked') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  MODIFY COLUMN `sort_order`       int NOT NULL DEFAULT 100,
  MODIFY COLUMN `deleted_at`       timestamp NULL DEFAULT NULL,
  MODIFY COLUMN `created_at`       timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY COLUMN `updated_at`       timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;


-- B5. store_ops_config_audit
CREATE TABLE IF NOT EXISTS `store_ops_config_audit` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `resource_type` varchar(20) NOT NULL,
  `resource_key` varchar(255) NOT NULL,
  `action` varchar(20) NOT NULL,
  `actor_user_id` int DEFAULT NULL,
  `actor_username` varchar(64) DEFAULT NULL,
  `request_payload` json DEFAULT NULL,
  `result_status` varchar(20) DEFAULT NULL,
  `result_message` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `store_ops_config_audit`
  MODIFY COLUMN `resource_type`  varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `resource_key`   varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `action`         varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `actor_user_id`  int DEFAULT NULL,
  MODIFY COLUMN `actor_username` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  MODIFY COLUMN `request_payload` json DEFAULT NULL,
  MODIFY COLUMN `result_status`  varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  MODIFY COLUMN `result_message` text COLLATE utf8mb4_unicode_ci,
  MODIFY COLUMN `created_at`     timestamp NULL DEFAULT CURRENT_TIMESTAMP;

CALL add_idx_if_missing('store_ops_config_audit', 'idx_resource_type', '`resource_type`');
CALL add_idx_if_missing('store_ops_config_audit', 'idx_created_at',    '`created_at`');


-- B6. store_ops_order_attributions
CREATE TABLE IF NOT EXISTS `store_ops_order_attributions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `shop_domain` varchar(255) NOT NULL,
  `order_id` varchar(64) NOT NULL,
  `placed_at_raw` varchar(64) DEFAULT NULL,
  `biz_date` date NOT NULL,
  `total_price` decimal(18,4) NOT NULL,
  `currency` varchar(16) DEFAULT 'USD',
  `financial_status` varchar(32) DEFAULT NULL,
  `attribution_type` enum('employee','public_pool') NOT NULL,
  `employee_slug` varchar(64) DEFAULT NULL,
  `utm_decision` varchar(32) DEFAULT NULL,
  `source_url` text,
  `last_landing_url` text,
  `raw_json` longtext,
  `sync_run_id` char(36) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_shop_order` (`shop_domain`,`order_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `store_ops_order_attributions`
  MODIFY COLUMN `shop_domain`       varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `order_id`          varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `placed_at_raw`     varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  MODIFY COLUMN `biz_date`          date NOT NULL,
  MODIFY COLUMN `total_price`       decimal(18,4) NOT NULL,
  MODIFY COLUMN `currency`          varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT 'USD',
  MODIFY COLUMN `financial_status`  varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  MODIFY COLUMN `attribution_type`  enum('employee','public_pool') COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `employee_slug`     varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  MODIFY COLUMN `utm_decision`      varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  MODIFY COLUMN `source_url`        text COLLATE utf8mb4_unicode_ci,
  MODIFY COLUMN `last_landing_url`  text COLLATE utf8mb4_unicode_ci,
  MODIFY COLUMN `raw_json`          longtext COLLATE utf8mb4_unicode_ci,
  MODIFY COLUMN `sync_run_id`       char(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  MODIFY COLUMN `created_at`        timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY COLUMN `updated_at`        timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

CALL add_idx_if_missing('store_ops_order_attributions', 'idx_shop_biz_date', '`shop_domain`,`biz_date`');


-- B7. store_ops_sync_runs
CREATE TABLE IF NOT EXISTS `store_ops_sync_runs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sync_run_id` char(36) NOT NULL,
  `status` varchar(16) NOT NULL,
  `shops_json` json DEFAULT NULL,
  `biz_dates_json` json DEFAULT NULL,
  `orders_seen` int NOT NULL DEFAULT 0,
  `orders_upserted_paid` int NOT NULL DEFAULT 0,
  `orders_skipped_not_paid` int NOT NULL DEFAULT 0,
  `error_count` int NOT NULL DEFAULT 0,
  `errors_json` json DEFAULT NULL,
  `per_shop_json` json DEFAULT NULL,
  `exception_message` text,
  `started_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `finished_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sync_run_id` (`sync_run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `store_ops_sync_runs`
  MODIFY COLUMN `sync_run_id`        char(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `status`             varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  MODIFY COLUMN `shops_json`         json DEFAULT NULL,
  MODIFY COLUMN `biz_dates_json`     json DEFAULT NULL,
  MODIFY COLUMN `orders_seen`        int NOT NULL DEFAULT 0,
  MODIFY COLUMN `orders_upserted_paid` int NOT NULL DEFAULT 0,
  MODIFY COLUMN `orders_skipped_not_paid` int NOT NULL DEFAULT 0,
  MODIFY COLUMN `error_count`        int NOT NULL DEFAULT 0,
  MODIFY COLUMN `errors_json`        json DEFAULT NULL,
  MODIFY COLUMN `per_shop_json`      json DEFAULT NULL,
  MODIFY COLUMN `exception_message`  text COLLATE utf8mb4_unicode_ci,
  MODIFY COLUMN `started_at`         timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY COLUMN `finished_at`        timestamp NULL DEFAULT NULL;

CALL add_idx_if_missing('store_ops_sync_runs', 'idx_started_at', '`started_at`');


-- ============================================
-- 清理存储过程
-- ============================================
DROP PROCEDURE IF EXISTS add_col_if_missing;
DROP PROCEDURE IF EXISTS add_idx_if_missing;
