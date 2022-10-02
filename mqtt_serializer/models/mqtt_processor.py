# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MQTTProcessor(models.Model):
    _inherit = "mqtt.processor"

    serializer_id = fields.Many2one(
        "ir.serializer",
        domain="[('model_id', '=', model_id)]",
    )

    def _get_eval_context(self):
        ctx = super()._get_eval_context()
        if self.serializer_id:
            ctx["serializer"] = self.serializer_id
        return ctx
