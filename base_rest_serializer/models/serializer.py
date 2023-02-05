# © 2023 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Serializer(models.Model):
    _inherit = "ir.serializer"

    code = fields.Char(help="Unique code for this serializer referred by the API")
    schema_ids = fields.One2many("ir.serializer.schema", "serializer_id")

    @api.constrains("code")
    def _check_code(self):
        for rec in self.filtered("code"):
            if self.search_count([("code", "=", rec.code)]) > 1:
                raise ValidationError(_("Code must be unique"))

    def find_by_code(self, code):
        return self.search([("code", "=", code)])

    def api_reference(self):
        self.ensure_one()
        return f"{self.name}"

    def to_schema(self, direction):
        self.ensure_one()
        required = [rec.name for rec in self.schema_ids.filtered("required")]
        dir_domain = [(direction, "=", True)]
        props = self.schema_ids.filtered_domain(dir_domain).to_schema()

        for rec in self.field_ids.filtered_domain(dir_domain):
            fname = rec.name or rec.field_id.name
            field = rec.field_id
            if field.required:
                required.append(fname)

            if field.ttype == "boolean":
                props[fname] = {"type": "boolean"}
            elif field.ttype in ("char", "html", "text"):
                props[fname] = {"type": "string"}
            elif field.ttype == "selection":
                props[fname] = {
                    "type": "string",
                    "enum": [sel.value for sel in field.selection_ids],
                }
            elif field.ttype in ("float", "monetary"):
                props[fname] = {"type": "number"}
            elif field.ttype == "integer":
                props[fname] = {"type": "integer"}
            elif field.ttype == "date":
                props[fname] = {"type": "string", "format": "date"}
            elif field.ttype == "datetime":
                props[fname] = {"type": "string", "format": "date-time"}
            elif field.ttype == "many2one":
                ref = rec.related_serializer_id.api_reference()
                props[fname] = {"$ref": f"#/components/schemas/{ref}"}
            elif field.ttype in ("one2many", "many2many"):
                ref = rec.related_serializer_id.api_reference()
                props[fname] = {
                    "type": "array",
                    "items": {"$ref": f"#/components/schemas/{ref}"},
                }
            else:
                _logger.warning(f"Schema not supported for {field.ttype}")
                continue

        return {"type": "object", "required": required, "properties": props}
