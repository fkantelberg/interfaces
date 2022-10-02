# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from datetime import date, datetime

from odoo import _, api, fields, models


class Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return fields.Datetime.to_string(o)
        if isinstance(o, date):
            return fields.Date.to_string(o)


class SerializerPreview(models.TransientModel):
    _name = "ir.serializer.preview"
    _description = _("Serializer Preview")

    @api.model
    def _selection_target_model(self):
        return [
            (model.model, model.name)
            for model in self.env["ir.model"].sudo().search([])
        ]

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)
        if not result.get("serializer_id") or "resource_ref" not in fields:
            return result

        serializer = self.env["ir.serializer"].browse(result["serializer_id"])
        res = self.env[serializer.model_id.model].search([], limit=1)
        if res:
            result["resource_ref"] = f"{res._name},{res.id}"
        return result

    serializer_id = fields.Many2one("ir.serializer", required=True)
    exporting = fields.Boolean(related="serializer_id.exporting")
    importing = fields.Boolean(related="serializer_id.importing")
    model_id = fields.Many2one("ir.model", related="serializer_id.model_id")
    resource_ref = fields.Reference(
        string="Record",
        selection="_selection_target_model",
        readonly=False,
    )
    serialized = fields.Text()
    deserialized = fields.Text()
    matching = fields.Integer("Matching Records", readonly=True)
    message = fields.Text(readonly=True)

    @api.onchange("resource_ref")
    def _onchange_serialized(self):
        if self.resource_ref:
            d = self.serializer_id._serialize(self.resource_ref)
            self.serialized = json.dumps(
                d,
                indent=2,
                skipkeys=True,
                sort_keys=True,
                cls=Encoder,
            )
            self._onchange_deserialized()
        else:
            self.serialized = ""

    @api.onchange("serialized")
    def _onchange_deserialized(self):
        if not self.serialized:
            return

        try:
            data = json.loads(self.serialized)
            self.deserialized = json.dumps(
                self.serializer_id._deserialize(data),
                indent=2,
                skipkeys=True,
                sort_keys=True,
                cls=Encoder,
            )
            self._onchange_matching()
        except Exception as e:
            self.message = str(e)

    @api.onchange("deserialized")
    def _onchange_matching(self):
        if not self.deserialized:
            self.message = ""
            self.matching = 0
            return

        try:
            data = json.loads(self.deserialized)
            domain = self.serializer_id._get_import_domain(data)
            self.matching = self.env[self.model_id.model].search_count(domain)
            self.message = ""
        except Exception as e:
            self.message = str(e)
            self.matching = 0
