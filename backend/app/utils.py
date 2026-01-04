"""
【新系统】FastAPI后端 - 工具函数模块
从根目录 utils.py 复制而来，完全独立，不影响旧系统
"""
import hashlib
import logging

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """密码加密（使用SHA256）"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return hash_password(password) == password_hash



