# contract-infra-authz

授权的族契约：每个授权成员（现在只有 `infra/authz`）都提供的系统面方法，以及从它生成的 Go 与 Python 代码。调用方（每个组件经 SDK）与授权成员都只导入这个包（决定 0101）。旧版本（2.0.0 的预发布 rc.2）在分支 `legacy/v2`，标签保留；本主分支按终局设计从零开始（D59），版本从 `3.0.0` 起（A110）。

依据：装配项目 [be-assembly-standard](https://github.com/brickKit/be-assembly-standard) 的安全 03（授权视图与核验）、安全 09a（记录、定义与错误）、D76（线上怎样传），组件协议 [be-protocol](https://github.com/brickKit/be-protocol) 第 08 章（调用方一侧，P8.9–P8.11）。

## 内容

| 位置 | 是什么 |
| --- | --- |
| `proto/be/authz/v3/authz.proto` | 两个服务：`ViewService.Verify`（核验视图）、`DefinitionService.Submit`（提交定义） |
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

## 引用

- Go：`go get github.com/brickKit/contract-infra-authz/v3@v3.0.0-alpha.1`，导入 `github.com/brickKit/contract-infra-authz/v3/gen/go/be/authz/v3`。
- Python（uv）：`contract-infra-authz = { git = "https://github.com/brickKit/contract-infra-authz", tag = "v3.0.0-alpha.1", subdirectory = "python" }`。

运行时的版本：生成代码要求 `google.golang.org/protobuf` v1.36.12 与 grpc-go v1.83.2 起，Python 要求 `protobuf` 7.36.2、`grpcio` 1.84.0 起，与 SDK 锁定的版本一致。

## 修改与发布

- 改 `proto/` 之后运行 `make gen`，生成的代码与 proto 一起提交；`make check` 依次核对风格（buf STANDARD）、生成的代码是否最新，以及 Go 模块能否构建。buf 在一次性容器里运行，镜像与插件的版本都是精确的（`Makefile`、`buf.gen.yaml`）。
- 只做加法：发布之后运行 `make breaking BASE=<上一个标签>`。
- 一个标签同时发布 Go 与 Python：`v3.0.0-alpha.N`，Python 版本写作 `3.0.0aN`（`python/pyproject.toml`）。
