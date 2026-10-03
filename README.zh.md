[English](README.md) · [中文](README.zh.md)

# contract-infra-authz

authz 槽位的族契约，版本 **authz/2.0**：每个授权成员必须实现的东西，以及 SDK、IAM 成员、前端生成器、一致性测试套件要消费的东西。这里只有契约：没有成员代码，也没有逻辑。

## 这是什么

- **provider 契约** `infra.authz.v2`：gRPC 服务 `AuthzProvider`；provider 面 REST（bundle、变更流、快照、目录、explain）；本人与管理 REST；事件；能力枚举；错误 reason；NDJSON 导出格式；以及 bundle 的含义（[EVALUATION.zh.md](EVALUATION.zh.md)），由决策向量锁定。
- **不在这里**：每个组件挂出的资源契约（`POST {prefix}/_authz/check`、`GET {prefix}/_authz/explain`、`GET|POST|DELETE {prefix}/_shares/{type}/{id}`）、投影表 `besdk_authz_acl` / `besdk_authz_cursor`、运行时怎么轮询、缓存和应答。这些属于组件一侧，归组件协议（`brickKit/be-protocol` 的 P6 章、`openapi/resource-authz.yaml`、`ddl/07-authz-projection.sql`）。P6 引用本仓库来说明数据的含义。
- **消费者**：官方 SDK（bundle、变更流、`WriteTuples`、`Check`、按 E1–E12 求值）；IAM 成员（登录和刷新时调 `ResolveClaims`，token exchange 时调 `CreateDelegation`）；前端生成器（本人与管理 REST）；`tools/be-acceptance/conformance/authz/`（provider 黑盒与端到端）；be-ops（能力名、目录格式）。

## 成员

| 成员 | 状态 | 声明（`provides_capabilities`） | 适合 |
|---|---|---|---|
| `infra/authz`（原生，默认） | 3.0.0：core、admin_write；之后在 phase 06 内 | sharing、relation_sync、check、explain_paths（随 06c）；delegation、access_review、impersonation（06c 之后）；`list_objects` 只到一跳 | 几乎所有 ERP / CRM 部署，一个 PostgreSQL |
| `infra/authz-static` | phase 06 | 只有 core；策略文件在 `AUTHZ_POLICY_PATH` | 演示、十人左右、边缘站点、测试夹具 |
| `infra/authz-openfga` | phase 06 | core、sharing、relation_sync、check、graph、list_objects、explain_paths、access_review | 协作重的部署、多跳关系 |
| Cedar / OPA | 不建 | core、conditions（只用于动作） | 有真实 ABAC 动作规则的客户 |

契约从 2.0 起就是完整的；成员逐步打开能力，这里不用改。

`agents` 只占位（A4）：没有成员声明它，`act.kind = agent` 一律拒收，profile 与天花板的形状定死，目录里可选的 `delegable` 字段只有形状。

## 目录结构

| 路径 | 内容 |
|---|---|
| `proto/infra/authz/v2/provider.proto` | gRPC 服务 `AuthzProvider` 及其消息 |
| `openapi/authz.openapi.yaml` | provider 面、本人与管理 REST（OpenAPI 3.1） |
| `schemas/bundle.schema.json` | bundle v2 |
| `schemas/changefeed.schema.json` | 变更流分页、元组快照分页、元组、poke |
| `schemas/catalog.schema.json` | 目录（键、维度、资源类型），以及 `RESOURCE_CATALOG` 的形状 |
| `schemas/export-record.schema.json` | NDJSON 导出 `authz-export/1` 的一行 |
| `schemas/vector.schema.json` | 一条决策向量 |
| `capabilities.yaml` | 能力枚举：core 与可选、成员必须做什么、缺了怎么降级 |
| `errors.yaml` | 族的错误 reason，domain 是 `infra/authz` |
| `events/authz.events.json` | 发布的事件、入站的关系同步、poke |
| `EVALUATION.md` | 规则 E1–E12：bundle、token 和一条记录怎样得出决策 |
| `vectors/decision/`、`vectors/SHA256SUMS` | 决策向量 |
| `vectors/tools/` | 用例定义、参考求值器（Python）、独立交叉验证（Go） |
| `examples/` | 一份完整 bundle、一份导出文件 |
| `gen/go/infra/authz/v2/` | 生成的 Go 包 `authzv2`（已提交，`make gen`） |
| `fs.go`、`go.mod` | Go 模块 `github.com/brickKit/contract-infra-authz/v2`，嵌入上面这些文件 |

## 寻址与两个面

- 每个消费者都经两个共享键找到已安装的成员，它们在 `config/vars.yaml` 里各写一次，写成指向该成员的 brickKit `$endpoint:` 引用：`AUTHZ_URL: $endpoint:infra/authz`（REST 基地址）和 `AUTHZ_GRPC_URL: $endpoint:infra/authz:grpc`（gRPC 地址；拨号目标是去掉 `http://` 的值），be-protocol P2.10。换成员只改这两行，别的都不动；值跟着版本、外壳和本机运行走。任何组件、任何 IAM 成员都不声明对 authz 成员的依赖：被依赖的成员无法替换（0104、0107）。
- **provider 面**（系统流量，永不经边缘）：`AUTHZ_URL` 下的 `GET /authz/v2/bundle`、`/authz/v2/changes`、`/authz/v2/tuples`、`/authz/v2/catalog`、`POST /authz/v2/explain`，以及 `AUTHZ_GRPC_URL` 上的 gRPC 服务 `AuthzProvider`。成员把 gRPC 额外端口命名为 `grpc` 并写 `protocol: grpc`（be-protocol P7.14），端口号随它定：没有任何东西从 HTTP 端口推算它。调用方带 `be-caller`。
- **成员的清单**：和任何组件一样（be-protocol P20，“`component.yaml` 里声明什么”），另外 `events.publishes` 是 `events/authz.events.json` 里 `events` 的每个主题，`events.subscribes` 是 `consumes` 和 `inbound_events` 里的主题（P12.16；`signals` 里标了 `x-signal: true` 的 poke 不列）。
- **边缘**：`/api/me/*`（任何已登录用户）和 `/api/admin/*`（键 `infra.authz.admin`）。成员把它们写进 `edge_routes`，`/authz/v2/*` 永不写进去，它的 operation 标 `x-be-internal: true`（be-protocol P3.16）；其余每个 operation 都声明 `x-be-permission`。

## 能力

- **core** 不可选：claims、键、档位、维度取值、字段键、stale、revision、目录同步、`/api/me/access`、基础 explain、限时授予、管理读、导出。
- **可选**：`admin_write`、`sharing`、`relation_sync`、`check`、`graph`、`list_objects`（对象 `{max_results}`）、`delegation`、`agents`（占位）、`impersonation`、`access_review`、`explain_paths`、`conditions`（占位，只用于动作）。
- **协商发生两次。** 组装期：成员的 `assembly.yaml` 写 `provides_capabilities`，组件的写 `requires_capabilities`，后者不是前者子集时门禁 `authz-capability-scan` 失败。运行期：bundle 的 `capabilities` 说明正在运行的成员提供什么，每个消费者按它降级。
- **缺失是显式的、可测的**：未声明能力的操作答 `501` / `UNIMPLEMENTED`，reason `CAPABILITY_UNAVAILABLE`（domain `be`），`metadata.capability` 写能力名；每种缺失下 SDK 和前端的行为写在 `capabilities.yaml`（`absent.backend`、`absent.frontend`）。
- 名字只增。消费者忽略不认识的名字。

## provider 面的接口

| 用途 | REST | gRPC | 能力 |
|---|---|---|---|
| 登录 / 刷新时的 claims | — | `ResolveClaims` | core |
| bundle | `GET /authz/v2/bundle`（ETag） | `GetBundle` | core |
| 目录 | `GET /authz/v2/catalog` | `GetCatalog` | core |
| 按码读角色 | `GET /api/admin/roles…` | `BatchGetRoles`（≤ 500） | core |
| 变更流 / 快照 | `GET /authz/v2/changes`、`/authz/v2/tuples` | `ReadChanges`、`ReadTuples` | sharing 或 relation_sync |
| 写共享 | —（属主的 `_shares` 走 gRPC） | `WriteTuples`（幂等键） | sharing |
| 远程判定 | — | `Check`、`BatchCheck`（≤ 500） | check |
| 图列表 | — | `ListObjects`（有上限） | graph、list_objects |
| explain | `POST /authz/v2/explain`、`GET /api/admin/users/{sub}/access` | `Explain` | core（+ explain_paths） |
| 委托 | `/api/me/delegations`、`/api/admin/delegations`、`/api/admin/profiles` | `CreateDelegation`、`RevokeDelegation`、`BatchGetDelegations` | delegation |
| 共享评审 | `/api/me/shares`、`/api/admin/shares` | — | sharing |
| 访问评审 | `GET /api/admin/access-review` | — | access_review |
| 导出 / 导入 | `GET /api/admin/export`、`POST /api/admin/import` | — | core / admin_write |

- **revision** 是成员单调递增的 int64，以十进制字符串传输。每次写入都返回它。变更流对一组类型无空洞，`watermark` 是头部；成员无法完整服务的 `after` 答 `410` / `CHANGES_EXPIRED`，消费者用快照重建。
- **元组有两个来源。** 共享归 authz：只有类型的 `owner_component`（按 `be-caller` 核对）在自己做完资格检查后经 `WriteTuples` 写入。组件主责的关系以 `infra.authz.relation.sync.v1` 进来（入站，整组替换，version 必须更新，`ce-source` 必须是属主）；管理员不能改它们。
- **事件**（`events/authz.events.json`）：`infra.authz.tuple.changed.v1`、`.scope_grant.changed.v1`、`.delegation.changed.v1`、`.role.changed.v1`、`.user_role.changed.v1`，都带 actor 及其 act 链；poke `infra.authz.changed.v1` 走 core NATS。每个成员发同样的主题；消费者永不按 `ce-source` 过滤。
- **消费的事件**（`events/authz.events.json` 的 `consumes`；core，每个成员都要）：来自身份族（contract-infra-iam `iam/1`）。`infra.iam.user.disabled.v1` 把 `stale_since[sub]` 设为事件的 `ce-time`，于是已签出的 access token 立刻答 `401 TOKEN_STALE`，身份成员也不再签新的；`infra.iam.user.deleted.v1` 设 `stale_since[sub]`，并删掉该 sub 的全部授予（角色、键、部门、subject 为 `user:<sub>` 的元组），发出 `user_role.changed.v1` 和 `tuple.changed.v1`；带 `bootstrap_admin: true` 的 `infra.iam.user.created.v1` 或 `.updated.v1` 把系统角色 `superuser` 授予该 sub，幂等。重新启用的用户（`updated.v1`，`status: active`）保留它原有的授予。成员和任何组件一样经 durable 消费这些事件（be-protocol P12），按聚合游标去重。

## 目录同步

- 成员启动时从三个配置键建目录：`PERMISSION_CATALOG`（`registry/permissions.tsv`）、`DATA_SCOPE_CATALOG`（`registry/data-scopes.tsv`）、`RESOURCE_CATALOG`（be-ops 从每个组件的 `resources` 段生成的 JSON 文件，形状见 `schemas/catalog.schema.json` 的 `resource_types`）。
- 每次同步后，系统角色 `superuser` 持有全部未退役的键；默认没有人持有 `superuser`。第一位管理员不在这里配置：身份成员在这个人第一次登录时，把共享键 `BOOTSTRAP_ADMIN_LOGIN`（IdP 登录名或邮箱）绑定到一个平台 `sub`，并在用户事件里写明（`bootstrap_admin: true`）；权限成员收到这条事件时授予 `superuser`（*消费的事件*）。`sub` 没法事先配置：第一次登录之前它并不存在（be-protocol P2.11）。
- `catalog_digest`（bundle 里）= `sha256:` + 目录（`GetCatalog` 返回的形状，数组已排序）的 RFC 8785 规范 JSON 的十六进制 SHA-256。门禁或测试拿它和 be-ops 生成物的摘要比较。
- 每个成员还接受 `IAM_URL`、`IAM_ISSUER`、`TENANT_ID`（像任何组件一样校验管理与本人请求的 token；JWKS 在 `{IAM_URL}/.well-known/jwks.json`）。成员自己的键（static 成员的 `AUTHZ_POLICY_PATH`）由成员自己定；其中的密钥一律是文件，`mount: file`，名字是 `…_FILE`（be-protocol P2.12）。

## 在成员之间搬授权数据

格式 `authz-export/1`（`schemas/export-record.schema.json`、`examples/export.example.ndjson`）：UTF-8 NDJSON，一行 `header`，然后按 `role`、`user_role`、`user_dept`、`profile`、`delegation`、`tuple`、`relation_group` 的顺序分组的记录，每组按自然键排序，最后一行 `footer`，带每种记录的条数和记录行的 SHA-256。同一状态导出两次，只有 `exported_at` 不同。

- **导出**（`GET /api/admin/export[?kinds=…]`，core）在成员停写时进行（管理界面只读，或导出后停掉成员）。`kinds=` 是唯一能留下某类记录不搬的办法，header 写明文件里有哪些类。
- **导入**（`POST /api/admin/import[?dry_run=true]`，admin_write）要么全成、要么全不成：成员装不下的记录（没有 `sharing` 的成员遇到 `tuple`、不认识的键或类）连同行号和原因一起报告，一行都不写（`400` / `IMPORT_REJECTED`）。同一文件导入两次，结果相同。
- **跨切换的 revision。** 导入方的第一个 revision 大于 header 的 `revision`，对小于 header revision 的 `after` 一律答 `410`。投影正好停在导出点的组件接着拉；其余的用快照重建。组件什么都不用改。
- **static 成员。** 导入 `infra/authz-static` 写的是它的策略文件而不是数据库；它装得下的是按 `role,user_role,user_dept` 过滤的导出。
- **步骤**：停管理写入 → 导出 → `brickkit add` 新成员、`brickkit remove` 旧成员 → 把 `config/vars.yaml` 里的 `AUTHZ_URL` 和 `AUTHZ_GRPC_URL` 指向新成员（`$endpoint:<新成员 ID>`，两行）→ `make gates`（`authz-capability-scan`）→ `dry_run` 导入 → 导入 → 跑一致性测试 → 上线。
- `relation_group` 记录保留 version，之后 version 更旧的同步仍会被丢弃；属主的 outbox 和流里也还留着这些同步，可以重放。

## 版本

- bundle 的 `contract` 是 `authz/2.<minor>`；Go 模块和仓库 tag 是 `v2.<minor>.<patch>`（只打带 `v` 的 tag：这不是 brickKit 组件）。
- **minor** 只增：可选字段、能力、rpc、端点、事件主题、导出记录类、错误 reason、新规则的向量。不改任何含义；minor 永远不会让一个符合的成员变得不符合，所以每个新能力都是可选的。
- **patch**：措辞、示例、给已有规则补向量。
- **major**（`authz/3`）是新的 proto 包 `infra.authz.v3`、新的模块路径 `/v3`、新的路径 `/authz/v3/*`，两个大版本都装着时新旧并存。
- 门禁：对上一个 tag 跑 `buf breaking`（FILE）（`make breaking BASE=v2.0.0`）；能力名、错误 reason、向量 ID 只增。
- 成员、SDK、套件各钉一个精确 tag。be-protocol 正文只引用大版本（"`contract: authz/2.x`"）。

## 生成代码

**决定**：Go 代码在这里生成、由本模块发布；其余语言从钉死的 tag 私下生成。

| 语言 | 内容 | 位置 |
|---|---|---|
| Go | `protoc-gen-go` + `protoc-gen-go-grpc` 的产物，与改 proto 的那个 tag 一起提交（`make gen`） | `github.com/brickKit/contract-infra-authz/v2/gen/go/infra/authz/v2`（包 `authzv2`）；契约文件经模块根的 `authzcontract.FS` |
| Python、TypeScript | 2.0 不出包；SDK 从钉死的 tag 拷 `proto/` 和 `schemas/`（`make sync-contracts`，按 tag 的文件核对），生成到私有模块（`besdk._contracts`、`@brickkit/be-sdk-ts/_contracts`） | be-sdk-python、be-sdk-ts 内部 |
| 前端 | 生成器从钉死的 tag 读 `openapi/authz.openapi.yaml` | 前端仓库 |

理由：

- **0101 增加第三类。** 此前只有 `be-sdk-*` 和某个组件自己的 `gen/<domain>/<name>` 包能跨组件边界。族契约不属于任何成员（iam 契约曾放在 Casdoor 成员仓库里，一有第二个成员就不成立），没有逻辑、没有组件语义，每个进程恰好一份：它满足 0101 的 revisit 条件，因此 0101 增补"族契约包"为第三类。
- **Go 里每个进程只能有一份生成包。** protobuf 运行时按全名注册每个消息；同一个二进制里有两份 `infra.authz.v2.*`（SDK 的客户端和 authz 成员的服务端，都编进 `be/go-infra`）会在启动时冲突。这正是已有的易错点"拷贝的生成代码在调用方与被调方同处一个外壳时会 panic"。只有发布唯一一份包才能避免。
- **Python 和 TypeScript 今天各只有一个消费者**（它们的 SDK），私有副本不会在同一进程里遇到第二份；组件从不直接 import 契约，都经 SDK。出现非 Go 成员或这两门语言里的第二个消费者时，本仓库加 `python/`、`ts/` 包，按 git tag 安装（同今天 be-sdk-ts 的装法），SDK 在同一个版本里改用它们。
- 这与 be-protocol 对它自己向量的规则一致：从 tag 拷契约文件是拷数据，不是拷代码。

## 证明符合

1. 在成员的 `assembly.yaml` 里声明 `provides_capabilities`（名字取自 `capabilities.yaml`），bundle 里宣告同一组。
2. 对运行中的成员跑 `tools/be-acceptance/conformance/authz/`（套件自己签 token，并灌一份夹具目录）：
   - **core** 必须通过；
   - 每个声明了的可选能力必须通过它那一组；
   - 每个没声明的必须答 `501` / `CAPABILITY_UNAVAILABLE` 并带能力名，在 bundle 里为 `false` 或缺省；
   - 导出后导入另一个成员，决策相同；
   - **端到端**：一个用真 SDK 构建的夹具组件跑在该成员上；随机授权、共享、委托和到期；List/Can 一致、带 revision 共享后立刻可见、撤销和到期后不可见、字段掩码。
3. 套件把能力矩阵（成员 × 能力 × 通过 / 降级正确 / 失败）写进该成员版本的测试记录；`make gates` 检查记录存在。
4. 每门官方 SDK 和组件测试用的进程内假 provider 都要通过 `vectors/decision/` 的全部向量，夹具才不会与成员漂移。

## 决策向量

- `vectors/decision/` 里 62 条向量，一条一个文件，ID 稳定、永不复用；格式见 [EVALUATION.zh.md](EVALUATION.zh.md#向量文件格式)。标签：`bundle`、`token`、`key`、`level`、`r60`、`window`、`values`、`sharing`、`relation_sync`、`delegation`、`ceiling`、`agents`、`impersonation`、`fields`、`graph`、`explain`、`r62`、`degrade`。
- **怎么产生**：`vectors/tools/cases.py` 写出每条的输入和手写的意图；`generate.py` 用 `reference.py` 算出完整期望，结果与意图矛盾的用例拒绝写入；`crosscheck/` 是 Go 写的第二份实现，按 EVALUATION.md 写、不共享代码，重算每条期望，并检查 List/Can 一致（用 `LIKE` 引擎对参数求列表谓词，与按路径语义求的单条规则比较）。信它之前，篡改的向量和改坏的规则都先跑出过红。
- **怎么读**：Go 经 `authzcontract.FS`；Python 和 TypeScript 从钉死的 tag 拷 `vectors/` 并核对 `vectors/SHA256SUMS`。

## 在本仓库工作

- `make check` = `lint`（buf、Redocly）+ `gen-check`（提交的 `gen/go` 与 `buf generate` 的结果一致）+ `build`（`go vet`、`go build`、`gofmt`）+ `validate`（JSON Schema、示例、事件、能力与 reason 的一致性）+ `vectors-check` + `vectors-crosscheck`，全部在一次性容器里跑。Go 1.25 和 buf 1.57.0，与 contract-infra-iam 相同，这样一个外壳只链接一份 protobuf 运行时。
- 改动按这个顺序：proto / OpenAPI / schema → `EVALUATION.md` 及中文镜像 → `cases.py` 加用例 → `make vectors` → `make check` → 打 tag。
- 文档：英文为准，中文镜像 `*.zh.md` 放在旁边，`##` 小节相同。
