"""
重新启用所有已禁用的 Shoplazza 店铺。

使用方式：
  python reenable_stores.py           # 执行更新，重新启用所有 is_active=0 的店铺
  python reenable_stores.py --list   # 仅列出将被启用的店铺，不执行更新（便于确认后再执行）
"""
import argparse
import sys

from database import Database


def main():
    parser = argparse.ArgumentParser(description='重新启用所有已禁用的店铺')
    parser.add_argument('--list', action='store_true', help='仅列出将被启用的店铺，不执行更新')
    args = parser.parse_args()

    db = Database()
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                if args.list:
                    cursor.execute(
                        'SELECT id, shop_domain, is_active FROM shoplazza_stores WHERE is_active = 0 ORDER BY id'
                    )
                    rows = cursor.fetchall()
                    if not rows:
                        print('当前没有已禁用的店铺。')
                        return
                    print(f'以下 {len(rows)} 个店铺将被重新启用：')
                    for r in rows:
                        print(f"  id={r['id']}  shop_domain={r['shop_domain']}")
                    print('\n执行 python reenable_stores.py 将实际更新。')
                    return

                cursor.execute('UPDATE shoplazza_stores SET is_active = 1 WHERE is_active = 0')
                n = cursor.rowcount
                conn.commit()
                print(f'已重新启用 {n} 个店铺。')
    except Exception as e:
        print(f'执行失败: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
