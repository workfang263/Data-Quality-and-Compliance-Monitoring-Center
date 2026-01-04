"""
禁用指定店铺的脚本
用于禁用过期或不再使用的店铺
"""
import sys
from database import Database

def disable_store(shop_domain: str) -> bool:
    """
    禁用指定店铺
    
    Args:
        shop_domain: 店铺域名（例如：hedian.myshoplaza.com）
    
    Returns:
        是否成功
    """
    db = Database()
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                # 检查店铺是否存在
                check_sql = """
                    SELECT id, shop_domain, is_active
                    FROM shoplazza_stores
                    WHERE shop_domain = %s
                """
                cursor.execute(check_sql, (shop_domain,))
                store = cursor.fetchone()
                
                if not store:
                    print(f"❌ 店铺 {shop_domain} 不存在！")
                    return False
                
                if not store['is_active']:
                    print(f"ℹ️  店铺 {shop_domain} 已经是禁用状态")
                    return True
                
                # 禁用店铺
                update_sql = """
                    UPDATE shoplazza_stores
                    SET is_active = FALSE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE shop_domain = %s
                """
                cursor.execute(update_sql, (shop_domain,))
                conn.commit()
                
                print(f"✅ 成功禁用店铺: {shop_domain}")
                return True
                
    except Exception as e:
        print(f"❌ 禁用店铺失败: {e}")
        return False


if __name__ == '__main__':
    # 默认禁用 hedian.myshoplaza.com
    shop_domain = 'hedian.myshoplaza.com'
    
    # 如果提供了命令行参数，使用命令行参数
    if len(sys.argv) > 1:
        shop_domain = sys.argv[1]
    
    print(f"正在禁用店铺: {shop_domain}")
    success = disable_store(shop_domain)
    
    if success:
        print("\n✅ 操作完成！")
    else:
        print("\n❌ 操作失败！")
        sys.exit(1)




