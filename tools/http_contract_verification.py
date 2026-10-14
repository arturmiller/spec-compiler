"""Black-box proof helpers for HTTP Contract Conventions v1."""

from copy import deepcopy
import json

from jsonschema import Draft202012Validator, FormatChecker


def read_pointer(value, pointer):
    for part in pointer.split("/")[1:]:
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def wrap_body(value, pointer):
    for part in reversed(pointer.split("/")[1:]):
        value = {part.replace("~1", "/").replace("~0", "~"): value}
    return value


def validate_body(schema, value):
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


def resolve_reference(document, value):
    seen = set()
    while isinstance(value, dict) and "$ref" in value:
        reference = value["$ref"]
        assert reference.startswith("#/"), "Only local OpenAPI references are supported"
        assert reference not in seen, "Cyclic OpenAPI reference"
        seen.add(reference)
        # Constraint-bearing siblings require general logical equivalence analysis.
        assert set(value) <= {"$ref", "title", "description", "summary"}
        value = read_pointer(document, reference[1:])
    return value


def _canonical_schema(document, schema, references=()):
    if isinstance(schema, bool):
        return schema
    if "$ref" in schema:
        reference = schema["$ref"]
        assert reference not in references, "Recursive schemas are unsupported"
        return _canonical_schema(
            document, resolve_reference(document, schema), (*references, reference)
        )
    result = {}
    for key, value in schema.items():
        if key in {"title", "description", "summary", "examples", "example", "$schema", "$defs"}:
            continue
        if key == "properties":
            result[key] = {
                name: _canonical_schema(document, child, references)
                for name, child in value.items()
            }
        elif key in {"items", "additionalProperties", "not"}:
            result[key] = _canonical_schema(document, value, references)
        elif key in {"allOf", "anyOf", "oneOf"}:
            result[key] = [_canonical_schema(document, child, references) for child in value]
        elif key in {"required", "enum"}:
            result[key] = sorted(value, key=lambda item: json.dumps(item, sort_keys=True))
        elif key == "type" and isinstance(value, list):
            result[key] = sorted(value) if len(value) != 1 else value[0]
        else:
            result[key] = value
    for key, default in (("required", []), ("additionalProperties", True), ("items", True)):
        if result.get(key) == default:
            result.pop(key, None)
    return result


def assert_schema_matches(actual_document, actual, expected):
    """Compare the supported structural schema contract, allowing local refs."""
    assert _canonical_schema(actual_document, actual) == _canonical_schema({}, expected)


def invalid_bodies(schema, valid_body):
    """Mutate authored constraints; emit only payloads rejected by the schema."""
    candidates = []

    def replace(parts, value, remove=False):
        body = deepcopy(valid_body)
        if not parts:
            candidates.append(value)
            return
        target = body
        for part in parts[:-1]:
            target = target[part]
        if remove:
            del target[parts[-1]]
        else:
            target[parts[-1]] = value
        candidates.append(body)

    def visit(current_schema, value, parts):
        if isinstance(current_schema, bool):
            return
        if "type" in current_schema:
            for wrong_value in (None, "invalid-type", 7, [], {}):
                replace(parts, wrong_value)
        if "const" in current_schema or "enum" in current_schema:
            replace(parts, "not-an-authored-value")
        if current_schema.get("format") == "date":
            replace(parts, "not-a-date")
        if "minLength" in current_schema:
            replace(parts, "")
        if isinstance(value, dict):
            for name in current_schema.get("required", []):
                if name in value:
                    replace([*parts, name], None, remove=True)
            forbidden = current_schema.get("not", {})
            if isinstance(forbidden, dict) and forbidden.get("required"):
                changed = {**value, **{name: True for name in forbidden["required"]}}
                replace(parts, changed)
            for name, child in current_schema.get("properties", {}).items():
                if name in value:
                    visit(child, value[name], [*parts, name])
        elif isinstance(value, list) and value and "items" in current_schema:
            visit(current_schema["items"], value[0], [*parts, 0])

    visit(schema, valid_body, [])
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    seen = set()
    for candidate in candidates:
        key = json.dumps(candidate, sort_keys=True)
        if key not in seen and not validator.is_valid(candidate):
            seen.add(key)
            yield candidate
