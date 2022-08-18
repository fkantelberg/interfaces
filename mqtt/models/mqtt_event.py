# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from uuid import uuid4

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import config, safe_eval

_logger = logging.getLogger(__name__)


class MQTTEventType(models.Model):
    _name = "mqtt.event.type"
    _description = _("MQTT event types")

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, readonly=True)
    model_ids = fields.Many2many("ir.model", readonly=True)

    _sql_constraints = [
        ("name_uniq", "UNIQUE(name)", _("The type must be unique")),
    ]

    def name_get(self):
        return [
            (rec.id, f"{rec.name} ({rec.code})" if rec.code else rec.name)
            for rec in self
        ]


class MQTTEvent(models.Model):
    _name = "mqtt.event"
    _inherit = ["mqtt.base"]
    _description = _("MQTT event to automatically generate messages")
    _rec_name = "topic"
    _order = "topic"

    def _get_mappings(self):
        return [
            ("simple", _("Simple")),
            ("code", _("Code")),
        ]

    def _get_default_code(self):
        variables = self.default_variables()
        desc = "\n".join(f"# - {v}: {desc}" for v, desc in variables.items())
        return f"# Possible variables:\n{desc}\n\n"

    model_id = fields.Many2one("ir.model", ondelete="cascade", required=True)
    active = fields.Boolean(default=False, copy=False)
    topic = fields.Char(
        help="The topic under which messages will get published. Use {code} to "
        "insert the code from the event type. Use {client} to insert the ID of the "
        "MQTT client",
    )
    mapping = fields.Selection("_get_mappings", default="simple", required=True)
    model = fields.Char("Model Name", related="model_id.model", store=True, index=True)
    filter_id = fields.Many2one("ir.filters")
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
    help_text = fields.Html(compute="_compute_help_text", readonly=True, store=False)
    code = fields.Text(default=lambda self: self._get_default_code())

    def _compute_help_text(self):
        variables = self.default_variables()
        lines = []
        for var, desc in variables.items():
            var = (f"<code>{v.strip()}</code>" for v in var.split(","))
            lines.append(f"<li>{', '.join(sorted(var))}: {desc}</li>")

        desc = "\n".join(lines)
        self.write({"help_text": f"<ul>{desc}</ul>"})

    @api.model
    def default_variables(self):
        """Informations about the available variables in the python code"""
        return {
            "records": "The records to convert",
            "fields": "Fields to include",
            "result": "The output to put into the payload",
            "datetime, time": "useful Python libraries",
            "UserError": "Warning Exception to use with raise",
        }

    @api.onchange("topic")
    def _onchange_topic(self):
        if self.topic and any(k in self.topic for k in "#+"):
            raise ValidationError(_("Topic can't include # or + as character"))

    @api.onchange("model_id")
    def _onchange_model(self):
        if self.model_id:
            model = self.env[self.model_id.model]
            if model.mqtt_blacklisted():
                raise ValidationError(
                    _("Model is blacklisted and can't be used for an event")
                )

    def _get_eval_context(self):
        self.ensure_one()
        return {
            "datetime": safe_eval.datetime,
            "time": safe_eval.time,
        }

    def convert_topic(self, event_type):
        self.ensure_one()
        topic = self.topic.replace("{code}", event_type.code)
        # If no client_id isn't set just generate new onces
        client_id = config.misc.get("mqtt", {}).get("client_id")
        topic = topic.replace("{client}", client_id or str(uuid4()))
        return topic

    def to_payload(self, records, fields=None):
        self.ensure_one()

        if self.filter_id:
            records = records.filtered_domain(self.filter_id._get_eval_domain())

        if not fields:
            fields = {"id", "create_date", "write_date", "create_uid", "write_uid"}
            fields.update(self.mapped("field_ids.name"))

        if self.mapping == "code":
            context = self._get_eval_context()
            context.update({"records": records, "fields": fields})
            safe_eval.safe_eval(self.code, context, mode="exec", nocopy=True)
            return context.get("result", None)

        return records.read(fields)

    def write(self, vals):
        res = super().write(vals)
        for rec in self.filtered("active"):
            if not rec.type_ids:
                raise ValidationError(_("The event must set atleast one type"))

            domain = [("topic", "=", rec.topic), ("active", "=", True)]
            if self.search_count(domain) > 1:
                raise ValidationError(_("Topic must be unique"))

        return res
