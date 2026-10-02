[English](EVALUATION.md) · [中文](EVALUATION.zh.md)

# 求值规则，authz/2.0

bundle 是什么意思：消费者（官方 SDK、进程内假 provider、任何语言写的组件）怎样把一份 bundle、一个已验签的 token 和一条资源的事实变成决策。本文是规范。每条规则有编号（E1–E12），`vectors/decision/` 的决策向量和 `vectors/tools/` 的参考代码都引用它。成员自己的决策（Check、Explain、`/api/me/access`）遵守同样的规则。

## 输入

| 输入 | 内容 |
|---|---|
| bundle | `schemas/bundle.schema.json` 的 JSON |
| claims | 来自已验签的 access token：`sub`、`iat`、`roles[]`、`dept_path`、`tenant_id`，可选 `act`、`ceil[]`、`dg` |
| now | 消费者的时钟，unix 秒 |
| 键 `K` | 路由的权限键 |
| 资源类型 `T` | 来自属主的 `resources` 声明（`schemas/catalog.schema.json` 的 `resource_type`）：`type`、`view_key`、`dimensions`、`relations`、`fields`、`derivation` |
| 行 `r`（仅单条） | `id`、`owner`、`dept_path`、`values{维度: 值}` |
| ACL 行（仅单条） | 这条记录在投影表 `besdk_authz_acl` 里的行：`rtype`、`rid`、`relation`、`subject`、`expires_at` |
| graph ids | `ListObjects` 返回的 id，仅 graph 类型 |

**排序。** 本文产生的每个数组都去重，并按字节序升序排列。档位顺序 `own < dept < subtree < all`；`none` 表示没有档位。

## E1 接受 bundle

- 只有 `contract` 匹配 `^authz/2\.(0|[1-9][0-9]*)$` 时才接受。否则拒绝：记 ERROR，不使用；在收到合法 bundle 之前，受保护路由一直答 `503` / `AUTHZ_NOT_READY`。被拒的 bundle 永不替换已接受的那份。
- 不认识的字段和能力名一律忽略。

## E2 token 检查

按顺序，第一个失败的决定结果：

1. **stale**：`stale_since[sub]` 存在且 `iat < stale_since[sub] − 5` → `TOKEN_STALE`。
2. **已撤销的授予**：`dg` 非空且是 `revoked_grants` 的键 → `TOKEN_STALE`。
3. **代理 token**：带 `act`、非空 `ceil` 或非空 `dg` 的 token 是代理 token，需要能力 `delegation`，否则 `UNSUPPORTED_DELEGATION`。
4. **act 链**：依次看 `act`、`act.act`……：kind `agent` 需要 `agents`；kind `user`（扮演）需要 `impersonation`；kind `svc` 不再需要别的；其它 kind → `UNSUPPORTED_DELEGATION`。

通过的 token 为 `OK`。

## E3 有效期

- 有效期是 unix 秒的 `[from_ts, until)`，缺的一端不设限。
- **有效角色** `R` = token 里 `grants[role]` 有效期包含 `now` 的角色（没有 grants 条目的角色视为有效）。有效期外的角色什么都不贡献：没有键、档位、取值，也没有主体。
- `on_behalf` 委托只在有效期内算数。
- ACL 行在 `expires_at` 为空或晚于 `now` 时算数（RFC 3339，不含端点）。

## E4 天花板

- 天花板是 `ceil[]` 指名的 profile；不认识的码是空 profile（`keys: []`、`max_level: own`、`relations: []`）。
- 每个天花板都在 `keys` 或 `fields` 里列了 `k` 时，天花板**允许**键 `k`。没有天花板时，所有键都允许。
- 天花板不允许的键在任何意义上都不存在：没有规则分支、没有 ACL 分支、没有图分支。
- 档位封顶到各天花板 `max_level` 的最低值（E6）；关系与每个天花板的 `relations` 取交集（E8）。

## E5 键

- `K` 的**持有角色** = 满足 `K ∈ roles[r]` 的有效角色 `r`。
- **`K` 的委托** `D_K` = 能力 `delegation` 为真时，bundle `delegations` 里 `mode = on_behalf`、`to = sub`、`K ∈ keys` 且在有效期内的条目；否则为空。
- `has(K)` = （持有角色非空或 `D_K` 非空）且天花板允许 `K`。

## E6 档位与身份部分

- 角色给 `K` 的档位：`grants[r].levels[K]`，没有就 `grants[r].default_level`，再没有就 `own`。
- `level(K)` = 持有角色中最高的档位，再按天花板封顶；没有持有角色或天花板不允许 `K` 时为 `none`。委托不给档位。
- **部门。** `dept_path` 匹配 `^/([^/]+/)*$` 才有效。空串或格式不对表示*没有部门*（R60）；`/` 是根，也是唯一表示整棵树的路径。
- **前缀编码。** 部门前缀 = 路径里的 `\`、`%`、`_` 各在前面加一个 `\`，再接 `%`（带反斜杠转义的 SQL `LIKE` 模式）。
- `K` 的 **org 取值** = 持有角色 `grants[r].values.org` 的并集。有天花板时，封顶低于 `subtree` 就丢掉路径，低于 `all` 就丢掉 `*`。
- 参数（名字同 foundations 20 的规范谓词）：

| 参数 | 值 |
|---|---|
| `s_all` | `level(K) ≠ none` 且（`level(K) = all` 或 `*` ∈ org 取值） |
| `s_owners` | `level(K) ≠ none` 时有 `sub`；另加每个 `D_K` 条目的 `from`（天花板允许 `K` 时） |
| `s_dept_exact` | `level(K) = dept` 且部门有效时为该部门 |
| `s_dept_prefix` | `level(K) = subtree` 且部门有效时为 prefix(部门)；另加每个有效且 `≠ *` 的 org 取值 `v` 的 prefix(v) |

- 委托人只贡献自己的 `sub`：他的角色和部门不在 bundle 里，永不合并。

## E7 资源维度

- 对 `T` 中 `owner`、`org` 以外的每个维度 `d`：`K` 的取值 = 持有角色 `grants[r].values[d]` 的并集（天花板不允许 `K` 时为空）。
- `s_dims[d] = {all: "*" ∈ 取值, ids: 取值 − {*}}`。没有取值就什么都匹配不到。`*` 只能显式授予。
- 委托不给维度取值。

## E8 主体集合与关系

- `S(K)` = `user:<sub>`；每个有效角色的 `role:<r>`；部门有效时，`dept:<部门>`，以及 `/`、部门的每个祖先和部门自身的 `dept_tree:<p>`；每个 `D_K` 条目的 `user:<from>`。没有部门就没有 `dept`、`dept_tree` 主体。
- 一个关系的 `grants` 含 `K`，或它 `includes` 的关系（可传递）的 grants 含 `K`，这个关系就**给出** `K`。
- `s_relations` = `T` 中给出 `K` 且对应能力为真（`owned_by: component` 看 `relation_sync`，其余看 `sharing`）的关系，再与每个天花板的 `relations` 取交集；天花板不允许 `K` 时为空。
- `s_acl` = `s_relations` 非空。`s_subjects` = `S(K)`。

## E9 图分支与降级

- 只针对 `derivation: graph`。有能力 `graph` 时：`s_graph_ids` = `ListObjects` 返回的 id（天花板允许 `K` 时）。没有时：`s_graph_ids` 为空，`degraded` 列出 `graph`（响应头 `X-Authz-Degraded: graph`）。
- 其它类型：`s_graph_ids` 为空，不降级。

## E10 单条记录的决策

- 下面任一分支成立，`vis(k, r)` 为真：
  - **规则**：`has(k)`，且身份部分成立，且每个资源维度成立。身份部分成立的条件：`T` 既不声明 `owner` 也不声明 `org`；或 `s_all`；或（声明了 `owner` 且 `r.owner ∈ s_owners`）；或（声明了 `org` 且 `r.dept_path` 等于某个 `s_dept_exact` 项或匹配某个 `s_dept_prefix` 模式）。维度 `d` 成立：`s_dims[d].all` 或 `r.values[d] ∈ s_dims[d].ids`。
  - **ACL**：`s_acl`，且有一条 `rtype = T.type`、`rid = r.id`、关系在 `s_relations`、主体在 `s_subjects`、在 `now` 仍算数（E3）的 ACL 行。
  - **图**：`r.id ∈ s_graph_ids`。
- `visible = vis(T.view_key, r)`；`allowed = visible 且 vis(K, r)`。
- `reason`：看不见时为 `NOT_FOUND`（读和命令都答 `404`）；允许时为空；否则 `has(K)` 时为 `OUT_OF_SCOPE`，不然为 `MISSING_PERMISSION`（都答 `403`）。
- **List/Can 一致。** 一行出现在 `K` 的列表里，当且仅当 `vis(K, r)`；列表的 SQL 谓词（用 E6–E9 的参数）与上面的单条规则是同一个函数。

## E11 字段

- 对 `T` 的每个字段集：`has(read)` 为假时，它的列被**掩码**（响应里为 `null`，列入 `_masked`）；持有 `read` 但没有 `edit` 或不持有 `edit` 时，它们**只读**。字段键和所有键一样遵守 E4、E5。

## E12 Explain 的事实

对一条记录上键 `K` 的事实，每条 `{kind, source, detail}`，按 (kind, source, detail) 排序：

- **`vis(K, r)` 为真时**（`reasons`）：规则分支成立的话，每个持有角色一条 `role_key`（角色，`K`）；`T` 声明了 `owner` 或 `org` 时一条 `level`（未封顶档位最高者中字典序最小的角色，封顶后的档位）；每个资源维度一条 `dimension`（d，`r.values[d]`）；每个 `from` 等于 `r.owner` 的 `D_K` 条目一条 `delegation`（id，from）；每个天花板一条 `ceiling`（码，`K`）。每条命中的 ACL 行：关系是 `owned_by: component` 时为 `relation`（关系，主体），否则为 `share`。图分支一条 `relation`（`graph`，`r.id`）。
- **否则**（`missing`）：每个不允许 `K` 的天花板一条 `ceiling`（码，`K`）；没有就看：既无持有角色也无委托时一条 `role_key`（空，`K`）；再不然，身份部分不成立时一条 `level`（空，`level(K)`），每个不成立的维度一条 `dimension`（d，值）。然后，`T` 中会给出 `K` 但对应能力为假的每个关系一条 `capability`（能力名，空），没有 `graph` 的图类型一条 `capability`（`graph`，空）。
- **R62。** 记录看不见时，`dimension` 事实的 detail 为空：解释永不透露调用方看不见的记录的任何属性。

## 向量文件格式

`vectors/decision/` 里一条向量一个 JSON 文件，按 `schemas/vector.schema.json` 校验：

| 字段 | 内容 |
|---|---|
| `id`、`title`、`tags` | 稳定 ID（永不复用）、一句话、覆盖的规则组 |
| `contract` | 算出它的规则所属的契约版本 |
| `input` | `bundle`、`claims`、`now`、`key`、`resource_type`，单条记录另有 `row`、`acl`、`graph_ids` |
| `expected` | `bundle`（`accepted` / `refused`）；`token`；`has_key`；`level`；`scope_params`；`degraded`；`fields`（有字段集的类型）；`decision` 和 `explain`（单条记录） |

消费者精确算出 `expected` 的每个字段，就算通过这条向量。bundle 被拒（`bundle: refused`）或 token 失败之后的字段不出现。向量只增：新规则或措辞更正只加向量；改了期望就是契约变更。
