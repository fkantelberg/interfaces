# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessDenied, ValidationError

_logger = logging.getLogger(__name__)

DEFAULT_GC_HOURS = 12


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
    subscriptions = fields.Html(compute="_compute_subscription", translate=False)

    @api.onchange("topic")
    def _onchange_topic(self):
        if self.topic and any(k in self.topic for k in "#+"):
            raise ValidationError(_("Topic can't include # or + as character"))

    def _compute_subscriber(self):
        """Counter the number of subscriber for a message"""
        subs = {rec: 0 for rec in self}

        # Subscribing only works for incoming messages
        messages = self.filtered_domain([("direction", "=", "incoming")])
        for _model, _attr, func in self._mqtt_functions():
            subbed = messages._filter_by_subscription(func._mqtt)
            for rec in subbed:
                subs[rec] += 1

        for processor in self.env["mqtt.processor"].search([]):
            subbed = messages._filter_by_subscription(processor.topic)
            for rec in subbed:
                subs[rec] += 1

        for rec, counter in subs.items():
            rec.subscriber = counter

    def _compute_subscription(self):
        """Counter the number of subscriber for a message"""
        subs = {rec: defaultdict(set) for rec in self}

        # Subscribing only works for incoming messages
        messages = self.filtered_domain([("direction", "=", "incoming")])
        for _model, _attr, func in self._mqtt_functions():
            subbed = messages._filter_by_subscription(func._mqtt)
            for rec in subbed:
                subs[rec][_("API")].add(func._mqtt)

        for processor in self.env["mqtt.processor"].search([]):
            subbed = messages._filter_by_subscription(processor.topic)
            for rec in subbed:
                subs[rec][_("Processor")].add(processor.topic)

        for rec, subscriptions in subs.items():
            content = ""
            for title, topics in sorted(subscriptions.items()):
                content += f'<div class="o_horizontal_separator">{title}</div><ul>'
                content += "".join(f"<li>{t}</li>" for t in topics)
                content += "</ul>"
            rec.subscriptions = content

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
                return rf"^{r'/'.join(pattern)}$"
            elif any(k in part for k in "+#"):
                return False
            else:
                pattern.append(part.replace("$", r"\$"))

        return rf"^{r'/'.join(pattern)}$"

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
        for model, attr, func in self._mqtt_functions():
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
                # pylint: disable=E8102
                self.env.cr.commit()
            except Exception:
                _logger.exception(f"Failed {model}.{attr}()")
                self.env.cr.rollback()

    def _run_mqtt_router_processor(self, messages):
        now = datetime.now()
        for processor in self.env["mqtt.processor"].search([]):
            subbed = messages._filter_by_subscription(processor.topic)
            if not subbed:
                continue

            try:
                # Make the messages appear to be newly received if
                # multiple routes are used for the same message
                subbed.write({"state": "enqueued"})
                processor.process(subbed.with_context(mqtt_lock=True))
                subbed.write({"state": "processed", "process_date": now})
                # pylint: disable=E8102
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
        self._run_mqtt_router_processor(messages)

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
