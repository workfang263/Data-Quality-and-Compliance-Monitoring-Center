"""
检查 TikTok 相关数据库表是否存在
这个脚本用于验证项目所需的基础数据库表是否已经创建

为什么要检查：
1. 如果表不存在，后续的所有代码都会报错
2. 提前发现问题，避免在运行时才发现
3. 确认 create_tt_tables.sql 是否已经执行
"""
import pymysql
from config import DB_CONFIG

def check_table_exists(cursor, table_name):
    """检查表是否存在"""
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = %s
    """, (table_name,))
    result = cursor.fetchone()
    return result['count'] > 0

def check_column_exists(cursor, table_name, column_name):
    """检查表中的列是否存在"""
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = %s 
        AND column_name = %s
    """, (table_name, column_name))
    result = cursor.fetchone()
    return result['count'] > 0

def main():
    print("=" * 80)
    print("检查 TikTok 相关数据库表状态")
    print("=" * 80)
    print()
    
    try:
        conn = pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            charset=DB_CONFIG.get("charset", "utf8mb4"),
            cursorclass=pymysql.cursors.DictCursor,
        )
        
        cursor = conn.cursor()
        
        # 需要检查的表
        required_tables = {
            'tt_ad_account_spend_hourly': [
                'time_hour', 'ad_account_id', 'owner', 'spend', 'currency'
            ],
            'tt_ad_account_owner_mapping': [
                'ad_account_id', 'owner', 'business_center'
            ],
        }
        
        # 检查 owner_daily_summary 表是否有 TikTok 相关字段
        owner_daily_summary_columns = ['tt_total_spend', 'total_spend_all']
        
        all_ok = True
        
        print("1. 检查核心表是否存在：")
        print("-" * 80)
        for table_name, required_columns in required_tables.items():
            exists = check_table_exists(cursor, table_name)
            status = "✅ 存在" if exists else "❌ 不存在"
            print(f"   {table_name:<35} {status}")
            
            if not exists:
                all_ok = False
                print(f"      ⚠️  警告：此表不存在，需要执行 create_tt_tables.sql")
            else:
                # 检查必需的列
                print(f"      检查必需字段：")
                for col in required_columns:
                    col_exists = check_column_exists(cursor, table_name, col)
                    col_status = "✅" if col_exists else "❌"
                    print(f"         {col:<30} {col_status}")
                    if not col_exists:
                        all_ok = False
        
        print()
        print("2. 检查 owner_daily_summary 表的 TikTok 字段：")
        print("-" * 80)
        owner_table_exists = check_table_exists(cursor, 'owner_daily_summary')
        if owner_table_exists:
            for col in owner_daily_summary_columns:
                col_exists = check_column_exists(cursor, 'owner_daily_summary', col)
                col_status = "✅ 存在" if col_exists else "❌ 不存在"
                print(f"   {col:<35} {col_status}")
                if not col_exists:
                    all_ok = False
                    print(f"      ⚠️  警告：此字段不存在，需要执行 create_tt_tables.sql")
        else:
            print("   ⚠️  警告：owner_daily_summary 表不存在")
            all_ok = False
        
        print()
        print("=" * 80)
        if all_ok:
            print("✅ 所有表结构检查通过！可以继续下一步操作。")
        else:
            print("❌ 发现缺失的表或字段，请先执行 create_tt_tables.sql")
            print()
            print("执行方式：")
            print("  mysql -u用户名 -p数据库名 < create_tt_tables.sql")
            print("  或")
            print("  在 MySQL 客户端中执行：")
            print("    source create_tt_tables.sql")
        print("=" * 80)
        
        cursor.close()
        conn.close()
        
    except pymysql.Error as e:
        print(f"❌ 数据库连接错误：{e}")
        print("   请检查 config.py 中的数据库配置是否正确")
    except Exception as e:
        print(f"❌ 发生错误：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()




