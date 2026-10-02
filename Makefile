# Every target runs in a throwaway container; nothing is installed locally.
# `make check` is what a change to this repository must pass.

BUF      := bufbuild/buf:1.57.0
REDOCLY  := redocly/cli:1.34.3
PYTHON   := python:3.13-slim
GO       := golang:1.25-alpine
UID      := $(shell id -u):$(shell id -g)
RUN      := docker run --rm -u $(UID) -e HOME=/tmp -v $(CURDIR):/w -w /w

.PHONY: check lint lint-proto lint-openapi validate vectors vectors-check vectors-crosscheck breaking gen gen-check build

check: lint gen-check build validate vectors-check vectors-crosscheck

lint: lint-proto lint-openapi

lint-proto:
	$(RUN) -e BUF_CACHE_DIR=/tmp/buf $(BUF) lint

lint-openapi:
	$(RUN) $(REDOCLY) lint openapi/authz.openapi.yaml

validate:
	$(RUN) $(PYTHON) sh -c 'pip install -q --user jsonschema==4.23.0 pyyaml==6.0.2 >/dev/null 2>&1 && python3 scripts/validate.py'

# Rewrite vectors/decision/ and vectors/SHA256SUMS from vectors/tools/cases.py.
vectors:
	$(RUN) $(PYTHON) python3 vectors/tools/generate.py

vectors-check:
	$(RUN) $(PYTHON) python3 vectors/tools/generate.py --check

# The independent Go implementation of EVALUATION.md, plus List/Can consistency.
vectors-crosscheck:
	$(RUN) -e GOCACHE=/tmp/gocache -e GOTOOLCHAIN=local -w /w/vectors/tools/crosscheck $(GO) go run . /w/vectors/decision

# Additive-only check against the previous release tag (BASE=v2.0.0).
breaking:
	$(RUN) -e BUF_CACHE_DIR=/tmp/buf $(BUF) breaking --against '.git#tag=$(BASE)'

# Generate the Go package gen/go/infra/authz/v2 (README, "Generated code"); committed.
gen:
	$(RUN) -e BUF_CACHE_DIR=/tmp/buf $(BUF) generate

# The committed gen/go must be exactly what buf generates from proto/.
gen-check:
	@T=$$(mktemp -d) && cp -r gen $$T/ && $(RUN) -e BUF_CACHE_DIR=/tmp/buf $(BUF) generate && \
	  diff -r $$T/gen gen && rm -rf $$T && echo "gen/go up to date"

# The Go module: vet, build, gofmt (the crosscheck is a module of its own).
build:
	$(RUN) -e GOCACHE=/tmp/gocache -e GOPATH=/tmp/gopath $(GO) sh -c 'go vet ./... && go build ./... && test -z "$$(gofmt -l .)"'
