# FastAPI 后端（新系统）

与根目录旧脚本分离；**店铺运营 / 员工归因**（`/api/store-ops/*`、`/api/internal/store-ops/sync`）已挂在本进程，**不需要再开一个服务**。

## 启动

1. 安装依赖（建议在项目根目录）：

   ```bash
   pip install -r backend/requirements.txt
   ```

2. 配置 **项目根目录** `.env`（数据库、`SHOPLAZZA_ACCESS_TOKEN_*`、可选 `STORE_OPS_HTTPS_VERIFY` 等）。`config_new.py` 会**自动加载上一级目录的 `.env`**。

3. 在 **`backend` 目录**下启动：

   ```bash
   cd backend
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

4. 浏览器打开 API 文档：`http://127.0.0.1:8000/docs`

## 重启（改代码或改 `.env` 后）

1. 在运行 uvicorn 的终端里按 **`Ctrl + C`** 停掉进程。  
2. 再执行同上一条 `uvicorn app.main:app --reload ...` 命令。

`--reload` 会在你**改 Python 代码**时自动重载；**改 `.env` 必须手动重启**一次，环境变量才会重新读入。

## 与前端一起用（只开两个窗口）

| 窗口 | 目录 | 命令 |
|------|------|------|
| 后端 | `backend` | `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` |
| 前端 | `frontend` | `npm run dev`（默认 `http://localhost:5173`，已代理 `/api` 到 8000） |

登录后菜单里的 **「店铺运营」** 与看板、权限同一套后端，**无需额外端口或进程**。

## 店铺运营相关环境变量（根目录 `.env`）

| 变量 | 说明 |
|------|------|
| `SHOPLAZZA_ACCESS_TOKEN_SHUTIAOES` / `SHOPLAZZA_ACCESS_TOKEN_NEWGGES` | 两店专用 token（与 `shoplazza_stores` 旧 token 无关） |
| `STORE_OPS_HTTPS_VERIFY` | 默认视为开启证书校验；本地走 SOCKS 若 SSL 报错可设为 `false`；**生产建议 `true` 或不写** |
| `STORE_OPS_SYNC_SECRET` | 可选；供 cron 调 `POST /api/internal/store-ops/sync` 时 header `X-Internal-Key` 校验 |

## 店铺运营：同步结果可查询

1. **数据库**：执行迁移 `db/migrations/20260403_store_ops_sync_runs.sql`（表 `store_ops_sync_runs`）。未执行时同步仍可进行，但**无法落库/查询**批次结果。

2. **接口**（需登录且 `can_view_store_ops`，或内部密钥仅对 POST sync）：
   - `GET /api/store-ops/sync-run/{sync_run_id}` — 单次批次明细（`errors` 全量错误文案、`per_shop` 按店错误）。
   - `GET /api/store-ops/sync-runs?limit=20` — 最近若干次摘要。

3. **状态说明**：`running` → 进行中；`success` 无错误；`partial` 有错误但任务跑完；`failed` 为未捕获异常（见 `exception_message`）。

4. **前端**：店铺运营页**不展示**批次列表（避免定时同步产生大量记录）；排障请直接查表或调上述 GET。
