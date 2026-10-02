[English](README.md) · [中文](README.zh.md)

# contract-infra-authz

The family contract of the authz slot, version **authz/2.0**: what every authorization member implements, and what SDKs, IAM members, the frontend generator and the conformance suite consume. It holds contracts only: no member code, no logic.

## What this is

- **The provider contract** `infra.authz.v2`: the gRPC service `AuthzProvider`, the provider-plane REST (bundle, changefeed, snapshot, catalogue, explain), the self-service and admin REST, the events, the capability enum, the error reasons, the NDJSON export format, and the meaning of a bundle ([EVALUATION.md](EVALUATION.md)) with decision vectors that lock it.
- **Not here**: the resource contract every component mounts (`POST {prefix}/_authz/check`, `GET {prefix}/_authz/explain`, `GET|POST|DELETE {prefix}/_shares/{type}/{id}`), the projection tables `besdk_authz_acl` / `besdk_authz_cursor`, and how a runtime polls, caches and answers. Those are component-side and belong to the component protocol (`brickKit/be-protocol`, chapter P6, `openapi/resource-authz.yaml`, `ddl/07-authz-projection.sql`). P6 cites this repository for what the data means.
- **Consumers**: the official SDKs (bundle, changefeed, `WriteTuples`, `Check`, evaluation by E1–E12); IAM members (`ResolveClaims` at login and refresh, `CreateDelegation` for token exchange); the frontend generator (admin and self-service REST); `tools/be-acceptance/conformance/authz/` (provider black box and end to end); be-ops (capability names, catalogue formats).

## Members

| Member | Status | Declares (`provides_capabilities`) | Fits |
|---|---|---|---|
| `infra/authz` (native, default) | 3.0.0: core, admin_write; then, in phase 06 | sharing, relation_sync, check, explain_paths (with 06c); delegation, access_review, impersonation (after 06c); `list_objects` one hop | almost every ERP / CRM deployment, one PostgreSQL |
| `infra/authz-static` | phase 06 | core only; policy file `AUTHZ_POLICY_FILE` | demos, up to ~10 users, edge sites, test fixtures |
| `infra/authz-openfga` | phase 06 | core, sharing, relation_sync, check, graph, list_objects, explain_paths, access_review | collaboration-heavy deployments, multi-hop relations |
| Cedar / OPA | not built | core, conditions (actions only) | real ABAC rules on actions |

The contract is complete from 2.0 on; a member opens capabilities over time without any change here.

`agents` is reserved (A4): no member declares it, `act.kind = agent` is refused, the profile and ceiling shapes are fixed, and the catalogue's optional `delegable` field is shape only.

## Layout

| Path | Holds |
|---|---|
| `proto/infra/authz/v2/provider.proto` | gRPC service `AuthzProvider` and its messages |
| `openapi/authz.openapi.yaml` | provider-plane, self-service and admin REST (OpenAPI 3.1) |
| `schemas/bundle.schema.json` | bundle v2 |
| `schemas/changefeed.schema.json` | changefeed page, tuple snapshot page, tuple, poke |
| `schemas/catalog.schema.json` | the catalogue (keys, dimensions, resource types) and the `RESOURCE_CATALOG` shape |
| `schemas/export-record.schema.json` | one line of the NDJSON export `authz-export/1` |
| `schemas/vector.schema.json` | one decision vector |
| `capabilities.yaml` | the capability enum: core vs optional, what a member must do, how its absence degrades |
| `errors.yaml` | the family's error reasons, domain `infra/authz` |
| `events/authz.events.json` | published events, the inbound relation sync, the poke |
| `EVALUATION.md` | rules E1–E12: how a bundle, a token and a record give a decision |
| `vectors/decision/`, `vectors/SHA256SUMS` | decision vectors |
| `vectors/tools/` | case definitions, the reference evaluator (Python), the independent cross-check (Go) |
| `examples/` | a full bundle and an export file |
| `gen/go/infra/authz/v2/` | the generated Go package `authzv2` (committed, `make gen`) |
| `fs.go`, `go.mod` | the Go module `github.com/brickKit/contract-infra-authz/v2`, which embeds the files above |

## Addressing and planes

- Every consumer reaches the installed member through the shared key `AUTHZ_URL` (base URL by the member's own service name, `config/vars.yaml`). No component, and no IAM member, declares a dependency on an authz member: a depended-on member could not be swapped (0104, 0107).
- **Provider plane** (system traffic, never through the edge): `GET /authz/v2/bundle`, `/authz/v2/changes`, `/authz/v2/tuples`, `/authz/v2/catalog`, `POST /authz/v2/explain`, and the gRPC service on the member's `grpc` port, whose target callers derive from `AUTHZ_URL`: its host and its port + 1000 (be-protocol P2.10), so a member registers its `grpc` port as its HTTP port + 1000. Callers send `be-caller`.
- **Edge**: `/api/me/*` (any signed-in user) and `/api/admin/*` (key `infra.authz.admin`). A member lists them in its `edge_routes`, never `/authz/v2/*`.

## Capabilities

- **Core** is not optional: claims, keys, levels, dimension values, field keys, stale, revision, catalogue sync, `/api/me/access`, basic explain, time-limited grants, admin reads, the export.
- **Optional**: `admin_write`, `sharing`, `relation_sync`, `check`, `graph`, `list_objects` (an object `{max_results}`), `delegation`, `agents` (reserved), `impersonation`, `access_review`, `explain_paths`, `conditions` (reserved, actions only).
- **Negotiation happens twice.** At assembly: a member's `assembly.yaml` lists `provides_capabilities`, a component's lists `requires_capabilities`, and gate `authz-capability-scan` fails when the second is not a subset of the first. At run time: the bundle's `capabilities` object says what the running member offers, and every consumer degrades by it.
- **Absence is explicit and tested**: an operation of an undeclared capability answers `501` / `UNIMPLEMENTED` with reason `CAPABILITY_UNAVAILABLE` (domain `be`) and `metadata.capability`; the SDK and frontend behaviour for each absence is in `capabilities.yaml` (`absent.backend`, `absent.frontend`).
- Names are append-only. Consumers ignore names they do not know.

## Provider surfaces

| Surface | REST | gRPC | Capability |
|---|---|---|---|
| claims at login / refresh | — | `ResolveClaims` | core |
| bundle | `GET /authz/v2/bundle` (ETag) | `GetBundle` | core |
| catalogue | `GET /authz/v2/catalog` | `GetCatalog` | core |
| roles by code | `GET /api/admin/roles…` | `BatchGetRoles` (≤ 500) | core |
| changefeed / snapshot | `GET /authz/v2/changes`, `/authz/v2/tuples` | `ReadChanges`, `ReadTuples` | sharing or relation_sync |
| share writes | — (the owner's `_shares` calls gRPC) | `WriteTuples` (idempotency key) | sharing |
| remote check | — | `Check`, `BatchCheck` (≤ 500) | check |
| graph listing | — | `ListObjects` (capped) | graph, list_objects |
| explain | `POST /authz/v2/explain`, `GET /api/admin/users/{sub}/access` | `Explain` | core (+ explain_paths) |
| delegations | `/api/me/delegations`, `/api/admin/delegations`, `/api/admin/profiles` | `CreateDelegation`, `RevokeDelegation`, `BatchGetDelegations` | delegation |
| shares review | `/api/me/shares`, `/api/admin/shares` | — | sharing |
| access review | `GET /api/admin/access-review` | — | access_review |
| export / import | `GET /api/admin/export`, `POST /api/admin/import` | — | core / admin_write |

- **Revision** is the member's monotonic int64 as a decimal string. Every write returns it. The changefeed is gap-free per type set, its `watermark` is the head, and an `after` the member cannot serve completely answers `410` / `CHANGES_EXPIRED`; the consumer rebuilds from the snapshot.
- **Two tuple sources.** Shares are authz-owned: only the type's `owner_component` (checked against `be-caller`) writes them, through `WriteTuples`, after its own eligibility check. Component-owned relations arrive as `infra.authz.relation.sync.v1` (inbound, replace-the-group, version must be newer, `ce-source` must be the owner); admins cannot edit them.
- **Events** (`events/authz.events.json`): `infra.authz.tuple.changed.v1`, `.scope_grant.changed.v1`, `.delegation.changed.v1`, `.role.changed.v1`, `.user_role.changed.v1`, each with the actor and its act chain; poke `infra.authz.changed.v1` on core NATS. Every member publishes the same subjects; consumers never filter on `ce-source`.
- **Consumed events** (`events/authz.events.json`, `consumes`; core, every member): from the identity family (contract-infra-iam `iam/1`), `infra.iam.user.disabled.v1` sets `stale_since[sub]` to the event's `ce-time`, so access tokens already issued answer `401 TOKEN_STALE` at once while the identity member refuses new ones; `infra.iam.user.deleted.v1` sets `stale_since[sub]` and removes every assignment of the sub (roles, keys, department, tuples with subject `user:<sub>`), publishing `user_role.changed.v1` and `tuple.changed.v1`; `infra.iam.user.created.v1` or `.updated.v1` with `bootstrap_admin: true` grants the system role `superuser` to that sub, idempotently. A re-enabled user (`updated.v1`, `status: active`) keeps the assignments it had. The member consumes them through a durable like any component (be-protocol P12), deduplicating by the aggregate cursor.

## Catalogue sync

- A member builds its catalogue at start from three configuration keys: `PERMISSION_CATALOG` (`registry/permissions.tsv`), `DATA_SCOPE_CATALOG` (`registry/data-scopes.tsv`) and `RESOURCE_CATALOG` (a JSON file be-ops generates from every component's `resources` block; shape: `schemas/catalog.schema.json`, `resource_types`).
- After every sync the system role `superuser` holds every key that is not deprecated; nobody holds `superuser` by default. The first administrator is not configured here: the identity member binds the shared key `BOOTSTRAP_ADMIN_LOGIN` (an IdP login name or e-mail) to a platform `sub` at that person's first login and says so in its user event (`bootstrap_admin: true`); the authorization member grants `superuser` on that event (*Consumed events*). A `sub` cannot be configured in advance: it does not exist before the first login (be-protocol P2.11).
- `catalog_digest` (bundle) = `sha256:` + hex SHA-256 of the RFC 8785 canonical JSON of the catalogue as `GetCatalog` returns it, arrays sorted. A gate or a test compares it with the digest of what be-ops generated.
- Every member also accepts `IAM_JWKS_URL`, `IAM_ISSUER` and `TENANT_ID` (to verify admin and self-service tokens like any component). Its own keys (`AUTHZ_POLICY_FILE` for the static member) are its own business.

## Moving assignments between members

Format `authz-export/1` (`schemas/export-record.schema.json`, `examples/export.example.ndjson`): UTF-8 NDJSON, a `header` line, records grouped in the order `role`, `user_role`, `user_dept`, `profile`, `delegation`, `tuple`, `relation_group`, each group sorted by its natural key, then a `footer` with per-kind counts and the SHA-256 of the record lines. Two exports of one state differ only in `exported_at`.

- **Export** (`GET /api/admin/export[?kinds=…]`, core) is taken from a member whose writes are stopped (admin UI read-only or member stopped after the export). `kinds=` is the only way to leave a kind behind, and the header lists what the file carries.
- **Import** (`POST /api/admin/import[?dry_run=true]`, admin_write) is all or nothing: a record the member cannot hold (a `tuple` for a member without `sharing`, an unknown key or kind) is reported with its line and reason and nothing is written (`400` / `IMPORT_REJECTED`). Importing the same file twice gives the same state.
- **Revisions across the switch.** The importer's first revision is above the header's `revision`, and it answers `410` for any `after` below the header's revision. A component whose projection is exactly at the export point continues; every other rebuilds from the snapshot. No component changes anything.
- **Static member.** Importing into `infra/authz-static` writes its policy file instead of a database; an export filtered to `role,user_role,user_dept` is what it can hold.
- **Steps**: stop admin writes → export → `brickkit add` the new member, `brickkit remove` the old one → point `AUTHZ_URL` at the new member → `make gates` (`authz-capability-scan`) → `dry_run` import → import → run the conformance suite → go live.
- `relation_group` records keep their version, so a later sync with an older version is still dropped; the owners' outbox and the stream also hold the syncs for replay.

## Versioning

- The bundle's `contract` is `authz/2.<minor>`; the Go module and the repository tags are `v2.<minor>.<patch>` (bare `v`-tags: this is not a brickKit component).
- **Minor** only adds: optional members, capabilities, rpcs, endpoints, event subjects, export kinds, error reasons, vectors for new rules. Nothing changes meaning; a minor never makes a conforming member non-conforming, so every new capability is optional.
- **Patch**: wording, examples, more vectors for existing rules.
- **Major** (`authz/3`) is a new proto package `infra.authz.v3`, a new module path `/v3`, new paths `/authz/v3/*` served beside the old ones while both majors are installed.
- Gates: `buf breaking` (FILE) against the previous tag (`make breaking BASE=v2.0.0`); capability names, error reasons and vector IDs are append-only.
- A member, an SDK or the suite pins one exact tag. be-protocol's text refers to the major only ("`contract: authz/2.x`").

## Generated code

**Decision**: Go code is generated here and published by this module; every other language generates privately from a pinned tag.

| Language | What | Where |
|---|---|---|
| Go | `protoc-gen-go` + `protoc-gen-go-grpc` output, committed with the tag that changes the proto (`make gen`) | `github.com/brickKit/contract-infra-authz/v2/gen/go/infra/authz/v2` (package `authzv2`); the contract files through `authzcontract.FS` at the module root |
| Python, TypeScript | no package in 2.0; the SDK copies `proto/` and `schemas/` from a pinned tag (`make sync-contracts`, checked against the tag's files) and generates into a private module (`besdk._contracts`, `@brickkit/be-sdk-ts/_contracts`) | inside be-sdk-python and be-sdk-ts |
| Frontend | its generator reads `openapi/authz.openapi.yaml` from a pinned tag | the frontend repository |

Why:

- **0101 gains a third category.** Until now only `be-sdk-*` and a component's own `gen/<domain>/<name>` package cross a component boundary. A family contract belongs to no member (the iam contract once lived in the Casdoor member's repository, which breaks as soon as a second member exists), carries no logic and no component semantics, and there is exactly one per process: it meets 0101's revisit conditions, so 0101 is amended to allow "family contract packages" as the third category.
- **One generated package per process is mandatory in Go.** The protobuf runtime registers every message by its full name; two copies of `infra.authz.v2.*` in one binary (the SDK's client and the authz member's server, both compiled into `be/go-infra`) conflict at start. This is the existing pitfall "copied generated code panics once caller and callee share a shell". Only a single published package avoids it.
- **Python and TypeScript have one consumer each today** (their SDK), so a private copy cannot meet a second copy in the same process; components never import the contract directly, they go through the SDK. When a non-Go member or a second consumer in one of those languages appears, this repository adds `python/` and `ts/` packages installable by git tag (the way be-sdk-ts is installed today), and the SDK switches to them in the same release.
- This matches be-protocol's rule for its own vectors: copying contract files from a tag is copying data, not code.

## Proving conformance

1. Declare `provides_capabilities` in the member's `assembly.yaml` (names from `capabilities.yaml`), and advertise the same set in the bundle.
2. Run `tools/be-acceptance/conformance/authz/` against the running member (the suite signs its own tokens and seeds a fixture catalogue):
   - **core** must pass;
   - every declared optional capability must pass its group;
   - every undeclared one must answer `501` / `CAPABILITY_UNAVAILABLE` with its name, and be `false` or absent in the bundle;
   - an export imported into another member gives the same decisions;
   - **end to end**: a fixture component built with the real SDK runs against the member; randomised grants, shares, delegations and expiry; List/Can consistency, visible right after a share with its revision, gone after revocation and expiry, masked fields.
3. The suite writes a capability matrix (member × capability × pass / degraded correctly / fail) into the test record for that member version; `make gates` checks the record exists.
4. Every official SDK and the in-process fake provider used by component tests pass every vector in `vectors/decision/`, so the fixture cannot drift from the members.

## Decision vectors

- 62 vectors in `vectors/decision/`, one file each, IDs stable and never reused; format in [EVALUATION.md](EVALUATION.md#vector-file-format). Tags: `bundle`, `token`, `key`, `level`, `r60`, `window`, `values`, `sharing`, `relation_sync`, `delegation`, `ceiling`, `agents`, `impersonation`, `fields`, `graph`, `explain`, `r62`, `degrade`.
- **How they are made**: `vectors/tools/cases.py` states each input and a hand-written intent; `generate.py` computes the full expected result with `reference.py` and refuses a case whose result contradicts its intent; `crosscheck/` is a second implementation in Go, written from EVALUATION.md with no shared code, that recomputes every expected result and also checks List/Can consistency (the list predicate evaluated with a `LIKE` engine against the single-record rule evaluated on path semantics). A corrupted vector and a mutated rule were both seen red before the suite was trusted.
- **How they are read**: Go through `authzcontract.FS`; Python and TypeScript copy `vectors/` from a pinned tag and check `vectors/SHA256SUMS`.

## Working on this repository

- `make check` = `lint` (buf, Redocly) + `gen-check` (the committed `gen/go` equals `buf generate`) + `build` (`go vet`, `go build`, `gofmt`) + `validate` (JSON Schema, examples, events, capability and reason consistency) + `vectors-check` + `vectors-crosscheck`, all in throwaway containers. Go 1.25 and buf 1.57.0, the same as contract-infra-iam, so one shell links one protobuf runtime.
- A change goes in this order: proto / OpenAPI / schema → `EVALUATION.md` and its Chinese mirror → a case in `cases.py` → `make vectors` → `make check` → tag.
- Documents: English canonical, Chinese mirror `*.zh.md` beside each, same `##` sections.
