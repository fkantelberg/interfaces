# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestClient(TransactionCase):
    def setUp(self):
        super().setUp()

        self.event = self.env["mqtt.event"].create(
            {
                "model_id": self.env.ref("base.model_res_users").id,
                "topic": "odoo/login",
                "active": True,
                "type_ids": [(4, self.env.ref("mqtt_login.type_login").id)],
            }
        )

    def test_mqtt_login(self):
        before = self.env["mqtt.message"].search_count([])
        self.env.user._mqtt_login_events()
        after = self.env["mqtt.message"].search_count([])
        self.assertTrue(before < after)
