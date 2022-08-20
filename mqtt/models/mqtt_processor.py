# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import safe_eval


class MQTTProcessor(models.Model):
    _name = "mqtt.processor"
    _description = _("MQTT Processor")

    def _get_default_code(self):
        variables = self.default_variables()
        desc = "\n".join(f"# - {v}: {desc}" for v, desc in variables.items())
        return f"# Possible variables:\n{desc}\n\n"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one("ir.model", ondelete="cascade", required=True)
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        help="User which executes the processing",
    )
    topic = fields.Char(
        required=True,
        help="Subscribed topic. MQTT wildcards with # and + are allowed",
    )
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
            "client_id": "The ID of the MQTT client",
            "env": "Odoo Environment on which the processing is triggered",
            "messages": "The messages to process",
            "model": "Odoo Model on whoch the processing is triggered",
            "datetime, time": "useful Python libraries",
            "UserError": "Warning Exception to use with raise",
        }

    def _get_model(self):
        self.ensure_one()
        return self.env[self.model_id.model].with_user(self.user_id)

    def _get_eval_context(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        return {
            "client_id": icp.get_param("mqtt.uuid", None),
            "datetime": safe_eval.datetime,
            "env": self.env(user=self.user_id),
            "model": self._get_model(),
            "time": safe_eval.time,
            "UserError": UserError,
        }

    def process(self, messages):
        self.ensure_one()
        if not messages:
            return

        context = self._get_eval_context()
        context["messages"] = messages.with_user(self.user_id)
        safe_eval.safe_eval(self.code, context, mode="exec", nocopy=True)
