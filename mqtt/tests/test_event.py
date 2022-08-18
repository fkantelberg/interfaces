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

    def test_blacklisting(self):
        self.event._onchange_model()

        self.event.model_id = self.env.ref("base.model_ir_model")
        with self.assertRaises(ValidationError):
            self.event._onchange_model()

    def test_help(self):
        self.assertIn("records", self.event._get_default_code())
        self.assertIn("<code>records</code>", self.event.help_text)

    def test_events_active(self):
        with self.assertRaises(ValidationError):
            self.event.write({"active": True, "type_ids": [(6, 0, [])]})

    def test_events_duplicate_topic(self):
        self.event.active = True

        event = self.event.copy()
        self.assertFalse(event.active)

        with self.assertRaises(ValidationError):
            event.write({"active": True})

    def test_to_payload(self):
        partner = self.env["res.partner"].create({"name": "testing", "city": "Test"})
        payload = self.event.to_payload(partner)
        self.assertEqual(payload[0]["id"], partner.id)
        self.assertNotIn("name", payload[0])

        payload = self.event.to_payload(partner, ["name"])
        self.assertEqual(payload[0]["id"], partner.id)
        self.assertEqual(payload[0]["name"], "testing")

        filt = self.env["ir.filters"].create(
            {
                "name": "test filter",
                "model_id": "res.partner",
                "domain": "[('name', '=', 'abc')]",
            }
        )
        self.event.filter_id = filt.id

        self.assertFalse(self.event.to_payload(partner))

        partner.name = "abc"
        self.assertTrue(self.event.to_payload(partner))

        self.event.write(
            {
                "mapping": "code",
                "code": "result = 42",
            }
        )
        self.assertEqual(self.event.to_payload(partner), 42)
