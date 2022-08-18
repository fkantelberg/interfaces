# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models


class MQTTSubscription(models.Model):
    _name = "mqtt.subscription"
    _inherit = ["mqtt.base"]
    _description = _("MQTT Subscriptions")

    active = fields.Boolean(default=True)
    topic = fields.Char(
        help="The topic under which messages will get published. Use {client} to "
        "insert the ID of the MQTT client",
    )
