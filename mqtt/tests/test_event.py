# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestEvent(TransactionCase):
    def setUp(self):
        super().setUp()
        self.event = self.env["mqtt.event"].create(
            {
                "model_id": self.env.ref("base.model_res_partner").id,
                "topic": "odoo/partner/create",
                "type_ids": [(4, self.env.ref("mqtt.type_write").id)],
            }
        )

    def test_topic(self):
        self.event._onchange_topic()

        self.event.topic = "odoo/#/create"
        with self.assertRaises(ValidationError):
            self.event._onchange_topic()

    def test_events_active(self):
        with self.assertRaises(ValidationError):
            self.event.write({"active": True, "type_ids": [(6, 0, [])]})

    def test_events_duplicate_topic(self):
        self.event.active = True

        event = self.event.copy()
        self.assertFalse(event.active)

        with self.assertRaises(ValidationError):
            event.write({"active": True})
