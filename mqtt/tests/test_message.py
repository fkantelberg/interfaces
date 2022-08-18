# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from unittest.mock import MagicMock

from odoo import api, models
from odoo.exceptions import AccessDenied, ValidationError
from odoo.tests import TransactionCase


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.mqtt("testing/#")
    def mqtt_process(self, message):
        pass

    @api.mqtt("testing/#")
    def mqtt_process_2nd(self, message):
        raise AccessDenied()


class TestMessage(TransactionCase):
    def setUp(self):
        super().setUp()
        self.messages = self.env["mqtt.message"]
        self.messages |= self.messages.create({"topic": "testing/a/b/c"})
        self.messages |= self.messages.create({"topic": "testing/a/b/c/d"})
        self.messages |= self.messages.create({"topic": "testing/b/b/c"})
        self.messages |= self.messages.create(
            {"topic": "incoming/testing/a", "direction": "incoming"}
        )

    def _create_processor(self):
        return self.env["mqtt.processor"].create(
            {
                "name": "Testing processor",
                "model_id": self.env.ref("base.model_res_partner").id,
                "topic": "testing/#",
            }
        )

    def topic_test(self, messages, wildcard, size):
        self.assertEqual(len(messages._filter_by_subscription(wildcard)), size)

    def test_subscription(self):
        self.topic_test(self.messages, "#", 4)
        self.topic_test(self.messages, "testing/#", 3)
        self.topic_test(self.messages, "testing/+", 0)
        self.topic_test(self.messages, "testing/+/b/c", 2)
        self.topic_test(self.messages, "testing/a/b/c", 1)
        self.topic_test(self.messages.browse(), "#", 0)
        self.topic_test(self.messages, "testing/#a", 0)

    def test_lock(self):
        msg = self.messages[0]
        msg.with_context(mqtt_lock=True).topic = "testing/invalid"
        self.assertEqual(msg.topic, "testing/a/b/c")
        msg.with_context(mqtt_lock=False).topic = "testing/invalid"
        self.assertEqual(msg.topic, "testing/invalid")

    def test_enqueuing(self):
        self.messages.action_enqueue()
        self.assertEqual(set(self.messages.mapped("state")), {"enqueued"})

    def test_json(self):
        msg = self.messages[0]
        self.assertEqual(msg.json(), None)
        msg.payload = '{"valid": "json"}'
        self.assertEqual(msg.json(), {"valid": "json"})
        msg.payload = "{invalid json"
        with self.assertRaises(json.JSONDecodeError):
            msg.json()

    def test_subscriber(self):
        msg = self.messages[0]
        self.assertEqual(msg.subscriber, 0)

        msg._compute_subscriber()
        self.assertEqual(msg.subscriber, 0)

        msg.direction = "incoming"
        msg._compute_subscriber()
        self.assertEqual(msg.subscriber, 2)

        proc = self._create_processor()
        msg._compute_subscriber()
        self.assertEqual(msg.subscriber, 3)

        proc.topic = "invalid"
        msg._compute_subscriber()
        self.assertEqual(msg.subscriber, 2)

    def test_gc(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("mqtt.message_vacuum", "")
        icp.set_param("mqtt.message_vacuum_hours", "a")
        self.messages._gc_messages()
        self.assertTrue(self.messages.exists())

        icp.set_param("mqtt.message_vacuum", "incoming")
        self.messages._gc_messages()
        self.assertTrue(self.messages.exists())

        icp.set_param("mqtt.message_vacuum", "outgoing")
        self.messages._gc_messages()
        self.assertTrue(self.messages.exists())

        self.messages.write({"state": "processed"})
        icp.set_param("mqtt.message_vacuum_hours", "0")
        self.messages._gc_messages()
        self.assertEqual(len(self.messages.exists()), 1)

    def test_mqtt_router(self):
        user = self.env["res.users"].create(
            {"login": "mqtt_test", "email": "test@example.org", "name": "tester"}
        )

        with self.assertRaises(AccessDenied):
            self.messages.with_user(user)._run_mqtt_router()

        self.messages.env.cr.commit = MagicMock()
        self.messages.env.cr.rollback = MagicMock()
        self.messages.write({"state": "enqueued", "direction": "incoming"})
        self.messages._run_mqtt_router()

        self.messages.env.cr.commit.assert_called_once()
        self.messages.env.cr.rollback.assert_called_once()

    def test_mqtt_router_processor(self):
        self.messages.env.cr.commit = MagicMock()
        self.messages.env.cr.rollback = MagicMock()
        proc = self._create_processor()
        proc.topic = "proc/#"
        self.messages.write(
            {"state": "enqueued", "direction": "incoming", "topic": "proc/abc"}
        )
        self.messages._run_mqtt_router()

        self.messages.env.cr.commit.assert_called_once()

        proc.code = "raise UserError('abc')"
        self.messages.write({"state": "enqueued", "direction": "incoming"})
        self.messages._run_mqtt_router()
        self.messages.env.cr.rollback.assert_called_once()

    def test_publish(self):
        msg = self.messages.mqtt_publish("testing/new", {"pay": "load"})
        self.assertNotIn(msg, self.messages)
        self.assertEqual(msg.topic, "testing/new")
        self.assertEqual(msg.payload, '{"pay": "load"}')

    def test_onchange_topic(self):
        msg = self.messages[0]
        msg._onchange_topic()

        msg.topic = "odoo/#/create"
        with self.assertRaises(ValidationError):
            msg._onchange_topic()
