
from odoo import _, fields, models


class MQTTSubscription(models.Model):
    _name = "mqtt.subscription"
    _inherit = ["mqtt.base"]
    _description = _("MQTT Subscriptions")

    active = fields.Boolean(default=True)
