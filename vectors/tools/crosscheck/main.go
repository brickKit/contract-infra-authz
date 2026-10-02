// Command crosscheck recomputes every decision vector from EVALUATION.md
// with no code shared with the Python reference, and checks two properties
// the reference cannot check on itself:
//
//   - every expected member equals the recomputed one;
//   - List/Can consistency: for the route key and the view key, the
//     canonical SQL predicate evaluated on the parameters (with a LIKE
//     engine) gives the same answer as the single-record rule evaluated on
//     path semantics (no LIKE at all).
//
// Usage: go run . <vectors/decision directory>
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"strings"
	"time"
)

type obj = map[string]any

var (
	contractRe = regexp.MustCompile(`^authz/2\.(0|[1-9][0-9]*)$`)
	deptRe     = regexp.MustCompile(`^/([^/]+/)*$`)
	levelRank  = map[string]int{"own": 0, "dept": 1, "subtree": 2, "all": 3}
	levelName  = []string{"own", "dept", "subtree", "all"}
)

func m(v any) obj {
	if o, ok := v.(obj); ok {
		return o
	}
	return obj{}
}

func strs(v any) []string {
	arr, _ := v.([]any)
	out := make([]string, 0, len(arr))
	for _, x := range arr {
		if s, ok := x.(string); ok {
			out = append(out, s)
		}
	}
	return out
}

func str(v any) string { s, _ := v.(string); return s }

func num(v any) (int64, bool) {
	f, ok := v.(float64)
	return int64(f), ok
}

func truthy(v any) bool { b, ok := v.(bool); return ok && b }

type set map[string]bool

func (s set) add(xs ...string) {
	for _, x := range xs {
		s[x] = true
	}
}

func (s set) list() []string {
	out := make([]string, 0, len(s))
	for k := range s {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func contains(xs []string, x string) bool {
	for _, y := range xs {
		if y == x {
			return true
		}
	}
	return false
}

// inWindow implements E3 for an object with optional from_ts / until.
func inWindow(o obj, now int64) bool {
	if f, ok := num(o["from_ts"]); ok && now < f {
		return false
	}
	if u, ok := num(o["until"]); ok && now >= u {
		return false
	}
	return true
}

type principal struct {
	bundle, caps, claims obj
	now                  int64
	sub, dept            string
	roles                []string // active roles, E3
	ceilings             []obj
	ceilCodes            []string
}

func newPrincipal(bundle, claims obj, now int64) *principal {
	p := &principal{bundle: bundle, caps: m(bundle["capabilities"]), claims: claims, now: now}
	p.sub = str(claims["sub"])
	if d := str(claims["dept_path"]); deptRe.MatchString(d) {
		p.dept = d
	}
	grants := m(bundle["grants"])
	rs := set{}
	for _, r := range strs(claims["roles"]) {
		g, ok := grants[r].(obj)
		if !ok || inWindow(g, now) {
			rs.add(r)
		}
	}
	p.roles = rs.list()
	codes := set{}
	codes.add(strs(claims["ceil"])...)
	p.ceilCodes = codes.list()
	for _, c := range p.ceilCodes {
		prof, ok := m(bundle["profiles"])[c].(obj)
		if !ok {
			prof = obj{"keys": []any{}, "max_level": "own", "relations": []any{}}
		}
		p.ceilings = append(p.ceilings, prof)
	}
	return p
}

func (p *principal) cap(name string) bool { return truthy(p.caps[name]) }

func (p *principal) allows(k string) bool {
	for _, c := range p.ceilings {
		if !contains(strs(c["keys"]), k) && !contains(strs(c["fields"]), k) {
			return false
		}
	}
	return true
}

func (p *principal) holders(k string) []string {
	var out []string
	for _, r := range p.roles {
		if contains(strs(m(p.bundle["roles"])[r]), k) {
			out = append(out, r)
		}
	}
	return out
}

func (p *principal) delegations(k string) []obj {
	if !p.cap("delegation") {
		return nil
	}
	var out []obj
	arr, _ := p.bundle["delegations"].([]any)
	for _, x := range arr {
		d := m(x)
		if str(d["mode"]) == "on_behalf" && str(d["to"]) == p.sub && contains(strs(d["keys"]), k) && inWindow(d, p.now) {
			out = append(out, d)
		}
	}
	sort.Slice(out, func(i, j int) bool { return str(out[i]["id"]) < str(out[j]["id"]) })
	return out
}

func (p *principal) has(k string) bool {
	return (len(p.holders(k)) > 0 || len(p.delegations(k)) > 0) && p.allows(k)
}

func (p *principal) grant(r string) obj { return m(m(p.bundle["grants"])[r]) }

func (p *principal) roleLevel(r, k string) string {
	g := p.grant(r)
	if l := str(m(g["levels"])[k]); l != "" {
		return l
	}
	if l := str(g["default_level"]); l != "" {
		return l
	}
	return "own"
}

func (p *principal) capRank() int {
	c := 3
	for _, prof := range p.ceilings {
		l := str(prof["max_level"])
		if l == "" {
			l = "own"
		}
		if levelRank[l] < c {
			c = levelRank[l]
		}
	}
	return c
}

// level returns E6's level and the first holder with the highest uncapped level.
func (p *principal) level(k string) (string, string) {
	hs := p.holders(k)
	if len(hs) == 0 || !p.allows(k) {
		return "none", ""
	}
	best, bestRole := -1, ""
	for _, r := range hs { // hs is sorted, so the first maximum is the smallest code
		if l := levelRank[p.roleLevel(r, k)]; l > best {
			best, bestRole = l, r
		}
	}
	if c := p.capRank(); c < best {
		best = c
	}
	return levelName[best], bestRole
}

func (p *principal) dimValues(k, dim string) set {
	out := set{}
	if !p.allows(k) {
		return out
	}
	for _, r := range p.holders(k) {
		out.add(strs(m(p.grant(r)["values"])[dim])...)
	}
	return out
}

func (p *principal) orgValues(k string) (paths []string, star bool) {
	v := p.dimValues(k, "org")
	c := p.capRank()
	for x := range v {
		switch {
		case x == "*":
			star = c >= 3
		case deptRe.MatchString(x) && c >= 2:
			paths = append(paths, x)
		}
	}
	sort.Strings(paths)
	return
}

func escapeLike(s string) string {
	r := strings.NewReplacer(`\`, `\\`, `%`, `\%`, `_`, `\_`)
	return r.Replace(s) + "%"
}

// likeMatch is an iterative SQL LIKE with backslash escape.
func likeMatch(s, pat string) bool {
	type tok struct {
		lit  rune
		kind byte // 'l' literal, '%' any run, '_' any one
	}
	var toks []tok
	pr := []rune(pat)
	for i := 0; i < len(pr); i++ {
		switch {
		case pr[i] == '\\' && i+1 < len(pr):
			i++
			toks = append(toks, tok{pr[i], 'l'})
		case pr[i] == '%':
			toks = append(toks, tok{0, '%'})
		case pr[i] == '_':
			toks = append(toks, tok{0, '_'})
		default:
			toks = append(toks, tok{pr[i], 'l'})
		}
	}
	sr := []rune(s)
	// dp[j] = tokens[:i] match s[:j]
	dp := make([]bool, len(sr)+1)
	dp[0] = true
	for _, t := range toks {
		next := make([]bool, len(sr)+1)
		for j := 0; j <= len(sr); j++ {
			switch t.kind {
			case '%':
				next[j] = dp[j] || (j > 0 && next[j-1])
			case '_':
				next[j] = j > 0 && dp[j-1]
			default:
				next[j] = j > 0 && dp[j-1] && sr[j-1] == t.lit
			}
		}
		dp = next
	}
	return dp[len(sr)]
}

func ancestorsOf(dept string) []string {
	out := []string{"/"}
	acc := "/"
	for _, part := range strings.Split(strings.Trim(dept, "/"), "/") {
		if part == "" {
			continue
		}
		acc += part + "/"
		out = append(out, acc)
	}
	return out
}

func relationGives(rels obj, name, k string, seen set) bool {
	if seen[name] {
		return false
	}
	seen.add(name)
	spec := m(rels[name])
	if contains(strs(spec["grants"]), k) {
		return true
	}
	for _, inc := range strs(spec["includes"]) {
		if relationGives(rels, inc, k, seen) {
			return true
		}
	}
	return false
}

func relCapability(spec obj) string {
	if str(spec["owned_by"]) == "component" {
		return "relation_sync"
	}
	return "sharing"
}

type params struct {
	All        bool                `json:"s_all"`
	Owners     []string            `json:"s_owners"`
	DeptExact  []string            `json:"s_dept_exact"`
	DeptPrefix []string            `json:"s_dept_prefix"`
	Dims       map[string]dimParam `json:"s_dims"`
	ACL        bool                `json:"s_acl"`
	Relations  []string            `json:"s_relations"`
	Subjects   []string            `json:"s_subjects"`
	GraphIDs   []string            `json:"s_graph_ids"`
}

type dimParam struct {
	All bool     `json:"all"`
	IDs []string `json:"ids"`
}

func identityDim(d string) bool { return d == "owner" || d == "org" }

func (p *principal) params(t obj, k string, graphIDs []string) (params, []string) {
	lvl, _ := p.level(k)
	out := params{Dims: map[string]dimParam{}}
	owners, exact, prefix := set{}, set{}, set{}
	if lvl != "none" {
		owners.add(p.sub)
		if lvl == "dept" && p.dept != "" {
			exact.add(p.dept)
		}
		if lvl == "subtree" && p.dept != "" {
			prefix.add(escapeLike(p.dept))
		}
	}
	if p.allows(k) {
		for _, d := range p.delegations(k) {
			owners.add(str(d["from"]))
		}
	}
	paths, star := p.orgValues(k)
	for _, o := range paths {
		prefix.add(escapeLike(o))
	}
	out.All = lvl != "none" && (lvl == "all" || star)
	out.Owners, out.DeptExact, out.DeptPrefix = owners.list(), exact.list(), prefix.list()
	for _, d := range strs(t["dimensions"]) {
		if identityDim(d) {
			continue
		}
		v := p.dimValues(k, d)
		dp := dimParam{All: v["*"], IDs: []string{}}
		for x := range v {
			if x != "*" {
				dp.IDs = append(dp.IDs, x)
			}
		}
		sort.Strings(dp.IDs)
		out.Dims[d] = dp
	}
	rels := m(t["relations"])
	rs := []string{}
	if p.allows(k) {
		names := make([]string, 0, len(rels))
		for n := range rels {
			names = append(names, n)
		}
		sort.Strings(names)
		for _, n := range names {
			if !p.cap(relCapability(m(rels[n]))) || !relationGives(rels, n, k, set{}) {
				continue
			}
			ok := true
			for _, c := range p.ceilings {
				if !contains(strs(c["relations"]), n) {
					ok = false
				}
			}
			if ok {
				rs = append(rs, n)
			}
		}
	}
	out.Relations, out.ACL = rs, len(rs) > 0
	subj := set{}
	subj.add("user:" + p.sub)
	for _, r := range p.roles {
		subj.add("role:" + r)
	}
	if p.dept != "" {
		subj.add("dept:" + p.dept)
		for _, a := range ancestorsOf(p.dept) {
			subj.add("dept_tree:" + a)
		}
	}
	for _, d := range p.delegations(k) {
		subj.add("user:" + str(d["from"]))
	}
	out.Subjects = subj.list()
	out.GraphIDs = []string{}
	var degraded []string
	if str(t["derivation"]) == "graph" {
		if p.cap("graph") {
			if p.allows(k) {
				g := set{}
				g.add(graphIDs...)
				out.GraphIDs = g.list()
			}
		} else {
			degraded = append(degraded, "graph")
		}
	}
	if degraded == nil {
		degraded = []string{}
	}
	return out, degraded
}

func instant(s string) int64 {
	t, err := time.Parse(time.RFC3339, s)
	if err != nil {
		panic(err)
	}
	return t.Unix()
}

func aclCounts(a obj, now int64) bool {
	e, ok := a["expires_at"].(string)
	return !ok || instant(e) > now
}

// predicate evaluates the canonical list predicate on parameters (with LIKE).
func predicate(t obj, pr params, row obj, acl []obj, now int64, ruleAllowed bool) bool {
	dims := strs(t["dimensions"])
	rule := ruleAllowed
	if rule {
		ident := true
		var hasIdent bool
		for _, d := range dims {
			hasIdent = hasIdent || identityDim(d)
		}
		if hasIdent {
			ident = pr.All
			if contains(dims, "owner") && contains(pr.Owners, str(row["owner"])) {
				ident = true
			}
			if contains(dims, "org") {
				rd := str(row["dept_path"])
				if contains(pr.DeptExact, rd) {
					ident = true
				}
				for _, pat := range pr.DeptPrefix {
					if likeMatch(rd, pat) {
						ident = true
					}
				}
			}
		}
		for d, dp := range pr.Dims {
			if !(dp.All || contains(dp.IDs, str(m(row["values"])[d]))) {
				rule = false
			}
		}
		rule = rule && ident
	}
	aclHit := false
	if pr.ACL {
		for _, a := range acl {
			if str(a["rtype"]) == str(t["type"]) && str(a["rid"]) == str(row["id"]) &&
				contains(pr.Relations, str(a["relation"])) && contains(pr.Subjects, str(a["subject"])) && aclCounts(a, now) {
				aclHit = true
			}
		}
	}
	return rule || aclHit || contains(pr.GraphIDs, str(row["id"]))
}

type branch struct {
	hasRule, identOK, rule, graph, visible bool
	failing                                []string
	acl                                    []obj
}

// semantic evaluates E10 on path semantics, without the parameters' LIKE patterns.
func (p *principal) semantic(t obj, k string, row obj, acl []obj, graphIDs []string) branch {
	b := branch{}
	b.hasRule = p.has(k)
	dims := strs(t["dimensions"])
	lvl, _ := p.level(k)
	rd := str(row["dept_path"])
	inside := func(base string) bool { // rd is base or below it
		return deptRe.MatchString(rd) && strings.HasPrefix(rd, base)
	}
	hasIdent := contains(dims, "owner") || contains(dims, "org")
	if !hasIdent {
		b.identOK = true
	} else {
		_, star := p.orgValues(k)
		b.identOK = lvl == "all" || (lvl != "none" && star)
		if contains(dims, "owner") {
			if lvl != "none" && str(row["owner"]) == p.sub {
				b.identOK = true
			}
			if p.allows(k) {
				for _, d := range p.delegations(k) {
					if str(row["owner"]) == str(d["from"]) {
						b.identOK = true
					}
				}
			}
		}
		if contains(dims, "org") && p.dept != "" {
			if lvl == "dept" && rd == p.dept {
				b.identOK = true
			}
			if lvl == "subtree" && inside(p.dept) {
				b.identOK = true
			}
		}
		if contains(dims, "org") {
			paths, _ := p.orgValues(k)
			for _, o := range paths {
				if inside(o) {
					b.identOK = true
				}
			}
		}
	}
	for _, d := range dims {
		if identityDim(d) {
			continue
		}
		v := p.dimValues(k, d)
		if !(v["*"] || (str(m(row["values"])[d]) != "" && v[str(m(row["values"])[d])] && str(m(row["values"])[d]) != "*")) {
			b.failing = append(b.failing, d)
		}
	}
	sort.Strings(b.failing)
	b.rule = b.hasRule && b.identOK && len(b.failing) == 0
	pr, _ := p.params(t, k, graphIDs)
	for _, a := range acl {
		if !pr.ACL || str(a["rtype"]) != str(t["type"]) || str(a["rid"]) != str(row["id"]) || !aclCounts(a, p.now) {
			continue
		}
		if contains(pr.Relations, str(a["relation"])) && contains(pr.Subjects, str(a["subject"])) {
			b.acl = append(b.acl, a)
		}
	}
	b.graph = contains(pr.GraphIDs, str(row["id"]))
	b.visible = b.rule || len(b.acl) > 0 || b.graph
	return b
}

type fact struct {
	Kind   string `json:"kind"`
	Source string `json:"source"`
	Detail string `json:"detail"`
}

func sortFacts(fs []fact) []fact {
	seen := map[fact]bool{}
	out := []fact{}
	for _, f := range fs {
		if !seen[f] {
			seen[f] = true
			out = append(out, f)
		}
	}
	sort.Slice(out, func(i, j int) bool {
		a, b := out[i], out[j]
		if a.Kind != b.Kind {
			return a.Kind < b.Kind
		}
		if a.Source != b.Source {
			return a.Source < b.Source
		}
		return a.Detail < b.Detail
	})
	return out
}

func (p *principal) explain(t obj, k string, row obj, b branch, visible bool) ([]fact, []fact) {
	dims := strs(t["dimensions"])
	hasIdent := contains(dims, "owner") || contains(dims, "org")
	rels := m(t["relations"])
	var reasons, missing []fact
	if b.visible {
		if b.rule {
			for _, h := range p.holders(k) {
				reasons = append(reasons, fact{"role_key", h, k})
			}
			if lvl, best := p.level(k); hasIdent && best != "" {
				reasons = append(reasons, fact{"level", best, lvl})
			}
			for _, d := range dims {
				if !identityDim(d) {
					reasons = append(reasons, fact{"dimension", d, str(m(row["values"])[d])})
				}
			}
			for _, d := range p.delegations(k) {
				if str(d["from"]) == str(row["owner"]) {
					reasons = append(reasons, fact{"delegation", str(d["id"]), str(d["from"])})
				}
			}
			for _, c := range p.ceilCodes {
				reasons = append(reasons, fact{"ceiling", c, k})
			}
		}
		for _, a := range b.acl {
			kind := "share"
			if str(m(rels[str(a["relation"])])["owned_by"]) == "component" {
				kind = "relation"
			}
			reasons = append(reasons, fact{kind, str(a["relation"]), str(a["subject"])})
		}
		if b.graph {
			reasons = append(reasons, fact{"relation", "graph", str(row["id"])})
		}
		return sortFacts(reasons), []fact{}
	}
	blocked := false
	for i, c := range p.ceilings {
		if !contains(strs(c["keys"]), k) && !contains(strs(c["fields"]), k) {
			missing = append(missing, fact{"ceiling", p.ceilCodes[i], k})
			blocked = true
		}
	}
	if !blocked {
		if len(p.holders(k)) == 0 && len(p.delegations(k)) == 0 {
			missing = append(missing, fact{"role_key", "", k})
		} else {
			if hasIdent && !b.identOK {
				lvl, _ := p.level(k)
				missing = append(missing, fact{"level", "", lvl})
			}
			for _, d := range b.failing {
				detail := ""
				if visible {
					detail = str(m(row["values"])[d])
				}
				missing = append(missing, fact{"dimension", d, detail})
			}
		}
	}
	for n, spec := range rels {
		c := relCapability(m(spec))
		if !p.cap(c) && relationGives(rels, n, k, set{}) {
			missing = append(missing, fact{"capability", c, ""})
		}
	}
	if str(t["derivation"]) == "graph" && !p.cap("graph") {
		missing = append(missing, fact{"capability", "graph", ""})
	}
	return []fact{}, sortFacts(missing)
}

func tokenCheck(bundle, claims obj) string {
	caps := m(bundle["capabilities"])
	iat, _ := num(claims["iat"])
	if since, ok := num(m(bundle["stale_since"])[str(claims["sub"])]); ok && iat < since-5 {
		return "TOKEN_STALE"
	}
	dg := str(claims["dg"])
	if _, revoked := m(bundle["revoked_grants"])[dg]; dg != "" && revoked {
		return "TOKEN_STALE"
	}
	act, hasAct := claims["act"].(obj)
	if (hasAct || len(strs(claims["ceil"])) > 0 || dg != "") && !truthy(caps["delegation"]) {
		return "UNSUPPORTED_DELEGATION"
	}
	for hasAct {
		switch str(act["kind"]) {
		case "agent":
			if !truthy(caps["agents"]) {
				return "UNSUPPORTED_DELEGATION"
			}
		case "user":
			if !truthy(caps["impersonation"]) {
				return "UNSUPPORTED_DELEGATION"
			}
		case "svc":
		default:
			return "UNSUPPORTED_DELEGATION"
		}
		act, hasAct = act["act"].(obj)
	}
	return "OK"
}

func toGeneric(v any) any {
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	var out any
	if err := json.Unmarshal(b, &out); err != nil {
		panic(err)
	}
	return out
}

func objs(v any) []obj {
	arr, _ := v.([]any)
	out := []obj{}
	for _, x := range arr {
		out = append(out, m(x))
	}
	return out
}

func evaluate(in obj) (obj, []string) {
	var problems []string
	bundle := m(in["bundle"])
	if !contractRe.MatchString(str(bundle["contract"])) {
		return obj{"bundle": "refused"}, nil
	}
	claims := m(in["claims"])
	now, _ := num(in["now"])
	k := str(in["key"])
	out := obj{"bundle": "accepted"}
	tok := tokenCheck(bundle, claims)
	out["token"] = tok
	if tok != "OK" {
		return out, nil
	}
	p := newPrincipal(bundle, claims, now)
	t := m(in["resource_type"])
	lvl, _ := p.level(k)
	out["has_key"] = p.has(k)
	out["level"] = lvl
	gids := strs(in["graph_ids"])
	pr, degraded := p.params(t, k, gids)
	out["scope_params"] = pr
	out["degraded"] = degraded
	if fs := objs(t["fields"]); len(fs) > 0 {
		masked, ro := set{}, set{}
		for _, f := range fs {
			cols := strs(f["columns"])
			if !p.has(str(f["read"])) {
				masked.add(cols...)
			} else if e := str(f["edit"]); e == "" || !p.has(e) {
				ro.add(cols...)
			}
		}
		for c := range masked {
			delete(ro, c)
		}
		out["fields"] = obj{"masked": masked.list(), "read_only": ro.list()}
	}
	if rowAny, ok := in["row"]; ok {
		row := m(rowAny)
		acl := objs(in["acl"])
		view := str(t["view_key"])
		vb := p.semantic(t, view, row, acl, gids)
		kb := p.semantic(t, k, row, acl, gids)
		// List/Can consistency on both keys.
		for _, pair := range []struct {
			key string
			b   branch
		}{{view, vb}, {k, kb}} {
			kp, _ := p.params(t, pair.key, gids)
			if got := predicate(t, kp, row, acl, now, p.has(pair.key)); got != pair.b.visible {
				problems = append(problems, fmt.Sprintf("List/Can mismatch for %s: predicate %v, rule %v", pair.key, got, pair.b.visible))
			}
		}
		visible := vb.visible
		allowed := visible && kb.visible
		reason := ""
		switch {
		case !visible:
			reason = "NOT_FOUND"
		case allowed:
		case p.has(k):
			reason = "OUT_OF_SCOPE"
		default:
			reason = "MISSING_PERMISSION"
		}
		out["decision"] = obj{"visible": visible, "allowed": allowed, "reason": reason}
		reasons, missing := p.explain(t, k, row, kb, visible)
		out["explain"] = obj{"reasons": reasons, "missing": missing}
	}
	return out, problems
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: crosscheck <vectors/decision>")
		os.Exit(2)
	}
	files, _ := filepath.Glob(filepath.Join(os.Args[1], "*.json"))
	if len(files) == 0 {
		fmt.Fprintln(os.Stderr, "no vectors found")
		os.Exit(2)
	}
	failed := 0
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			panic(err)
		}
		var doc obj
		if err := json.Unmarshal(raw, &doc); err != nil {
			fmt.Printf("FAIL %s: %v\n", filepath.Base(f), err)
			failed++
			continue
		}
		got, problems := evaluate(m(doc["input"]))
		want := doc["expected"]
		if g := toGeneric(got); !reflect.DeepEqual(g, want) {
			gj, _ := json.Marshal(g)
			wj, _ := json.Marshal(want)
			problems = append(problems, fmt.Sprintf("expected differs\n  go:     %s\n  vector: %s", gj, wj))
		}
		if len(problems) > 0 {
			failed++
			fmt.Printf("FAIL %s\n  %s\n", filepath.Base(f), strings.Join(problems, "\n  "))
		}
	}
	fmt.Printf("%d vectors, %d failed\n", len(files), failed)
	if failed > 0 {
		os.Exit(1)
	}
}
