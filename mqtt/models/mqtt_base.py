# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import inspect

from odoo import _, fields, models


def is_mqtt(func):
    return callable(func) and getattr(func, "_mqtt", False)


class MQTTBase(models.AbstractModel):
    _name = "mqtt.base"
    _description = _("MQTT Base Model")
    _rec_name = "topic"
    _order = "topic"

    def _get_qos(self):
        return [
            ("0", _("At Most Once")),
            ("1", _("At Least Once")),
            ("2", _("Exactly Once")),
        ]

    topic = fields.Char(required=True)
    qos = fields.Selection("_get_qos", "Quality of Service", default="0")

    def _mqtt_functions(self):
        for model in self.env.values():
            for attr, func in inspect.getmembers(type(model), is_mqtt):
                yield model, attr, func
