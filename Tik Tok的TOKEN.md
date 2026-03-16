# TikTok 的 TOKEN 获取与报表调用实战（基于官方文档精读）
> 参考文档：  
> - 全站入口：[官方文档索引](https://business-api.tiktok.com/portal/docs?id=1709207091520514)  
> - OAuth 长期 Token 说明：[长效 Token](https://business-api.tiktok.com/portal/docs?id=1739965703387137)  
> - OAuth 授权流程/接口：[OAuth 流程与接口](https://business-api.tiktok.com/portal/docs?id=1740859280958466)  
> - 报表接口（Integrated Report）：[报表指标与参数](https://business-api.tiktok.com/portal/docs?id=1738373164380162)  

## 0. 你要的最终收获
- 拿到：`app_id`、`app_secret`、授权返回的 `access_token`（长效）、`refresh_token`（若返回）、`advertiser_ids`（授权覆盖的广告账户列表）。  
- 能做：调用报表接口按天/小时拉取 `spend`，并发遍历多个广告账户。  
- 适用场景：内部使用，不发布应用，但仍需 OAuth + redirect_uri。  

## 1. 名词和前置条件（为什么要广告账户）
- `Business Center`：业务资产管理主体，里边挂广告账户。  
- `advertiser_id`：广告账户 ID，报表/花费都是按它授权和查询。没有广告账户就查不到花费。  
- 授权主体：可对广告账户或 Business Center 授权，但最终返回的是你可访问的 `advertiser_ids` 列表。  
- 账号权限：授权人需对这些广告账户有足够权限（至少读报表）。  

## 2. 创建应用并配置（内部私有也要）
1) 登录 TikTok for Business → 开发者中心 → 创建 Marketing API 应用。  
2) 记下 `app_id`、`app_secret`。  
3) 配置 `redirect_uri`（HTTPS，和授权 URL 完全一致；本地可用 ngrok/Cloudflare Tunnel 暴露）。  
4) 勾选 scope：包含读广告/报表（控制台实际名称为准）。  

## 3. 准备回调地址（redirect_uri）
- 要求：HTTPS；必须与应用配置完全一致。  
- 本地示例（Flask）：  
```python
from flask import Flask, request
app = Flask(__name__)
@app.route("/callback")
def cb():
    return f"code={request.args.get('code')}, state={request.args.get('state')}"
app.run(host="0.0.0.0", port=8000)
```
  用 ngrok/Cloudflare Tunnel 把 `https://xxx.ngrok.io` 映射到本地 8000，`redirect_uri` 填 `https://xxx.ngrok.io/callback`。  

## 4. 生成授权 URL（老板/自己点一下）
```
https://ads.tiktok.com/marketing_api/auth
  ?app_id=你的APPID
  &state=xyz123
  &scope=ads.read,report.read
  &redirect_uri=https://你的回调域名/callback
  &response_type=code
```
- 打开后勾选要授权的广告账户（可多选），确认后跳回 `redirect_uri`，URL 带 `code`。  

## 5. 用 code 换长效 token
- 接口：`POST https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/`  
```json
{
  "app_id": "APPID",
  "secret": "APPSECRET",
  "auth_code": "回调里拿到的code"
}
```
- 返回重点：`access_token`（长效，不自动过期）、`refresh_token`（若下发则可刷新）、`advertiser_ids`。  

## 6. Token 有效期、刷新与撤销
- 长效 token：官方说明“不自动过期”，但可能被撤销或因安全/配置变更失效。  
- 撤销：`POST https://business-api.tiktok.com/open_api/v1.3/oauth2/revoke_token/`（带 app_id/app_secret/token）。  
- 刷新（若返回 refresh_token）：  
```json
POST https://business-api.tiktok.com/open_api/v1.3/oauth2/refresh_token/
{
  "app_id": "APPID",
  "secret": "APPSECRET",
  "refresh_token": "REFRESH_TOKEN"
}
```
- 实务策略：平时直接用 access_token；遇到 401/403 再刷新或重新授权；密钥泄露/权限变更需重授权。  

## 7. 拉广告花费（Integrated Report）
- 接口：`POST https://business-api.tiktok.com/open_api/v1.3/report/integrated/get/`  
- Header：`Authorization: Bearer <access_token>`，`Content-Type: application/json`  
- 按天示例：  
```json
{
  "advertiser_id": "<一个advertiser_id>",
  "service_type": "AUCTION",
  "report_type": "BASIC",
  "data_level": "AUCTION_ADVERTISER",
  "dimensions": ["stat_time_day"],
  "metrics": ["spend"],
  "start_date": "2025-12-01",
  "end_date": "2025-12-10",
  "page_size": 200
}
```
- 按小时：`dimensions` 换成 `["stat_time_hour"]`（需账户/地区支持小时维度）。  
- 常用参数提示：  
  - `service_type`: AUCTION（常见竞价）  
  - `report_type`: BASIC / REALTIME 等，按文档选择  
  - `data_level`: AUCTION_ADVERTISER / AUCTION_CAMPAIGN / ADGROUP / AD  
  - 分页：`page`、`page_size`（文档建议 ≤200）；或使用 `page_token` 视版本。  
  - 时间范围：部分场景限制单次跨度，建议按 30 天内分段。  

## 8. 多账号批量流程
1) 授权后保存 `advertiser_ids`。  
2) 遍历列表，逐个调用报表接口；可并发但注意限频。  
3) 数据入库前做去重、幂等（以 advertiser_id + 日期/小时为唯一键）。  

## 9. 常见报错与排查
- 405：用浏览器 GET 打 token 接口，需 POST。  
- 401/403：token 被撤销/权限不足/签名错误 → 重新授权或刷新。  
- 空 `advertiser_ids`：授权时未勾选账户，或账号权限不够 → 重新授权并勾选。  
- 小时维度无数据：账户/地区未开通小时粒度或该指标不支持小时 → 先用天粒度验证。  
- redirect_uri 不匹配：检查应用配置与授权 URL 完全一致（含 https、路径、尾斜杠）。  

## 10. 你需要准备/提供
- `app_id`、`app_secret`（勿外泄）。  
- `redirect_uri`（HTTPS，可用 ngrok 域名）。  
- 授权后返回的 `code`（或最终 token）。  
- 目标广告账户列表（如果想过滤）。  

## 11. 我可以帮你做的
- 写一键脚本：生成授权 URL、开启本地回调、自动抓 code、换 token、可选刷新；并带多账号拉花费示例（按天/小时）。  
- 对接你现有的数据库/前端：落表、聚合、幂等写入、覆盖模式、重试与限频策略。  

