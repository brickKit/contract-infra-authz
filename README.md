# contract-infra-authz

授权的族契约：每个授权成员（现在只有 `infra/authz`）都提供的系统面方法，以及从它生成的 Go 与 Python 代码。调用方（每个组件经 SDK）与授权成员都只导入这个包（决定 0101）。旧版本（2.0.0 的预发布 rc.2）在分支 `legacy/v2`，标签保留；本主分支按终局设计从零开始（D59），版本从 `3.0.0` 起（A110）。

依据：装配项目 [be-assembly-standard](https://github.com/brickKit/be-assembly-standard) 的安全 03（授权视图与核验）、安全 09a（记录、定义与错误）、D76（线上怎样传），组件协议 [be-protocol](https://github.com/brickKit/be-protocol) 第 08 章（调用方一侧，P8.9–P8.11）。

## 内容

| 位置 | 是什么 |
| --- | --- |
| `proto/be/authz/v3/authz.proto` | 四个服务：`ViewService.Verify`（核验视图）、`DefinitionService.Submit`（提交定义）、`AccountService.CheckAccountChange`（账号状态变更前的确认，alpha.3 起）、`RecoveryService`（整套恢复的 6.4–6.5，alpha.5 起） |
| `gen/go/be/authz/v3/` | Go 代码，包 `authzv3`（消息与 gRPC 桩），提交在仓库里 |
| `python/` | Python 包 `contract-infra-authz`，模块 `be.authz.v3`（`authz_pb2`、`authz_pb2_grpc`）；`be` 是各契约包共用的命名空间，没有 `__init__.py` |

**线上怎样传**（D76）：protobuf 只作信封。视图分片与定义是安全记录，以规范 JSON 字节放在 `bytes` 字段里，不带自己的摘要；摘要放在旁边的字段里，按 P8.8 对这些字节计算。接收方先按 `be-protocol` 的 `schemas/security/<记录类型>.schema.json` 校验，再核对字节是规范形式、摘要相符，然后才使用。

## 授权成员的义务

### `ViewService.Verify`

1. **准入**：只接受带合格服务证书的连接（P8.5）；请求的 `component` 必须等于证书里的组件，否则答 `PERMISSION_DENIED`（P8.6）。
2. **在主库上重新计算**：收到请求时，在**主库**上读取已提交的安全状态，重新计算调用者的每个分片的完整视图。不读只读副本，不缓存回答；否则“收紧提交之后的核验都得到收紧后的视图”不成立（安全 03）。
3. **逐个分片回答**：
   - 持有的摘要等于当前视图的摘要，答 `SHARD_STATUS_UNCHANGED`；
   - 否则答 `SHARD_STATUS_CHANGED`，附当前视图的字节与摘要；
   - 调用者应有、却没有持有的分片，同样答 `CHANGED`。

   视图字节里有恢复代次、各依赖域的安全修订、纪元与成员实例，所以这几样任何一样变了，摘要都会变，安全 03 的回答表因此自动满足：恢复代次、成员实例或纪元不同，就发完整的新视图。
4. **不能完整证明时答关闭**：范围暂时关闭或事实未补齐时，对受影响的分片答 `SHARD_STATUS_CLOSED`，不发旧视图；其他已完整证明的分片照常回答。
5. **回答的其余字段**：
   - `nonce` 原样带回；
   - `computed_at` 是计算时刻，只供审计；
   - `instance` 是本成员的实例身份（安装时生成，随运行档案保存，不随库恢复改变；协议 14 第 3 条）；
   - `recovery_generation` 是部署恢复代次（域 `authz.recovery`）。
6. **分片方式**：第 5 步一个组件一个分片。分片键是组件 ID 的 `/` 换成 `.`；`applicability` 是这个组件已被接受的定义里的资源类型。分片方式与大小按负载再定（安全 09a 的待定）。

### `DefinitionService.Submit`

1. **准入与属主**：
   - 请求的 `component` 必须等于调用者证书里的组件，且等于每份定义的 `authority`；
   - 资源类型与权限键的属主按注册表核对，注册表由部署作为本成员的配置提供，不读项目仓库；
   - 不符的答 `DEFINITION_OWNER_MISMATCH`，并记录安全事件（安全 09a 的 EN21、EN23）。
2. **逐份校验**：
   - 记录类型只能是 `be.security.resource_definition` 或 `be.security.operation_definition`；
   - 先按 schema 校验，再核对字节是规范形式、摘要相符，最后查约束一列的条件规则（例如 `restricted` 字段要有 `read_key`、写字段要在读字段中、操作的资源类型已定义）；
   - 不合格的答 `DEFINITION_INVALID`。
3. **版本与幂等**：
   - 被接受的集合按 `be.security.definition_set` 算出摘要（组件、版本、各定义摘要的集合）；
   - 同一组件、同一版本再提交同一集合，答 `SUBMIT_STATUS_ACCEPTED`，`set_digest` 相同；
   - 版本相同、集合不同，整次拒绝（`DEFINITION_VERSION_CONFLICT`）。
4. **拒绝列全**：被拒时，`rejections` 列出找到的全部原因，不只列第一条。
5. **新版本生效**：一个组件的新版本被接受后，它的视图按新定义计算。旧版本的定义保留，供 `DefinitionRef` 引用。

### `AccountService.CheckAccountChange`（alpha.3 起）

身份成员在停用、冻结、重新启用或解冻一个账号之前问一次（安全 08 的“管理员账号的状态变更”、安全 03 超过 `T_tight` 的两人规则）。

1. **准入**：只许部署配置的身份成员调用（服务身份）。
2. **要不要确认**：账号持有授权管理资格（受保护操作），或请求里 `second_person` 为真（身份成员按自己陈旧的依据办理、超过 `T_tight`），就要确认；否则答 `ALLOWED`。回答里的 `administrator` 说明账号是否持有授权管理资格（停用它时按安全 08 严重告警）。
3. **确认是否成立**：确认记录的对象是这个账号，`target_state` 与 `target_state_version` 是这次的状态与账号当前的安全状态版本；没用过、没过期；确认人不是请求者，也不是账号本人；`holding` 的确认人此刻合格（对象不是授权管理员时，两人规则的确认人可按最后已应用的事实判断）；部署所有者的确认在收紧时随时可以，放宽（重新启用、解冻）只在除申请人与对象外没有可用管理员时。成立答 `ALLOWED`，没给答 `CONFIRMATION_REQUIRED`，不成立答 `REFUSED` 并写明原因；确认人的资格此刻证明不了（身份来源停住，管理员账号的确认人要此刻可证明）答 `UNPROVABLE`（alpha.4 起）：什么也不定，身份成员答处理中（`ADMIN_AVAILABILITY_UNPROVABLE`），来源恢复后重试。
4. **不使用**：这一步只核对；确认在授权成员应用带着它的账号状态（`be.security.account_status` 的 `confirmation`）时才标为已使用，核对不通过的重新启用与解冻使该账号的授权管理持有资格转为待补确认。

### `RecoveryService`（alpha.5 起）

整套恢复第 6 步的 6.4–6.5（装配项目协议 15）。三个方法都只许恢复工具（`ops/recover`）调用，在恢复阶段 `replaying` 中使用。

1. **`Sources`（6.4）**：第一次调用 `since` 为空，成员答 `as_of`（自己主库时钟上的此刻），并请每个水位来源在下一步补取；之后带回这个 `as_of`。每个来源答对齐状态与 `applied`（水位不早于 `as_of`，组件协议 P9.35：来源在这一刻之前提交的已全部应用）；`all_applied` 为真才进 6.5。
2. **`ReplayDeferred`（6.5）**：执行推迟到 6.5 的“只有意图”的管理员撤销（协议 15 的重放表）。记录身份已在变更历史里答 `reflected`；被撤销的记录不在答 `dangling`；执行之后可用的授权管理员可证明为零的，不执行，被撤销的持有资格转暂停待复核，答 `for_review`；否则执行，答 `applied`。证据记录的核对与 `ReplayService` 相同（记录者是本成员）。
3. **`Check`（6.5）**：对最终状态检查不变量：
   - 每条生效或暂停的记录按它的来源重新判断（等于对每个来源跑一遍影响闭包：来源结束或什么都不剩的结束、无法计算的暂停、部分越出上限的标记复核），计数在回答里；账号状态此刻证明不了的列在 `unprovable`，这一次什么都不判，来源应用之后再调用；
   - `review_subjects` 中按重放后的状态不是授权管理员的，各建一条来源为 `recovery_review` 的安全处置（暂停他的全部段，第 10 步的人复核后解除），是授权管理员的不关闭，列在 `admins_not_closed`；同一主体已有生效中的 `recovery_review` 处置时不再新建；
   - 最后判可用的授权管理员：可证明为零就进待恢复（安全 08），`admin_state` 答判后的状态；
   - 职责分离：现在没有可声明的静态互斥角色，这一项为空。

## 引用

- Go：`go get github.com/brickKit/contract-infra-authz/v3@v3.0.0-alpha.5`，导入 `github.com/brickKit/contract-infra-authz/v3/gen/go/be/authz/v3`。
- Python（uv）：`contract-infra-authz = { git = "https://github.com/brickKit/contract-infra-authz", tag = "v3.0.0-alpha.5", subdirectory = "python" }`。

运行时的版本：生成代码要求 `google.golang.org/protobuf` v1.36.12 与 grpc-go v1.83.2 起，Python 要求 `protobuf` 7.36.2、`grpcio` 1.84.0 起，与 SDK 锁定的版本一致。

## 修改与发布

- 改 `proto/` 之后运行 `make gen`，生成的代码与 proto 一起提交；`make check` 依次核对风格（buf STANDARD）、生成的代码是否最新，以及 Go 模块能否构建。buf 在一次性容器里运行，镜像与插件的版本都是精确的（`Makefile`、`buf.gen.yaml`）。
- 只做加法：发布之后运行 `make breaking BASE=<上一个标签>`。
- 一个标签同时发布 Go 与 Python：`v3.0.0-alpha.N`，Python 版本写作 `3.0.0aN`（`python/pyproject.toml`）。
