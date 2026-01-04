"""
导入 TikTok 广告账户 → 负责人映射数据
支持从 CSV 文件或直接传入数据导入

使用方式：
  # 从 CSV 文件导入
  python import_tt_owner_mappings.py --csv tt_mappings_template.csv
  
  # CSV 文件格式（表头）：
  # ad_account_id,owner,business_center
  # 7576614236823322642,负责人A,GARRY INTERNATIONAL TRADING CO.. LIMITED
  # 7550981544345845761,负责人B,AlylikeFs01

  # 或者直接在代码中配置数据（见 main 函数）
  python import_tt_owner_mappings.py
"""
import argparse
import csv
import pymysql
from typing import List, Dict

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


def import_from_csv(csv_file: str) -> List[Dict]:
    """从 CSV 文件读取映射数据"""
    mappings = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mappings.append({
                'ad_account_id': row['ad_account_id'].strip(),
                'owner': row['owner'].strip(),
                'business_center': row.get('business_center', '').strip() if 'business_center' in row else None
            })
    return mappings


def import_mappings(mappings: List[Dict], overwrite: bool = False):
    """
    导入映射数据到数据库
    
    Args:
        mappings: 映射数据列表，格式：[{'ad_account_id': '...', 'owner': '...', 'business_center': '...'}]
        overwrite: 如果已存在是否覆盖，False 则跳过
    """
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
                            print(f"[更新] {ad_account_id} -> {owner} ({business_center or 'N/A'})")
                        else:
                            # 跳过已存在的记录
                            skipped += 1
                            print(f"[跳过] {ad_account_id} 已存在，当前负责人: {existing['owner']}")
                    else:
                        # 插入新记录
                        cur.execute(
                            """INSERT INTO tt_ad_account_owner_mapping 
                               (ad_account_id, owner, business_center) 
                               VALUES (%s, %s, %s)""",
                            (ad_account_id, owner, business_center)
                        )
                        inserted += 1
                        print(f"[新增] {ad_account_id} -> {owner} ({business_center or 'N/A'})")
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                error_msg = f"处理 {ad_account_id} 失败: {e}"
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


def get_all_advertiser_ids() -> List[str]:
    """从 config.py 获取所有广告账户ID（用于验证）"""
    advertiser_ids = []
    business_centers = TT_CONFIG.get("business_centers", [])
    for bc in business_centers:
        advertiser_ids.extend(bc.get("advertiser_ids", []))
    return advertiser_ids


def validate_mappings(mappings: List[Dict]) -> tuple[List[Dict], List[str]]:
    """
    验证映射数据的有效性
    返回：(有效映射列表, 错误信息列表)
    """
    valid_mappings = []
    errors = []
    
    # 获取所有配置的广告账户ID
    config_ids = set(get_all_advertiser_ids())
    
    seen_ids = set()
    
    for i, mapping in enumerate(mappings, 1):
        ad_account_id = mapping.get('ad_account_id', '').strip()
        owner = mapping.get('owner', '').strip()
        
        # 验证必填字段
        if not ad_account_id:
            errors.append(f"第 {i} 行：ad_account_id 为空")
            continue
        if not owner:
            errors.append(f"第 {i} 行：owner 为空")
            continue
        
        # 检查重复
        if ad_account_id in seen_ids:
            errors.append(f"第 {i} 行：ad_account_id {ad_account_id} 重复")
            continue
        seen_ids.add(ad_account_id)
        
        # 检查是否在配置中存在（可选，给出警告）
        if ad_account_id not in config_ids:
            print(f"[警告] 第 {i} 行：ad_account_id {ad_account_id} 不在 config.py 的配置中")
        
        valid_mappings.append(mapping)
    
    return valid_mappings, errors


def main():
    parser = argparse.ArgumentParser(description="导入 TikTok 广告账户 → 负责人映射数据")
    parser.add_argument("--csv", help="CSV 文件路径（表头：ad_account_id,owner,business_center）")
    parser.add_argument("--overwrite", action="store_true", help="如果已存在则覆盖，否则跳过")
    args = parser.parse_args()
    
    if args.csv:
        # 从 CSV 文件导入
        print(f"从 CSV 文件导入：{args.csv}")
        mappings = import_from_csv(args.csv)
    else:
        # 直接配置数据（请在这里填入你的映射数据）
        print("从代码配置导入映射数据")
        mappings = [
            # TODO: 请在这里填入 TikTok 广告账户和负责人的对应关系
            # 格式：{'ad_account_id': '广告账户ID', 'owner': '负责人名称', 'business_center': 'Business Center名称（可选）'}
            # 示例：
            # {'ad_account_id': '7576614236823322642', 'owner': '负责人A', 'business_center': 'GARRY INTERNATIONAL TRADING CO.. LIMITED'},
            # {'ad_account_id': '7550981544345845761', 'owner': '负责人B', 'business_center': 'AlylikeFs01'},
        ]
        
        if not mappings:
            print("\n❌ 错误：请在代码中配置映射数据，或使用 --csv 参数从文件导入")
            print("\n参考格式：")
            print("mappings = [")
            print("    {'ad_account_id': '7576614236823322642', 'owner': '负责人A', 'business_center': 'GARRY INTERNATIONAL TRADING CO.. LIMITED'},")
            print("    {'ad_account_id': '7550981544345845761', 'owner': '负责人B', 'business_center': 'AlylikeFs01'},")
            print("]")
            return
    
    # 验证数据
    print(f"\n验证 {len(mappings)} 条映射数据...")
    valid_mappings, errors = validate_mappings(mappings)
    
    if errors:
        print("\n❌ 验证失败，发现以下错误：")
        for err in errors:
            print(f"  - {err}")
        return
    
    if not valid_mappings:
        print("\n❌ 没有有效的映射数据")
        return
    
    print(f"✅ 验证通过，共 {len(valid_mappings)} 条有效映射")
    
    # 确认导入
    print(f"\n准备导入 {len(valid_mappings)} 条映射数据...")
    confirm = input("确认导入？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消导入")
        return
    
    # 执行导入
    print("\n开始导入...")
    import_mappings(valid_mappings, overwrite=args.overwrite)


if __name__ == "__main__":
    main()




