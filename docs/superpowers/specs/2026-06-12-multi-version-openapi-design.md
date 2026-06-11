# Multi-Version OpenAPI Support — Design

**Date:** 2026-06-12
**Status:** Approved (direction), pending spec review

## Goal

Make pytest-synapse correctly measure coverage and validate schemas
against all major OpenAPI specification versions:

- **Swagger / OpenAPI 2.0**
- **OpenAPI 3.0.x**
- **OpenAPI 3.1.x**

"Correctly" means: operations behind these specs are matched to captured
traffic, request/response bodies are detected and schema-validated, and
field-level coverage is tracked — without false contract violations.

## Current State (measured 2026-06-12)

| Concern | 2.0 | 3.0.x | 3.1.x |
|---|---|---|---|
| Path/method matching | OK | OK | OK |
| Response schema detection (`schema` on response) | OK | OK | OK |
| `$ref` resolution (`#/definitions`, `#/components`) | OK | OK | OK |
| Request body detection | **BROKEN** | OK | OK |
| Base-path stripping for matching | **BROKEN** | OK | OK |
| `nullable: true` accepting `null` | n/a | **BROKEN** | OK (native) |
| `field_type` readout for `type` arrays | n/a | n/a | cosmetic |

Root causes:

1. **2.0 request bodies** are modelled as parameters (`in: body` with a
   `schema`, or one-or-more `in: formData` fields), not a `requestBody`
   object. `has_request_body` / `get_request_body_schema` only look for
   `requestBody`, so 2.0 bodies are invisible → `NOT_APPLICABLE`.
2. **2.0 base path** comes from top-level `basePath` (e.g. `/v1`), not
   `servers[].url`. `get_base_paths()` only reads `servers`, returns
   `[]`, so a request to `/v1/users` never matches spec key `/users`.
3. **3.0 `nullable: true`** is an OpenAPI extension, not a JSON Schema
   keyword. The `Draft7Validator` ignores it and rejects `null`,
   producing false `INVALID` results.

## Approach

**Version-aware accessors in the parser** (chosen over a normalization
layer or an external converter library). This follows the pattern the
parser already uses — `has_response_schema` already branches on 2.x vs
3.x — keeps changes local and low-risk, and avoids a heavy runtime
dependency that conflicts with the tool's lightweight design.

Validation strictness is **best-effort**: recognised versions are parsed
as fully as possible; an unrecognised or malformed spec keeps the
current behaviour rather than raising. This is a coverage tool, not a
spec linter.

## Components & Changes

### 1. `spec_parser.py` — version-aware spec access

- Add `version_major` → returns `2`, `3`, or `None` derived from the
  `swagger` / `openapi` field. Single source of version truth.
- `has_request_body(path, method)`:
  - 3.x: unchanged (`"requestBody" in operation`).
  - 2.0: true if any operation parameter has `in: body` or
    `in: formData`.
- `get_request_body_schema(path, method, content_type=None)`:
  - 3.x: unchanged.
  - 2.0 `in: body`: return that parameter's `schema`.
  - 2.0 `in: formData`: synthesise an object schema —
    `{"type": "object", "properties": {<name>: <param type schema>},
    "required": [<names with required: true>]}` — so form fields get
    field-level coverage like any object body.
- `get_base_paths()`:
  - 3.x: unchanged (`servers[].url` paths).
  - 2.0: return `[basePath]` (without trailing slash) when `basePath`
    is set and not `/`.

Parameters can live on the path item (shared) or the operation; the
body/formData scan reads both, operation-level taking precedence.

### 2. `coverage_engine.py` — single source for schema extraction

`_process_request_body` / `_process_response` currently call the
validator's private `_get_request_body_schema` / `_get_response_schema`,
duplicating extraction logic. Change them to call the parser's
(now version-aware) `get_request_body_schema` / `get_response_schema`
and pass the resulting schema into `validate_with_coverage`. This
removes the duplication and lets 2.0 bodies flow through validation
without touching the validator's extraction code.

### 3. `schema_validator.py` — draft selection & nullable

- Constructor detects the spec version and picks the validator class:
  - 2.0 / 3.0 → `Draft7Validator` (superset of the Draft 4 dialect
    these versions use).
  - 3.1 → `Draft202012Validator`.
- For 2.0 / 3.0, normalise `nullable` once at construction: deep-copy
  the entire spec dict and walk every nested mapping (covering both
  inline schemas under `paths` and the shared `#/definitions` /
  `#/components/schemas` schemas), rewriting `{"nullable": true,
  "type": T}` into `{"type": [T, "null"]}` and dropping the `nullable`
  key. Both `$ref` resolution and validation then run against this
  rewritten copy. 3.1 specs are left untouched.
- `field_type` normalisation: when a schema's `type` is a list (3.1
  style, e.g. `["string", "null"]`), report the first non-`"null"`
  entry as the field type for coverage display; keep the raw list out of
  the user-facing readout.
- `$ref` resolution keeps using the existing resolver. If the 2020-12
  validator proves incompatible with the legacy resolver during
  implementation, resolve refs eagerly for that path; the public
  behaviour (validate against `#/.../schemas/...`) must not change.

### 4. Tests & fixtures

New fixtures, one per version, exercising the gaps:

- `swagger2.json` — `basePath`, an `in: body` POST, a `formData` POST,
  a response with `schema` on the response, `#/definitions` refs.
- `openapi31.json` — `type: [..., "null"]`, `const`, `#/components` refs.
- 3.0 `nullable` case can extend the existing `openapi.yaml` fixture or
  a small dedicated fixture.

TDD: a red test per gap first (2.0 body coverage, 2.0 formData coverage,
2.0 base-path matching, 3.0 nullable-accepts-null, 3.1 field_type
readout), then the implementation. Existing 188 tests must stay green.

### 5. Docs

- README: add a "Supported OpenAPI versions" matrix (2.0, 3.0.x, 3.1.x).
- `docs/configuration.md`: note 2.0 `basePath` handling alongside the
  existing `servers` base-path section.

## Out of Scope

- Migrating off the deprecated `jsonschema.RefResolver` (works today;
  separate change to limit risk).
- OpenAPI 3.1 `webhooks` / `pathItems` without traffic semantics.
- Swagger 2.0 `host`/`schemes` reconstruction (only the path prefix
  matters for matching).
- Spec linting / rejecting invalid specs.

## Success Criteria

- A Swagger 2.0 spec with `basePath` and `body`/`formData` POSTs reports
  request-body and operation coverage for exercised endpoints.
- An OpenAPI 3.0 spec with `nullable: true` fields validates `null`
  values as `VALID`.
- An OpenAPI 3.1 spec with `type: [..., "null"]` validates and shows a
  clean `field_type`.
- Full existing suite remains green; new per-version tests pass.
