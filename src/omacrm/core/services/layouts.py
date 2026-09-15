"""Layout data validation shared by the Layout editor and the authoring editors.

``Layout.data`` has two shapes: a list layout is a list of field names, a
detail/edit layout is a list of sections with a title and a fields list.
"""

from omacrm.core.metadata.registry import registry


def layout_fields(entity_type: str) -> dict:
    return {**registry.fields(entity_type), **registry.link_fields(entity_type)}


def _error(path: str, message) -> dict:
    return {"path": path, "message": str(message)}


def validate_layout(entity_type: str, layout_name: str, data) -> list[dict]:
    """Return ``[{"path", "message"}]`` for invalid layout data."""

    if not registry.has(entity_type):
        return [_error("entity_type", "Unknown entity type.")]
    fields = layout_fields(entity_type)
    if layout_name == "list":
        return _validate_list(data, fields)
    return _validate_sections(data, fields)


def _validate_list(data, fields) -> list[dict]:
    if not isinstance(data, list):
        return [_error("data", "The list layout must be a JSON list.")]
    return [
        _error(f"data[{index}]", f"Unknown field: {name}")
        for index, name in enumerate(data)
        if name not in fields
    ]


def _validate_sections(data, fields) -> list[dict]:
    if not isinstance(data, list):
        return [_error("data", "The detail layout must be a JSON list.")]
    errors = []
    for index, section in enumerate(data):
        if not isinstance(section, dict) or not isinstance(
            section.get("fields", []), list
        ):
            errors.append(
                _error(
                    f"data[{index}]",
                    "Each section must be an object with a 'fields' list.",
                )
            )
            continue
        errors.extend(
            _error(f"data[{index}].fields", f"Unknown field: {name}")
            for name in section.get("fields", [])
            if name not in fields
        )
    return errors


def clean_sections(data) -> list[dict]:
    """Normalize detail sections into ``{title, fields}`` objects."""

    cleaned = []
    for section in data if isinstance(data, list) else []:
        if not isinstance(section, dict):
            continue
        cleaned.append(
            {
                "title": section.get("title"),
                "fields": [
                    name
                    for name in section.get("fields", [])
                    if isinstance(name, str)
                ],
            }
        )
    return cleaned
