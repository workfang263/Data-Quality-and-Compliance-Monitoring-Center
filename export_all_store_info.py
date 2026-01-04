"""
导出所有店铺信息（包括URL和TOKEN）
"""
import sys
import os
# 设置Windows控制台UTF-8编码
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')

from database import Database
from config import LOG_CONFIG
from utils import setup_logging

setup_logging(LOG_CONFIG['log_file'], LOG_CONFIG['log_level'])


def export_all_stores():
    """导出所有店铺信息"""
    db = Database()
    
    try:
        # 获取所有店铺（包括禁用的）
        stores = db.get_all_stores()
        
        print("=" * 80)
        print("所有店铺信息（包括URL和TOKEN）")
        print("=" * 80)
        print()
        
        # 按启用状态分组
        active_stores = [s for s in stores if s['is_active']]
        inactive_stores = [s for s in stores if not s['is_active']]
        
        print(f"启用店铺数量：{len(active_stores)}")
        print(f"禁用店铺数量：{len(inactive_stores)}")
        print(f"总店铺数量：{len(stores)}")
        print()
        print("=" * 80)
        print("启用店铺列表")
        print("=" * 80)
        print(f"{'序号':<6}{'店铺域名':<40}{'状态':<8}{'创建时间':<20}")
        print("-" * 80)
        
        for idx, store in enumerate(active_stores, 1):
            created = store.get('created_at', '').strftime('%Y-%m-%d %H:%M:%S') if store.get('created_at') else 'N/A'
            print(f"{idx:<6}{store['shop_domain']:<40}{'启用':<8}{created:<20}")
        
        print()
        print("=" * 80)
        print("完整店铺信息（包含TOKEN）")
        print("=" * 80)
        print()
        
        # 生成CSV格式
        csv_lines = ["店铺域名,访问令牌(TOKEN),启用状态"]
        
        for store in stores:
            status = '启用' if store['is_active'] else '禁用'
            csv_lines.append(f"{store['shop_domain']},{store['access_token']},{status}")
        
        # 保存到文件
        output_file = "店铺完整信息_包含TOKEN.csv"
        with open(output_file, 'w', encoding='utf-8-sig') as f:
            f.write('\n'.join(csv_lines))
        
        print(f"[OK] 店铺信息已保存到: {output_file}")
        print()
        print("[WARNING] 注意：此文件包含敏感信息（TOKEN），请妥善保管！")
        print()
        
        # 同时生成Markdown格式（不包含TOKEN，用于文档）
        md_lines = [
            "# 店铺列表",
            "",
            f"**总店铺数量**：{len(stores)}",
            f"**启用店铺数量**：{len(active_stores)}",
            f"**禁用店铺数量**：{len(inactive_stores)}",
            "",
            "## 启用店铺列表",
            "",
            "| 序号 | 店铺域名 | 状态 | 创建时间 |",
            "|------|---------|------|----------|"
        ]
        
        for idx, store in enumerate(active_stores, 1):
            created = store.get('created_at', '').strftime('%Y-%m-%d') if store.get('created_at') else 'N/A'
            md_lines.append(f"| {idx} | {store['shop_domain']} | 启用 | {created} |")
        
        if inactive_stores:
            md_lines.extend([
                "",
                "## 禁用店铺列表",
                "",
                "| 序号 | 店铺域名 | 状态 |",
                "|------|---------|------|"
            ])
            
            for idx, store in enumerate(inactive_stores, 1):
                md_lines.append(f"| {idx} | {store['shop_domain']} | 禁用 |")
        
        md_output_file = "店铺列表_不含TOKEN.md"
        with open(md_output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))
        
        print(f"[OK] 店铺列表（不含TOKEN）已保存到: {md_output_file}")
        print()
        
        # 显示详细信息（包含TOKEN，但以安全方式显示）
        print("=" * 80)
        print("详细店铺信息（TOKEN仅显示前10个字符和后5个字符）")
        print("=" * 80)
        print()
        
        for idx, store in enumerate(stores, 1):
            token = store['access_token']
            if len(token) > 15:
                token_display = f"{token[:10]}...{token[-5:]}"
            else:
                token_display = "***"
            
            status = '[启用]' if store['is_active'] else '[禁用]'
            
            print(f"{idx}. {store['shop_domain']}")
            print(f"   状态: {status}")
            print(f"   TOKEN: {token_display}")
            print(f"   完整TOKEN: {token}")
            print()
        
    except Exception as e:
        print(f"[ERROR] 导出失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    export_all_stores()

