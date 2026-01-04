"""
从 "Tik Tok账户和负责人对应关系.txt" 文件导入映射数据
解析制表符分隔的文本文件，自动识别 Business Center，导入到数据库

使用方式：
  python import_tt_mappings_from_txt.py
  
说明：
  - 负责人"无"表示账户暂时未分配，但会作为有效负责人名称导入（与Facebook逻辑一致）
  - 脚本会自动根据 config.py 识别账户属于哪个 BC
"""
import pymysql
import re
from typing import List, Dict, Optional

from config import DB_CONFIG, TT_CONFIG


def get_db_conn():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_bc_for_account(advertiser_id: str) -> Optional[str]:
    """根据广告账户ID查找对应的 Business Center 名称"""
    business_centers = TT_CONFIG.get("business_centers", [])
    for bc in business_centers:
        if advertiser_id in bc.get("advertiser_ids", []):
            return bc.get("name")
    return None


def parse_txt_file(file_path: str = "Tik Tok账户和负责人对应关系.txt") -> List[Dict]:
    """
    解析文本文件，返回映射数据列表
    格式：负责人\t广告账户ID\t账户名称
    """
    mappings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            # 跳过空行和表头行
            if not line or line.startswith('负责人'):
                continue
            
            # 解析制表符分隔的数据
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            
            owner = parts[0].strip()
            ad_account_id = parts[1].strip()
            account_name = parts[2].strip() if len(parts) > 2 else ''
            
            # 清理账户名称中的引号
            account_name = account_name.strip('"').strip("'")
            
            # 跳过负责人为空的账户（但保留"无"作为有效负责人名称）
            if not owner:
                print(f"[跳过] 第 {line_num} 行：账户 {ad_account_id} ({account_name}) 负责人为空，已跳过")
                continue
            
            # 查找所属的 Business Center
            bc_name = get_bc_for_account(ad_account_id)
            if not bc_name:
                print(f"[警告] 第 {line_num} 行：账户 {ad_account_id} 不在 config.py 的配置中，无法确定 BC")
                continue
            
            mappings.append({
                'ad_account_id': ad_account_id,
                'owner': owner,
                'business_center': bc_name,
                'account_name': account_name  # 保留账户名称用于显示
            })
    
    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {file_path}")
        return []
    except Exception as e:
        print(f"❌ 解析文件失败：{e}")
        import traceback
        traceback.print_exc()
        return []
    
    return mappings


def import_mappings(mappings: List[Dict], overwrite: bool = False):
    """
    导入映射数据到数据库
    """
    if not mappings:
        print("❌ 没有要导入的映射数据")
        return
    
    conn = get_db_conn()
    try:
        inserted = 0
        updated = 0
        skipped = 0
        errors = []
        
        for mapping in mappings:
            ad_account_id = mapping['ad_account_id']
            owner = mapping['owner']
            business_center = mapping.get('business_center')
            account_name = mapping.get('account_name', '')
            
            try:
                with conn.cursor() as cur:
                    # 检查是否已存在
                    cur.execute(
                        "SELECT id, owner, business_center FROM tt_ad_account_owner_mapping WHERE ad_account_id = %s",
                        (ad_account_id,)
                    )
                    existing = cur.fetchone()
                    
                    if existing:
                        if overwrite:
                            # 更新现有记录
                            cur.execute(
                                """UPDATE tt_ad_account_owner_mapping 
                                   SET owner = %s, business_center = %s, updated_at = CURRENT_TIMESTAMP
                                   WHERE ad_account_id = %s""",
                                (owner, business_center, ad_account_id)
                            )
                            updated += 1
                            print(f"[更新] {ad_account_id} ({account_name}) -> {owner} ({business_center})")
                        else:
                            # 跳过已存在的记录
                            skipped += 1
                            print(f"[跳过] {ad_account_id} ({account_name}) 已存在，当前负责人: {existing['owner']}")
                    else:
                        # 插入新记录
                        cur.execute(
                            """INSERT INTO tt_ad_account_owner_mapping 
                               (ad_account_id, owner, business_center) 
                               VALUES (%s, %s, %s)""",
                            (ad_account_id, owner, business_center)
                        )
                        inserted += 1
                        print(f"[新增] {ad_account_id} ({account_name}) -> {owner} ({business_center})")
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                error_msg = f"处理 {ad_account_id} ({account_name}) 失败: {e}"
                errors.append(error_msg)
                print(f"[错误] {error_msg}")
        
        print("\n" + "=" * 80)
        print(f"导入完成：新增 {inserted} 条，更新 {updated} 条，跳过 {skipped} 条")
        if errors:
            print(f"错误 {len(errors)} 条：")
            for err in errors:
                print(f"  - {err}")
        print("=" * 80)
        
    finally:
        conn.close()


def main():
    print("=" * 80)
    print("从文本文件导入 TikTok 广告账户映射数据")
    print("=" * 80)
    print()
    
    # 解析文件
    print("解析文件：Tik Tok账户和负责人对应关系.txt")
    mappings = parse_txt_file()
    
    if not mappings:
        print("❌ 没有找到有效的映射数据")
        return
    
    print(f"\n✅ 解析完成，找到 {len(mappings)} 条有效映射数据")
    
    # 显示将要导入的数据
    print("\n将要导入的数据预览：")
    print("-" * 80)
    for m in mappings[:10]:  # 只显示前10条
        print(f"  {m['ad_account_id']:<20} -> {m['owner']:<10} ({m['business_center']})")
    if len(mappings) > 10:
        print(f"  ... 还有 {len(mappings) - 10} 条")
    print("-" * 80)
    
    # 确认导入
    print(f"\n准备导入 {len(mappings)} 条映射数据...")
    confirm = input("确认导入？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消导入")
        return
    
    # 询问是否覆盖已存在的记录
    overwrite = input("如果记录已存在，是否覆盖？(y/n，默认n): ").strip().lower() == 'y'
    
    # 执行导入
    print("\n开始导入...")
    import_mappings(mappings, overwrite=overwrite)


if __name__ == "__main__":
    main()

