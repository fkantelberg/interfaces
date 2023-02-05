import logging

from werkzeug.exceptions import BadRequest, InternalServerError

from odoo import _, http
from odoo.models import BaseModel

from odoo.addons.base_rest import restapi

_logger = logging.getLogger(__name__)


class Serializer(restapi.RestMethodParam):
    def __init__(self, serializer_code, is_list=False):
        self.serializer_code = serializer_code
        self.is_list = is_list

    def from_params(self, service, params):
        serializer = service.env["ir.serializer"].find_by_code(self.serializer_code)
        if not serializer:
            raise InternalServerError(_("No serializer"))

        if self.is_list:
            if not isinstance(params, (list, tuple)):
                raise BadRequest(_("Expected a list of dictionaries"))

            if not all(isinstance(x, dict) for x in params):
                raise BadRequest(_("Expected a list of dictionaries"))

            return list(map(serializer._deserialize, params))

        if not isinstance(params, dict):
            raise BadRequest(_("Expected a dictionary"))

        return serializer._deserialize(params)

    def to_response(self, service, result) -> http.Response:
        if result is None:
            return None

        if not isinstance(result, BaseModel):
            _logger.error(f"{result} is not a recordset")
            raise InternalServerError(_("Unexpected result"))

        serializer = service.env["ir.serializer"].find_by_code(self.serializer_code)
        if not serializer:
            raise InternalServerError(_("No serializer"))

        serializer = serializer.with_context(
            include_empty_keys=serializer.include_empty_keys,
            raise_on_duplicate=serializer.raise_on_duplicate,
        )

        if self.is_list:
            return list(map(serializer._serialize, result))

        if len(result) != 1:
            _logger.error(f"Expected a recordset wit length 1 or None: {result}")
            raise BadRequest()

        return serializer._serialize(result)

    def to_openapi_query_parameters(self, service, spec) -> dict:
        return {}

    def to_openapi_requestbody(self, service, spec) -> dict:
        return {
            "content": {
                "application/json": {
                    "schema": self.to_json_schema(service, spec, "importing")
                }
            }
        }

    def to_openapi_responses(self, service, spec) -> dict:
        return {
            "200": {
                "content": {
                    "application/json": {
                        "schema": self.to_json_schema(service, spec, "exporting")
                    }
                }
            }
        }

    def to_json_schema(self, service, spec, direction) -> dict:
        serializer = service.env["ir.serializer"].find_by_code(self.serializer_code)
        if not serializer:
            return {}

        field_dom = [("field_id.ttype", "in", ("many2one", "many2many", "one2many"))]
        schema_dom = [("type", "=", "serializer")]

        schemes = set()
        stack = [serializer]
        while stack:
            serial = stack.pop()
            if serial in schemes:
                continue
            schemes.add(serial)

            fields = serial.field_ids.filtered_domain(field_dom)
            stack.extend(fields.mapped("related_serializer_id"))

            schema = serial.schema_ids.filtered_domain(schema_dom)
            stack.extend(schema.mapped("related_serializer_id"))

            ref = serial.api_reference()
            if ref not in spec.components.schemas:
                spec.components.schema(ref, serial.to_schema(direction))

        schema = {"$ref": f"#/components/schemas/{serializer.api_reference()}"}
        if self.is_list:
            return {"type": "array", "items": schema}
        return schema


restapi.Serializer = Serializer
