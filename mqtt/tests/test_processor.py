# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestProcessor(TransactionCase):
    def setUp(self):
        super().setUp()

        self.messages = self.env["mqtt.message"]
        self.proc = self.env["mqtt.processor"].create(
            {
                "name": "Testing processor",
                "model_id": self.env.ref("base.model_res_partner").id,
                "topic": "testing/#",
                "code": "raise UserError('abc')",
            }
        )

    def test_help(self):
        self.assertIn("env", self.proc._get_default_code())
        self.assertIn("<code>env</code>", self.proc.help_text)

    def test_processing(self):
        self.proc.process(self.messages.browse())
        message = self.messages.create({"topic": "testing/b/b/c"})
        with self.assertRaises(UserError):
            self.proc.process(message)

    def test_context(self):
        ctx = self.proc._get_eval_context()
        self.assertEqual(ctx["env"].user, self.env.user)
        self.assertEqual(ctx["model"].env.user, self.env.user)
        self.assertEqual(self.proc.user_id, self.env.user)

        self.proc.user_id = self.env.ref("base.user_admin")
        ctx = self.proc._get_eval_context()
        self.assertNotEqual(ctx["env"].user, self.env.user)
        self.assertNotEqual(ctx["model"].env.user, self.env.user)
        self.assertNotEqual(self.proc.user_id, self.env.user)
