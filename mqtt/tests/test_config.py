from odoo.tests import TransactionCase


class TestConfig(TransactionCase):
    def setUp(self):
        super().setUp()
        self.config = self.env["res.config.settings"].create({})

    def test_get_config(self):
        icp = self.env["ir.config_parameter"]

        icp.set_param("mqtt.message_vacuum", "")
        icp.set_param("mqtt.message_vacuum_hours", "a")
        vals = self.config.get_values()
        self.assertFalse(vals["mqtt_gc_incoming"])
        self.assertFalse(vals["mqtt_gc_outgoing"])
        self.assertEqual(vals["mqtt_gc_hours"], 12)

        icp.set_param("mqtt.message_vacuum", "incoming,outgoing")
        icp.set_param("mqtt.message_vacuum_hours", "15")
        vals = self.config.get_values()
        self.assertTrue(vals["mqtt_gc_incoming"])
        self.assertTrue(vals["mqtt_gc_outgoing"])
        self.assertEqual(vals["mqtt_gc_hours"], 15)

    def test_set_config(self):
        self.config.write(
            {
                "mqtt_gc_incoming": True,
                "mqtt_gc_outgoing": True,
                "mqtt_gc_hours": 42,
            }
        )
        self.config.set_values()
        vals = self.config.get_values()
        self.assertTrue(vals["mqtt_gc_incoming"])
        self.assertTrue(vals["mqtt_gc_outgoing"])
        self.assertEqual(vals["mqtt_gc_hours"], 42)
