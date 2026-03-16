"""
修正店铺域名：将 ucky1028.myshoplaza.com 改为 lucky1028.myshoplaza.com，并重新启用该店铺。
在项目根目录执行：python fix_store_domain.py
"""
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from database import Database

OLD_DOMAIN = 'ucky1028.myshoplaza.com'
NEW_DOMAIN = 'lucky1028.myshoplaza.com'

def main():
    db = Database()
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                # 1. 修改 shoplazza_stores 的域名并重新启用
                cur.execute(
                    "UPDATE shoplazza_stores SET shop_domain = %s, is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE shop_domain = %s",
                    (NEW_DOMAIN, OLD_DOMAIN)
                )
                n1 = cur.rowcount
                if n1:
                    print(f"[OK] shoplazza_stores: 已将 {OLD_DOMAIN} 改为 {NEW_DOMAIN}，并已重新启用")
                else:
                    print(f"[提示] shoplazza_stores: 未找到 {OLD_DOMAIN}，可能已是正确域名或不存在")

                # 2. 修改 store_owner_mapping 的域名
                cur.execute(
                    "UPDATE store_owner_mapping SET shop_domain = %s, updated_at = NOW() WHERE shop_domain = %s",
                    (NEW_DOMAIN, OLD_DOMAIN)
                )
                n2 = cur.rowcount
                if n2:
                    print(f"[OK] store_owner_mapping: 已将 {OLD_DOMAIN} 改为 {NEW_DOMAIN}")
                else:
                    print(f"[提示] store_owner_mapping: 未找到 {OLD_DOMAIN}")

            conn.commit()
        if n1 or n2:
            print(f"\n完成。下次同步任务会使用 {NEW_DOMAIN} 拉取数据。")
        else:
            print("\n未做任何修改。若店铺之前被禁用，可手动在数据库中把该店铺 is_active 设为 1。")
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
