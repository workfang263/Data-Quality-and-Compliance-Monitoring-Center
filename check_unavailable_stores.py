"""
检查所有店铺中「不可用」（Shoplazza 显示店铺暂时关闭）的店铺。

对每个店铺请求一次订单 API，若返回 404 则视为与后台「This store is currently unavailable」一致，
便于你在系统中禁用这些店铺。

使用方式：
  python check_unavailable_stores.py              # 只检查当前启用的店铺
  python check_unavailable_stores.py --all       # 检查所有店铺（含已禁用）
  python check_unavailable_stores.py --all -o list.txt   # 结果同时写入 list.txt
"""
import argparse
import sys
from datetime import datetime, timedelta

import pytz

from database import Database
from shoplazza_api import ShoplazzaAPI
from config import LOG_CONFIG
import logging

# 简单控制台日志
logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)


def get_check_time_range():
    """返回用于探测的起止时间戳（昨天 00:00 - 00:10 北京时间）。"""
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz)
    yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    start = yesterday
    end = yesterday.replace(minute=10)
    return int(start.timestamp()), int(end.timestamp())


def is_store_unavailable(shop_domain: str, access_token: str) -> bool:
    """
    请求该店铺的订单 API（不重试）。若返回 404 则视为不可用。
    """
    api = ShoplazzaAPI(shop_domain, access_token or '')
    # 用数据分析接口探测（订单接口同样会 404，用其中一个即可）
    begin_ts, end_ts = get_check_time_range()
    result = api.get_data_analysis(
        begin_ts, end_ts,
        dt_by='dt_by_hour',
        page=1,
        limit=1,
        max_retries=0,
    )
    if result is not None:
        return False
    failure = getattr(api, '_last_api_failure', None) or {}
    err = failure.get('error', '')
    return '404' in err


def main():
    parser = argparse.ArgumentParser(description='检查不可用（店铺关闭）的 Shoplazza 店铺')
    parser.add_argument('--all', action='store_true', help='检查所有店铺（默认只检查启用店铺）')
    parser.add_argument('-o', '--output', metavar='FILE', help='将不可用店铺列表写入文件')
    args = parser.parse_args()

    db = Database()
    stores = db.get_all_stores() if args.all else db.get_active_stores()
    if not stores:
        print('没有找到店铺。')
        return

    label = '所有' if args.all else '启用'
    print(f'共 {len(stores)} 个{label}店铺，开始逐店探测（仅请求一次，不重试）...\n')

    unavailable = []
    for i, s in enumerate(stores, 1):
        shop_domain = s.get('shop_domain', '')
        is_active = s.get('is_active', True)
        active_str = '启用' if is_active else '禁用'
        print(f'[{i}/{len(stores)}] {shop_domain} ({active_str}) ... ', end='', flush=True)
        try:
            if is_store_unavailable(shop_domain, s.get('access_token') or ''):
                print('不可用 (404)')
                unavailable.append(shop_domain)
            else:
                print('可用')
        except Exception as e:
            print(f'探测异常: {e}')
            # 异常时保守起见不加入不可用列表
            pass

    print()
    if not unavailable:
        print('未发现不可用店铺。')
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write('')
        return

    print(f'以下 {len(unavailable)} 个店铺为不可用（与 Shoplazza 后台「店铺暂时关闭」一致）：')
    for d in unavailable:
        print(f'  {d}')
    print('\n可在后台手动禁用上述店铺，或使用数据库/后台管理功能批量禁用。')

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write('\n'.join(unavailable))
        print(f'\n已写入: {args.output}')


if __name__ == '__main__':
    main()
