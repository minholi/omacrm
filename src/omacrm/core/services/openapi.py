"""OpenAPI 3.1 contract generated from the metadata registry.

The document is built from the same definitions the API itself uses, so it
covers built-in and runtime custom entities, their custom fields and their
custom relationships, and it is filtered by the requesting user's ACL.
"""

from omacrm.core.api.filters import _COMPARISONS
from omacrm.core.metadata.registry import registry
from omacrm.core.services.acl import AclService

OPENAPI_VERSION = "3.1.1"
LEAD_CAPTURE_PATH = "/lead-capture/{api_key}/"

_FIELD_TYPES = {
    "varchar": {"type": "string"},
    "text": {"type": "string"},
    "email": {"type": "string", "format": "email"},
    "phone": {"type": "string"},
    "url": {"type": "string", "format": "uri"},
    "bool": {"type": "boolean"},
    "int": {"type": "integer"},
    "number": {"type": "integer"},
    "float": {"type": "number"},
    "decimal": {"type": "number"},
    "currency": {"type": "number"},
    "date": {"type": "string", "format": "date"},
    "datetime": {"type": "string", "format": "date-time"},
    "address": {"type": "object", "additionalProperties": True},
    "file": {"type": "integer"},
    "image": {"type": "integer"},
    "attachmentMultiple": {"type": "array", "items": {"type": "integer"}},
    "link": {"type": "integer"},
    "linkMultiple": {"type": "array", "items": {"type": "integer"}},
    "foreign": {"type": "string", "readOnly": True},
}

_WHERE_DESCRIPTION = (
    "JSON filter expression. Leaf nodes are "
    '{"type": "<operator>", "attribute": "<field>", "value": <value>} with '
    "operators: "
    + ", ".join(sorted(_COMPARISONS))
    + ". Groups of nodes use and/or and are wrapped as "
    '{"type": "and", "value": [...]}; not is also supported. Example: '
    '[{"type": "equals", "attribute": "stage", "value": "Proposal"}].'
)

_LEAD_CAPTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "first_name": {"type": "string"},
        "last_name": {"type": "string"},
        "email_address": {"type": "string", "format": "email"},
        "phone_number": {"type": "string"},
        "description": {"type": "string"},
        "captcha_token": {
            "type": "string",
            "description": (
                "Captcha token, required when the capture enables a captcha. "
                "g-recaptcha-response and cf-turnstile-response are accepted "
                "as alternatives."
            ),
        },
    },
    "description": (
        "Accepted fields are the capture's configured field list "
        "(first_name, last_name, email_address, phone_number and description "
        "by default); last_name or email_address is required."
    ),
}

_LEAD_CAPTURE_RESPONSE = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "status": {
            "type": "string",
            "description": "pending_confirmation when the capture uses double opt-in.",
        },
    },
}


def _company_name() -> str:
    try:
        from constance import config

        return config.company_name or "OmaCRM"
    except Exception:  # noqa: BLE001 - constance may be unavailable
        return "OmaCRM"


def _enum_values(field_def) -> list[str]:
    values = []
    for option in field_def.options or []:
        if isinstance(option, (list, tuple)) and option:
            values.append(str(option[0]))
        else:
            values.append(str(option))
    return values


def _field_schema(field_def) -> dict:
    schema = dict(_FIELD_TYPES.get(field_def.type, {"type": "string"}))
    if field_def.type == "enum":
        schema["enum"] = _enum_values(field_def)
    elif field_def.type == "multiEnum":
        schema = {"type": "array", "items": {"type": "string"}}
        values = _enum_values(field_def)
        if values:
            schema["items"]["enum"] = values
    if field_def.read_only:
        schema["readOnly"] = True
    description = field_def.help_text or field_def.label
    if description:
        schema["description"] = str(description)
    return schema


def _entity_schema(entity_type: str, user) -> dict:
    fields = registry.fields(entity_type)
    try:
        model_field_names = {
            field.name
            for field in registry.model_for(entity_type)._meta.concrete_fields
        }
    except (KeyError, LookupError):
        model_field_names = set()

    properties: dict[str, dict] = {"id": {"type": "integer", "readOnly": True}}
    required: list[str] = []

    for name, field_def in fields.items():
        if field_def.custom or name not in model_field_names:
            continue
        if not AclService.check_field(user, entity_type, name, "read"):
            continue
        properties[name] = _field_schema(field_def)
        if field_def.required:
            required.append(name)

    for name in ("created_at", "modified_at", "created_by", "modified_by"):
        if name in model_field_names and name not in properties:
            schema = {"readOnly": True}
            if name.endswith("_by"):
                schema["type"] = "integer"
            else:
                schema["type"] = "string"
                schema["format"] = "date-time"
            properties[name] = schema

    if "custom_data" in model_field_names:
        custom_properties = {}
        for name, field_def in fields.items():
            if not field_def.custom:
                continue
            if not AclService.check_field(user, entity_type, name, "read"):
                continue
            custom_properties[name] = _field_schema(field_def)
        properties["custom_data"] = {
            "type": "object",
            "properties": custom_properties,
            "additionalProperties": True,
        }

    for name, definition in registry.link_definitions(entity_type).items():
        if name in properties:
            continue
        if not AclService.check_field(user, entity_type, name, "read"):
            continue
        if definition.multiple:
            properties[name] = {"type": "array", "items": {"type": "integer"}}
        else:
            properties[name] = {"type": "integer"}

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _list_schema(entity_type: str) -> dict:
    return {
        "type": "object",
        "properties": {
            "count": {"type": "integer"},
            "next": {"type": ["string", "null"]},
            "previous": {"type": ["string", "null"]},
            "results": {
                "type": "array",
                "items": {"$ref": f"#/components/schemas/{entity_type}"},
            },
        },
    }


def _list_parameters(entity) -> list[dict]:
    parameters = [
        {
            "name": "limit",
            "in": "query",
            "schema": {"type": "integer"},
            "description": "Page size (default 20).",
        },
        {
            "name": "offset",
            "in": "query",
            "schema": {"type": "integer"},
            "description": "Number of records to skip.",
        },
    ]
    if entity.search_fields:
        parameters.append(
            {
                "name": "search",
                "in": "query",
                "schema": {"type": "string"},
                "description": "Search terms across: %s."
                % ", ".join(entity.search_fields),
            }
        )
    parameters.append(
        {
            "name": "ordering",
            "in": "query",
            "schema": {"type": "string"},
            "description": "Comma-separated field names; '-' prefixes descending order.",
        }
    )
    parameters.append(
        {
            "name": "where",
            "in": "query",
            "schema": {"type": "string"},
            "description": _WHERE_DESCRIPTION,
        }
    )
    return parameters


def _entity_paths(entity_type: str, entity, prefix: str) -> dict:
    ref = {"$ref": f"#/components/schemas/{entity_type}"}
    list_ref = {"$ref": f"#/components/schemas/{entity_type}List"}
    id_parameter = {
        "name": "id",
        "in": "path",
        "required": True,
        "schema": {"type": "integer"},
    }
    error_responses = {
        "401": {"description": "Authentication required."},
        "403": {"description": "Permission denied."},
    }

    collection = {
        "get": {
            "tags": [entity_type],
            "summary": "List %s" % entity.display_label_plural,
            "operationId": "%s_list" % prefix,
            "parameters": _list_parameters(entity),
            "responses": {
                "200": {
                    "description": "Paginated list of records.",
                    "content": {"application/json": {"schema": list_ref}},
                },
                **error_responses,
            },
        },
        "post": {
            "tags": [entity_type],
            "summary": "Create a %s" % entity.display_label,
            "operationId": "%s_create" % prefix,
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": ref}},
            },
            "responses": {
                "201": {
                    "description": "Record created.",
                    "content": {"application/json": {"schema": ref}},
                },
                "400": {"description": "Validation error."},
                **error_responses,
            },
        },
    }

    detail = {
        "get": {
            "tags": [entity_type],
            "summary": "Retrieve a %s" % entity.display_label,
            "operationId": "%s_retrieve" % prefix,
            "parameters": [id_parameter],
            "responses": {
                "200": {
                    "description": "Record.",
                    "content": {"application/json": {"schema": ref}},
                },
                "404": {"description": "Not found."},
                **error_responses,
            },
        },
        "put": {
            "tags": [entity_type],
            "summary": "Replace a %s" % entity.display_label,
            "operationId": "%s_update" % prefix,
            "parameters": [id_parameter],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": ref}},
            },
            "responses": {
                "200": {
                    "description": "Record updated.",
                    "content": {"application/json": {"schema": ref}},
                },
                "400": {"description": "Validation error."},
                "404": {"description": "Not found."},
                **error_responses,
            },
        },
        "patch": {
            "tags": [entity_type],
            "summary": "Update a %s partially" % entity.display_label,
            "operationId": "%s_partial_update" % prefix,
            "parameters": [id_parameter],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": ref}},
            },
            "responses": {
                "200": {
                    "description": "Record updated.",
                    "content": {"application/json": {"schema": ref}},
                },
                "400": {"description": "Validation error."},
                "404": {"description": "Not found."},
                **error_responses,
            },
        },
        "delete": {
            "tags": [entity_type],
            "summary": "Delete a %s" % entity.display_label,
            "operationId": "%s_delete" % prefix,
            "parameters": [id_parameter],
            "responses": {
                "204": {"description": "Record deleted."},
                "404": {"description": "Not found."},
                **error_responses,
            },
        },
    }

    return {f"/{prefix}/": collection, f"/{prefix}/{{id}}/": detail}


def _lead_capture_path() -> dict:
    return {
        "post": {
            "tags": ["Lead capture"],
            "summary": "Create a lead from a public web form",
            "operationId": "lead_capture",
            "security": [],
            "parameters": [
                {
                    "name": "api_key",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/LeadCaptureSubmission"
                        }
                    }
                },
            },
            "responses": {
                "201": {
                    "description": "Lead created.",
                    "content": {
                        "application/json": {"schema": _LEAD_CAPTURE_RESPONSE}
                    },
                },
                "400": {"description": "Invalid payload or missing captcha token."},
                "403": {"description": "Captcha verification failed."},
                "404": {"description": "Unknown or inactive capture."},
                "503": {"description": "Captcha required but not configured."},
            },
        }
    }


def build_spec(user) -> dict:
    """Build the OpenAPI document visible to ``user``."""

    schemas: dict[str, dict] = {}
    paths: dict[str, dict] = {}
    tags: list[dict] = []

    for entity_type in sorted(registry.entities()):
        if not AclService.check(user, entity_type, "read"):
            continue
        entity = registry.get(entity_type)
        schemas[entity_type] = _entity_schema(entity_type, user)
        schemas[f"{entity_type}List"] = _list_schema(entity_type)
        prefix = entity_type if registry.is_dynamic(entity_type) else entity_type.lower()
        paths.update(_entity_paths(entity_type, entity, prefix))
        tags.append(
            {
                "name": entity_type,
                "description": str(entity.display_label_plural),
            }
        )

    schemas["LeadCaptureSubmission"] = _LEAD_CAPTURE_SCHEMA
    paths[LEAD_CAPTURE_PATH] = _lead_capture_path()
    tags.append(
        {
            "name": "Lead capture",
            "description": "Public web-to-lead endpoint.",
        }
    )

    return {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": "%s API" % _company_name(),
            "version": "1.0.0",
        },
        "servers": [{"url": "/api/v1"}],
        "tags": tags,
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-Api-Key",
                    "description": "A user's API key, generated from the user admin.",
                },
                "TokenAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "Authorization",
                    "description": "Token authentication: 'Token <token>'.",
                },
                "SessionAuth": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "sessionid",
                    "description": "Session cookie used by the admin UI.",
                },
            },
        },
        "security": [
            {"ApiKeyAuth": []},
            {"TokenAuth": []},
            {"SessionAuth": []},
        ],
    }
