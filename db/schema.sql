/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ad_account_owner_mapping` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ad_account_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ad_account_id` (`ad_account_id`)
) ENGINE=InnoDB AUTO_INCREMENT=86 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ad_account_timezone_mapping` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ad_account_id` varchar(64) NOT NULL,
  `timezone` varchar(64) NOT NULL COMMENT '时区名称',
  `timezone_offset` decimal(4,1) NOT NULL COMMENT '时区偏移量（小时）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ad_account_id` (`ad_account_id`),
  KEY `idx_ad_account_id` (`ad_account_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='广告账户时区配置表';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fb_ad_account_spend_hourly` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `time_hour` datetime NOT NULL,
  `ad_account_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `spend` decimal(18,4) NOT NULL,
  `currency` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_account_time` (`ad_account_id`,`time_hour`)
) ENGINE=InnoDB AUTO_INCREMENT=1707857 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `operation_logs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `log_type` varchar(50) NOT NULL COMMENT '日志类型：api_call, data_sync, error, manual_trigger',
  `shop_domain` varchar(255) DEFAULT NULL COMMENT '店铺域名（如果有）',
  `message` text NOT NULL COMMENT '日志内容',
  `status` varchar(20) DEFAULT NULL COMMENT '状态：success, error, warning',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_log_type` (`log_type`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=81308 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='操作日志表';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `owner_daily_summary` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `date` date NOT NULL,
  `owner` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `total_gmv` decimal(18,4) NOT NULL DEFAULT '0.0000',
  `total_orders` int NOT NULL DEFAULT '0',
  `total_visitors` int NOT NULL DEFAULT '0',
  `avg_order_value` decimal(18,4) NOT NULL DEFAULT '0.0000',
  `total_spend` decimal(18,4) NOT NULL DEFAULT '0.0000',
  `roas` decimal(18,4) DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `tt_total_spend` decimal(18,4) NOT NULL DEFAULT '0.0000' COMMENT 'TikTok广告花费',
  `total_spend_all` decimal(18,4) GENERATED ALWAYS AS ((`total_spend` + `tt_total_spend`)) STORED COMMENT '总广告花费(FB+TikTok)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_owner_date` (`owner`,`date`)
) ENGINE=InnoDB AUTO_INCREMENT=351748 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `owner_timezone_mapping` (
  `id` int NOT NULL AUTO_INCREMENT,
  `owner` varchar(255) NOT NULL,
  `timezone` varchar(64) NOT NULL COMMENT '时区名称，如 Asia/Shanghai, America/Los_Angeles',
  `timezone_offset` decimal(4,1) NOT NULL COMMENT '时区偏移量（小时），如 8.0 表示 UTC+8, -8.0 表示 UTC-8',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `owner` (`owner`),
  KEY `idx_owner` (`owner`)
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='负责人时区配置表';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `shoplazza_overview_hourly` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `time_hour` datetime NOT NULL COMMENT '小时时间点（北京时间UTC+8）',
  `total_gmv` decimal(15,2) NOT NULL COMMENT '总销售额（所有店铺订单total_price累加）',
  `total_orders` int NOT NULL COMMENT '总订单数（所有店铺订单count累加）',
  `total_visitors` int NOT NULL COMMENT '总访客数（所有店铺data.uv累加）',
  `avg_order_value` decimal(10,2) NOT NULL COMMENT '总客单价（total_gmv / total_orders）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_time_hour` (`time_hour`),
  KEY `idx_time_hour` (`time_hour`)
) ENGINE=InnoDB AUTO_INCREMENT=26361 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Shoplazza总店铺按小时聚合数据';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `shoplazza_store_hourly` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `shop_domain` varchar(255) NOT NULL COMMENT '店铺域名',
  `owner` varchar(255) DEFAULT NULL,
  `time_hour` datetime NOT NULL COMMENT '小时时间点（北京时间UTC+8）',
  `total_gmv` decimal(15,2) NOT NULL DEFAULT '0.00' COMMENT '销售额（来自订单接口total_price累加）',
  `total_orders` int NOT NULL DEFAULT '0' COMMENT '订单数（来自订单接口订单条数）',
  `total_visitors` int NOT NULL DEFAULT '0' COMMENT '访客数（来自分析接口uv，按天去重）',
  `avg_order_value` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '客单价（total_gmv / total_orders）',
  `gmv_from_analysis` decimal(15,2) DEFAULT '0.00' COMMENT '销售额（来自分析接口，用于对比）',
  `orders_from_analysis` int DEFAULT '0' COMMENT '订单数（来自分析接口，用于对比）',
  `gmv_diff` decimal(15,2) DEFAULT '0.00' COMMENT '销售额差异（订单接口 - 分析接口）',
  `orders_diff` int DEFAULT '0' COMMENT '订单数差异（订单接口 - 分析接口）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_shop_time` (`shop_domain`,`time_hour`),
  KEY `idx_shop_domain` (`shop_domain`),
  KEY `idx_time_hour` (`time_hour`),
  KEY `idx_shop_time` (`shop_domain`,`time_hour`)
) ENGINE=InnoDB AUTO_INCREMENT=662431 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='单店铺每小时明细数据表（用于逐店铺对比验证）';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `shoplazza_stores` (
  `id` int NOT NULL AUTO_INCREMENT,
  `shop_domain` varchar(255) NOT NULL COMMENT '店铺域名（例如：shop1.myshoplaza.com）',
  `access_token` text NOT NULL COMMENT '店铺API访问令牌',
  `is_active` tinyint(1) DEFAULT '1' COMMENT '是否启用（TRUE=启用，FALSE=禁用）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `shop_domain` (`shop_domain`),
  KEY `idx_is_active` (`is_active`)
) ENGINE=InnoDB AUTO_INCREMENT=42 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Shoplazza店铺配置表（45个店铺）';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `store_owner_mapping` (
  `id` int NOT NULL AUTO_INCREMENT,
  `shop_domain` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `shop_domain` (`shop_domain`)
) ENGINE=InnoDB AUTO_INCREMENT=57 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sync_status` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sync_type` varchar(50) NOT NULL COMMENT '同步类型（five_minute_realtime）',
  `last_sync_end_time` datetime NOT NULL COMMENT '最后收集的结束时间（精确到秒）',
  `last_sync_date` date NOT NULL COMMENT '最后同步日期',
  `last_visitor_cumulative` int DEFAULT '0' COMMENT '上次查询的累计访客数（所有店铺累加）',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `sync_type` (`sync_type`),
  KEY `idx_sync_type` (`sync_type`),
  KEY `idx_last_sync_date` (`last_sync_date`)
) ENGINE=InnoDB AUTO_INCREMENT=14298 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='数据同步状态表';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tt_ad_account_owner_mapping` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ad_account_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `business_center` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ad_account_id` (`ad_account_id`)
) ENGINE=InnoDB AUTO_INCREMENT=32 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tt_ad_account_spend_hourly` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `time_hour` datetime NOT NULL,
  `ad_account_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `spend` decimal(18,4) NOT NULL,
  `currency` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_account_time` (`ad_account_id`,`time_hour`)
) ENGINE=InnoDB AUTO_INCREMENT=437571 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tt_ad_account_timezone_mapping` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ad_account_id` varchar(64) NOT NULL,
  `timezone` varchar(64) NOT NULL COMMENT '时区名称',
  `timezone_offset` decimal(4,1) NOT NULL COMMENT '时区偏移量（小时）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ad_account_id` (`ad_account_id`),
  KEY `idx_ad_account_id` (`ad_account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='TikTok广告账户时区配置表';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_owner_permissions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL COMMENT '用户ID（外键关联users表）',
  `owner` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '负责人名称',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_owner` (`user_id`,`owner`) COMMENT '唯一约束：同一用户不能重复授权同一个负责人',
  KEY `idx_user_id` (`user_id`) COMMENT '用户ID索引',
  KEY `idx_owner` (`owner`) COMMENT '负责人索引'
) ENGINE=InnoDB AUTO_INCREMENT=86 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户权限表：存储普通用户可以查看的负责人列表';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL COMMENT '用户名',
  `password_hash` varchar(255) NOT NULL COMMENT '密码（加密后）',
  `role` enum('admin','user') DEFAULT 'user',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `can_view_dashboard` tinyint(1) DEFAULT '0' COMMENT '是否可以查看看板总数据（默认FALSE，普通用户不能查看）',
  `can_edit_mappings` tinyint(1) DEFAULT '0' COMMENT '是否可以编辑映射（默认FALSE，普通用户不能编辑）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  KEY `idx_username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户表（登录系统）';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

