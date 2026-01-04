"""
端口检查工具
"""
import socket
import sys

def is_port_in_use(port: int, host: str = '0.0.0.0') -> bool:
    """
    检查端口是否被占用
    
    Args:
        port: 端口号
        host: 主机地址（默认0.0.0.0表示监听所有接口）
    
    Returns:
        True表示端口被占用，False表示端口可用
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.bind((host, port))
            return False  # 绑定成功，端口可用
    except OSError:
        return True  # 绑定失败，端口被占用


def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """
    查找可用端口
    
    Args:
        start_port: 起始端口号
        max_attempts: 最大尝试次数
    
    Returns:
        可用的端口号，如果找不到则返回None
    """
    for i in range(max_attempts):
        port = start_port + i
        if not is_port_in_use(port):
            return port
    return None


if __name__ == '__main__':
    # 测试
    port = 8502
    if is_port_in_use(port):
        print(f"端口 {port} 已被占用")
        available = find_available_port(port)
        if available:
            print(f"建议使用端口: {available}")
        else:
            print("未找到可用端口")
    else:
        print(f"端口 {port} 可用")





