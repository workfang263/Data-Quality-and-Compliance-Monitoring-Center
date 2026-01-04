"""
同步昨天的 Facebook 广告花费数据（最终数据）
用于在第二天凌晨执行，确保获取前一天最终确定的数据

使用方式：
  python sync_yesterday_fb_spend.py
"""
import subprocess
import sys
from datetime import date, timedelta

def main():
    # 计算昨天的日期
    yesterday = date.today() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    
    print("=" * 80)
    print(f"同步昨天的 Facebook 广告花费数据（最终数据）")
    print(f"日期：{date_str}")
    print("=" * 80)
    print()
    
    # 调用同步脚本，使用覆盖模式（不使用incremental，确保完全覆盖）
    cmd = [
        sys.executable,
        "fb_spend_sync.py",
        "--date", date_str
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print()
        print("=" * 80)
        print(f"✅ 昨天（{date_str}）的 Facebook 广告花费数据同步完成")
        print("=" * 80)
        return 0
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 80)
        print(f"❌ 同步失败，退出码：{e.returncode}")
        print("=" * 80)
        return e.returncode

if __name__ == "__main__":
    sys.exit(main())




