# 添加新Facebook广告账户 - SQL命令详细解释

## 步骤3：添加新的Facebook广告账户

### SQL命令

```sql
INSERT INTO ad_account_owner_mapping (ad_account_id, owner) 
VALUES ('act_1867789100501535', '小一')
ON DUPLICATE KEY UPDATE owner = VALUES(owner);
```

**命令分解：**

1. **`INSERT INTO ad_account_owner_mapping (ad_account_id, owner)`**
   - `INSERT INTO`：插入数据到表中
   - `ad_account_owner_mapping`：目标表名（广告账户→负责人映射表）
   - `(ad_account_id, owner)`：要插入的字段列表
     - `ad_account_id`：广告账户ID
     - `owner`：负责人名称

2. **`VALUES ('act_1867789100501535', '小一')`**
   - `'act_1867789100501535'`：新的Facebook广告账户ID
     - 注意：必须以 `act_` 开头
   - `'小一'`：负责人名称

3. **`ON DUPLICATE KEY UPDATE owner = VALUES(owner)`**
   - `ON DUPLICATE KEY`：如果插入时遇到唯一键冲突（账户ID已存在）
   - `UPDATE owner = VALUES(owner)`：更新负责人字段为新值
   - 作用：如果账户已存在，就更新负责人；如果不存在，就插入

**整体作用：**
- 将新的Facebook广告账户 `act_1867789100501535` 添加到映射表
- 关联到负责人"小一"
- 如果账户已存在，就更新负责人为"小一"

**为什么需要这个映射？**
- 数据同步脚本需要知道每个广告账户属于哪个负责人
- 这样才能正确地将广告花费数据关联到负责人
- 用于后续的数据聚合和ROAS计算

---

## 执行后验证

执行完这个SQL后，运行以下查询验证：

```sql
-- 查看"小一"的所有Facebook广告账户
SELECT ad_account_id, owner 
FROM ad_account_owner_mapping 
WHERE owner = '小一';
```

**预期结果：**
```
+----------------------+------+
| ad_account_id        | owner|
+----------------------+------+
| act_1867789100501535 | 小一 |
+----------------------+------+
```

**注意：**
- 如果之前"小一"已经有其他Facebook广告账户（如 `act_1899226041013050`），也会显示出来
- 新账户 `act_1867789100501535` 应该出现在列表中

---

## 验证账户是否已存在

如果想检查这个账户是否已经存在：

```sql
-- 检查账户是否已存在
SELECT ad_account_id, owner 
FROM ad_account_owner_mapping 
WHERE ad_account_id = 'act_1867789100501535';
```

**可能的结果：**
- 如果返回空：账户不存在，会插入新记录
- 如果有结果：账户已存在，会更新负责人为"小一"

---

## 总结

这个SQL的作用：
- ✅ 将新的Facebook广告账户添加到映射表
- ✅ 关联到负责人"小一"
- ✅ 如果账户已存在，就更新负责人

执行后，数据同步脚本就能识别这个新账户，并正确地将广告花费数据关联到"小一"。




