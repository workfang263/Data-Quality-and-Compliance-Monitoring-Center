---
name: 员工UTM子串匹配优化
overview: 仅优化店铺运营归因中「从 utm_source 识别员工」的规则：由「首段 `-` 前精确匹配」改为「整段小写串中子串匹配」，命中顺序严格按 `EMPLOYEE_SLUGS_ORDERED`；`resolve_attribution` 末次链、utm_decision、public_pool 分支全部保留不变。
todos:
  - id: impl-match-slug
    content: 改写 match_employee_slug：子串 + EMPLOYEE_SLUGS_ORDERED；更新 docstring/模块说明
    status: completed
  - id: tests-attribution
    content: 新增 pytest：子串、多命中顺序、空/无命中、resolve_attribution 可选集成
    status: completed
  - id: verify-lint
    content: 清理未使用导入；本地跑 pytest 相关文件
    status: completed
isProject: false
---

# 员工 UTM 匹配容错 — 执行方案

## 背景与目标

- **现状**：[`match_employee_slug`](backend/app/services/store_ops_attribution.py) 只取 `utm_source` **第一个 `-` 之前**的一段，且须**整段等于**白名单 slug。运营若漏写 `-`，整段无法等值匹配，易进公共池。
- **目标**：对 **完整 `utm_raw`（已 unquote 的 utm_source 值）** 做 **不区分大小写** 的 **子串包含** 判断：只要字符串里出现某位员工的**全拼 slug**，即归为该员工。
- **多人同时命中**：按 [`EMPLOYEE_SLUGS_ORDERED`](backend/app/services/store_ops_constants.py) **从左到右**（`xiaoyang` → `kiki` → … → `wanqiu`）**第一个在串中出现的 slug** 作为归属（名单优先级，**不是**按字符串从左到右第一个出现的位置）。
- **范围**：**只改** `match_employee_slug`（及文件头/函数 docstring）；**不修改** `extract_utm`、`landing_has_utm_source_param`、`resolve_attribution` 及 [`store_ops_sync.py`](backend/app/services/store_ops_sync.py)。

## 依据（代码位置）

当前匹配逻辑（将被替换行为，结构保留函数名）：

```37:49:backend/app/services/store_ops_attribution.py
def match_employee_slug(utm_raw: Optional[str]) -> Optional[str]:
    """
    utm_source 第一个 '-' 之前的段，转小写后与白名单匹配。
    未命中返回 None。
    """
    if not utm_raw:
        return None
    seg = utm_raw.split("-")[0].strip().lower()
    ...
```

白名单顺序源（**唯一顺序源**）：

```14:22:backend/app/services/store_ops_constants.py
EMPLOYEE_SLUGS_ORDERED: List[str] = [
    "xiaoyang",
    "kiki",
    "jieni",
    "amao",
    "jimi",
    "xiaozhang",
    "wanqiu",
]
```

## 实现要点

1. **导入**：在 [`store_ops_attribution.py`](backend/app/services/store_ops_attribution.py) 中由 `EMPLOYEE_SLUG_SET` 改为（或补充）使用 **`EMPLOYEE_SLUGS_ORDERED`** 做遍历；若 `EMPLOYEE_SLUG_SET` 仅被本函数使用，可删除未使用导入（以 linter 为准）。
2. **算法**：

   - `utm_raw` 为空 / 仅空白 → `None`。
   - `haystack = utm_raw.strip().lower()`。
   - `for slug in EMPLOYEE_SLUGS_ORDERED: if slug in haystack: return slug`。
   - 无命中 → `None`。

3. **语义说明**：Python 子串 `in` 对 ASCII 全拼足够；与现有「全小写 slug」一致。
4. **风险说明**（文档或注释一行即可）：短 slug（如 `kiki`）可能在无关英文词中偶然出现，属业务可接受误差；若未来需收紧，可再加「边界符」策略（本轮不做）。

## 行为示例（验收用）

| utm_source 内容（示意） | 结果 |

|-------------------------|------|

| `jieni-promo` | `jieni`（与旧行为一致，子串命中） |

| `promo_jieni_nocode` | `jieni`（无 `-` 仍可命中） |

| 同时含 `kiki` 与 `jieni`（任意顺序写在串里） | `kiki`（因名单顺序在 `jieni` 前） |

| 无任一则 `None`，后续仍走 `public_pool` |

## 测试

- 仓库内**尚无** `store_ops_attribution` 单测；建议新增 **`backend/tests/test_store_ops_attribution.py`**（或项目既有 pytest 路径），覆盖：
  - 无 `-` 含全拼；
  - 多 slug 时按 `EMPLOYEE_SLUGS_ORDERED` 取第一个在串中存在的（构造 `haystack` 同时包含后项与前项，验证前项胜出）；
  - 空串 / 无命中 → `None`；
  - 大小写混合 `JieNi` → 仍命中 `jieni`。
- **回归**：对 [`resolve_attribution`](backend/app/services/store_ops_attribution.py) 做 1～2 条集成级用例（固定 `source`/`last_landing_url`，断言 `utm_decision` 不变、仅员工 slug 变化），可选。

## 部署与数据

- **无需** DB 迁移。
- **历史订单**：已写入 [`store_ops_order_attributions`](db/schema.sql) 的数据不会自动重算；若需按新规则刷新，需另行安排 **重新跑 store_ops 同步**（覆盖日期范围），不在本最小改动内强制。

## 任务清单