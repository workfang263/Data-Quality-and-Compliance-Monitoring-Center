"""
手动修复 sync_status 格式（从旧格式转换为新格式）

旧格式：整点时间（例如：17:10:00）
新格式：段的结束时间（例如：17:09:59.999999）
"""

import sys
from datetime import datetime, timedelta
from database import Database
from data_sync import beijing_time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fix_sync_status_format():
    """修复 sync_status 格式"""
    print("=" * 80)
    print("修复 sync_status 格式")
    print("=" * 80)
    
    db = Database()
    sync_status = db.get_sync_status('ten_minute_realtime')
    
    if not sync_status:
        print("\n⚠️  警告：sync_status不存在，无法修复")
        return False
    
    old_time = sync_status['last_sync_end_time']
    print(f"\n当前 sync_status：")
    print(f"   最后同步时间：{old_time}")
    print(f"   秒数：{old_time.second}")
    print(f"   微秒数：{old_time.microsecond}")
    
    # 检查是否是旧格式
    if old_time.second == 0 and old_time.microsecond == 0:
        print(f"\n✅ 检测到旧格式，开始转换...")
        
        # 转换为新格式：
        # 旧格式：17:10:00 代表下一个段的开始时间（即 17:00:00-17:09:59 这个段处理完后）
        # 新格式：17:09:59 代表 17:00:00-17:09:59 这个段的结束时间
        # 转换逻辑：17:10:00 - 1秒 = 17:09:59
        # 注意：数据库的 DATETIME 类型不支持微秒精度，所以使用 17:09:59 即可
        # 实际比较时用 >= 17:09:59 就能正确判断段的结束
        new_time = old_time - timedelta(seconds=1)
        # 确保微秒为0（因为数据库不支持微秒）
        new_time = new_time.replace(microsecond=0)
        
        print(f"   旧格式：{old_time}")
        print(f"   新格式（计算值）：{new_time}")
        print(f"   新格式（显示）：{new_time.strftime('%Y-%m-%d %H:%M:%S.%f')}")
        
        # 更新 sync_status
        success = db.update_sync_status(
            'ten_minute_realtime',
            new_time,
            sync_status['last_sync_date'],
            sync_status.get('last_visitor_cumulative', 0)
        )
        
        if success:
            print(f"\n✅ 格式转换成功！")
            
            # 验证
            verify_status = db.get_sync_status('ten_minute_realtime')
            if verify_status:
                verify_time = verify_status['last_sync_end_time']
                print(f"\n验证结果：")
                print(f"   最后同步时间：{verify_time}")
                print(f"   秒数：{verify_time.second}")
                print(f"   微秒数：{verify_time.microsecond}")
                
                # 验证：秒数应该是59（数据库不支持微秒，所以微秒数应该是0）
                if verify_time.second == 59 and verify_time.microsecond == 0:
                    print(f"\n✅ 格式验证通过！")
                    print(f"   数据库不支持微秒精度，但秒数59是正确的，可以正常工作")
                    return True
                elif verify_time.second == 59:
                    print(f"\n✅ 格式验证通过！（秒数59正确）")
                    print(f"   注意：微秒数为 {verify_time.microsecond}（数据库可能不支持微秒精度）")
                    return True
                else:
                    print(f"\n❌ 格式验证失败！秒数应该是59，实际是{verify_time.second}")
                    return False
            else:
                print(f"\n❌ 无法验证（sync_status不存在）")
                return False
        else:
            print(f"\n❌ 格式转换失败！")
            return False
    else:
        print(f"\n✅ 已经是新格式，无需转换")
        return True


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("sync_status 格式修复工具")
    print("=" * 80)
    
    success = fix_sync_status_format()
    
    if success:
        print("\n" + "=" * 80)
        print("修复完成")
        print("=" * 80)
        print("\n建议运行以下命令验证：")
        print("   python check_double_counting_risk.py")
    else:
        print("\n" + "=" * 80)
        print("修复失败")
        print("=" * 80)
        print("\n请检查错误信息并重试")

