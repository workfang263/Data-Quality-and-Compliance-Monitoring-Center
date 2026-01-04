"""
数据库初始化脚本
用于插入测试店铺数据和创建默认管理员账号
"""
import sys
import os
# 设置Windows控制台UTF-8编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')

from database import Database
from utils import hash_password, setup_logging
from config import LOG_CONFIG

setup_logging(LOG_CONFIG['log_file'], LOG_CONFIG['log_level'])


def init_stores():
    """初始化店铺数据"""
    db = Database()
    
    # 测试店铺数据（示例，请替换为实际店铺信息）
    test_stores = [
        {
            'shop_domain': 'demo_store_1.myshoplaza.com',
            'access_token': 'YOUR_SHOPLAZZA_TOKEN_1_HERE',
            'is_active': True
        },
        {
            'shop_domain': 'demo_store_2.myshoplaza.com',
            'access_token': 'YOUR_SHOPLAZZA_TOKEN_2_HERE',
            'is_active': True
        }
    ]
    
    try:
        conn = db.get_connection()
        with conn.cursor() as cursor:
            for store in test_stores:
                # 检查是否已存在
                check_sql = "SELECT id FROM shoplazza_stores WHERE shop_domain = %s"
                cursor.execute(check_sql, (store['shop_domain'],))
                existing = cursor.fetchone()
                
                if existing:
                    print(f"店铺 {store['shop_domain']} 已存在，跳过")
                    continue
                
                # 插入新店铺
                insert_sql = """
                    INSERT INTO shoplazza_stores (shop_domain, access_token, is_active)
                    VALUES (%s, %s, %s)
                """
                cursor.execute(insert_sql, (
                    store['shop_domain'],
                    store['access_token'],
                    store['is_active']
                ))
                print(f"[OK] 成功插入店铺: {store['shop_domain']}")
        
        conn.commit()
        print(f"\n[OK] 成功初始化 {len(test_stores)} 个店铺")
        
    except Exception as e:
        print(f"[ERROR] 初始化店铺失败: {e}")
        sys.exit(1)


def init_admin_user():
    """初始化管理员账号"""
    db = Database()
    
    # 默认管理员账号
    admin_username = 'admin'
    admin_password = 'admin123'  # 默认密码，首次登录后请修改
    
    try:
        conn = db.get_connection()
        with conn.cursor() as cursor:
            # 检查是否已存在
            check_sql = "SELECT id FROM users WHERE username = %s"
            cursor.execute(check_sql, (admin_username,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"管理员账号 {admin_username} 已存在，跳过")
                return
            
            # 插入管理员账号
            password_hash = hash_password(admin_password)
            insert_sql = """
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, 'admin')
            """
            cursor.execute(insert_sql, (admin_username, password_hash))
            conn.commit()
            
            print(f"[OK] 成功创建管理员账号")
            print(f"  用户名: {admin_username}")
            print(f"  密码: {admin_password}")
            print(f"  [WARNING] 请首次登录后立即修改密码！")
        
    except Exception as e:
        print(f"[ERROR] 初始化管理员账号失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    print("=" * 50)
    print("数据库初始化脚本")
    print("=" * 50)
    
    print("\n1. 初始化店铺数据...")
    init_stores()
    
    print("\n2. 初始化管理员账号...")
    init_admin_user()
    
    print("\n" + "=" * 50)
    print("[OK] 初始化完成！")
    print("=" * 50)

