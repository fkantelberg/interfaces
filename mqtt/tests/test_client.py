# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import MagicMock

from odoo import api
from odoo.tests import TransactionCase
from odoo.tools import config

from ..runner.client import MQTTRunner, to_bool


class TestClient(TransactionCase):
    def setUp(self):
        super().setUp()
        self.runner = MQTTRunner()
        self.runner.subscriptions.add("odoo/#")
        self.runner.cursor = MagicMock()
        self.runner.cursor.return_value.__enter__.return_value = self.env.cr

    def test_bool(self):
        self.assertTrue(to_bool(1))
        self.assertTrue(to_bool(True))
        self.assertTrue(to_bool("TrUe"))
        self.assertTrue(to_bool("1"))
        self.assertTrue(to_bool("yes"))
        self.assertFalse(to_bool(0))
        self.assertFalse(to_bool(False))
        self.assertFalse(to_bool("FALSE"))
        self.assertFalse(to_bool("invalid"))
        self.assertFalse(to_bool(""))

    def test_context(self):
        with self.runner.env() as env:
            self.assertTrue(isinstance(env, api.Environment))

    def test_installed(self):
        self.assertTrue(self.runner._has_mqtt())

    def test_callback(self):
        before = self.env["mqtt.message"].search_count([])
        self.runner._message_callback(
            None,
            None,
            MagicMock(
                topic="odoo/testing",
                payload="testing",
                qos=0,
                retain=False,
            ),
        )
        after = self.env["mqtt.message"].search_count([])
        self.assertTrue(after > before)

        # Connect/disconnect will reset the subscriptions
        self.runner.subscriptions.add("odoo/#")
        self.runner._connect_callback()
        self.assertFalse(self.runner.subscriptions)
        self.runner.subscriptions.add("odoo/#")
        self.runner._disconnect_callback()
        self.assertFalse(self.runner.subscriptions)

    def test_publish(self):
        self.runner.client = MagicMock()
        mock = self.runner.client.publish = MagicMock()
        mock.return_value.rc = 0

        msg = self.env["mqtt.message"].create(
            {
                "state": "enqueued",
                "direction": "outgoing",
                "topic": "odoo/testing",
                "payload": "testing payload",
            }
        )

        msg.flush()
        self.runner.publish()
        mock.assert_called_once()

        self.env.cr.execute(
            "SELECT 1 FROM mqtt_message WHERE id = %s AND state = 'processed'",
            (msg.id,),
        )
        self.assertTrue(self.env.cr.fetchone())

        self.runner.publish()
        mock.assert_called_once()

    def test_subscription(self):
        ret = 0, None
        self.runner.client = MagicMock()
        subscribe = self.runner.client.subscribe = MagicMock(return_value=ret)
        unsubscribe = self.runner.client.unsubscribe = MagicMock(return_value=ret)

        self.runner.subscribe()
        unsubscribe.assert_called_once()
        self.assertFalse(self.runner.subscriptions)

        self.env["mqtt.subscription"].create({"topic": "odoo/testing/#"})
        self.runner.subscribe()
        subscribe.assert_called_once()
        self.assertEqual(self.runner.subscriptions, {"odoo/testing/#"})

    def test_connect(self):
        config.misc["mqtt"] = {
            "host": "abc",
            "username": "tester",
            "will_topic": "dying",
        }
        self.assertTrue(self.runner.connect())

        config.misc["mqtt"] = {}
        self.assertFalse(self.runner.connect())
