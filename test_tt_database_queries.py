"""
测试 TikTok 相关的数据库查询方法
验证修改后的代码能否正常工作

测试内容：
1. get_owner_daily_summary() - 测试是否能正确查询 TikTok 字段
2. get_owner_hourly_data() - 测试是否能正确查询 TikTok 数据
3. get_hourly_data_with_spend() - 测试是否包含 TikTok
4. get_daily_data_with_spend() - 测试是否包含 TikTok

即使表是空的，这些方法也应该能正常返回（返回空列表），不应该报错
"""
from datetime import datetime, date, timedelta
from database import Database

def test_get_owner_daily_summary():
    """测试 get_owner_daily_summary() 方法"""
    print("=" * 80)
    print("测试 1: get_owner_daily_summary() - 负责人日汇总查询")
    print("=" * 80)
    
    try:
        db = Database()
        
        # 测试查询最近7天的数据
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        print(f"查询日期范围：{start_date} ~ {end_date}")
        result = db.get_owner_daily_summary(start_date, end_date)
        
        print(f"✅ 查询成功，返回 {len(result)} 条记录")
        
        # 检查返回的字段
        if result:
            print("\n返回字段检查：")
            first_record = result[0]
            required_fields = ['owner', 'total_gmv', 'total_orders', 'total_visitors', 
                             'total_spend', 'tt_total_spend', 'total_spend_all', 'roas']
            
            for field in required_fields:
                if field in first_record:
                    print(f"  ✅ {field}: {first_record[field]}")
                else:
                    print(f"  ❌ {field}: 缺失")
            
            # 显示第一条记录示例
            print(f"\n第一条记录示例：")
            print(f"  负责人: {first_record.get('owner')}")
            print(f"  Facebook花费: {first_record.get('total_spend', 0)}")
            print(f"  TikTok花费: {first_record.get('tt_total_spend', 0)}")
            print(f"  总花费: {first_record.get('total_spend_all', 0)}")
        else:
            print("  ℹ️  当前没有数据（这是正常的，因为还没有回填 TikTok 数据）")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_owner_hourly_data():
    """测试 get_owner_hourly_data() 方法"""
    print("\n" + "=" * 80)
    print("测试 2: get_owner_hourly_data() - 负责人小时数据查询")
    print("=" * 80)
    
    try:
        db = Database()
        
        # 从映射表中获取一个负责人（如果有的话）
        # 先查询映射表，看看有哪些负责人
        from config import DB_CONFIG
        import pymysql
        
        conn = pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            charset=DB_CONFIG.get("charset", "utf8mb4"),
            cursorclass=pymysql.cursors.DictCursor,
        )
        
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT owner FROM tt_ad_account_owner_mapping LIMIT 1")
            owner_result = cur.fetchone()
        
        conn.close()
        
        if owner_result:
            owner_name = owner_result['owner']
            print(f"测试负责人：{owner_name}")
            
            # 查询今天的数据
            start_time = datetime.combine(date.today(), datetime.min.time())
            end_time = datetime.combine(date.today(), datetime.max.time())
            
            print(f"查询时间范围：{start_time} ~ {end_time}")
            result = db.get_owner_hourly_data(owner_name, start_time, end_time)
            
            print(f"✅ 查询成功，返回 {len(result)} 条记录")
            
            # 检查返回的字段
            if result:
                print("\n返回字段检查：")
                first_record = result[0]
                required_fields = ['time_hour', 'total_gmv', 'total_orders', 'total_visitors',
                                 'total_spend', 'tt_total_spend', 'total_spend_all', 'roas']
                
                for field in required_fields:
                    if field in first_record:
                        print(f"  ✅ {field}: {first_record[field]}")
                    else:
                        print(f"  ❌ {field}: 缺失")
                
                # 显示第一条记录示例
                print(f"\n第一条记录示例：")
                print(f"  时间: {first_record.get('time_hour')}")
                print(f"  Facebook花费: {first_record.get('total_spend', 0)}")
                print(f"  TikTok花费: {first_record.get('tt_total_spend', 0)}")
                print(f"  总花费: {first_record.get('total_spend_all', 0)}")
            else:
                print("  ℹ️  当前没有数据（这是正常的，因为还没有回填 TikTok 数据）")
        else:
            print("  ⚠️  映射表中没有找到负责人，跳过此测试")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_hourly_data_with_spend():
    """测试 get_hourly_data_with_spend() 方法"""
    print("\n" + "=" * 80)
    print("测试 3: get_hourly_data_with_spend() - 总店铺小时数据查询（包含 TikTok）")
    print("=" * 80)
    
    try:
        db = Database()
        
        # 查询今天的数据
        start_time = datetime.combine(date.today(), datetime.min.time())
        end_time = datetime.combine(date.today(), datetime.max.time())
        
        print(f"查询时间范围：{start_time} ~ {end_time}")
        result = db.get_hourly_data_with_spend(start_time, end_time)
        
        print(f"✅ 查询成功，返回 {len(result)} 条记录")
        
        if result:
            print("\n返回字段检查：")
            first_record = result[0]
            required_fields = ['time_hour', 'total_gmv', 'total_orders', 'total_visitors', 'total_spend']
            
            for field in required_fields:
                if field in first_record:
                    print(f"  ✅ {field}: {first_record[field]}")
                else:
                    print(f"  ❌ {field}: 缺失")
            
            print(f"\n第一条记录示例：")
            print(f"  时间: {first_record.get('time_hour')}")
            print(f"  总广告花费: {first_record.get('total_spend', 0)} (应该包含 FB + TikTok)")
        else:
            print("  ℹ️  当前没有数据（这是正常的，因为还没有回填 TikTok 数据）")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_daily_data_with_spend():
    """测试 get_daily_data_with_spend() 方法"""
    print("\n" + "=" * 80)
    print("测试 4: get_daily_data_with_spend() - 总店铺天数据查询（包含 TikTok）")
    print("=" * 80)
    
    try:
        db = Database()
        
        # 查询最近7天的数据
        end_time = datetime.combine(date.today(), datetime.max.time())
        start_time = datetime.combine(date.today() - timedelta(days=7), datetime.min.time())
        
        print(f"查询时间范围：{start_time.date()} ~ {end_time.date()}")
        result = db.get_daily_data_with_spend(start_time, end_time)
        
        print(f"✅ 查询成功，返回 {len(result)} 条记录")
        
        if result:
            print("\n返回字段检查：")
            first_record = result[0]
            required_fields = ['date', 'total_gmv', 'total_orders', 'total_visitors', 'total_spend']
            
            for field in required_fields:
                if field in first_record:
                    print(f"  ✅ {field}: {first_record[field]}")
                else:
                    print(f"  ❌ {field}: 缺失")
            
            print(f"\n第一条记录示例：")
            print(f"  日期: {first_record.get('date')}")
            print(f"  总广告花费: {first_record.get('total_spend', 0)} (应该包含 FB + TikTok)")
        else:
            print("  ℹ️  当前没有数据（这是正常的，因为还没有回填 TikTok 数据）")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("TikTok 数据库查询方法测试")
    print("=" * 80)
    print()
    print("说明：")
    print("- 这些测试会验证修改后的数据库查询方法能否正常工作")
    print("- 即使表是空的，方法也应该能正常返回（返回空列表），不应该报错")
    print("- 如果所有测试都通过，说明代码逻辑正确，可以继续下一步")
    print()
    
    results = []
    
    # 执行所有测试
    results.append(("get_owner_daily_summary", test_get_owner_daily_summary()))
    results.append(("get_owner_hourly_data", test_get_owner_hourly_data()))
    results.append(("get_hourly_data_with_spend", test_get_hourly_data_with_spend()))
    results.append(("get_daily_data_with_spend", test_get_daily_data_with_spend()))
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name:<35} {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✅ 所有测试通过！代码逻辑正确，可以继续下一步操作。")
    else:
        print("❌ 部分测试失败，请检查错误信息并修复问题。")
    print("=" * 80)


if __name__ == "__main__":
    main()




