# 数据翻倍问题分析报告

## 问题现象
- 数据库数据 = API数据 × 2（正好2倍）
- 数据库内部一致（明细表 = 汇总表）
- 没有重复的小时记录

## 代码流程分析

### 1. 同步流程（`sync_realtime_data_five_minutes()`）

```
1. 获取最后同步时间 (last_sync_end_time)
2. 计算要收集的时间段 (start_time, end_time)
3. 收集数据
4. 使用 insert_or_update_hourly_data_incremental() 累加写入
5. 更新同步状态 (update_sync_status)
```

### 2. 关键代码位置

**时间段判断逻辑** (data_sync.py:1500-1521):
```python
if recent_5min_end <= last_sync_end_time:
    # 已收集，返回
    return
else:
    # 未收集，处理这个时间段
    start_time = recent_5min_start
    end_time = recent_5min_end
```

**累加写入** (database.py:739-740):
```python
total_gmv = total_gmv + VALUES(total_gmv),
total_orders = total_orders + VALUES(total_orders),
```

**同步状态更新** (database.py:697):
```python
last_sync_end_time = VALUES(last_sync_end_time),
```

## 可能的原因

### 原因1：竞态条件（Race Condition）⚠️ 最可能

**场景：**
1. 任务计划程序每5分钟执行一次
2. 如果脚本执行时间较长（>5分钟），可能出现两个进程同时运行
3. 两个进程读取到相同的 `last_sync_end_time`
4. 两个进程都认为需要处理同一个时间段
5. 两个进程都使用累加模式写入，导致数据翻倍

**时间线示例：**
```
10:00:00 - 进程A启动，读取 last_sync_end_time = 10:20:00
10:00:05 - 进程A判断需要处理 10:20:00-10:24:59
10:03:00 - 进程B启动（前一个还没完成），读取 last_sync_end_time = 10:20:00（还是旧值）
10:03:05 - 进程B也判断需要处理 10:20:00-10:24:59（重复！）
10:05:00 - 进程A写入数据（累加）
10:05:01 - 进程B写入数据（再次累加）→ 数据翻倍！
10:05:02 - 进程A更新同步状态为 10:24:59
10:05:03 - 进程B更新同步状态为 10:24:59（覆盖）
```

### 原因2：同步状态更新失败

如果 `update_sync_status()` 执行失败，下次运行时会重复处理相同的时间段。

### 原因3：脚本执行超时

如果脚本执行时间超过5分钟，下一个任务启动时可能还没有更新同步状态。

## 检查方法

1. **检查日志文件**：查看是否有两个进程同时处理同一个时间段
2. **检查脚本执行时间**：确认脚本是否能在5分钟内完成
3. **检查同步状态**：查看 `sync_status` 表的数据是否正常更新

## 验证步骤

1. 检查 `logs/app.log`，搜索是否有重复的时间段处理记录
2. 检查任务计划程序的执行历史，看是否有重叠执行
3. 检查脚本的实际执行时间

