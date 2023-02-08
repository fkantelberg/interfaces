# © 2023 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SerializerField(models.Model):
    _inherit = "ir.serializer.field"

    def to_schema(self):
        schema = {}
        for rec in self:
            fname = rec.name or rec.field_id.name
            field = rec.field_id

            if field.ttype == "boolean":
                schema[fname] = {"type": "boolean"}
            elif field.ttype in ("char", "html", "text"):
                schema[fname] = {"type": "string"}
            elif field.ttype == "selection":
                schema[fname] = {
                    "type": "string",
                    "enum": [sel.value for sel in field.selection_ids],
                }
            elif field.ttype in ("float", "monetary"):
                schema[fname] = {"type": "number"}
            elif field.ttype == "integer":
                schema[fname] = {"type": "integer"}
            elif field.ttype == "date":
                schema[fname] = {"type": "string", "format": "date"}
            elif field.ttype == "datetime":
                schema[fname] = {"type": "string", "format": "date-time"}
            elif field.ttype == "many2one":
                ref = rec.related_serializer_id.api_reference()
                schema[fname] = {"$ref": f"#/components/schemas/{ref}"}
            elif field.ttype in ("one2many", "many2many"):
                ref = rec.related_serializer_id.api_reference()
                schema[fname] = {
                    "type": "array",
                    "items": {"$ref": f"#/components/schemas/{ref}"},
                }
            else:
                _logger.warning(f"Schema not supported for {field.ttype}")
                continue

        return schema
