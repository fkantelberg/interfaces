# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class MQTTEvent(models.Model):
    _inherit = "mqtt.event"

    def _get_mappings(self):
        return super()._get_mappings() + [("serializer", _("Serializer"))]

    serializer_id = fields.Many2one(
        "ir.serializer",
        domain="[('model_id', '=', model_id)]",
    )

    def _to_payload(self, records, fields=None):
        self.ensure_one()

        if self.mapping == "serializer":
            return self.serializer_id.serialize(records)

        return super()._to_payload(records, fields)
