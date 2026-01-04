# Streamlit → Vue + FastAPI 迁移项目计划

## 📁 项目结构（已创建）

```
line chart/
├── backend/          ← 【新系统】FastAPI后端（已创建，待填充）
├── frontend/         ← 【新系统】Vue前端（已创建，待填充）
├── database.py       ← 【旧系统】继续使用
├── dashboard.py      ← 【旧系统】继续使用
└── config.py         ← 【旧系统】继续使用
```

---

## 🎯 项目目标

将现有的 Streamlit 系统迁移到 Vue + FastAPI 架构，实现前后端分离。

**采用方案二：复制代码，完全隔离**

### 核心原则
1. ✅ **完全隔离**：新旧系统互不影响
   - 新系统有自己的 `database_new.py`（复制自 `database.py`）
   - 新系统有自己的 `config_new.py`（复制自 `config.py`）
   - 修改新系统不会影响旧系统
2. ✅ **并行运行**：两个系统同时运行，不同端口
3. ✅ **共用数据库**：数据一致，无需迁移
4. ✅ **逐步切换**：功能模块逐步迁移，测试通过后再切换

---

## 📋 实施阶段规划

### 阶段1：规划与准备（当前阶段）

**目标**：明确需求，规划架构

**任务清单**：
- [x] 创建基础目录结构（backend/、frontend/）
- [ ] 确定技术栈版本
- [ ] 设计 API 接口规范
- [ ] 设计前端路由结构
- [ ] 确定命名规范

**输出**：
- 项目计划文档（本文档）
- 技术栈清单
- API 接口设计文档

---

### 阶段2：搭建 FastAPI 后端框架

**目标**：创建后端基础框架，实现第一个 API 接口

**任务清单**：
- [ ] 创建 `backend/app/main.py`（FastAPI 入口）
- [ ] 创建 `backend/app/services/database_new.py`（复制并修改 database.py）
- [ ] 创建 `backend/config_new.py`（复制并修改 config.py）
- [ ] 创建 `backend/requirements.txt`（FastAPI 依赖）
- [ ] 创建第一个 API：`GET /api/dashboard/data`（看板数据）
- [ ] 配置 CORS（允许 Vue 访问）
- [ ] 测试 API（使用 Swagger 文档）

**技术栈**：
- FastAPI
- pymysql（新系统复制 database.py，使用相同的数据库连接方式）
- Pydantic（数据验证）

**重要说明**：
- `database_new.py` 是**复制**自根目录的 `database.py`，不是导入
- 新系统完全独立，修改不会影响旧系统
- 两个系统共用同一个 MySQL 数据库（数据一致）

**输出**：
- FastAPI 基础框架
- 第一个可用的 API 接口
- Swagger 文档（自动生成）

---

### 阶段3：搭建 Vue 前端框架

**目标**：创建前端基础框架，实现第一个页面

**任务清单**：
- [ ] 创建 Vue 项目（使用 Vite）
- [ ] 安装依赖（Element Plus、Axios、Vue Router、ECharts）
- [ ] 配置 Axios（HTTP 请求封装）
- [ ] 配置 Vue Router（路由）
- [ ] 创建第一个页面：看板页面（Dashboard.vue）
- [ ] 使用 mock 数据先跑通页面
- [ ] 连接后端 API，替换 mock 数据

**技术栈**：
- Vue 3 + TypeScript
- Vite
- Element Plus
- Axios
- Vue Router
- ECharts

**输出**：
- Vue 基础框架
- 第一个可用的页面（看板页面）
- 前后端联调成功

---

### 阶段4：功能对齐（逐步实现）

**目标**：确保 Vue 版本功能与 Streamlit 版本一致

**功能模块清单**：

#### 4.1 登录认证
- [ ] 登录页面
- [ ] 登录 API
- [ ] Token 管理
- [ ] 路由守卫

#### 4.2 数据看板（主功能）
- [ ] 折线图展示（ECharts）
- [ ] 数据表格（Element Plus Table）
- [ ] 日期选择器
- [ ] 店铺筛选
- [ ] 粒度切换（小时/天）
- [ ] 数据对比功能
- [ ] CSV 导出

#### 4.3 负责人汇总
- [ ] 负责人表格
- [ ] 点击弹窗
- [ ] 小时趋势图

#### 4.4 店铺列表
- [ ] 店铺汇总表格
- [ ] 日期筛选
- [ ] 排序功能

**输出**：
- 所有功能模块实现完成
- 功能测试通过

---

### 阶段5：测试与优化

**目标**：确保新系统稳定可靠

**任务清单**：
- [ ] 功能测试（对比新旧系统数据一致性）
- [ ] 性能测试（响应速度、并发）
- [ ] 错误处理（网络错误、API 错误）
- [ ] UI/UX 优化
- [ ] 代码优化

**输出**：
- 测试报告
- 优化后的代码

---

### 阶段6：切换上线

**目标**：正式切换到新系统

**任务清单**：
- [ ] 通知用户（如有）
- [ ] 停止 Streamlit 服务
- [ ] 启动 FastAPI + Vue 服务
- [ ] 验证功能正常
- [ ] 保留 Streamlit 代码作为备份

**输出**：
- 新系统正式运行
- 旧系统代码备份

---

## 🔧 技术栈清单

### 后端（FastAPI）
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pymysql>=1.1.0
pydantic>=2.0.0
python-multipart>=0.0.6
```

### 前端（Vue）
```
vue@^3.3.0
typescript@^5.0.0
vite@^5.0.0
element-plus@^2.4.0
axios@^1.6.0
vue-router@^4.2.0
echarts@^5.4.0
vue-echarts@^6.6.0
```

---

## 📝 命名规范

### 目录命名
- `backend/` - 新系统后端（明显标识）
- `frontend/` - 新系统前端（明显标识）
- 根目录文件 - 旧系统（明显标识）

### 文件命名
- `database_new.py` - 新系统的数据库操作（区别于 `database.py`）
- `config_new.py` - 新系统的配置（区别于 `config.py`）
- `*_api.py` - API 路由文件（如 `dashboard_api.py`）

### 注释标识
每个新系统文件顶部添加注释：
```python
"""
【新系统】FastAPI后端 - 看板API
从 Streamlit dashboard.py 迁移而来
"""
```

---

## 🚀 下一步行动

1. **确定技术栈版本**（是否需要我帮你查最新稳定版本？）
2. **设计 API 接口规范**（需要我帮你设计吗？）
3. **开始阶段2：搭建 FastAPI 后端框架**

---

## ⚠️ 注意事项

1. **不要删除旧系统文件**：保留作为备份
2. **并行运行测试**：新旧系统同时运行，对比数据
3. **逐步切换**：功能模块逐个迁移，测试通过后再切换
4. **错误隔离**：新系统出错不影响旧系统

---

## 📊 进度跟踪

- [x] 阶段1：规划与准备（进行中）
- [ ] 阶段2：搭建 FastAPI 后端框架
- [ ] 阶段3：搭建 Vue 前端框架
- [ ] 阶段4：功能对齐
- [ ] 阶段5：测试与优化
- [ ] 阶段6：切换上线

---

**最后更新**：2025-12-18

