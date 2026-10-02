"""Case definitions of the decision vectors.

Each case gives the input and an `intent`: the part of the expected result
the author states by hand from EVALUATION.md. generate.py computes the full
expected result with reference.py and refuses to write a vector whose
computed result contradicts its intent. Dotted intent paths address nested
members ("decision.visible").
"""

import copy

NOW = 1760000000
DIGEST = "sha256:" + "ab" * 32

CAPS = {
    "core": True, "admin_write": True, "sharing": True, "relation_sync": True,
    "check": True, "graph": False, "list_objects": {"max_results": 1000},
    "delegation": True, "agents": False, "impersonation": False,
    "access_review": True, "explain_paths": True, "conditions": False,
}

ORDER = {
    "type": "erp.sales.order",
    "owner_component": "erp/sales",
    "view_key": "erp.sales.view",
    "keys": ["erp.sales.view", "erp.sales.confirm", "erp.sales.cancel", "erp.sales.ship", "erp.sales.share"],
    "dimensions": ["owner", "org"],
    "relations": {
        "viewer": {"grants": ["erp.sales.view"]},
        "editor": {"includes": ["viewer"], "grants": ["erp.sales.ship"]},
    },
    "share": {"key": "erp.sales.share", "relations": ["viewer", "editor"],
              "subjects": ["user", "role", "dept", "dept_tree"]},
    "fields": [{"set": "erp.sales.pricing", "columns": ["discount", "unit_price"],
                "read": "erp.sales.pricing.read", "edit": "erp.sales.pricing.edit"}],
    "derivation": "direct",
}

BALANCE = {
    "type": "erp.inventory.balance",
    "owner_component": "erp/inventory",
    "view_key": "erp.inventory.view",
    "keys": ["erp.inventory.view", "erp.inventory.adjust"],
    "dimensions": ["warehouse"],
    "relations": {},
    "derivation": "direct",
}

ENTRY = {
    "type": "erp.finance.entry",
    "owner_component": "erp/finance",
    "view_key": "erp.finance.view",
    "keys": ["erp.finance.view", "erp.finance.post"],
    "dimensions": ["legal_entity"],
    "relations": {},
    "derivation": "direct",
}

OPPORTUNITY = {
    "type": "crm.opportunity.opportunity",
    "owner_component": "crm/opportunity",
    "view_key": "crm.opportunity.view",
    "keys": ["crm.opportunity.view", "crm.opportunity.edit"],
    "dimensions": ["owner", "org"],
    "relations": {
        "viewer": {"grants": ["crm.opportunity.view"]},
        "member": {"owned_by": "component", "includes": ["viewer"], "grants": ["crm.opportunity.edit"]},
    },
    "derivation": "direct",
}

TASK = {
    "type": "infra.workflow.task",
    "owner_component": "infra/workflow",
    "view_key": "infra.workflow.task.view",
    "keys": ["infra.workflow.task.view", "infra.workflow.task.act"],
    "dimensions": ["owner"],
    "relations": {},
    "derivation": "direct",
}

FOLDER = {
    "type": "prj.project.folder",
    "owner_component": "prj/project",
    "view_key": "prj.project.view",
    "keys": ["prj.project.view"],
    "dimensions": ["owner", "org"],
    "relations": {"viewer": {"grants": ["prj.project.view"]}},
    "derivation": "graph",
}


def bundle(roles, grants=None, caps=None, **extra):
    b = {
        "contract": "authz/2.0",
        "revision": "100",
        "capabilities": copy.deepcopy(caps if caps is not None else CAPS),
        "roles": roles,
        "grants": grants or {},
        "profiles": {},
        "delegations": [],
        "stale_since": {},
        "revoked_grants": {},
        "catalog_digest": DIGEST,
    }
    b.update(extra)
    return b


def caps(**changes):
    c = copy.deepcopy(CAPS)
    c.update(changes)
    return c


def claims(roles, dept="/1/12/", sub="u_me", **extra):
    c = {"sub": sub, "iat": NOW - 60, "roles": roles, "dept_path": dept, "tenant_id": "t1"}
    c.update(extra)
    return c


def row(rid, owner="u_other", dept="/1/12/", **values):
    return {"id": rid, "owner": owner, "dept_path": dept, "values": values}


def acl(rtype, rid, relation, subject, expires_at=None):
    a = {"rtype": rtype, "rid": rid, "relation": relation, "subject": subject}
    if expires_at is not None:
        a["expires_at"] = expires_at
    return a


SALES_ROLES = {"rep": ["erp.sales.view", "erp.sales.cancel", "erp.sales.confirm"]}


def case(cid, title, tags, inp, intent):
    full = {"now": NOW}
    full.update(inp)
    return {"id": cid, "title": title, "tags": tags, "input": full, "intent": intent}


CASES = [
    # ---- E1 bundle acceptance -------------------------------------------
    case("bundle-contract-missing-refused", "A bundle without contract is refused", ["bundle", "invalid-bundle"],
         {"bundle": {k: v for k, v in bundle(SALES_ROLES).items() if k != "contract"},
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER},
         {"bundle": "refused"}),
    case("bundle-contract-v1-refused", "A bundle of another major is refused; there is no v1 fallback", ["bundle", "invalid-bundle"],
         {"bundle": dict(bundle(SALES_ROLES), contract="authz/1.0"),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER},
         {"bundle": "refused"}),
    case("bundle-later-minor-unknown-members-ignored", "A later minor with unknown members and capabilities is accepted; unknown names are ignored", ["bundle"],
         {"bundle": dict(bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "subtree"}}},
                                caps=caps(future_thing=True)),
                         contract="authz/2.7", future_member={"x": 1}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER},
         {"bundle": "accepted", "token": "OK", "level": "subtree"}),

    # ---- E2 token checks ------------------------------------------------
    case("token-stale", "iat before stale_since - 5 is stale", ["token"],
         {"bundle": bundle(SALES_ROLES, stale_since={"u_me": NOW - 30}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER},
         {"token": "TOKEN_STALE"}),
    case("token-stale-within-skew", "iat within 5 s before stale_since is still accepted", ["token"],
         {"bundle": bundle(SALES_ROLES, stale_since={"u_me": NOW - 57}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER},
         {"token": "OK"}),
    case("token-ceil-without-delegation-capability", "A token with ceil when the member lacks delegation", ["token", "delegation"],
         {"bundle": bundle(SALES_ROLES, caps=caps(delegation=False)),
          "claims": claims(["rep"], ceil=["ro"]), "key": "erp.sales.view", "resource_type": ORDER},
         {"token": "UNSUPPORTED_DELEGATION"}),
    case("token-agent-reserved", "act.kind agent is refused while agents is false (A4)", ["token", "agents"],
         {"bundle": bundle(SALES_ROLES),
          "claims": claims(["rep"], act={"sub": "agent_1", "kind": "agent"}, ceil=["ro"], dg="dg_1"),
          "key": "erp.sales.view", "resource_type": ORDER},
         {"token": "UNSUPPORTED_DELEGATION"}),
    case("token-impersonation-not-offered", "act.kind user (impersonation) is refused while impersonation is false", ["token", "impersonation"],
         {"bundle": bundle(SALES_ROLES),
          "claims": claims(["rep"], act={"sub": "u_admin", "kind": "user"}, ceil=["ro"], dg="dg_2"),
          "key": "erp.sales.view", "resource_type": ORDER},
         {"token": "UNSUPPORTED_DELEGATION"}),
    case("token-revoked-grant", "A token whose dg is in revoked_grants is stale", ["token", "delegation"],
         {"bundle": bundle(SALES_ROLES, revoked_grants={"dg_9": NOW - 10},
                           profiles={"ro": {"keys": ["erp.sales.view"], "max_level": "own", "relations": []}}),
          "claims": claims(["rep"], ceil=["ro"], dg="dg_9"), "key": "erp.sales.view", "resource_type": ORDER},
         {"token": "TOKEN_STALE"}),

    # ---- E5/E6 keys and levels ------------------------------------------
    case("key-missing", "No role grants the key: nothing visible, MISSING_PERMISSION never leaks existence", ["key"],
         {"bundle": bundle({"rep": ["erp.sales.confirm"]}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", owner="u_me")},
         {"has_key": False, "level": "none", "decision.visible": False, "decision.reason": "NOT_FOUND"}),
    case("level-highest-wins", "Two roles grant the key; the highest level wins", ["level"],
         {"bundle": bundle({"a": ["erp.sales.view"], "b": ["erp.sales.view"]},
                           {"a": {"levels": {"erp.sales.view": "own"}}, "b": {"levels": {"erp.sales.view": "subtree"}}}),
          "claims": claims(["a", "b"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="/1/12/5/")},
         {"level": "subtree", "decision.visible": True}),
    case("level-default-level", "A key without an explicit level takes the role's default_level", ["level"],
         {"bundle": bundle({"boss": ["erp.sales.view"]}, {"boss": {"default_level": "all"}}),
          "claims": claims(["boss"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="/9/")},
         {"level": "all", "scope_params.s_all": True, "decision.visible": True}),
    case("level-absent-is-own", "A key granted without any level is own", ["level"],
         {"bundle": bundle(SALES_ROLES),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", owner="u_other", dept="/1/12/")},
         {"level": "own", "scope_params.s_owners": ["u_me"], "decision.visible": False}),
    case("level-own-sees-own", "own sees the caller's own record", ["level"],
         {"bundle": bundle(SALES_ROLES),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", owner="u_me", dept="/7/")},
         {"decision.visible": True, "decision.allowed": True}),
    case("level-dept-excludes-children", "dept sees the department itself, not its sub-departments", ["level"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "dept"}}}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="/1/12/5/")},
         {"level": "dept", "scope_params.s_dept_exact": ["/1/12/"], "scope_params.s_dept_prefix": [],
          "decision.visible": False}),
    case("level-dept-same-department", "dept sees another person's record in the same department", ["level"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "dept"}}}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="/1/12/")},
         {"decision.visible": True}),
    case("level-subtree-includes-children", "subtree sees sub-departments through a LIKE prefix", ["level"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "subtree"}}}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="/1/12/5/")},
         {"scope_params.s_dept_prefix": ["/1/12/%"], "decision.visible": True}),
    case("level-subtree-not-sibling", "subtree does not see a sibling department whose id shares a prefix", ["level"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "subtree"}}}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="/1/123/")},
         {"decision.visible": False}),
    case("no-department-r60", "No department: no department arrays and no department subjects (R60)", ["level", "r60"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "subtree"}}}),
          "claims": claims(["rep"], dept=""), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="")},
         {"scope_params.s_dept_prefix": [], "scope_params.s_dept_exact": [],
          "scope_params.s_subjects": ["role:rep", "user:u_me"], "decision.visible": False}),
    case("malformed-department-is-none", "A malformed dept_path counts as no department", ["level", "r60"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "subtree"}}}),
          "claims": claims(["rep"], dept="1/12"), "key": "erp.sales.view", "resource_type": ORDER},
         {"scope_params.s_dept_prefix": [], "scope_params.s_subjects": ["role:rep", "user:u_me"]}),
    case("root-department-subtree", "Department / with subtree sees every department but not a record without one", ["level", "r60"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "subtree"}}}),
          "claims": claims(["rep"], dept="/"), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="")},
         {"scope_params.s_dept_prefix": ["/%"], "scope_params.s_all": False, "decision.visible": False}),
    case("org-custom-subtrees", "org values add custom department subtrees to the key", ["values", "level"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "own"},
                                                 "values": {"org": ["/1/3/", "/1/7/"]}}}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="/1/7/2/")},
         {"scope_params.s_dept_prefix": ["/1/3/%", "/1/7/%"], "decision.visible": True}),
    case("like-escaping", "Department ids containing % or _ are escaped in prefixes", ["level"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "subtree"}}}),
          "claims": claims(["rep"], dept="/a_b/c%d/"), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="/aXb/cYd/")},
         {"scope_params.s_dept_prefix": ["/a\\_b/c\\%d/%"], "decision.visible": False}),
    case("cancel-own-view-subtree-colleague", "view at subtree and cancel at own: a colleague's order is visible but not cancellable", ["level"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "subtree", "erp.sales.cancel": "own"}}}),
          "claims": claims(["rep"]), "key": "erp.sales.cancel", "resource_type": ORDER,
          "row": row("o1", owner="u_other", dept="/1/12/")},
         {"decision.visible": True, "decision.allowed": False, "decision.reason": "OUT_OF_SCOPE"}),
    case("cancel-own-view-subtree-mine", "The same caller may cancel their own order", ["level"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "subtree", "erp.sales.cancel": "own"}}}),
          "claims": claims(["rep"]), "key": "erp.sales.cancel", "resource_type": ORDER,
          "row": row("o1", owner="u_me", dept="/1/12/")},
         {"decision.allowed": True, "decision.reason": ""}),
    case("action-key-missing-visible", "Visible through view, but no role grants confirm", ["key"],
         {"bundle": bundle({"rep": ["erp.sales.view"]}, {"rep": {"levels": {"erp.sales.view": "subtree"}}}),
          "claims": claims(["rep"]), "key": "erp.sales.confirm", "resource_type": ORDER,
          "row": row("o1", dept="/1/12/")},
         {"decision.visible": True, "decision.allowed": False, "decision.reason": "MISSING_PERMISSION"}),

    # ---- E3 validity windows --------------------------------------------
    case("grant-window-expired", "A role grant past until contributes nothing", ["window"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"default_level": "all", "until": NOW}}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", owner="u_me")},
         {"has_key": False, "level": "none", "decision.visible": False}),
    case("grant-window-not-started", "A role grant before from_ts contributes nothing", ["window"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"default_level": "all", "from_ts": NOW + 1}}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER},
         {"has_key": False}),
    case("grant-window-open", "A role grant inside its window counts", ["window"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"default_level": "all", "from_ts": NOW - 1, "until": NOW + 1}}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER},
         {"has_key": True, "level": "all"}),

    # ---- E7 resource dimensions -----------------------------------------
    case("values-per-key", "view holds warehouses S and N, adjust only S: adjusting N is visible but out of scope", ["values"],
         {"bundle": bundle({"wh_view": ["erp.inventory.view"], "wh_adjust": ["erp.inventory.adjust"]},
                           {"wh_view": {"values": {"warehouse": ["S", "N"]}},
                            "wh_adjust": {"values": {"warehouse": ["S"]}}}),
          "claims": claims(["wh_view", "wh_adjust"]), "key": "erp.inventory.adjust", "resource_type": BALANCE,
          "row": row("b1", warehouse="N")},
         {"scope_params.s_dims": {"warehouse": {"all": False, "ids": ["S"]}},
          "decision.visible": True, "decision.allowed": False, "decision.reason": "OUT_OF_SCOPE"}),
    case("values-star", "* grants every value of the dimension", ["values"],
         {"bundle": bundle({"wh": ["erp.inventory.view"]}, {"wh": {"values": {"warehouse": ["*"]}}}),
          "claims": claims(["wh"]), "key": "erp.inventory.view", "resource_type": BALANCE,
          "row": row("b1", warehouse="Z")},
         {"scope_params.s_dims": {"warehouse": {"all": True, "ids": []}}, "decision.visible": True}),
    case("values-none", "A key without values for a resource dimension sees nothing", ["values"],
         {"bundle": bundle({"wh": ["erp.inventory.view"]}, {"wh": {"default_level": "all"}}),
          "claims": claims(["wh"]), "key": "erp.inventory.view", "resource_type": BALANCE,
          "row": row("b1", warehouse="S")},
         {"scope_params.s_dims": {"warehouse": {"all": False, "ids": []}}, "decision.visible": False}),
    case("values-other-role-not-counted", "Values of a role that does not grant the key do not count", ["values"],
         {"bundle": bundle({"viewer": ["erp.finance.view"], "poster": ["erp.finance.post"]},
                           {"viewer": {"values": {"legal_entity": ["le1"]}},
                            "poster": {"values": {"legal_entity": ["le2"]}}}),
          "claims": claims(["viewer", "poster"]), "key": "erp.finance.view", "resource_type": ENTRY,
          "row": row("e1", legal_entity="le2")},
         {"scope_params.s_dims": {"legal_entity": {"all": False, "ids": ["le1"]}}, "decision.visible": False}),

    # ---- E8 shares and relations ----------------------------------------
    case("share-viewer-without-role-key", "A viewer share makes one record visible without a role key", ["sharing"],
         {"bundle": bundle({"other": ["erp.inventory.view"]}),
          "claims": claims(["other"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1"), "acl": [acl("erp.sales.order", "o1", "viewer", "user:u_me")]},
         {"has_key": False, "scope_params.s_acl": True, "scope_params.s_relations": ["editor", "viewer"],
          "decision.visible": True, "decision.allowed": True}),
    case("share-capability-off", "sharing false: the projection is not consulted", ["sharing", "degrade"],
         {"bundle": bundle({"other": ["erp.inventory.view"]}, caps=caps(sharing=False)),
          "claims": claims(["other"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1"), "acl": [acl("erp.sales.order", "o1", "viewer", "user:u_me")]},
         {"scope_params.s_acl": False, "decision.visible": False}),
    case("share-expired", "An expired share no longer counts", ["sharing", "window"],
         {"bundle": bundle({}),
          "claims": claims([]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1"), "acl": [acl("erp.sales.order", "o1", "viewer", "user:u_me", "2025-10-09T08:53:20Z")]},
         {"decision.visible": False}),
    case("share-not-yet-expired", "A share before its expiry counts", ["sharing", "window"],
         {"bundle": bundle({}),
          "claims": claims([]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1"), "acl": [acl("erp.sales.order", "o1", "viewer", "user:u_me", "2025-10-09T08:53:21Z")]},
         {"decision.visible": True}),
    case("share-to-department-tree", "A share to dept_tree of an ancestor reaches a member of a sub-department", ["sharing"],
         {"bundle": bundle({}),
          "claims": claims([]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="/4/"), "acl": [acl("erp.sales.order", "o1", "viewer", "dept_tree:/1/")]},
         {"scope_params.s_subjects": ["dept:/1/12/", "dept_tree:/", "dept_tree:/1/", "dept_tree:/1/12/", "user:u_me"],
          "decision.visible": True}),
    case("share-to-department-exact", "A share to dept of a parent does not reach a sub-department", ["sharing"],
         {"bundle": bundle({}),
          "claims": claims([]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1", dept="/4/"), "acl": [acl("erp.sales.order", "o1", "viewer", "dept:/1/")]},
         {"decision.visible": False}),
    case("share-to-role", "A share to a role reaches its holders", ["sharing"],
         {"bundle": bundle({"auditor": []}),
          "claims": claims(["auditor"]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1"), "acl": [acl("erp.sales.order", "o1", "viewer", "role:auditor")]},
         {"decision.visible": True}),
    case("share-editor-grants-ship", "An editor share gives ship on that record", ["sharing"],
         {"bundle": bundle({}),
          "claims": claims([]), "key": "erp.sales.ship", "resource_type": ORDER,
          "row": row("o1"), "acl": [acl("erp.sales.order", "o1", "editor", "user:u_me")]},
         {"scope_params.s_relations": ["editor"], "decision.allowed": True}),
    case("share-viewer-not-ship", "A viewer share does not give ship", ["sharing"],
         {"bundle": bundle({}),
          "claims": claims([]), "key": "erp.sales.ship", "resource_type": ORDER,
          "row": row("o1"), "acl": [acl("erp.sales.order", "o1", "viewer", "user:u_me")]},
         {"decision.visible": True, "decision.allowed": False, "decision.reason": "MISSING_PERMISSION"}),
    case("share-other-record", "A share on another record does not count", ["sharing"],
         {"bundle": bundle({}),
          "claims": claims([]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1"), "acl": [acl("erp.sales.order", "o2", "viewer", "user:u_me")]},
         {"decision.visible": False}),
    case("component-relation-member", "A component-owned member relation gives edit", ["relation_sync"],
         {"bundle": bundle({}),
          "claims": claims([]), "key": "crm.opportunity.edit", "resource_type": OPPORTUNITY,
          "row": row("p1"), "acl": [acl("crm.opportunity.opportunity", "p1", "member", "user:u_me")]},
         {"scope_params.s_relations": ["member"], "decision.allowed": True}),
    case("component-relation-sync-off", "relation_sync false: component-owned relations do not count, shares still do", ["relation_sync", "degrade"],
         {"bundle": bundle({}, caps=caps(relation_sync=False)),
          "claims": claims([]), "key": "crm.opportunity.view", "resource_type": OPPORTUNITY,
          "row": row("p1"), "acl": [acl("crm.opportunity.opportunity", "p1", "member", "user:u_me")]},
         {"scope_params.s_relations": ["viewer"], "decision.visible": False}),

    # ---- E8/E5 on_behalf delegation -------------------------------------
    case("on-behalf-covers-key", "B handles A's tasks for a delegated key without holding it", ["delegation"],
         {"bundle": bundle({}, delegations=[{"id": "dg_1", "mode": "on_behalf", "from": "u_a", "to": "u_me",
                                             "keys": ["infra.workflow.task.view", "infra.workflow.task.act"],
                                             "from_ts": NOW - 100, "until": NOW + 100}]),
          "claims": claims([]), "key": "infra.workflow.task.act", "resource_type": TASK,
          "row": row("t1", owner="u_a")},
         {"has_key": True, "level": "none", "scope_params.s_owners": ["u_a"],
          "decision.visible": True, "decision.allowed": True}),
    case("on-behalf-plus-own-role", "A delegate who holds the key keeps their own scope too", ["delegation"],
         {"bundle": bundle({"clerk": ["infra.workflow.task.view"]},
                           delegations=[{"id": "dg_1", "mode": "on_behalf", "from": "u_a", "to": "u_me",
                                         "keys": ["infra.workflow.task.view"]}]),
          "claims": claims(["clerk"]), "key": "infra.workflow.task.view", "resource_type": TASK,
          "row": row("t1", owner="u_me")},
         {"scope_params.s_owners": ["u_a", "u_me"], "decision.visible": True}),
    case("on-behalf-expired", "An expired delegation is not expanded", ["delegation", "window"],
         {"bundle": bundle({}, delegations=[{"id": "dg_1", "mode": "on_behalf", "from": "u_a", "to": "u_me",
                                             "keys": ["infra.workflow.task.view"], "until": NOW - 1}]),
          "claims": claims([]), "key": "infra.workflow.task.view", "resource_type": TASK,
          "row": row("t1", owner="u_a")},
         {"has_key": False, "decision.visible": False}),
    case("on-behalf-other-key", "A delegation of another key is not expanded", ["delegation"],
         {"bundle": bundle({}, delegations=[{"id": "dg_1", "mode": "on_behalf", "from": "u_a", "to": "u_me",
                                             "keys": ["infra.workflow.task.act"]}]),
          "claims": claims([]), "key": "infra.workflow.task.view", "resource_type": TASK,
          "row": row("t1", owner="u_a")},
         {"has_key": False, "decision.visible": False}),
    case("on-behalf-capability-off", "delegation false: on_behalf entries are ignored", ["delegation", "degrade"],
         {"bundle": bundle({}, caps=caps(delegation=False),
                           delegations=[{"id": "dg_1", "mode": "on_behalf", "from": "u_a", "to": "u_me",
                                         "keys": ["infra.workflow.task.view"]}]),
          "claims": claims([]), "key": "infra.workflow.task.view", "resource_type": TASK,
          "row": row("t1", owner="u_a")},
         {"has_key": False, "decision.visible": False}),
    case("on-behalf-share-to-delegator", "A share to the delegator reaches the delegate for the delegated key", ["delegation", "sharing"],
         {"bundle": bundle({}, delegations=[{"id": "dg_1", "mode": "on_behalf", "from": "u_a", "to": "u_me",
                                             "keys": ["erp.sales.view"]}]),
          "claims": claims([]), "key": "erp.sales.view", "resource_type": ORDER,
          "row": row("o1"), "acl": [acl("erp.sales.order", "o1", "viewer", "user:u_a")]},
         {"decision.visible": True}),

    # ---- E4 ceilings ----------------------------------------------------
    case("ceiling-caps-level-and-keys", "A ceiling caps the level and removes keys it does not list", ["ceiling", "delegation"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"default_level": "all"}},
                           caps=caps(impersonation=True),
                           profiles={"view_ro": {"keys": ["erp.sales.view"], "max_level": "subtree", "relations": ["viewer"]}}),
          "claims": claims(["rep"], act={"sub": "u_admin", "kind": "user"}, ceil=["view_ro"], dg="dg_5"),
          "key": "erp.sales.view", "resource_type": ORDER, "row": row("o1", dept="/2/")},
         {"level": "subtree", "scope_params.s_all": False, "scope_params.s_relations": ["viewer"],
          "decision.visible": False}),
    case("ceiling-blocks-action", "A key outside the ceiling is refused even though a role grants it", ["ceiling", "delegation"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"default_level": "all"}},
                           caps=caps(impersonation=True),
                           profiles={"view_ro": {"keys": ["erp.sales.view"], "max_level": "all", "relations": ["viewer"]}}),
          "claims": claims(["rep"], act={"sub": "u_admin", "kind": "user"}, ceil=["view_ro"], dg="dg_5"),
          "key": "erp.sales.cancel", "resource_type": ORDER, "row": row("o1")},
         {"has_key": False, "decision.visible": True, "decision.allowed": False,
          "decision.reason": "MISSING_PERMISSION"}),
    case("ceiling-unknown-profile", "An unknown ceiling profile allows nothing", ["ceiling", "delegation"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"default_level": "all"}}),
          "claims": claims(["rep"], ceil=["ghost"], dg="dg_6"),
          "key": "erp.sales.view", "resource_type": ORDER, "row": row("o1", owner="u_me")},
         {"has_key": False, "decision.visible": False}),
    case("ceiling-drops-org-values", "A ceiling below subtree drops custom department subtrees", ["ceiling", "values"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"values": {"org": ["/1/3/", "*"]}}},
                           profiles={"own_only": {"keys": ["erp.sales.view"], "max_level": "own", "relations": []}}),
          "claims": claims(["rep"], ceil=["own_only"], dg="dg_7"),
          "key": "erp.sales.view", "resource_type": ORDER, "row": row("o1", dept="/1/3/")},
         {"scope_params.s_all": False, "scope_params.s_dept_prefix": [], "decision.visible": False}),
    case("agent-shape-when-enabled", "Shape lock (A4): with agents true an agent token is evaluated under its ceiling", ["agents", "ceiling"],
         {"bundle": bundle(SALES_ROLES, {"rep": {"levels": {"erp.sales.view": "subtree"}}},
                           caps=caps(agents=True),
                           profiles={"agent_sales_ro": {"keys": ["erp.sales.view"], "max_level": "own", "relations": ["viewer"], "fields": []}}),
          "claims": claims(["rep"], act={"sub": "agent_1", "kind": "agent"}, ceil=["agent_sales_ro"], dg="dg_8"),
          "key": "erp.sales.view", "resource_type": ORDER, "row": row("o1", owner="u_me")},
         {"token": "OK", "level": "own", "decision.visible": True}),

    # ---- E11 fields -----------------------------------------------------
    case("fields-masked-and-read-only", "No read key masks the set; read without edit makes it read-only", ["fields"],
         {"bundle": bundle({"rep": ["erp.sales.view", "erp.sales.pricing.read"]}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER},
         {"fields": {"masked": [], "read_only": ["discount", "unit_price"]}}),
    case("fields-masked", "Without the read key every column of the set is masked", ["fields"],
         {"bundle": bundle({"rep": ["erp.sales.view"]}),
          "claims": claims(["rep"]), "key": "erp.sales.view", "resource_type": ORDER},
         {"fields": {"masked": ["discount", "unit_price"], "read_only": []}}),
    case("fields-ceiling", "A ceiling without the field key masks the field", ["fields", "ceiling"],
         {"bundle": bundle({"rep": ["erp.sales.view", "erp.sales.pricing.read", "erp.sales.pricing.edit"]},
                           profiles={"ro": {"keys": ["erp.sales.view"], "fields": [], "max_level": "own", "relations": []}}),
          "claims": claims(["rep"], ceil=["ro"], dg="dg_3"), "key": "erp.sales.view", "resource_type": ORDER},
         {"fields": {"masked": ["discount", "unit_price"], "read_only": []}}),

    # ---- E9 graph -------------------------------------------------------
    case("graph-capability-off", "A graph type on a member without graph: ids empty, degraded", ["graph", "degrade"],
         {"bundle": bundle({}),
          "claims": claims([]), "key": "prj.project.view", "resource_type": FOLDER,
          "row": row("f1"), "graph_ids": ["f1"]},
         {"degraded": ["graph"], "scope_params.s_graph_ids": [], "decision.visible": False}),
    case("graph-capability-on", "A graph type on a member with graph: ListObjects ids make records visible", ["graph"],
         {"bundle": bundle({}, caps=caps(graph=True)),
          "claims": claims([]), "key": "prj.project.view", "resource_type": FOLDER,
          "row": row("f1"), "graph_ids": ["f2", "f1"]},
         {"degraded": [], "scope_params.s_graph_ids": ["f1", "f2"], "decision.visible": True}),

    # ---- E10 explain under R62 ------------------------------------------
    case("explain-invisible-hides-attributes", "Explain of an invisible record never reveals its dimension values", ["explain", "r62"],
         {"bundle": bundle({"wh": ["erp.inventory.view"]}, {"wh": {"values": {"warehouse": ["S"]}}}),
          "claims": claims(["wh"]), "key": "erp.inventory.view", "resource_type": BALANCE,
          "row": row("b1", warehouse="SECRET")},
         {"decision.visible": False, "explain.missing": [{"kind": "dimension", "source": "warehouse", "detail": ""}]}),
]
