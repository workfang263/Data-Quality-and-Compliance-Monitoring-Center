"""
【新系统】FastAPI后端 - 用户认证API接口
提供用户登录、登出、获取当前用户信息等API接口
"""
from fastapi import APIRouter, HTTPException, Depends, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import jwt
import secrets

from app.services.database_new import Database
from app.utils import verify_password, hash_password

logger = logging.getLogger(__name__)

router = APIRouter()
# 延迟初始化 Database，避免模块导入时连接数据库
db: Optional[Database] = None

def get_db():
    """获取数据库实例（单例模式）"""
    global db
    if db is None:
        db = Database()
    return db

security = HTTPBearer()

# JWT密钥（生产环境应该使用环境变量）
SECRET_KEY = secrets.token_urlsafe(32)  # 生成随机密钥
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7  # Token有效期7天（记住我）


def create_access_token(username: str, remember_me: bool = False) -> str:
    """
    创建访问令牌（JWT）
    
    Args:
        username: 用户名
        remember_me: 是否记住我（影响token有效期）
    
    Returns:
        JWT token字符串
    """
    # 如果记住我，有效期7天；否则1天
    expire_days = ACCESS_TOKEN_EXPIRE_DAYS if remember_me else 1
    expire = datetime.utcnow() + timedelta(days=expire_days)
    
    payload = {
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证JWT token
    
    Args:
        token: JWT token字符串
    
    Returns:
        如果验证成功，返回payload字典；否则返回None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token已过期")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Token无效")
        return None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    从请求头中获取当前用户信息（依赖注入）
    
    Args:
        credentials: HTTP Bearer token凭证
    
    Returns:
        用户信息字典
    
    Raises:
        HTTPException: 如果token无效或用户不存在
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username = payload.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token格式错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 从数据库获取用户信息
    user = get_db().get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 获取扩展权限（管理员自动拥有所有权限）
    user_role = user.get("role", "user")
    if user_role == "admin":
        can_view_dashboard = True
        can_edit_mappings = True
    else:
        extended_permissions = get_db().get_user_extended_permissions(user.get("id"))
        can_view_dashboard = extended_permissions.get("can_view_dashboard", False)
        can_edit_mappings = extended_permissions.get("can_edit_mappings", False)
    
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "role": user.get("role"),
        "can_view_dashboard": can_view_dashboard,
        "can_edit_mappings": can_edit_mappings
    }


# 登录请求模型
class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False


# 注册请求模型
class RegisterRequest(BaseModel):
    username: str
    password: str
    confirm_password: str


@router.post("/api/auth/login")
async def login(request_data: LoginRequest = Body(...)) -> Dict[str, Any]:
    """
    用户登录
    
    请求体：
    {
        "username": "admin",
        "password": "admin123",
        "remember_me": false
    }
    """
    try:
        # 验证用户名和密码
        user = get_db().get_user_by_username(request_data.username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        if not verify_password(request_data.password, user.get("password_hash", "")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 创建token
        token = create_access_token(request_data.username, request_data.remember_me)
        
        # 获取扩展权限（管理员自动拥有所有权限）
        user_role = user.get("role", "user")
        if user_role == "admin":
            can_view_dashboard = True
            can_edit_mappings = True
        else:
            extended_permissions = get_db().get_user_extended_permissions(user.get("id"))
            can_view_dashboard = extended_permissions.get("can_view_dashboard", False)
            can_edit_mappings = extended_permissions.get("can_edit_mappings", False)
        
        return {
            "code": 200,
            "message": "登录成功",
            "data": {
                "token": token,
                "user": {
                    "id": user.get("id"),
                    "username": user.get("username"),
                    "role": user.get("role"),
                    "can_view_dashboard": can_view_dashboard,
                    "can_edit_mappings": can_edit_mappings
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {str(e)}"
        )


@router.post("/api/auth/logout")
async def logout(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    用户登出（实际上只是返回成功，真正的登出由前端删除token完成）
    """
    return {
        "code": 200,
        "message": "登出成功",
        "data": None
    }


@router.post("/api/auth/register")
async def register(request_data: RegisterRequest = Body(...)) -> Dict[str, Any]:
    """
    用户注册
    
    请求体：
    {
        "username": "新用户名",
        "password": "密码",
        "confirm_password": "确认密码"
    }
    """
    try:
        # 验证密码和确认密码是否一致
        if request_data.password != request_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码和确认密码不一致"
            )
        
        # 验证密码长度（至少6位）
        if len(request_data.password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码长度至少6位"
            )
        
        # 验证用户名长度（至少3位）
        if len(request_data.username) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名长度至少3位"
            )
        
        # 检查用户名是否已存在
        existing_user = get_db().get_user_by_username(request_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        
        # 创建新用户（默认角色为user）
        password_hash = hash_password(request_data.password)
        with get_db().get_connection() as conn:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO users (username, password_hash, role)
                    VALUES (%s, %s, 'user')
                """
                cursor.execute(sql, (request_data.username, password_hash))
                conn.commit()
                user_id = cursor.lastrowid
        
        logger.info(f"新用户注册成功: {request_data.username}")
        
        return {
            "code": 200,
            "message": "注册成功",
            "data": {
                "user": {
                    "id": user_id,
                    "username": request_data.username,
                    "role": "user"
                }
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )


@router.get("/api/auth/me")
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    获取当前登录用户信息
    """
    return {
        "code": 200,
        "message": "success",
        "data": current_user
    }

