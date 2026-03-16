"""
添加新的 Shoplazza 店铺（交互式）

用法：在项目根目录执行
  python add_store.py

按提示依次输入：
  1. 店铺域名：例如 新店铺.myshoplaza.com（以 Shoplazza 后台为准）
  2. Access Token：你已有的读取 token
  3. 该店铺的负责人：你决定的负责人

也可命令行传参（可选）：
  python add_store.py "店铺.myshoplaza.com" "token" "负责人"
"""
import sys
import os

# Windows 控制台 UTF-8
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from database import Database


def add_store(shop_domain: str, access_token: str, owner: str) -> bool:
    """
    在 shoplazza_stores 和 store_owner_mapping 中添加新店铺。
    若店铺已存在则只更新 token 和映射。
    """
    shop_domain = (shop_domain or "").strip()
    if not shop_domain:
        print("错误：店铺域名不能为空")
        return False
    if not shop_domain.endswith(".myshoplaza.com") and ".myshoplaza.com" not in shop_domain:
        print("提示：常见格式为 xxx.myshoplaza.com，请确认域名正确。")

    access_token = (access_token or "").strip()
    if not access_token:
        print("错误：Access Token 不能为空")
        return False

    owner = (owner or "").strip()
    if not owner:
        print("错误：负责人不能为空")
        return False

    db = Database()

    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                # 1. 店铺表：存在则更新 token，不存在则插入
                cur.execute(
                    "SELECT id, access_token FROM shoplazza_stores WHERE shop_domain = %s",
                    (shop_domain,),
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        """
                        UPDATE shoplazza_stores
                        SET access_token = %s, is_active = 1, updated_at = CURRENT_TIMESTAMP
                        WHERE shop_domain = %s
                        """,
                        (access_token, shop_domain),
                    )
                    print(f"[OK] 店铺已存在，已更新 token: {shop_domain}")
                else:
                    cur.execute(
                        """
                        INSERT INTO shoplazza_stores (shop_domain, access_token, is_active)
                        VALUES (%s, %s, 1)
                        """,
                        (shop_domain, access_token),
                    )
                    print(f"[OK] 已添加店铺: {shop_domain}")

                # 2. 店铺-负责人映射：存在则更新负责人，不存在则插入
                cur.execute(
                    "SELECT 1 FROM store_owner_mapping WHERE shop_domain = %s",
                    (shop_domain,),
                )
                if cur.fetchone():
                    cur.execute(
                        """
                        UPDATE store_owner_mapping SET owner = %s, updated_at = NOW() WHERE shop_domain = %s
                        """,
                        (owner, shop_domain),
                    )
                    print(f"[OK] 已更新负责人映射: {shop_domain} -> {owner}")
                else:
                    cur.execute(
                        """
                        INSERT INTO store_owner_mapping (shop_domain, owner) VALUES (%s, %s)
                        """,
                        (shop_domain, owner),
                    )
                    print(f"[OK] 已添加负责人映射: {shop_domain} -> {owner}")

            conn.commit()
        return True
    except Exception as e:
        print(f"[ERROR] 添加失败: {e}")
        return False


def main():
    """交互式输入：店铺域名、Access Token、负责人"""
    if len(sys.argv) >= 4:
        shop_domain = sys.argv[1].strip()
        access_token = sys.argv[2].strip()
        owner = sys.argv[3].strip()
    else:
        print()
        print("==========  添加新 Shoplazza 店铺  ==========")
        print()
        shop_domain = input("店铺域名（例如 新店铺.myshoplaza.com，以 Shoplazza 后台为准）: ").strip()
        access_token = input("Access Token（你已有的读取 token）: ").strip()
        owner = input("该店铺的负责人（你决定的负责人）: ").strip()
        print()

    if not shop_domain or not access_token or not owner:
        print("店铺域名、Access Token 和负责人均不能为空。")
        sys.exit(1)

    ok = add_store(shop_domain, access_token, owner)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
