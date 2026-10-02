// Package authzcontract exposes the files of the authz family contract
// (authz/2.x) to Go tests and tools: schemas, the decision vectors, the
// capability enum, the error reasons, the events, the OpenAPI and the proto
// sources. It contains no logic. The generated gRPC package lives beside
// it in gen/go/infra/authz/v2 (package authzv2), committed (make gen).
package authzcontract

import "embed"

// FS holds the contract files at their repository paths, for example
// "vectors/decision/level-highest-wins.json" or "schemas/bundle.schema.json".
//
//go:embed capabilities.yaml errors.yaml schemas openapi events proto examples vectors/decision vectors/SHA256SUMS
var FS embed.FS
