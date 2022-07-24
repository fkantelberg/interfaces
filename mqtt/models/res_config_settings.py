from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mqtt_gc_incoming = fields.Boolean()
    mqtt_gc_outgoing = fields.Boolean()
    mqtt_gc_hours = fields.Integer()

    def get_values(self):
        res = super().get_values()
        icp = self.env["ir.config_parameter"].sudo()
        gc = icp.get_param("mqtt.message_vacuum", "").split(",")
        res.update({f"mqtt_gc_{d}": d in gc for d in ("incoming", "outgoing")})

        try:
            hours = int(icp.get_param("mqtt.message_vacuum_hours", 12))
        except ValueError:
            hours = 12

        res["mqtt_gc_hours"] = hours
        return res

    def set_values(self):
        gc = [d for d in ("incoming", "outgoing") if getattr(self, f"mqtt_gc_{d}")]

        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("mqtt.message_vacuum", ",".join(gc))
        icp.set_param("mqtt.message_vacuum_hours", str(self.mqtt_gc_hours))
