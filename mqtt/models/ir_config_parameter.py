# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import uuid

from odoo import models


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    def init(self, force=False):
        res = super().init(force=force)

        params = self.sudo().search([("key", "=", "mqtt.uuid")])
        if force or not params:
            params.set_param("mqtt.uuid", str(uuid.uuid4()))

        return res
