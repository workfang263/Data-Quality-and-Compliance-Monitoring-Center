# Vue迁移项目 - 详细TODO说明

## 📋 使用说明

这个文档配合TODO列表使用，每个任务都有详细的：
- **做什么**：具体要完成的任务
- **为什么**：为什么要这么做
- **怎么做**：详细的步骤
- **如何验证**：如何确认完成了
- **可能的问题**：常见问题和解决方案

---

## 🎯 阶段1：规划与准备

### ✅ 阶段1.1：创建基础目录结构（已完成）

**做什么**：创建 `backend/` 和 `frontend/` 目录

**为什么**：
- 新系统需要独立的目录结构
- 便于管理和维护
- 避免与旧系统文件混淆

**怎么做**：
```bash
# 在项目根目录创建
mkdir backend
mkdir frontend
```

**如何验证**：
- 检查 `backend/` 和 `frontend/` 目录是否存在
- 目录应该是空的

---

### 📝 阶段1.2：确定技术栈版本

**做什么**：确定要使用的技术栈及其版本号

**为什么**：
- 不同版本可能有API差异
- 确保团队使用相同版本
- 避免兼容性问题

**需要确定的版本**：
- FastAPI：推荐 `0.104.0+`
- Vue：推荐 `3.3.0+`
- TypeScript：推荐 `5.0.0+`
- Element Plus：推荐 `2.4.0+`
- ECharts：推荐 `5.4.0+`

**怎么做**：
1. 查询各技术栈的最新稳定版本
2. 记录在 `backend/requirements.txt` 和 `frontend/package.json` 中
3. 确认版本兼容性

**如何验证**：
- 查看版本文档，确认功能支持
- 检查版本之间的兼容性

**可能的问题**：
- 版本过新可能有bug → 选择稳定版本
- 版本过旧可能缺少功能 → 选择推荐的稳定版本

---

### 📝 阶段1.3：设计API接口规范

**做什么**：设计所有API接口的规范（路径、参数、返回值）

**为什么**：
- 前后端开发可以并行
- 接口规范明确，减少沟通成本
- 便于测试和文档生成

**需要设计的接口**：
1. `GET /api/dashboard/data` - 看板数据
2. `GET /api/owners/summary` - 负责人汇总
3. `GET /api/stores/list` - 店铺列表
4. `POST /api/auth/login` - 登录

**怎么做**：
1. 分析 `dashboard.py` 中的功能
2. 设计每个接口的：
   - 请求方法（GET/POST）
   - 路径
   - 请求参数（查询参数/请求体）
   - 返回数据结构
3. 写成文档或使用OpenAPI规范

**如何验证**：
- 接口规范文档完整
- 前后端都认可这个规范

**可能的问题**：
- 接口设计不合理 → 参考RESTful规范
- 数据结构复杂 → 使用Pydantic模型定义

---

### 📝 阶段1.4：设计前端路由结构

**做什么**：设计Vue Router的路由结构

**为什么**：
- 明确页面结构
- 便于导航和权限控制
- 符合前端路由最佳实践

**需要设计的路由**：
- `/` - 看板页面（默认）
- `/owners` - 负责人汇总
- `/stores` - 店铺列表
- `/login` - 登录页面

**怎么做**：
1. 分析 `dashboard.py` 中的页面结构
2. 设计路由层级
3. 确定路由守卫（哪些需要登录）

**如何验证**：
- 路由结构清晰
- 符合用户使用习惯

---

## 🚀 阶段2：搭建FastAPI后端框架

### 📝 阶段2.1：创建backend目录结构

**做什么**：创建 `backend/app/` 下的子目录

**为什么**：
- 代码组织清晰
- 符合FastAPI项目结构
- 便于维护和扩展

**目录结构**：
```
backend/
├── app/
│   ├── api/          # API路由
│   ├── services/     # 业务逻辑（数据库操作）
│   └── models/       # 数据模型（Pydantic）
├── config_new.py
└── requirements.txt
```

**怎么做**：
```bash
cd backend
mkdir -p app/api app/services app/models
```

**如何验证**：
- 检查目录结构是否正确
- 目录应该是空的

---

### 📝 阶段2.2：复制config.py到backend/config_new.py

**做什么**：复制配置文件并修改导入路径

**为什么**：
- 新系统需要自己的配置
- 完全隔离，不影响旧系统
- 可以独立修改配置

**怎么做**：
1. 复制 `config.py` 到 `backend/config_new.py`
2. 检查文件内容
3. 确认数据库配置正确

**如何验证**：
- `backend/config_new.py` 文件存在
- 内容与 `config.py` 一致（除了文件名）

**可能的问题**：
- 导入路径错误 → 检查相对路径
- 配置不完整 → 对比原文件

---

### 📝 阶段2.3：复制database.py到backend/app/services/database_new.py

**做什么**：复制数据库操作文件并修改导入路径

**为什么**：
- 新系统需要自己的数据库操作类
- 完全隔离，可以独立修改
- 复用现有逻辑，减少开发量

**怎么做**：
1. 复制 `database.py` 到 `backend/app/services/database_new.py`
2. 修改导入语句：
   ```python
   # 原：from config import DB_CONFIG
   # 改：from config_new import DB_CONFIG
   # 或者：import sys; sys.path.append('../..'); from config_new import DB_CONFIG
   ```
3. 检查所有导入路径

**如何验证**：
- 文件存在且内容正确
- 导入路径修改正确
- 可以正常导入（测试导入）

**可能的问题**：
- 导入路径错误 → 使用绝对导入或调整sys.path
- 依赖缺失 → 检查requirements.txt

---

### 📝 阶段2.4：创建backend/requirements.txt

**做什么**：创建Python依赖文件

**为什么**：
- 明确项目依赖
- 便于环境配置
- 确保团队使用相同版本

**需要包含的依赖**：
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pymysql>=1.1.0
pydantic>=2.0.0
python-multipart>=0.0.6
```

**怎么做**：
1. 创建 `backend/requirements.txt`
2. 写入依赖列表
3. 指定版本号（使用 `>=` 允许更新）

**如何验证**：
- 文件存在
- 依赖列表完整
- 版本号合理

**可能的问题**：
- 版本冲突 → 测试安装
- 依赖缺失 → 根据错误提示添加

---

### 📝 阶段2.5：创建backend/app/main.py

**做什么**：创建FastAPI应用入口

**为什么**：
- FastAPI需要一个主入口文件
- 配置CORS允许Vue前端访问
- 注册API路由

**怎么做**：
1. 创建 `backend/app/main.py`
2. 导入FastAPI
3. 配置CORS中间件
4. 创建app实例

**代码结构**：
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Shoplazza Dashboard API")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vue开发服务器
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（后续添加）
# app.include_router(dashboard.router)
```

**如何验证**：
- 文件存在
- 代码语法正确
- 可以启动服务（`uvicorn app.main:app --reload`）

**可能的问题**：
- CORS配置错误 → 检查允许的源
- 端口被占用 → 更换端口或关闭占用进程

---

### 📝 阶段2.6：创建第一个API接口

**做什么**：创建 `GET /api/dashboard/data` 接口

**为什么**：
- 这是核心功能
- 验证整个流程
- 为后续接口提供模板

**怎么做**：
1. 创建 `backend/app/api/dashboard_api.py`
2. 导入必要的模块
3. 创建路由和接口函数
4. 调用 `database_new.py` 的方法

**代码结构**：
```python
from fastapi import APIRouter
from app.services.database_new import Database

router = APIRouter()
db = Database()

@router.get("/api/dashboard/data")
async def get_dashboard_data(
    shop_domain: str = None,
    start_date: str = None,
    end_date: str = None
):
    # 调用数据库方法
    data = db.get_hourly_data_with_spend(...)
    return {"data": data}
```

**如何验证**：
- 接口可以访问
- 返回数据格式正确
- 在Swagger文档中测试

**可能的问题**：
- 数据库连接失败 → 检查配置
- 返回数据格式错误 → 检查序列化
- 参数验证失败 → 使用Pydantic模型

---

### 📝 阶段2.7：测试FastAPI服务

**做什么**：启动FastAPI服务并访问Swagger文档

**为什么**：
- 验证服务可以正常启动
- 查看自动生成的API文档
- 测试接口

**怎么做**：
1. 安装依赖：`pip install -r requirements.txt`
2. 启动服务：`uvicorn app.main:app --reload --port 8000`
3. 访问：`http://localhost:8000/docs`

**如何验证**：
- 服务启动成功
- Swagger文档可以访问
- 没有错误日志

**可能的问题**：
- 端口被占用 → 更换端口
- 依赖缺失 → 安装requirements.txt
- 导入错误 → 检查Python路径

---

### 📝 阶段2.8：测试第一个API接口

**做什么**：在Swagger文档中测试接口

**为什么**：
- 验证接口功能正常
- 检查返回数据
- 发现潜在问题

**怎么做**：
1. 在Swagger文档中找到接口
2. 点击"Try it out"
3. 输入参数（可选）
4. 点击"Execute"
5. 查看返回结果

**如何验证**：
- 接口返回200状态码
- 返回数据格式正确
- 数据内容符合预期

**可能的问题**：
- 返回500错误 → 查看后端日志
- 数据为空 → 检查数据库查询
- 参数错误 → 检查参数验证

---

## 🎨 阶段3：搭建Vue前端框架

### 📝 阶段3.1：创建Vue项目

**做什么**：使用Vite创建Vue3+TypeScript项目

**为什么**：
- Vite是现代化的构建工具
- TypeScript提供类型安全
- 符合最佳实践

**怎么做**：
```bash
cd frontend
npm create vite@latest . -- --template vue-ts
```

**如何验证**：
- 项目创建成功
- `package.json` 存在
- 可以运行 `npm run dev`

**可能的问题**：
- 目录不为空 → 在空目录中创建
- npm版本过低 → 更新npm
- 网络问题 → 使用国内镜像

---

### 📝 阶段3.2：安装依赖

**做什么**：安装Element Plus、Axios、Vue Router、ECharts等

**为什么**：
- 这些是项目必需的依赖
- 提前安装便于后续开发

**需要安装的依赖**：
```bash
npm install element-plus axios vue-router echarts vue-echarts
npm install -D @types/node
```

**如何验证**：
- `package.json` 中有依赖记录
- `node_modules` 目录存在
- 没有安装错误

**可能的问题**：
- 版本冲突 → 检查版本兼容性
- 网络问题 → 使用国内镜像
- 内存不足 → 增加Node.js内存限制

---

### 📝 阶段3.3：配置Vite

**做什么**：配置Vite（代理、环境变量等）

**为什么**：
- 开发时需要代理API请求
- 环境变量管理配置
- 优化开发体验

**怎么做**：
1. 创建 `.env.development` 文件
2. 配置 `vite.config.ts`
3. 设置代理（如果需要）

**如何验证**：
- 配置文件存在
- 代理配置正确
- 环境变量可以访问

---

### 📝 阶段3.4：创建Axios封装

**做什么**：创建HTTP请求封装

**为什么**：
- 统一管理API请求
- 添加拦截器（请求/响应）
- 统一错误处理

**怎么做**：
1. 创建 `frontend/src/api/request.ts`
2. 配置baseURL
3. 添加请求/响应拦截器
4. 导出axios实例

**如何验证**：
- 文件存在
- 可以正常导入
- 拦截器配置正确

---

### 📝 阶段3.5：配置Vue Router

**做什么**：配置前端路由

**为什么**：
- 实现单页应用导航
- 管理页面路由
- 支持路由守卫

**怎么做**：
1. 创建 `frontend/src/router/index.ts`
2. 定义路由配置
3. 导出router实例
4. 在 `main.ts` 中使用

**如何验证**：
- 路由配置正确
- 可以正常导航
- 路由守卫生效（如果有）

---

### 📝 阶段3.6：创建第一个页面（使用mock数据）

**做什么**：创建Dashboard.vue页面，先用mock数据

**为什么**：
- 先搭建页面结构
- 验证UI组件正常
- 不依赖后端，可以并行开发

**怎么做**：
1. 创建 `frontend/src/views/Dashboard.vue`
2. 使用Element Plus组件
3. 使用mock数据填充
4. 实现基本布局

**如何验证**：
- 页面可以正常显示
- UI组件正常渲染
- 没有控制台错误

---

### 📝 阶段3.7：创建API调用函数

**做什么**：创建调用后端API的函数

**为什么**：
- 封装API调用逻辑
- 统一管理API接口
- 便于维护和测试

**怎么做**：
1. 创建 `frontend/src/api/dashboard.ts`
2. 导入request实例
3. 定义API调用函数
4. 导出函数

**如何验证**：
- 文件存在
- 函数可以正常调用
- 类型定义正确（TypeScript）

---

### 📝 阶段3.8：连接后端API

**做什么**：在Dashboard.vue中调用API，替换mock数据

**为什么**：
- 实现真实数据展示
- 验证前后端联调
- 完成数据流

**怎么做**：
1. 在Dashboard.vue中导入API函数
2. 在 `onMounted` 中调用API
3. 处理加载状态
4. 处理错误情况
5. 替换mock数据

**如何验证**：
- 数据可以正常加载
- 页面显示真实数据
- 错误处理正常

---

### 📝 阶段3.9：测试前后端联调

**做什么**：启动前后端，验证数据流

**为什么**：
- 验证整个系统可以正常工作
- 发现集成问题
- 确认数据一致性

**怎么做**：
1. 启动FastAPI后端（端口8000）
2. 启动Vue前端（端口5173）
3. 在浏览器中访问前端
4. 测试数据加载
5. 检查网络请求

**如何验证**：
- 前端可以正常访问后端
- 数据可以正常加载
- 没有CORS错误
- 数据格式正确

**可能的问题**：
- CORS错误 → 检查后端CORS配置
- 网络错误 → 检查后端是否启动
- 数据格式错误 → 检查API返回格式

---

## 📝 后续阶段说明

阶段4-6的详细说明将在完成阶段3后补充，确保每个步骤都有清晰的指导。

---

## ⚠️ 重要原则

1. **一步一步做**：不要跳步骤，确保每步都完成
2. **验证再继续**：每完成一步都要验证
3. **遇到问题先分析**：不要盲目修改
4. **记录问题**：遇到问题记录下来，便于后续参考
5. **保持沟通**：有问题及时询问

---

**最后更新**：2025-12-18




