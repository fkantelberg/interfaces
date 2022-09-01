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
    def mqtt_blacklisted(self):
        """Disable the MQTT events for specific models to prevent an impact to basic
        structures and spam"""
        return self._name.startswith("ir.") or self._name == "mqtt.message"

    @api.model
    def mqtt_publish(
        self,
        topic,
        payload,
        qos="0",
        retain=False,
        enqueue=True,
        skip_empty_payload=False,
    ):
        """Helper function to publish a new message"""
        if skip_empty_payload and not payload:
            return self.env["mqtt.message"].browse()

        if not isinstance(payload, str):
            payload = json.dumps(payload, cls=Encoder)

        return self.env["mqtt.message"].create(
            {
                "direction": "outgoing",
                "state": "enqueued" if enqueue else "draft",
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
        if self.mqtt_blacklisted():
            return records

        # Generate messages for defined events
        etype = self.sudo().env.ref("mqtt.type_create", False)
        if not etype or not records:
            return records

        domain = [("model", "=", self._name), ("type_ids", "=", etype.id)]
        for event in self.env["mqtt.event"].sudo().search(domain):
            fields = set(event.mapped("field_ids.name"))
            fields.update(["create_date", "create_uid"])
            self.sudo().mqtt_publish(
                event.convert_topic(etype),
                payload=event.to_payload(records, fields),
                qos=event.qos,
                retain=event.retain,
                skip_empty_payload=True,
            )

        return records

    def write(self, vals):
        res = super().write(vals)
        if self.mqtt_blacklisted():
            return res

        # Generate messages for defined events
        etype = self.sudo().env.ref("mqtt.type_write", False)
        if not etype:
            return res

        domain = [("model", "=", self._name), ("type_ids", "=", etype.id)]
        for event in self.env["mqtt.event"].sudo().search(domain):
            fields = set(event.mapped("field_ids.name"))
            if event.changes_only:
                fields = fields.intersection(vals)

            if fields:
                fields.update(("write_date", "write_uid"))
                self.sudo().mqtt_publish(
                    event.convert_topic(etype),
                    payload=event.to_payload(self, fields),
                    qos=event.qos,
                    retain=event.retain,
                    skip_empty_payload=True,
                )

        return res

    def unlink(self):
        if self.mqtt_blacklisted():
            return super().unlink()

        # Generate messages for defined events
        etype = self.sudo().env.ref("mqtt.type_delete", False)
        if not etype:
            return super().unlink()

        domain = [("model", "=", self._name), ("type_ids", "=", etype.id)]
        for event in self.env["mqtt.event"].sudo().search(domain):
            fields = set(event.mapped("field_ids.name"))
            self.sudo().mqtt_publish(
                event.convert_topic(etype),
                payload=event.to_payload(self, fields),
                qos=event.qos,
                retain=event.retain,
                skip_empty_payload=True,
            )

        return super().unlink()
