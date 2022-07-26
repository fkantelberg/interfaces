# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MQTTEventType(models.Model):
    _name = "mqtt.event.type"
    _description = _("MQTT event types")
    _rec_name = "name"

    name = fields.Char(required=True, translate=True)
    model_ids = fields.Many2many("ir.model")

    _sql_constraints = [
        ("name_uniq", "UNIQUE(name)", _("The type must be unique")),
    ]


class MQTTEvent(models.Model):
    _name = "mqtt.event"
    _inherit = ["mqtt.base"]
    _description = _("MQTT event to automatically generate messages")
    _rec_name = "topic"
    _order = "topic"

    model_id = fields.Many2one("ir.model", ondelete="cascade", required=True)
    active = fields.Boolean(default=False, copy=False)
    model = fields.Char("Model Name", related="model_id.model", store=True, index=True)
    field_ids = fields.Many2many(
        "ir.model.fields",
        domain="[('model_id', '=', model_id), ('relation', '=', False)]",
        help="Controls which fields are watched and are part of the payload",
    )
    type_ids = fields.Many2many(
        "mqtt.event.type",
        required=True,
        domain="['|', ('model_ids', '=', model_id), ('model_ids', '=', False)]",
        help="The type of the event to listen for the given model",
    )
    retain = fields.Boolean(default=False)

    @api.onchange("topic")
    def _onchange_topic(self):
        if self.topic and any(k in self.topic for k in "#+"):
            raise ValidationError(_("Topic can't include # or + as character"))

    def write(self, vals):
        res = super().write(vals)
        for rec in self.filtered("active"):
            if not rec.type_ids:
                raise ValidationError(_("The event must set atleast one type"))

            domain = [("topic", "=", rec.topic), ("active", "=", True)]
            if self.search_count(domain) > 1:
                raise ValidationError(_("Topic must be unique"))

        return res
