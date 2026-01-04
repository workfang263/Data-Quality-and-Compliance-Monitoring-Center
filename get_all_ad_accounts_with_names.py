"""
批量获取所有Facebook广告账户的详细信息（包括名称）
用于匹配到店铺域名
"""
import json
import requests
import sys
from typing import List, Dict

# ==================== 配置 ====================
# 你的长期访问令牌
ACCESS_TOKEN = "YOUR_LONG_LIVED_TOKEN"  # ⚠️ 替换为你的长期token

# System User ID
SYSTEM_USER_ID = "122102744337087687"

# API版本
API_VERSION = "v24.0"

# ==================== 函数 ====================

def get_all_ad_accounts(access_token: str, system_user_id: str) -> List[Dict]:
    """
    获取所有广告账户（自动处理分页）
    
    Returns:
        所有广告账户列表
    """
    all_accounts = []
    url = f"https://graph.facebook.com/{API_VERSION}/{system_user_id}/adaccounts"
    params = {
        "fields": "id,account_id,name,currency,account_status,timezone_name",
        "access_token": access_token,
        "limit": 200
    }
    
    try:
        while True:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "data" in data:
                accounts = data["data"]
                all_accounts.extend(accounts)
                print(f"✅ 已获取 {len(accounts)} 个账户，累计 {len(all_accounts)} 个")
                
                # 检查是否有下一页
                if "paging" in data and "next" in data["paging"]:
                    # 使用next URL继续获取
                    url = data["paging"]["next"]
                    params = {}  # next URL已经包含所有参数
                else:
                    break
            else:
                print(f"❌ 返回数据格式异常: {data}")
                break
                
    except requests.exceptions.RequestException as e:
        print(f"❌ API请求失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   错误详情: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"   响应内容: {e.response.text}")
    
    return all_accounts

def match_accounts_to_stores(accounts: List[Dict], stores_file: str = "店铺列表_待填写广告账户ID.csv"):
    """
    尝试根据账户名称匹配到店铺域名
    
    Args:
        accounts: 广告账户列表
        stores_file: 店铺列表CSV文件路径
    
    Returns:
        匹配结果字典 {店铺域名: [账户ID列表]}
    """
    # 读取店铺列表
    try:
        with open(stores_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        store_domains = [line.strip().split(',')[0] for line in lines[1:] if line.strip()]  # 跳过表头
    except Exception as e:
        print(f"⚠️  读取店铺列表失败: {e}")
        return {}
    
    # 提取店铺名称（域名前缀部分）
    store_names = {}
    for domain in store_domains:
        if domain and domain != "店铺域名":
            # 提取域名前缀，例如：jaymiart.myshoplaza.com -> jaymiart
            store_name = domain.split('.')[0].lower()
            store_names[store_name] = domain
    
    # 匹配账户到店铺
    matches = {domain: [] for domain in store_domains if domain and domain != "店铺域名"}
    unmatched_accounts = []
    
    for account in accounts:
        account_id = account.get("id", "")
        account_name = account.get("name", "").lower()
        
        matched = False
        
        # 方法1：账户名称包含店铺名称
        for store_name, domain in store_names.items():
            if store_name in account_name or account_name in store_name:
                matches[domain].append(account_id)
                print(f"✅ 匹配: {account_name} -> {domain}")
                matched = True
                break
        
        # 方法2：账户名称完全匹配店铺名称
        if not matched:
            for store_name, domain in store_names.items():
                if account_name == store_name:
                    matches[domain].append(account_id)
                    print(f"✅ 完全匹配: {account_name} -> {domain}")
                    matched = True
                    break
        
        if not matched:
            unmatched_accounts.append({
                "account_id": account_id,
                "account_name": account.get("name", "未命名"),
                "currency": account.get("currency", "未知")
            })
    
    return matches, unmatched_accounts

def main():
    """主函数"""
    if ACCESS_TOKEN == "YOUR_LONG_LIVED_TOKEN":
        print("❌ 请先在脚本中设置你的长期访问令牌（ACCESS_TOKEN）")
        sys.exit(1)
    
    print("🔍 正在获取所有广告账户的详细信息...")
    print("=" * 60)
    
    # 获取所有账户
    accounts = get_all_ad_accounts(ACCESS_TOKEN, SYSTEM_USER_ID)
    
    if not accounts:
        print("\n❌ 未能获取到广告账户")
        sys.exit(1)
    
    print(f"\n✅ 总共获取到 {len(accounts)} 个广告账户\n")
    print("=" * 60)
    
    # 保存完整账户列表
    output_file = "facebook_所有广告账户_完整信息.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=2, ensure_ascii=False)
    print(f"✅ 完整账户信息已保存到: {output_file}")
    
    # 保存CSV格式（方便查看）
    csv_file = "facebook_所有广告账户_完整信息.csv"
    with open(csv_file, 'w', encoding='utf-8-sig') as f:
        f.write("账户ID,账户名称,币种,状态,时区\n")
        for account in accounts:
            account_id = account.get("id", "")
            name = account.get("name", "未命名").replace(",", "，")
            currency = account.get("currency", "未知")
            status = account.get("account_status", {}).get("name", "未知")
            timezone = account.get("timezone_name", "未知")
            f.write(f"{account_id},{name},{currency},{status},{timezone}\n")
    print(f"✅ CSV格式已保存到: {csv_file}")
    
    # 尝试自动匹配
    print("\n" + "=" * 60)
    print("🔍 正在尝试自动匹配账户到店铺...")
    print("=" * 60)
    
    try:
        matches, unmatched = match_accounts_to_stores(accounts)
    except Exception as e:
        print(f"⚠️  自动匹配失败: {e}")
        matches = {}
        unmatched = []
    
    # 生成匹配结果
    result_file = "账户匹配结果.csv"
    with open(result_file, 'w', encoding='utf-8-sig') as f:
        f.write("店铺域名,广告账户ID列表,账户数量\n")
        for domain, account_ids in matches.items():
            if account_ids:
                f.write(f"{domain},{';'.join(account_ids)},{len(account_ids)}\n")
            else:
                f.write(f"{domain},,0\n")
    print(f"✅ 匹配结果已保存到: {result_file}")
    
    # 显示未匹配的账户
    if unmatched:
        print(f"\n⚠️  有 {len(unmatched)} 个账户无法自动匹配:")
        for acc in unmatched:
            print(f"   - {acc['account_name']} ({acc['account_id']})")
        
        unmatched_file = "未匹配的账户.csv"
        with open(unmatched_file, 'w', encoding='utf-8-sig') as f:
            f.write("账户ID,账户名称,币种\n")
            for acc in unmatched:
                f.write(f"{acc['account_id']},{acc['account_name']},{acc['currency']}\n")
        print(f"✅ 未匹配账户已保存到: {unmatched_file}")
    
    print("\n" + "=" * 60)
    print("\n📝 下一步操作：")
    print("   1. 打开 facebook_所有广告账户_完整信息.csv，查看所有账户的名称")
    print("   2. 打开 账户匹配结果.csv，查看自动匹配的结果")
    print("   3. 手动检查并修正匹配结果（根据账户名称和店铺域名的对应关系）")
    print("   4. 对于未匹配的账户，根据账户名称手动判断对应哪个店铺")
    print("   5. 最终更新 店铺列表_待填写广告账户ID.csv 文件")

if __name__ == "__main__":
    main()

