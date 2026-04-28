"""
【新系统】FastAPI后端 - 应用入口
这是FastAPI应用的主入口文件，负责：
1. 创建FastAPI应用实例
2. 配置CORS（允许Vue前端访问）
3. 注册API路由（含看板、权限、店铺运营/员工归因 store-ops 等，无需单独进程）

启动与重启：见 backend/README.md
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# 注入项目根（lib 包）与 backend（config_new），不依赖「必须从哪一目录启动 uvicorn」
_here = Path(__file__).resolve()
_BACKEND_ROOT = _here.parents[1]
_REPO_ROOT = _here.parents[2]
for _p in (_BACKEND_ROOT, _REPO_ROOT):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from lib.log_config import setup_logging
from config_new import LOG_CONFIG

setup_logging(LOG_CONFIG['log_file'], LOG_CONFIG['log_level'], LOG_CONFIG)


def _uvicorn_loggers_use_root_only() -> None:
    """去掉 uvicorn 自带 handler，避免与根 InterceptHandler 叠加导致同一条日志重复。"""
    for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


_uvicorn_loggers_use_root_only()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# 创建FastAPI应用实例
# title: API文档的标题
# description: API文档的描述（可选）
app = FastAPI(
    title="Shoplazza Dashboard API",
    description="Shoplazza多店铺数据看板API接口",
    version="1.0.0"
)

# 配置CORS（跨域资源共享）
# 为什么需要CORS？
# - Vue前端运行在 http://localhost:5173
# - FastAPI后端运行在 http://localhost:8000
# - 浏览器默认不允许跨域请求，需要后端明确允许
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（开发环境，生产环境应该限制具体域名）
    # 如果需要更安全的配置，可以这样写：
    # allow_origins=[
    #     "http://localhost:5173",
    #     "http://localhost:3000",
    #     "http://192.168.*:*",  # 允许局域网访问（需要根据实际IP段调整）
    # ],
    allow_credentials=True,  # 允许携带凭证（如Cookie、Token）
    allow_methods=["*"],      # 允许所有HTTP方法（GET、POST、PUT、DELETE等）
    allow_headers=["*"],      # 允许所有请求头
)

# 根路径：健康检查接口
@app.get("/")
async def root():
    """
    根路径接口，用于健康检查
    访问 http://localhost:8000/ 可以看到这个响应
    """
    return {
        "message": "Shoplazza Dashboard API is running",
        "status": "ok"
    }

# 添加请求日志中间件（记录所有API请求）
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有API请求和响应"""
    start_time = time.time()
    
    # 记录请求信息
    logger.info(f"📥 请求: {request.method} {request.url.path}?{request.url.query}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # 记录响应信息
        logger.info(f"📤 响应: {request.method} {request.url.path} - 状态码: {response.status_code} - 耗时: {process_time:.3f}秒")
        
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"❌ 错误: {request.method} {request.url.path} - 异常: {str(e)} - 耗时: {process_time:.3f}秒", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": f"服务器内部错误: {str(e)}"}
        )

# 注册API路由
from app.api import (
    dashboard_api,
    owners_api,
    mappings_api,
    audit_api,
    auth_api,
    permissions_api,
    store_ops_api,
    store_ops_config_api,
)

# 注册看板数据API路由
app.include_router(dashboard_api.router)

# 注册负责人汇总API路由
app.include_router(owners_api.router)

# 注册映射编辑API路由
app.include_router(mappings_api.router)

# 注册映射审计 API
app.include_router(audit_api.router)

# 注册用户认证API路由
app.include_router(auth_api.router)

# 注册权限管理API路由
app.include_router(permissions_api.router)

# 店铺运营 / 员工归因
app.include_router(store_ops_api.router)

# 店铺运营子系统配置中心（阶段 B.1：只读 GET）
app.include_router(store_ops_config_api.router)


# 应用启动时的初始化操作
@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化操作"""
    logger.info("🚀 应用启动中...")
    try:
        # 测试数据库连接
        from app.services.database_new import Database
        db = Database()
        logger.info("正在测试数据库连接...")
        conn = db.get_connection()
        conn.close()
        logger.info("✅ 数据库连接测试成功")
    except Exception as e:
        logger.error(f"❌ 数据库连接测试失败: {e}", exc_info=True)
        logger.error("⚠️  应用将继续启动，但数据库操作可能会失败")

