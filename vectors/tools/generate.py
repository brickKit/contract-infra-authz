"""Writes vectors/decision/*.json and vectors/SHA256SUMS from cases.py.

    python3 vectors/tools/generate.py           # write
    python3 vectors/tools/generate.py --check   # fail if the files are stale

Every expected result is computed by reference.py and must agree with the
case's hand-written intent; the files are then recomputed independently by
crosscheck/ (make vectors-crosscheck).
"""

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cases  # noqa: E402
import reference  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "decision")
SUMS = os.path.join(ROOT, "SHA256SUMS")
CONTRACT = "authz/2.0"


def lookup(obj, dotted):
    for part in dotted.split("."):
        if not isinstance(obj, dict) or part not in obj:
            raise KeyError(dotted)
        obj = obj[part]
    return obj


def render(case):
    expected = reference.evaluate(case["input"])
    for path, want in case["intent"].items():
        try:
            got = lookup(expected, path)
        except KeyError:
            raise SystemExit(f"{case['id']}: intent {path} absent from computed result {expected}")
        if got != want:
            raise SystemExit(f"{case['id']}: intent {path} = {want!r}, reference computed {got!r}")
    doc = {
        "id": case["id"],
        "title": case["title"],
        "contract": CONTRACT,
        "tags": case["tags"],
        "input": case["input"],
        "expected": expected,
    }
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main():
    check = "--check" in sys.argv
    ids = [c["id"] for c in cases.CASES]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate case ids")
    files = {f"{c['id']}.json": render(c) for c in cases.CASES}
    sums = "".join(f"{hashlib.sha256(files[n].encode()).hexdigest()}  decision/{n}\n" for n in sorted(files))
    if check:
        stale = []
        present = set(os.listdir(OUT)) if os.path.isdir(OUT) else set()
        for name, text in files.items():
            path = os.path.join(OUT, name)
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
                stale.append(name)
        stale += sorted(present - set(files))
        if not os.path.exists(SUMS) or open(SUMS, encoding="utf-8").read() != sums:
            stale.append("SHA256SUMS")
        if stale:
            raise SystemExit("stale vectors: " + ", ".join(stale))
        print(f"vectors fresh: {len(files)}")
        return
    os.makedirs(OUT, exist_ok=True)
    for name in os.listdir(OUT):
        if name.endswith(".json") and name not in files:
            os.remove(os.path.join(OUT, name))
    for name, text in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    with open(SUMS, "w", encoding="utf-8") as fh:
        fh.write(sums)
    print(f"wrote {len(files)} vectors")


if __name__ == "__main__":
    main()
