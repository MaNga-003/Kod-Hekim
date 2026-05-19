"""JSON Schema → Gemini responseSchema (OpenAPI alt kümesi) dönüşümü."""

from __future__ import annotations

from typing import Any


def sanitize_json_schema_for_gemini(schema: Any) -> Any:
    """Gemini'nin kabul etmediği JSON Schema özelliklerini temizler."""
    if isinstance(schema, list):
        return [sanitize_json_schema_for_gemini(x) for x in schema]

    if not isinstance(schema, dict):
        return schema

    out: dict[str, Any] = {}

    for key, value in schema.items():
        if key == "type":
            if isinstance(value, list):
                non_null = [t for t in value if t != "null"]
                if non_null:
                    out["type"] = non_null[0]
                if "null" in value:
                    out["nullable"] = True
            else:
                out["type"] = value
            continue

        if key == "properties" and isinstance(value, dict):
            out["properties"] = {
                k: sanitize_json_schema_for_gemini(v) for k, v in value.items()
            }
            continue

        if key == "items":
            out["items"] = sanitize_json_schema_for_gemini(value)
            continue

        if key in {"required", "enum", "minimum", "maximum", "nullable", "description"}:
            out[key] = value

    return out
