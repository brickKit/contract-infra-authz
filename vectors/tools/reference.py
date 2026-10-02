"""Reference evaluator of EVALUATION.md (authz/2.0).

Pure functions, standard library only. The decision vectors in
vectors/decision/ are computed by this module (generate.py) and recomputed by
an independent Go implementation (crosscheck/) that shares no code with it.
Section numbers (E1..E12) refer to EVALUATION.md.
"""

import re
from datetime import datetime

LEVELS = ["own", "dept", "subtree", "all"]
RANK = {name: i for i, name in enumerate(LEVELS)}
CONTRACT_RE = re.compile(r"^authz/2\.(0|[1-9][0-9]*)$")
DEPT_RE = re.compile(r"^/([^/]+/)*$")
IDENTITY_DIMS = ("owner", "org")
STALE_SKEW = 5


def _unix(instant):
    return int(datetime.fromisoformat(instant.replace("Z", "+00:00")).timestamp())


def _active(window, now):
    """E3: [from_ts, until), unix seconds, both optional."""
    if window is None:
        return True
    start = window.get("from_ts")
    end = window.get("until")
    if start is not None and now < start:
        return False
    if end is not None and now >= end:
        return False
    return True


def valid_dept(path):
    return isinstance(path, str) and DEPT_RE.match(path) is not None


def like_prefix(path):
    """E6: escape \\, % and _ with a backslash, then append %."""
    out = path.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return out + "%"


def like_match(value, pattern):
    """SQL LIKE with backslash escape, for the List/Can self-check."""
    rx = ""
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            rx += re.escape(pattern[i + 1])
            i += 2
            continue
        if c == "%":
            rx += ".*"
        elif c == "_":
            rx += "."
        else:
            rx += re.escape(c)
        i += 1
    return re.fullmatch(rx, value, re.DOTALL) is not None


def ancestors(path):
    """'/1/12/' -> ['/', '/1/', '/1/12/']."""
    parts = [p for p in path.split("/") if p]
    out = ["/"]
    acc = "/"
    for p in parts:
        acc = acc + p + "/"
        out.append(acc)
    return out


def check_token(bundle, claims, now):
    """E2: returns 'OK' or the reason the token is refused."""
    caps = bundle.get("capabilities", {})
    sub = claims["sub"]
    since = bundle.get("stale_since", {}).get(sub)
    if since is not None and claims["iat"] < since - STALE_SKEW:
        return "TOKEN_STALE"
    dg = claims.get("dg") or ""
    if dg and dg in bundle.get("revoked_grants", {}):
        return "TOKEN_STALE"
    act = claims.get("act")
    delegated = bool(act) or bool(claims.get("ceil")) or bool(dg)
    if delegated and caps.get("delegation") is not True:
        return "UNSUPPORTED_DELEGATION"
    while act:
        kind = act.get("kind")
        if kind == "agent":
            if caps.get("agents") is not True:
                return "UNSUPPORTED_DELEGATION"
        elif kind == "user":
            if caps.get("impersonation") is not True:
                return "UNSUPPORTED_DELEGATION"
        elif kind != "svc":
            return "UNSUPPORTED_DELEGATION"
        act = act.get("act")
    return "OK"


class Evaluator:
    """One principal against one bundle at one instant."""

    def __init__(self, bundle, claims, now):
        self.b = bundle
        self.c = claims
        self.now = now
        self.caps = bundle.get("capabilities", {})
        grants = bundle.get("grants", {})
        # E3: a role whose grant window is closed contributes nothing.
        self.active_roles = sorted({r for r in claims.get("roles", [])
                                    if _active(grants.get(r), now)})
        # E4: ceilings; an unknown code is an empty profile.
        empty = {"keys": [], "fields": [], "max_level": "own", "relations": []}
        self.ceil = [(code, bundle.get("profiles", {}).get(code, empty))
                     for code in sorted(set(claims.get("ceil", [])))]
        dp = claims.get("dept_path", "")
        self.dept = dp if valid_dept(dp) else ""

    # E4
    def ceiling_allows(self, key):
        return all(key in p.get("keys", []) or key in p.get("fields", [])
                   for _, p in self.ceil)

    def ceilings_blocking(self, key):
        return [code for code, p in self.ceil
                if not (key in p.get("keys", []) or key in p.get("fields", []))]

    # E5
    def role_holders(self, key):
        roles = self.b.get("roles", {})
        return [r for r in self.active_roles if key in roles.get(r, [])]

    def on_behalf(self, key):
        if self.caps.get("delegation") is not True:
            return []
        out = [d for d in self.b.get("delegations", [])
               if d.get("mode") == "on_behalf" and d.get("to") == self.c["sub"]
               and key in d.get("keys", []) and _active(d, self.now)]
        return sorted(out, key=lambda d: d["id"])

    def has(self, key):
        return bool(self.role_holders(key) or self.on_behalf(key)) and self.ceiling_allows(key)

    # E6
    def role_level(self, role, key):
        g = self.b.get("grants", {}).get(role, {})
        return g.get("levels", {}).get(key) or g.get("default_level") or "own"

    def level(self, key):
        holders = self.role_holders(key)
        if not holders or not self.ceiling_allows(key):
            return "none", None
        best = max(RANK[self.role_level(r, key)] for r in holders)
        best_role = sorted(r for r in holders if RANK[self.role_level(r, key)] == best)[0]
        for _, p in self.ceil:
            best = min(best, RANK[p.get("max_level", "own")])
        return LEVELS[best], best_role

    def values(self, key, dim):
        if not self.ceiling_allows(key):
            return set()
        out = set()
        for r in self.role_holders(key):
            out.update(self.b.get("grants", {}).get(r, {}).get("values", {}).get(dim, []))
        return out

    # E8
    def subjects(self, key):
        s = {"user:" + self.c["sub"]}
        s.update("role:" + r for r in self.active_roles)
        if self.dept:
            s.add("dept:" + self.dept)
            s.update("dept_tree:" + a for a in ancestors(self.dept))
        s.update("user:" + d["from"] for d in self.on_behalf(key))
        return sorted(s)

    def relations_for(self, rtype, key):
        rels = rtype.get("relations", {})

        def closure(name, seen):
            if name in seen:
                return set()
            seen.add(name)
            spec = rels.get(name, {})
            out = set(spec.get("grants", []))
            for inc in spec.get("includes", []):
                out |= closure(inc, seen)
            return out

        out = []
        for name, spec in rels.items():
            if spec.get("owned_by", "authz") == "component":
                if self.caps.get("relation_sync") is not True:
                    continue
            elif self.caps.get("sharing") is not True:
                continue
            if key in closure(name, set()):
                out.append(name)
        for _, p in self.ceil:
            out = [r for r in out if r in p.get("relations", [])]
        return sorted(out)

    def scope_params(self, rtype, key, graph_ids):
        lvl, _ = self.level(key)
        held = lvl != "none"
        delegs = self.on_behalf(key) if self.ceiling_allows(key) else []
        org = self.values(key, "org")
        prefixes = set()
        exact = set()
        owners = set()
        if held:
            owners.add(self.c["sub"])
            if lvl == "dept" and self.dept:
                exact.add(self.dept)
            if lvl == "subtree" and self.dept:
                prefixes.add(like_prefix(self.dept))
        owners.update(d["from"] for d in delegs)
        # E6: org values behave as subtree (paths) and all (*); a ceiling
        # below that level drops them.
        cap = min([RANK[p.get("max_level", "own")] for _, p in self.ceil] or [RANK["all"]])
        if cap < RANK["all"]:
            org.discard("*")
        if cap < RANK["subtree"]:
            org = {o for o in org if o == "*"}
        for o in org:
            if o != "*" and valid_dept(o):
                prefixes.add(like_prefix(o))
        dims = {}
        for d in rtype.get("dimensions", []):
            if d in IDENTITY_DIMS:
                continue
            v = self.values(key, d)
            dims[d] = {"all": "*" in v, "ids": sorted(v - {"*"})}
        rels = self.relations_for(rtype, key) if self.ceiling_allows(key) else []
        degraded = []
        gids = []
        if rtype.get("derivation") == "graph":
            if self.caps.get("graph") is True:
                gids = sorted(set(graph_ids or [])) if self.ceiling_allows(key) else []
            else:
                degraded.append("graph")
        params = {
            "s_all": held and (lvl == "all" or "*" in org),
            "s_owners": sorted(owners),
            "s_dept_exact": sorted(exact),
            "s_dept_prefix": sorted(prefixes),
            "s_dims": dims,
            "s_acl": bool(rels),
            "s_relations": rels,
            "s_subjects": self.subjects(key),
            "s_graph_ids": gids,
        }
        return params, degraded

    # E9
    def branches(self, rtype, key, row, acl, graph_ids):
        p, _ = self.scope_params(rtype, key, graph_ids)
        dims = rtype.get("dimensions", [])
        has_rule = bool(self.role_holders(key) or self.on_behalf(key)) and self.ceiling_allows(key)
        ident_dims = [d for d in dims if d in IDENTITY_DIMS]
        if not ident_dims:
            ident_ok = True
        else:
            ident_ok = p["s_all"]
            if "owner" in ident_dims and row.get("owner") in p["s_owners"]:
                ident_ok = True
            rdp = row.get("dept_path", "")
            if "org" in ident_dims and (rdp in p["s_dept_exact"]
                                        or any(like_match(rdp, x) for x in p["s_dept_prefix"])):
                ident_ok = True
        failing_dims = []
        for d, v in p["s_dims"].items():
            if not (v["all"] or row.get("values", {}).get(d) in v["ids"]):
                failing_dims.append(d)
        rule = has_rule and ident_ok and not failing_dims
        matches = []
        if p["s_acl"]:
            for a in acl:
                if (a["rtype"] == rtype["type"] and a["rid"] == row["id"]
                        and a["relation"] in p["s_relations"]
                        and a["subject"] in p["s_subjects"]
                        and (a.get("expires_at") is None or _unix(a["expires_at"]) > self.now)):
                    matches.append(a)
        graph = row["id"] in p["s_graph_ids"]
        return {
            "params": p, "has_rule": has_rule, "ident_ok": ident_ok,
            "failing_dims": failing_dims, "rule": rule, "acl": matches,
            "graph": graph, "visible": rule or bool(matches) or graph,
        }


def _reason(kind, source, detail):
    return {"kind": kind, "source": source, "detail": detail}


def _sorted_reasons(items):
    uniq = {(r["kind"], r["source"], r["detail"]): r for r in items}
    return [uniq[k] for k in sorted(uniq)]


def explain(ev, rtype, key, row, k_br, visible):
    """E10: the facts behind the decision for key on row."""
    reasons, missing = [], []
    rels = rtype.get("relations", {})
    ident = [d for d in rtype.get("dimensions", []) if d in IDENTITY_DIMS]
    if k_br["visible"]:
        if k_br["rule"]:
            holders = ev.role_holders(key)
            for r in holders:
                reasons.append(_reason("role_key", r, key))
            lvl, best = ev.level(key)
            if ident and best is not None:
                reasons.append(_reason("level", best, lvl))
            for d in k_br["params"]["s_dims"]:
                reasons.append(_reason("dimension", d, row.get("values", {}).get(d, "")))
            for d in ev.on_behalf(key):
                if row.get("owner") == d["from"]:
                    reasons.append(_reason("delegation", d["id"], d["from"]))
            for code, _ in ev.ceil:
                reasons.append(_reason("ceiling", code, key))
        for a in k_br["acl"]:
            owned = rels.get(a["relation"], {}).get("owned_by", "authz")
            reasons.append(_reason("relation" if owned == "component" else "share",
                                   a["relation"], a["subject"]))
        if k_br["graph"]:
            reasons.append(_reason("relation", "graph", row["id"]))
        return _sorted_reasons(reasons), []
    blocking = ev.ceilings_blocking(key)
    if blocking:
        for code in blocking:
            missing.append(_reason("ceiling", code, key))
    elif not k_br["has_rule"]:
        missing.append(_reason("role_key", "", key))
    else:
        if ident and not k_br["ident_ok"]:
            lvl, _ = ev.level(key)
            missing.append(_reason("level", "", lvl))
        for d in k_br["failing_dims"]:
            # R62: never reveal an attribute of a record the caller cannot see.
            missing.append(_reason("dimension", d, row.get("values", {}).get(d, "") if visible else ""))
    for name, spec in rels.items():
        cap = "relation_sync" if spec.get("owned_by", "authz") == "component" else "sharing"
        if ev.caps.get(cap) is not True and key in _grants_closure(rels, name):
            missing.append(_reason("capability", cap, ""))
    if rtype.get("derivation") == "graph" and ev.caps.get("graph") is not True:
        missing.append(_reason("capability", "graph", ""))
    return [], _sorted_reasons(missing)


def _grants_closure(rels, name, seen=None):
    seen = seen or set()
    if name in seen:
        return set()
    seen.add(name)
    spec = rels.get(name, {})
    out = set(spec.get("grants", []))
    for inc in spec.get("includes", []):
        out |= _grants_closure(rels, inc, seen)
    return out


def evaluate(inp):
    """E1..E12 for one vector input; returns the expected object."""
    bundle = inp["bundle"]
    if not isinstance(bundle.get("contract"), str) or not CONTRACT_RE.match(bundle["contract"]):
        return {"bundle": "refused"}
    out = {"bundle": "accepted"}
    claims, now, key = inp["claims"], inp["now"], inp["key"]
    tok = check_token(bundle, claims, now)
    out["token"] = tok
    if tok != "OK":
        return out
    ev = Evaluator(bundle, claims, now)
    rtype = inp["resource_type"]
    lvl, _ = ev.level(key)
    out["has_key"] = ev.has(key)
    out["level"] = lvl
    params, degraded = ev.scope_params(rtype, key, inp.get("graph_ids"))
    out["scope_params"] = params
    out["degraded"] = degraded
    if rtype.get("fields"):
        masked, read_only = set(), set()
        for f in rtype["fields"]:
            if not ev.has(f["read"]):
                masked.update(f["columns"])
            elif not f.get("edit") or not ev.has(f["edit"]):
                read_only.update(f["columns"])
        out["fields"] = {"masked": sorted(masked), "read_only": sorted(read_only - masked)}
    row = inp.get("row")
    if row is not None:
        acl = inp.get("acl", [])
        gids = inp.get("graph_ids")
        view = ev.branches(rtype, rtype["view_key"], row, acl, gids)
        k_br = view if key == rtype["view_key"] else ev.branches(rtype, key, row, acl, gids)
        visible = view["visible"]
        allowed = visible and k_br["visible"]
        if not visible:
            reason = "NOT_FOUND"
        elif allowed:
            reason = ""
        elif ev.has(key):
            reason = "OUT_OF_SCOPE"
        else:
            reason = "MISSING_PERMISSION"
        out["decision"] = {"visible": visible, "allowed": allowed, "reason": reason}
        reasons, missing = explain(ev, rtype, key, row, k_br, visible)
        out["explain"] = {"reasons": reasons, "missing": missing}
    return out
