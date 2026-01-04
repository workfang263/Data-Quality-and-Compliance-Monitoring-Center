"""
检查 shoplazza_store_hourly 表中 owner 字段为 NULL 的记录
"""
import pymysql
from datetime import datetime
from config_new import DB_CONFIG

def check_null_owners():
    """检查 owner 字段为 NULL 的记录"""
    try:
        # 连接数据库
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG['charset'],
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with conn.cursor() as cursor:
            print("=" * 60)
            print("检查 shoplazza_store_hourly 表中 owner 字段为 NULL 的记录")
            print("=" * 60)
            print()
            
            # 1. 统计总记录数
            cursor.execute("SELECT COUNT(*) as total FROM shoplazza_store_hourly")
            total_count = cursor.fetchone()['total']
            print(f"📊 总记录数: {total_count:,}")
            print()
            
            # 2. 统计 owner 为 NULL 的记录数
            cursor.execute("""
                SELECT COUNT(*) as null_count 
                FROM shoplazza_store_hourly 
                WHERE owner IS NULL OR owner = ''
            """)
            null_count = cursor.fetchone()['null_count']
            print(f"❌ owner 为 NULL 或空字符串的记录数: {null_count:,}")
            if total_count > 0:
                null_percentage = (null_count / total_count) * 100
                print(f"   占比: {null_percentage:.2f}%")
            print()
            
            # 3. 统计 owner 不为 NULL 的记录数
            cursor.execute("""
                SELECT COUNT(*) as not_null_count 
                FROM shoplazza_store_hourly 
                WHERE owner IS NOT NULL AND owner != ''
            """)
            not_null_count = cursor.fetchone()['not_null_count']
            print(f"✅ owner 不为 NULL 的记录数: {not_null_count:,}")
            if total_count > 0:
                not_null_percentage = (not_null_count / total_count) * 100
                print(f"   占比: {not_null_percentage:.2f}%")
            print()
            
            # 4. 如果有 NULL 记录，显示详细信息
            if null_count > 0:
                print("=" * 60)
                print("📋 owner 为 NULL 的记录详情（前20条）:")
                print("=" * 60)
                cursor.execute("""
                    SELECT 
                        shop_domain,
                        time_hour,
                        total_gmv,
                        total_orders,
                        total_visitors,
                        owner
                    FROM shoplazza_store_hourly 
                    WHERE owner IS NULL OR owner = ''
                    ORDER BY time_hour DESC
                    LIMIT 20
                """)
                null_records = cursor.fetchall()
                
                print(f"{'店铺域名':<30} {'时间':<20} {'销售额':<15} {'订单数':<10} {'访客数':<10} {'owner':<10}")
                print("-" * 100)
                for record in null_records:
                    shop_domain = record['shop_domain'][:28] if record['shop_domain'] else 'N/A'
                    time_hour = str(record['time_hour'])[:19] if record['time_hour'] else 'N/A'
                    gmv = f"{record['total_gmv']:.2f}" if record['total_gmv'] else '0.00'
                    orders = record['total_orders'] or 0
                    visitors = record['total_visitors'] or 0
                    owner = record['owner'] or 'NULL'
                    print(f"{shop_domain:<30} {time_hour:<20} {gmv:<15} {orders:<10} {visitors:<10} {owner:<10}")
                print()
                
                # 5. 统计哪些 shop_domain 有 NULL 记录
                print("=" * 60)
                print("📋 有 NULL owner 记录的店铺列表:")
                print("=" * 60)
                cursor.execute("""
                    SELECT 
                        shop_domain,
                        COUNT(*) as null_count,
                        MIN(time_hour) as earliest_time,
                        MAX(time_hour) as latest_time
                    FROM shoplazza_store_hourly 
                    WHERE owner IS NULL OR owner = ''
                    GROUP BY shop_domain
                    ORDER BY null_count DESC
                """)
                shop_null_records = cursor.fetchall()
                
                print(f"{'店铺域名':<40} {'NULL记录数':<15} {'最早时间':<20} {'最晚时间':<20}")
                print("-" * 100)
                for record in shop_null_records:
                    shop_domain = record['shop_domain'][:38] if record['shop_domain'] else 'N/A'
                    null_count = record['null_count']
                    earliest = str(record['earliest_time'])[:19] if record['earliest_time'] else 'N/A'
                    latest = str(record['latest_time'])[:19] if record['latest_time'] else 'N/A'
                    print(f"{shop_domain:<40} {null_count:<15} {earliest:<20} {latest:<20}")
                print()
                
                # 6. 检查这些店铺是否在映射表中
                print("=" * 60)
                print("🔍 检查这些店铺是否在 store_owner_mapping 表中:")
                print("=" * 60)
                if shop_null_records:
                    shop_domains = [r['shop_domain'] for r in shop_null_records]
                    placeholders = ','.join(['%s'] * len(shop_domains))
                    cursor.execute(f"""
                        SELECT 
                            shop_domain,
                            owner
                        FROM store_owner_mapping
                        WHERE shop_domain IN ({placeholders})
                    """, shop_domains)
                    mapped_shops = cursor.fetchall()
                    
                    print(f"{'店铺域名':<40} {'映射表中的owner':<20}")
                    print("-" * 65)
                    mapped_shop_domains = {r['shop_domain']: r['owner'] for r in mapped_shops}
                    for shop_domain in shop_domains:
                        owner = mapped_shop_domains.get(shop_domain, '❌ 不在映射表中')
                        shop_domain_short = shop_domain[:38] if shop_domain else 'N/A'
                        print(f"{shop_domain_short:<40} {owner:<20}")
                    print()
            
            # 7. 检查最近的数据（最近7天）
            print("=" * 60)
            print("📅 最近7天的数据统计:")
            print("=" * 60)
            cursor.execute("""
                SELECT 
                    DATE(time_hour) as date,
                    COUNT(*) as total_count,
                    SUM(CASE WHEN owner IS NULL OR owner = '' THEN 1 ELSE 0 END) as null_count,
                    SUM(CASE WHEN owner IS NOT NULL AND owner != '' THEN 1 ELSE 0 END) as not_null_count
                FROM shoplazza_store_hourly
                WHERE time_hour >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY DATE(time_hour)
                ORDER BY date DESC
            """)
            recent_stats = cursor.fetchall()
            
            print(f"{'日期':<15} {'总记录数':<15} {'NULL记录数':<15} {'非NULL记录数':<15} {'NULL占比':<15}")
            print("-" * 80)
            for stat in recent_stats:
                date_str = str(stat['date'])
                total = stat['total_count']
                null = stat['null_count']
                not_null = stat['not_null_count']
                null_pct = (null / total * 100) if total > 0 else 0
                print(f"{date_str:<15} {total:<15} {null:<15} {not_null:<15} {null_pct:.2f}%")
            print()
            
        conn.close()
        print("=" * 60)
        print("✅ 检查完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_null_owners()



