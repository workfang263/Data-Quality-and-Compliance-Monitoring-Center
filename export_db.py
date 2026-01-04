"""
数据库导出脚本
自动导出数据库表结构（schema.sql）和生成模拟数据（seeds.sql）

使用方法：
    python export_db.py

输出文件：
    db/schema.sql - 数据库表结构（不含数据）
    db/seeds.sql - 模拟演示数据（脱敏后的虚假数据）
"""
import os
import sys
import subprocess
from datetime import datetime
from config import DB_CONFIG

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# 设置输出目录
DB_DIR = 'db'
SCHEMA_FILE = os.path.join(DB_DIR, 'schema.sql')
SEEDS_FILE = os.path.join(DB_DIR, 'seeds.sql')

def ensure_db_dir():
    """确保 db 目录存在"""
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        print(f"✅ 创建目录: {DB_DIR}")

def export_schema():
    """
    导出数据库表结构（不含数据）
    使用 mysqldump --no-data 选项
    """
    print("\n" + "="*60)
    print("步骤 1/2: 导出数据库表结构")
    print("="*60)
    
    try:
        # 构建 mysqldump 命令
        cmd = [
            'mysqldump',
            f"--host={DB_CONFIG['host']}",
            f"--port={DB_CONFIG['port']}",
            f"--user={DB_CONFIG['user']}",
            f"--password={DB_CONFIG['password']}",
            '--no-data',  # 只导出结构，不导出数据
            '--skip-add-drop-table',  # 不添加 DROP TABLE 语句（安全：不会删除表）
            '--skip-comments',  # 跳过注释
            '--skip-set-charset',  # 跳过字符集设置
            '--single-transaction',  # 保证数据一致性
            '--skip-triggers',  # 跳过触发器
            DB_CONFIG['database']
        ]
        
        print(f"正在导出表结构到: {SCHEMA_FILE}")
        
        # 执行命令并写入文件
        with open(SCHEMA_FILE, 'w', encoding='utf-8') as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True
            )
        
        if result.returncode != 0:
            print(f"❌ 导出失败: {result.stderr}")
            return False
        
        # 检查文件大小
        file_size = os.path.getsize(SCHEMA_FILE)
        print(f"✅ 导出成功: {SCHEMA_FILE} ({file_size:,} 字节)")
        
        return True
        
    except FileNotFoundError:
        print("❌ 错误: 未找到 mysqldump 命令")
        print("   请确保 MySQL 已安装并添加到 PATH")
        return False
    except Exception as e:
        print(f"❌ 导出失败: {e}")
        return False

def generate_seeds_header():
    """生成 seeds.sql 文件头部注释"""
    return f"""-- ============================================
-- 模拟演示数据（脱敏后的虚假数据）
-- ============================================
-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- 说明: 此文件包含用于演示的模拟数据，所有敏感信息已脱敏
-- ============================================

USE {DB_CONFIG['database']};

-- 清理现有演示数据（可选，首次导入时不需要）
-- TRUNCATE TABLE shoplazza_stores;
-- TRUNCATE TABLE shoplazza_overview_hourly;
-- TRUNCATE TABLE shoplazza_store_hourly;
-- TRUNCATE TABLE owner_daily_summary;
-- TRUNCATE TABLE store_owner_mapping;
-- TRUNCATE TABLE ad_account_owner_mapping;
-- TRUNCATE TABLE tt_ad_account_owner_mapping;
-- TRUNCATE TABLE sync_status;

"""

def generate_demo_stores():
    """
    生成虚构的店铺数据（不读取真实数据）
    生成 10 个虚构店铺：Store_Alpha, Store_Beta, ...
    """
    stores = []
    store_names = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 
                   'Zeta', 'Eta', 'Theta', 'Iota', 'Kappa']
    
    for i, name in enumerate(store_names, 1):
        # 生成虚构的 Token（40位随机字符串格式）
        fake_token = f"demo_token_{name.lower()}_{'x' * 30}"
        stores.append({
            'shop_domain': f'store_{name.lower()}.myshoplaza.com',
            'access_token': fake_token,
            'is_active': True
        })
    
    sql_lines = ["-- ==================== 虚构店铺数据 ====================\n"]
    sql_lines.append("INSERT INTO shoplazza_stores (shop_domain, access_token, is_active) VALUES\n")
    
    values = []
    for store in stores:
        values.append(f"    ('{store['shop_domain']}', '{store['access_token']}', {1 if store['is_active'] else 0})")
    
    sql_lines.append(",\n".join(values) + ";\n\n")
    
    return ''.join(sql_lines), stores

def generate_demo_mappings(stores):
    """
    生成虚构的映射数据
    """
    # 虚构的负责人名称
    owners = ['Owner_A', 'Owner_B', 'Owner_C', 'Manager_01', 'Manager_02']
    
    sql_lines = ["-- ==================== 虚构映射数据 ====================\n"]
    
    # 店铺映射
    sql_lines.append("-- 店铺 → 负责人映射\n")
    sql_lines.append("INSERT INTO store_owner_mapping (shop_domain, owner) VALUES\n")
    store_values = []
    for i, store in enumerate(stores):
        owner = owners[i % len(owners)]
        store_values.append(f"    ('{store['shop_domain']}', '{owner}')")
    sql_lines.append(",\n".join(store_values) + ";\n\n")
    
    # Facebook 广告账户映射（虚构）
    sql_lines.append("-- Facebook 广告账户 → 负责人映射\n")
    sql_lines.append("INSERT INTO ad_account_owner_mapping (ad_account_id, owner) VALUES\n")
    fb_values = []
    for i in range(5):
        ad_account_id = f"demo_fb_account_{i+1:03d}"
        owner = owners[i % len(owners)]
        fb_values.append(f"    ('{ad_account_id}', '{owner}')")
    sql_lines.append(",\n".join(fb_values) + ";\n\n")
    
    # TikTok 广告账户映射（虚构）
    sql_lines.append("-- TikTok 广告账户 → 负责人映射\n")
    sql_lines.append("INSERT INTO tt_ad_account_owner_mapping (ad_account_id, owner) VALUES\n")
    tt_values = []
    for i in range(5):
        ad_account_id = f"demo_tt_account_{i+1:03d}"
        owner = owners[i % len(owners)]
        tt_values.append(f"    ('{ad_account_id}', '{owner}')")
    sql_lines.append(",\n".join(tt_values) + ";\n\n")
    
    return ''.join(sql_lines)

def main():
    """主函数"""
    print("="*60)
    print("数据库导出脚本")
    print("="*60)
    print(f"数据库: {DB_CONFIG['database']}")
    print(f"输出目录: {DB_DIR}")
    print("="*60)
    
    # 确保目录存在
    ensure_db_dir()
    
    # 步骤1: 导出表结构
    if not export_schema():
        print("\n❌ 导出表结构失败，终止执行")
        sys.exit(1)
    
    # 步骤2: 生成模拟数据
    print("\n" + "="*60)
    print("步骤 2/2: 生成模拟数据")
    print("="*60)
    print("⚠️  注意: 模拟数据将由 generate_mock_data.py 生成")
    print("   此脚本仅生成基础配置数据（店铺、映射）")
    
    try:
        # 生成 seeds.sql 头部
        seeds_content = generate_seeds_header()
        
        # 生成虚构店铺数据
        stores_sql, stores = generate_demo_stores()
        seeds_content += stores_sql
        
        # 生成虚构映射数据
        mappings_sql = generate_demo_mappings(stores)
        seeds_content += mappings_sql
        
        # 写入文件
        with open(SEEDS_FILE, 'w', encoding='utf-8') as f:
            f.write(seeds_content)
        
        file_size = os.path.getsize(SEEDS_FILE)
        print(f"✅ 生成成功: {SEEDS_FILE} ({file_size:,} 字节)")
        print(f"   包含 {len(stores)} 个虚构店铺")
        print(f"   包含映射数据")
        
    except Exception as e:
        print(f"❌ 生成模拟数据失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "="*60)
    print("✅ 导出完成！")
    print("="*60)
    print(f"📄 表结构: {SCHEMA_FILE}")
    print(f"📄 基础数据: {SEEDS_FILE}")
    print("\n下一步: 运行 generate_mock_data.py 生成 90 天模拟数据")
    print("="*60)

if __name__ == '__main__':
    main()

