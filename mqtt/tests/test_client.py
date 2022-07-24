from odoo.tests import TransactionCase

from ..runner.client import MQTTRunner


class TestConfig(TransactionCase):
    def setUp(self):
        super().setUp()
        self.runner = MQTTRunner()

    def test_installed(self):
        self.assertTrue(self.runner._has_mqtt())
