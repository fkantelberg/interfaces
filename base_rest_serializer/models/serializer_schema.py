# © 2023 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class SerializerSchema(models.Model):
    _name = "ir.serializer.schema"
    _description = _("Schema of serializer")

    def _get_types(self):
        return [
            ("boolean", _("Boolean")),
            ("integer", _("Integer")),
            ("number", _("Number")),
            ("string", _("String")),
            ("selection", _("Selection")),
            ("serializer", _("Serializer")),
        ]

    def _get_str_formats(self):
        return [
            ("date", _("Date")),
            ("date-time", _("Datetime")),
        ]

    serializer_id = fields.Many2one("ir.serializer", required=True)
    name = fields.Char(required=True)
    type = fields.Selection("_get_types", required=True)
    str_format = fields.Selection("_get_str_formats")
    values = fields.Char(help="Values for the selection as comma-separated list")
    is_list = fields.Boolean()
    required = fields.Boolean()
    importing = fields.Boolean(default=True)
    exporting = fields.Boolean(default=True)
    related_serializer_id = fields.Many2one("ir.serializer")

    def to_schema(self):
        schema = {}
        for rec in self:
            if rec.type == "serializer":
                if not rec.related_serializer_id:
                    _logger.warning(f"Missing serializer for {rec}")
                    continue

                ref = rec.related_serializer_id.api_reference()
                obj = {"$ref": f"#/components/schemas/{ref}"}
                if rec.is_list:
                    schema[rec.name] = {"type": "array", "items": obj}
                else:
                    schema[rec.name] = obj
            elif rec.type == "selection":
                schema[rec.name] = {
                    "type": "string",
                    "enum": [x.strip() for x in rec.values.split(",")],
                }
            elif rec.type == "string":
                schema[rec.name] = {"type": rec.type}
                if rec.str_format:
                    schema[rec.name]["format"] = rec.str_format
            else:
                schema[rec.name] = {"type": rec.type}
        return schema
