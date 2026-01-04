"""
更新店铺TOKEN
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database import Database

def update_store_token(shop_domain: str, access_token: str):
    """更新店铺TOKEN"""
    db = Database()
    
    # 清理域名格式
    shop_domain = shop_domain.replace('https://', '').replace('http://', '').rstrip('/')
    
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                # 检查店铺是否存在
                cursor.execute(
                    "SELECT id, shop_domain FROM shoplazza_stores WHERE shop_domain = %s",
                    (shop_domain,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # 更新现有店铺的token
                    cursor.execute(
                        "UPDATE shoplazza_stores SET access_token = %s, is_active = TRUE WHERE shop_domain = %s",
                        (access_token, shop_domain)
                    )
                    conn.commit()
                    print(f"✅ 成功更新店铺TOKEN: {shop_domain}")
                    return True
                else:
                    print(f"❌ 店铺不存在: {shop_domain}")
                    print("   如果需要添加新店铺，请使用 add_stores.py")
                    return False
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("使用方法：")
        print("  python update_store_token.py <shop_domain> <access_token>")
        print("\n示例：")
        print('  python update_store_token.py "yoki.myshoplaza.com" "P8aBJOiUAJSelb-rzZfG83YN8Oa0E_Wd_tpjjuAWSas"')
        sys.exit(1)
    
    shop_domain = sys.argv[1]
    access_token = sys.argv[2]
    
    print("=" * 60)
    print("更新店铺TOKEN")
    print("=" * 60)
    print(f"\n店铺域名: {shop_domain}")
    print(f"TOKEN: {access_token[:20]}...")
    print()
    
    update_store_token(shop_domain, access_token)




