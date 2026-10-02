[English](EVALUATION.md) · [中文](EVALUATION.zh.md)

# Evaluation rules, authz/2.0

What a bundle means: how a consumer (an official SDK, the in-process fake provider, a component in any language) turns a bundle, a verified token and a resource's facts into a decision. Normative. Every rule has an ID (E1–E12) that the decision vectors in `vectors/decision/` and the reference code in `vectors/tools/` cite. A member's own decisions (Check, Explain, `/api/me/access`) follow the same rules.

## Inputs

| Input | Content |
|---|---|
| bundle | the JSON of `schemas/bundle.schema.json` |
| claims | from a verified access token: `sub`, `iat`, `roles[]`, `dept_path`, `tenant_id`, optional `act`, `ceil[]`, `dg` |
| now | the consumer's clock, unix seconds |
| key `K` | the route's permission key |
| resource type `T` | from the owner's `resources` declaration (`schemas/catalog.schema.json`, `resource_type`): `type`, `view_key`, `dimensions`, `relations`, `fields`, `derivation` |
| row `r` (single record only) | `id`, `owner`, `dept_path`, `values{dimension: value}` |
| ACL rows (single record only) | the projection rows `besdk_authz_acl` for the record: `rtype`, `rid`, `relation`, `subject`, `expires_at` |
| graph ids | what `ListObjects` returned, graph types only |

**Ordering.** Every array this document produces is deduplicated and sorted ascending by byte order. Levels are ordered `own < dept < subtree < all`; `none` means no level.

## E1 Bundle acceptance

- The bundle is accepted only when `contract` matches `^authz/2\.(0|[1-9][0-9]*)$`. Otherwise it is refused: logged at ERROR, never used, and protected routes keep answering `503` / `AUTHZ_NOT_READY` until a valid bundle arrives. A refused bundle never replaces an accepted one.
- Unknown members and unknown capability names are ignored.

## E2 Token checks

In this order; the first failure decides:

1. **Stale**: `stale_since[sub]` exists and `iat < stale_since[sub] − 5` → `TOKEN_STALE`.
2. **Revoked grant**: `dg` is non-empty and a key of `revoked_grants` → `TOKEN_STALE`.
3. **Delegated token**: a token is delegated when it has `act`, a non-empty `ceil` or a non-empty `dg`. A delegated token needs capability `delegation` → otherwise `UNSUPPORTED_DELEGATION`.
4. **Act chain**: walk `act`, `act.act`, …: kind `agent` needs `agents`; kind `user` (impersonation) needs `impersonation`; kind `svc` needs nothing more; any other kind → `UNSUPPORTED_DELEGATION`.

A token that passes is `OK`.

## E3 Validity windows

- A window is `[from_ts, until)` in unix seconds; a missing bound is open.
- **Active roles** `R` = the token's roles whose `grants[role]` window contains `now` (a role without a grants entry is active). A role outside its window contributes nothing: no keys, levels, values or subjects.
- An `on_behalf` delegation counts only inside its window.
- An ACL row counts while `expires_at` is null or later than `now` (RFC 3339, exclusive).

## E4 Ceilings

- The ceilings are the profiles named by `ceil[]`; an unknown code is an empty profile (`keys: []`, `max_level: own`, `relations: []`).
- The ceilings **allow** key `k` when every ceiling lists `k` in `keys` or `fields`. With no ceilings, every key is allowed.
- A key the ceilings do not allow is absent for every purpose: no rule, no ACL, no graph branch.
- The level is capped at the lowest `max_level` of the ceilings (E6); relations are intersected with every ceiling's `relations` (E8).

## E5 Keys

- **Holders** of `K` = the active roles `r` with `K ∈ roles[r]`.
- **Delegations of `K`** `D_K` = when capability `delegation` is true, the bundle's `delegations` with `mode = on_behalf`, `to = sub`, `K ∈ keys`, inside their window. Otherwise empty.
- `has(K)` = (holders non-empty or `D_K` non-empty) and the ceilings allow `K`.

## E6 Levels and the identity part

- The level a role gives `K`: `grants[r].levels[K]`, else `grants[r].default_level`, else `own`.
- `level(K)` = the highest among the holders, capped by the ceilings; `none` when there are no holders or the ceilings do not allow `K`. Delegations give no level.
- **Department.** `dept_path` is valid when it matches `^/([^/]+/)*$`. An empty or malformed path means *no department* (R60); `/` is the root and the only path that means the whole tree.
- **Prefix encoding.** A department prefix is the path with `\`, `%` and `_` each preceded by `\`, followed by `%` (a SQL `LIKE` pattern with backslash escape).
- **org values** of `K` = the union of `grants[r].values.org` over the holders. Under ceilings, paths are dropped when the cap is below `subtree`, and `*` when it is below `all`.
- Parameters (names as in the canonical predicate, foundations 20):

| Parameter | Value |
|---|---|
| `s_all` | `level(K) ≠ none` and (`level(K) = all` or `*` ∈ org values) |
| `s_owners` | `sub` when `level(K) ≠ none`, plus `from` of every `D_K` entry (when the ceilings allow `K`) |
| `s_dept_exact` | the department, when `level(K) = dept` and the department is valid |
| `s_dept_prefix` | prefix(department) when `level(K) = subtree` and the department is valid; plus prefix(v) for every valid org value `v ≠ *` |

- A delegator contributes only their `sub`: their roles and department are not in the bundle and are never merged.

## E7 Resource dimensions

- For each dimension `d` of `T` other than `owner` and `org`: the values of `K` = the union of `grants[r].values[d]` over the holders (empty when the ceilings do not allow `K`).
- `s_dims[d] = {all: "*" ∈ values, ids: values − {*}}`. No values means nothing matches. `*` is only ever granted explicitly.
- Delegations give no dimension values.

## E8 Subject set and relations

- `S(K)` = `user:<sub>`; `role:<r>` for every active role; when the department is valid, `dept:<department>` and `dept_tree:<p>` for `/` and every ancestor of the department and the department itself; `user:<from>` for every `D_K` entry. No department, no `dept` or `dept_tree` subjects.
- A relation **gives** `K` when `K` is in its `grants` or in the grants of a relation it `includes`, transitively.
- `s_relations` = the relations of `T` that give `K` and whose capability is true (`relation_sync` for `owned_by: component`, `sharing` otherwise), intersected with every ceiling's `relations`; empty when the ceilings do not allow `K`.
- `s_acl` = `s_relations` is non-empty. `s_subjects` = `S(K)`.

## E9 Graph branch and degradation

- Only for `derivation: graph`. With capability `graph`: `s_graph_ids` = the ids `ListObjects` returned (when the ceilings allow `K`). Without it: `s_graph_ids` is empty and `degraded` lists `graph` (header `X-Authz-Degraded: graph`).
- Every other type: `s_graph_ids` is empty and nothing is degraded.

## E10 Decision for one record

- `vis(k, r)` is true when one branch holds:
  - **rule**: `has(k)` and the identity part holds and every resource dimension holds. The identity part holds when `T` declares neither `owner` nor `org`, or `s_all`, or (`owner` declared and `r.owner ∈ s_owners`), or (`org` declared and `r.dept_path` equals an `s_dept_exact` entry or matches an `s_dept_prefix` pattern). Dimension `d` holds when `s_dims[d].all` or `r.values[d] ∈ s_dims[d].ids`.
  - **ACL**: `s_acl` and an ACL row with `rtype = T.type`, `rid = r.id`, relation in `s_relations`, subject in `s_subjects`, counting at `now` (E3).
  - **graph**: `r.id ∈ s_graph_ids`.
- `visible = vis(T.view_key, r)`; `allowed = visible and vis(K, r)`.
- `reason`: `NOT_FOUND` when not visible (reads and commands answer `404`); empty when allowed; else `OUT_OF_SCOPE` when `has(K)`, else `MISSING_PERMISSION` (both `403`).
- **List/Can consistency.** A row is in a list for `K` exactly when `vis(K, r)`; the list's SQL predicate with the parameters of E6–E9 and the single-record rule above are the same function.

## E11 Fields

- For each field set of `T`: when `has(read)` is false its columns are **masked** (`null` in responses, listed in `_masked`); when `read` is held but `edit` is absent or not held, they are **read-only**. Field keys follow E4 and E5 like every key.

## E12 Explain facts

Facts for key `K` on one record, each `{kind, source, detail}`, sorted by (kind, source, detail):

- **When `vis(K, r)`** (`reasons`): if the rule branch holds, `role_key` (holder, `K`) for each holder; `level` (the lexicographically first holder with the highest uncapped level, the capped level) when `T` declares `owner` or `org`; `dimension` (d, `r.values[d]`) for each resource dimension; `delegation` (id, from) for each `D_K` entry whose `from` is `r.owner`; `ceiling` (code, `K`) for each ceiling. For each matching ACL row, `relation` (relation, subject) when the relation is `owned_by: component`, otherwise `share`. `relation` (`graph`, `r.id`) for the graph branch.
- **Otherwise** (`missing`): `ceiling` (code, `K`) for each ceiling that does not allow `K`; else `role_key` (empty, `K`) when there is neither a holder nor a delegation; else `level` (empty, `level(K)`) when the identity part fails and `dimension` (d, value) for each failing dimension. Then `capability` (name, empty) for each relation of `T` that would give `K` but whose capability is false, and `capability` (`graph`, empty) for a graph type without `graph`.
- **R62.** When the record is not visible, a `dimension` fact carries an empty detail: an explanation never reveals an attribute of a record the caller cannot see.

## Vector file format

One JSON file per vector in `vectors/decision/`, validated by `schemas/vector.schema.json`:

| Member | Content |
|---|---|
| `id`, `title`, `tags` | stable ID (never reused), a sentence, the rule groups it covers |
| `contract` | the contract version whose rules computed it |
| `input` | `bundle`, `claims`, `now`, `key`, `resource_type`, and for a single record `row`, `acl`, `graph_ids` |
| `expected` | `bundle` (`accepted` / `refused`); `token`; `has_key`; `level`; `scope_params`; `degraded`; `fields` (types with field sets); `decision` and `explain` (single record) |

A consumer passes a vector when it computes every member of `expected` exactly. Members after a refusal (`bundle: refused`) or a token failure are absent. Vectors only grow: a new rule or a corrected wording adds vectors; a changed expectation is a contract change.
