# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from datetime import date, datetime

from odoo import api, fields, models


class Encoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return fields.Datetime.to_string(o)
        if isinstance(o, date):
            return fields.Date.to_string(o)


class Base(models.AbstractModel):
    _inherit = "base"

    @api.model
    def mqtt_publish(self, topic, payload, qos="0", retain=False):
        """Helper function to publish a new message"""
        if not isinstance(payload, str):
            payload = json.dumps(payload, cls=Encoder)

        return self.env["mqtt.message"].create(
            {
                "direction": "outgoing",
                "state": "enqueued",
                "enqueue_date": datetime.now(),
                "topic": topic,
                "payload": payload,
                "qos": qos,
                "retain": retain,
            }
        )

    @api.model_create_multi
    @api.returns("self", lambda value: value.id)
    def create(self, vals_list):
        records = super().create(vals_list)
        if self._name.startswith("ir.") and self._name != "mqtt.message":
            return records

        # Generate messages for defined events
        etype = self.sudo().env.ref("mqtt.type_create", False)
        if not etype or not records:
            return records

        domain = [("model", "=", self._name), ("type_ids", "=", etype.id)]
        for event in self.env["mqtt.event"].sudo().search(domain):
            print(records, etype, event)
            fields = event.mapped("field_ids.name") + ["create_date", "create_uid"]
            self.sudo().mqtt_publish(
                event.topic,
                payload=records.read(fields),
                qos=event.qos,
                retain=event.retain,
            )

        return records

    def write(self, vals):
        res = super().write(vals)
        if self._name.startswith("ir.") and self._name != "mqtt.message":
            return res

        # Generate messages for defined events
        etype = self.sudo().env.ref("mqtt.type_write", False)
        if not etype:
            return res

        domain = [("model", "=", self._name), ("type_ids", "=", etype.id)]
        for event in self.env["mqtt.event"].sudo().search(domain):
            fields = set(vals).intersection(event.mapped("field_ids.name"))
            if fields:
                fields.update(("write_date", "write_uid"))
                self.sudo().mqtt_publish(
                    event.topic,
                    payload=self.read(fields),
                    qos=event.qos,
                    retain=event.retain,
                )

        return res
