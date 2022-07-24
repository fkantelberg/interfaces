from odoo import SUPERUSER_ID, api, models
from odoo.http import request


class ResUsers(models.Model):
    _inherit = "res.users"

    @classmethod
    def _login(cls, *args, **kwargs):
        res = super()._login(*args, **kwargs)

        with cls.pool.cursor() as cr:
            user = api.Environment(cr, SUPERUSER_ID, {})[cls._name].browse(res)

            payload = {
                "login": user.login,
                "ip": request.httprequest.environ["REMOTE_ADDR"] if request else "n/a",
                "login_date": user.login_date,
            }

            etype = user.env.ref("mqtt_login.type_login")
            domain = [("model", "=", user._name), ("type_ids", "=", etype.id)]
            for event in user.env["mqtt.event"].search(domain):
                user.mqtt_publish(
                    event.topic,
                    payload=payload,
                    qos=event.qos,
                    retain=event.retain,
                )

        return res
