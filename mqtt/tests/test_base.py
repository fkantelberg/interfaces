# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date, datetime

from odoo.tests import TransactionCase


class TestBase(TransactionCase):
    def setUp(self):
        super().setUp()

        model = self.env.ref("base.model_res_partner")
        fields = self.env.ref("base.field_res_partner__name")

        self.partner = self.env["res.partner"].create({"name": "old"})
        self.write_event = self.env["mqtt.event"].create(
            {
                "model_id": model.id,
                "active": True,
                "topic": "odoo/partner/write",
                "type_ids": [
                    (4, self.env.ref("mqtt.type_write").id),
                ],
                "field_ids": [(6, 0, fields.ids)],
            }
        )
        self.create_event = self.env["mqtt.event"].create(
            {
                "model_id": self.env.ref("base.model_res_partner").id,
                "active": True,
                "topic": "odoo/partner/create",
                "type_ids": [
                    (4, self.env.ref("mqtt.type_create").id),
                ],
                "field_ids": [(6, 0, fields.ids)],
            }
        )
        self.delete_event = self.env["mqtt.event"].create(
            {
                "model_id": self.env.ref("base.model_res_partner").id,
                "active": True,
                "topic": "odoo/partner/delete",
                "type_ids": [
                    (4, self.env.ref("mqtt.type_delete").id),
                ],
                "field_ids": [(6, 0, fields.ids)],
            }
        )

    def test_event_create(self):
        before = self.env["mqtt.message"].search_count([])
        self.partner.create({"name": "Test"})
        after = self.env["mqtt.message"].search_count([])
        self.assertTrue(after > before)

    def test_event_create_deleted(self):
        # Can happen during installation of modules
        domain = [("name", "=", "type_create"), ("module", "=", "mqtt")]
        self.env["ir.model.data"].search(domain).unlink()
        before = self.env["mqtt.message"].search_count([])
        self.partner.create({"name": "Test"})
        after = self.env["mqtt.message"].search_count([])
        self.assertEqual(after, before)

    def test_event_delete(self):
        p = self.partner.create({"name": "Test"})
        before = self.env["mqtt.message"].search_count([])
        p.unlink()
        after = self.env["mqtt.message"].search_count([])
        self.assertTrue(after > before)

    def test_event_delete_deleted(self):
        # Can happen during installation of modules
        p = self.partner.create({"name": "Test"})
        domain = [("name", "=", "type_delete"), ("module", "=", "mqtt")]
        self.env["ir.model.data"].search(domain).unlink()
        before = self.env["mqtt.message"].search_count([])
        p.unlink()
        after = self.env["mqtt.message"].search_count([])
        self.assertEqual(after, before)

    def test_event_write(self):
        before = self.env["mqtt.message"].search_count([])
        self.partner.write({"name": "Test"})
        after = self.env["mqtt.message"].search_count([])
        self.assertTrue(after > before)

    def test_event_write_deleted(self):
        # Can happen during installation of modules
        domain = [("name", "=", "type_write"), ("module", "=", "mqtt")]
        self.env["ir.model.data"].search(domain).unlink()
        before = self.env["mqtt.message"].search_count([])
        self.partner.write({"name": "Test"})
        after = self.env["mqtt.message"].search_count([])
        self.assertEqual(after, before)

    def test_publish(self):
        data = {"i": 0, "f": 0.5, "d": date(2022, 2, 2), "dt": datetime(2022, 2, 2)}
        self.partner.mqtt_publish("odoo/test", data)
        msg = self.env["mqtt.message"].search([], order="create_date DESC", limit=1)
        self.assertEqual(msg.topic, "odoo/test")
        self.assertEqual(
            msg.payload,
            '{"i": 0, "f": 0.5, "d": "2022-02-02", "dt": "2022-02-02 00:00:00"}',
        )
