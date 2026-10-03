"""Static validation of the contract files (make validate).

Needs jsonschema and pyyaml; the Makefile runs it in a throwaway python
container. Checks:
  1. every JSON Schema in schemas/ is a valid 2020-12 schema;
  2. examples/bundle.example.json and every vector's bundle (except tag
     invalid-bundle) match schemas/bundle.schema.json;
  3. every vector matches schemas/vector.schema.json and SHA256SUMS;
  4. examples/export.example.ndjson: every line matches the export schema,
     header first, footer last, kinds in order, counts and digest right;
  5. every event payload in events/ is a valid schema; every subject follows be-protocol P12.3;
     every consumed subject names its source contract and its effect;
  6. capability names agree across capabilities.yaml, the bundle schema and
     the OpenAPI x-capability values; error reasons are unique UPPER_SNAKE.
"""

import glob
import hashlib
import json
import os
import re
import sys

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
problems = []


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return json.load(fh) if path.endswith(".json") else yaml.safe_load(fh)


def fail(msg):
    problems.append(msg)


schemas = {}
for path in sorted(glob.glob(os.path.join(ROOT, "schemas", "*.json"))):
    name = os.path.basename(path)
    doc = load(os.path.join("schemas", name))
    try:
        Draft202012Validator.check_schema(doc)
    except Exception as exc:  # noqa: BLE001
        fail(f"schemas/{name}: invalid schema: {exc}")
    schemas[name] = doc

registry = Registry().with_resources(
    (doc["$id"], Resource.from_contents(doc)) for doc in schemas.values())


def validator(name, fragment=None):
    schema = schemas[name]
    if fragment:
        schema = {"$ref": schema["$id"] + "#" + fragment}
    return Draft202012Validator(schema, registry=registry)


def check(v, instance, where):
    for err in sorted(v.iter_errors(instance), key=lambda e: list(e.path)):
        fail(f"{where}: {'/'.join(map(str, err.path))}: {err.message}")


bundle_v = validator("bundle.schema.json")
check(bundle_v, load("examples/bundle.example.json"), "examples/bundle.example.json")

vector_v = validator("vector.schema.json")
sums = {}
for line in open(os.path.join(ROOT, "vectors", "SHA256SUMS"), encoding="utf-8"):
    digest, name = line.split()
    sums[name] = digest
files = sorted(glob.glob(os.path.join(ROOT, "vectors", "decision", "*.json")))
if not files:
    fail("no vectors")
for path in files:
    rel = "decision/" + os.path.basename(path)
    raw = open(path, "rb").read()
    if sums.pop(rel, None) != hashlib.sha256(raw).hexdigest():
        fail(f"vectors/{rel}: SHA256SUMS mismatch")
    doc = json.loads(raw)
    check(vector_v, doc, f"vectors/{rel}")
    if doc["id"] + ".json" != os.path.basename(path):
        fail(f"vectors/{rel}: id does not match the file name")
    if "invalid-bundle" not in doc["tags"]:
        check(bundle_v, doc["input"]["bundle"], f"vectors/{rel} input.bundle")
for name in sums:
    fail(f"SHA256SUMS lists a missing file {name}")

export_v = validator("export-record.schema.json")
order = ["role", "user_role", "user_dept", "profile", "delegation", "tuple", "relation_group"]
lines = open(os.path.join(ROOT, "examples", "export.example.ndjson"), "rb").read().split(b"\n")
if lines[-1] != b"":
    fail("export example: last line lacks LF")
lines = lines[:-1]
recs = [json.loads(x) for x in lines]
for i, rec in enumerate(recs, 1):
    check(export_v, rec, f"examples/export.example.ndjson line {i}")
if recs[0]["kind"] != "header" or recs[-1]["kind"] != "footer":
    fail("export example: header first and footer last")
body = recs[1:-1]
kinds = [r["kind"] for r in body]
if kinds != sorted(kinds, key=order.index):
    fail("export example: kinds out of order")
counts = {}
for k in kinds:
    counts[k] = counts.get(k, 0) + 1
if counts != recs[-1]["counts"]:
    fail(f"export example: footer counts {recs[-1]['counts']} != {counts}")
digest = hashlib.sha256(b"".join(x + b"\n" for x in lines[1:-1])).hexdigest()
if digest != recs[-1]["sha256"]:
    fail("export example: footer sha256 mismatch")

events = load("events/authz.events.json")
for group in ("events", "inbound_events", "signals"):
    for ev in events[group]:
        schema = dict(ev["payload"])
        schema["$defs"] = events["$defs"]
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # noqa: BLE001
            fail(f"events {ev['subject']}: {exc}")
        if not re.match(r"^infra\.authz\.[a-z0-9_.]+\.v[0-9]+$", ev["subject"]):
            fail(f"events {ev['subject']}: subject format")

SUBJECT = r"^[a-z][a-z0-9]*(_[a-z0-9]+)*(\.[a-z][a-z0-9]*(_[a-z0-9]+)*){2,}\.v[1-9][0-9]*$"
for ev in events["events"] + events["inbound_events"] + events["signals"]:
    if not re.match(SUBJECT, ev["subject"]):
        fail(f"events {ev['subject']}: not a be-protocol P12.3 subject")
for ev in events["signals"]:
    if ev.get("x-signal") is not True:
        fail(f"signals {ev['subject']}: a poke is marked x-signal: true (be-protocol P12.10)")
for ev in events.get("consumes", []):
    if not re.match(SUBJECT, ev["subject"]) or ev["subject"].startswith("infra.authz."):
        fail(f"consumes {ev['subject']}: must be another family's P12.3 subject")
    if not ev.get("effect") or not ev.get("from"):
        fail(f"consumes {ev['subject']}: from and effect are required")

caps = load("capabilities.yaml")
names = [c["name"] for c in caps["capabilities"]]
if len(names) != len(set(names)):
    fail("capabilities.yaml: duplicate names")
schema_caps = set(schemas["bundle.schema.json"]["$defs"]["capabilities"]["properties"])
if set(names) != schema_caps:
    fail(f"capabilities differ: yaml-only {set(names) - schema_caps}, schema-only {schema_caps - set(names)}")
api = load("openapi/authz.openapi.yaml")
for path, item in api["paths"].items():
    for method, op in item.items():
        if isinstance(op, dict) and "operationId" in op:
            cap = op.get("x-capability")
            if cap not in names:
                fail(f"openapi {method.upper()} {path}: x-capability {cap!r} unknown")
            # be-protocol P3.16: a guard on every operation, fail closed; the provider plane is x-be-internal
            internal = op.get("x-be-internal") is True
            if not internal and not op.get("x-be-permission"):
                fail(f"openapi {method.upper()} {path}: no x-be-permission and not x-be-internal")
            if internal != path.startswith("/authz/v2/"):
                fail(f"openapi {method.upper()} {path}: x-be-internal must mark exactly the provider plane")

errors = load("errors.yaml")
reasons = [r["reason"] for r in errors["reasons"]]
if len(reasons) != len(set(reasons)):
    fail("errors.yaml: duplicate reasons")
for r in reasons:
    if not re.match(r"^[A-Z][A-Z0-9_]*$", r):
        fail(f"errors.yaml: {r} is not UPPER_SNAKE")

if problems:
    print("\n".join(problems))
    sys.exit(1)
print(f"valid: {len(schemas)} schemas, {len(files)} vectors, {len(recs)} export lines, "
      f"{sum(len(events[g]) for g in ('events', 'inbound_events', 'signals'))} events, "
      f"{len(names)} capabilities, {len(reasons)} reasons")
