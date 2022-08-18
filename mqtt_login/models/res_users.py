# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api, models
from odoo.http import request


class ResUsers(models.Model):
    _inherit = "res.users"

    @classmethod
    def _login(cls, *args, **kwargs):
        res = super()._login(*args, **kwargs)
        with cls.pool.cursor() as cr:
            user = api.Environment(cr, SUPERUSER_ID, {})[cls._name].browse(res)
            user._mqtt_login_events()
        return res

    def _mqtt_login_events(self):
        self.ensure_one()
        payload = {
            "login": self.login,
            "ip": request.httprequest.environ["REMOTE_ADDR"] if request else "n/a",
            "login_date": self.login_date,
        }

        etype = self.env.ref("mqtt_login.type_login")
        domain = [("model", "=", self._name), ("type_ids", "=", etype.id)]
        for event in self.env["mqtt.event"].search(domain):
            self.mqtt_publish(
                event.topic,
                payload=payload,
                qos=event.qos,
                retain=event.retain,
            )
