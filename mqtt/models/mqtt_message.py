# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import inspect
import json
import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessDenied, ValidationError

_logger = logging.getLogger(__name__)

DEFAULT_GC_HOURS = 12


def is_mqtt(func):
    return callable(func) and getattr(func, "_mqtt", False)


class MQTTMessage(models.Model):
    _name = "mqtt.message"
    _inherit = ["mqtt.base"]
    _description = _("MQTT Message")
    _order = "create_date DESC"

    def _get_states(self):
        return [
            ("draft", _("Draft")),
            ("enqueued", _("Enqueued")),
            ("processed", _("Processed")),
        ]

    def _get_directions(self):
        return [
            ("incoming", _("Incoming")),
            ("outgoing", _("Outgoing")),
        ]

    state = fields.Selection("_get_states", required=True, default="draft")
    direction = fields.Selection("_get_directions", default="outgoing", readonly=True)
    enqueue_date = fields.Datetime(readonly=True)
    process_date = fields.Datetime(readonly=True)
    topic = fields.Char(
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    payload = fields.Text(
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    qos = fields.Selection(
        default="0",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    retain = fields.Boolean(
        default=False,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    subscriber = fields.Integer(
        compute="_compute_subscriber",
        store=False,
        help="The number of subscribed functions to the topic of the message",
    )

    @api.onchange("topic")
    def _onchange_topic(self):
        if any(k in (self.topic or "") for k in "#+"):
            raise ValidationError(_("Topic can't include # or + as character"))

    def _compute_subscriber(self):
        """Counter the number of subscriber for a message"""
        subs = {rec: 0 for rec in self}

        # Subscribing only works for incoming messages
        messages = self.filtered_domain([("direction", "=", "incoming")])
        for model in self.sudo().env.values():
            for attr, func in inspect.getmembers(type(model), is_mqtt):
                _logger.debug(f"Calling {model}.{attr}()")

                subbed = messages._filter_by_subscription(func._mqtt)
                for rec in subbed:
                    subs[rec] += 1

        for consumer in self.env["mqtt.consumer"].search([]):
            subbed = messages._filter_by_subscription(consumer.topic)
            for rec in subbed:
                subs[rec] += 1

        for rec, counter in subs.items():
            rec.subscriber = counter

    def json(self):
        """Interpret the payload as json"""
        self.ensure_one()
        return json.loads(self.payload) if self.payload else None

    @api.autovacuum
    def _gc_messages(self):
        """Garbage collection for messages"""
        param = self.env["ir.config_parameter"].get_param

        directions = param("mqtt.message_vacuum", None)
        if not directions:
            return

        try:
            hours = int(param("mqtt.message_vacuum_hours", DEFAULT_GC_HOURS))
        except ValueError:
            hours = DEFAULT_GC_HOURS

        domain = [
            ("write_date", "<", datetime.now() - timedelta(hours=hours)),
            ("state", "=", "processed"),
            ("direction", "in", directions.split(",")),
        ]
        self.search(domain).unlink()

    @api.model
    def _convert_subscription(self, subscription):
        """Convert the subscription wildcard into a regex expression"""
        pattern = []
        for part in subscription.split("/"):
            if part == "+":
                pattern.append(r"[^/]*")
            elif part == "#":
                pattern.append(r".*")
                return fr"^{r'/'.join(pattern)}$"
            elif any(k in part for k in "+#"):
                return False
            else:
                pattern.append(part.replace("$", r"\$"))

        return fr"^{r'/'.join(pattern)}$"

    def _filter_by_subscription(self, subscription):
        """Filter the recordset by the MQTT wildcard"""
        if not self:
            return self

        pattern = self._convert_subscription(subscription)
        if not pattern:
            return self.browse()

        query = "SELECT id FROM mqtt_message WHERE topic ~ %s AND id IN %s"
        self.env.cr.execute(query, (pattern, tuple(self.ids)))
        ids = self.env.cr.fetchall()
        return self.browse([x[0] for x in ids])

    def _run_mqtt_router_api(self, messages):
        now = datetime.now()
        for model in self.env.values():
            for attr, func in inspect.getmembers(type(model), is_mqtt):
                _logger.debug(f"Calling {model}.{attr}()")

                subbed = messages._filter_by_subscription(func._mqtt)
                if not subbed:
                    continue

                try:
                    # Make the messages appear to be newly received if
                    # multiple routes are used for the same message
                    subbed.write({"state": "enqueued"})
                    func(model, subbed.with_context(mqtt_lock=True))
                    subbed.write({"state": "processed", "process_date": now})
                    self.env.cr.commit()
                except Exception:
                    _logger.exception(f"Failed {model}.{attr}()")
                    self.env.cr.rollback()

    def _run_mqtt_router_consumer(self, messages):
        now = datetime.now()
        for consumer in self.env["mqtt.consumer"].search([]):
            subbed = messages._filter_by_subscription(consumer.topic)
            if not subbed:
                continue

            try:
                # Make the messages appear to be newly received if
                # multiple routes are used for the same message
                subbed.write({"state": "enqueued"})
                consumer.process(subbed.with_context(mqtt_lock=True))
                subbed.write({"state": "processed", "process_date": now})
                self.env.cr.commit()
            except Exception as e:
                _logger.exception(e)
                self.env.cr.rollback()

    def _run_mqtt_router(self):
        """Route the newly received messages"""
        if not self.env.is_admin():
            raise AccessDenied()

        domain = [("state", "=", "enqueued"), ("direction", "=", "incoming")]
        messages = self.search(domain)
        self._run_mqtt_router_api(messages)
        self._run_mqtt_router_consumer(messages)

    def action_enqueue(self):
        recs = self.filtered_domain([("state", "=", "draft")])
        recs.write({"state": "enqueued", "enqueue_date": datetime.now()})

    def write(self, vals):
        """Lock any changes to the messages to prevent side-effects if multiple
        subscriber for a topic exist but if the subscribing function try to write
        to the messages"""
        if self.env.context.get("mqtt_lock"):
            return True
        return super().write(vals)
