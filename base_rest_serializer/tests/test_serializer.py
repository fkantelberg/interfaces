# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import MagicMock

from werkzeug.exceptions import BadRequest, InternalServerError

from odoo.fields import Command
from odoo.tests import TransactionCase

from odoo.addons.base_rest.restapi import Serializer


class TestSerializerSchema(TransactionCase):
    def setUp(self):
        super().setUp()

        self.serializer = self.env["ir.serializer"].create(
            {
                "name": "Test Serializer",
                "code": "testing",
                "model_id": self.env.ref("base.model_res_partner").id,
                "use_sync_date": False,
                "raise_on_duplicate": True,
            }
        )
        self.ref = {"$ref": f"#/components/schemas/{self.serializer.name}"}
        self.partner = self.env["res.partner"].search([], limit=1)

    def _create_field(
        self, name, alias=None, importing=True, exporting=True, serializer=None
    ):
        return Command.create(
            {
                "name": alias,
                "field_id": self.env.ref(f"base.field_res_partner__{name}").id,
                "importing": importing,
                "exporting": exporting,
                "related_serializer_id": serializer.id if serializer else None,
            }
        )

    def _create_schema(
        self, name, ttype, importing=True, exporting=True, serializer=None, **kwargs
    ):
        return Command.create(
            {
                **kwargs,
                "name": name,
                "type": ttype,
                "importing": importing,
                "exporting": exporting,
                "related_serializer_id": serializer.id if serializer else None,
            }
        )

    def test_serializer_generation(self):
        self.serializer.field_ids = [
            self._create_field("id"),
            self._create_field("name"),
            self._create_field("date"),
            self._create_field("create_date"),
            self._create_field("ref", exporting=False),
            self._create_field("type"),
            self._create_field("active"),
            self._create_field("partner_latitude"),
            self._create_field("image_1024"),
            self._create_field("parent_id", serializer=self.serializer),
            self._create_field("child_ids", serializer=self.serializer),
        ]
        self.serializer.schema_ids = [
            self._create_schema("name", ttype="string", required=True),
            self._create_schema("custom_date", ttype="string", str_format="date"),
            self._create_schema("exp_only", ttype="boolean", importing=False),
            self._create_schema(
                "address_id", ttype="serializer", serializer=self.serializer
            ),
            self._create_schema(
                "address_ids",
                ttype="serializer",
                serializer=self.serializer,
                is_list=True,
            ),
            self._create_schema("unlinked", ttype="serializer"),
            self._create_schema("select", ttype="selection", values="a,b,c"),
        ]

        props = {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "create_date": {"type": "string", "format": "date-time"},
            "date": {"type": "string", "format": "date"},
            "custom_date": {"type": "string", "format": "date"},
            "active": {"type": "boolean"},
            "partner_latitude": {"type": "number"},
            "type": {
                "type": "string",
                "enum": ["contact", "invoice", "delivery", "private", "other"],
            },
            "select": {"type": "string", "enum": ["a", "b", "c"]},
            "address_id": self.ref,
            "address_ids": {"type": "array", "items": self.ref},
            "parent_id": self.ref,
            "child_ids": {"type": "array", "items": self.ref},
        }

        self.assertEqual(
            self.serializer.to_schema("importing"),
            {
                "type": "object",
                "required": ["name"],
                "properties": {**props, "ref": {"type": "string"}},
            },
        )

        self.assertEqual(
            self.serializer.to_schema("exporting"),
            {
                "type": "object",
                "required": ["name"],
                "properties": {**props, "exp_only": {"type": "boolean"}},
            },
        )

    def test_rest_serializer(self):
        self.serializer.field_ids = [
            self._create_field("name", exporting=False),
            self._create_field("ref", importing=False),
        ]

        serial = Serializer("testing")
        spec = MagicMock()
        self.assertEqual(
            serial.to_json_schema(MagicMock(env=self.env), spec, "importing"),
            {"$ref": f"#/components/schemas/{self.serializer.name}"},
        )
        spec.components.schema.assert_called_once_with(
            self.serializer.name,
            {
                "type": "object",
                "required": [],
                "properties": {"name": {"type": "string"}},
            },
        )
        spec.reset_mock()

        serial = Serializer("testing", is_list=True)
        self.assertEqual(
            serial.to_json_schema(MagicMock(env=self.env), spec, "exporting"),
            {"type": "array", "items": self.ref},
        )
        spec.components.schema.assert_called_once_with(
            self.serializer.name,
            {
                "type": "object",
                "required": [],
                "properties": {"ref": {"type": "string"}},
            },
        )
        spec.reset_mock()

        serial = Serializer("invalid")
        self.assertEqual(
            serial.to_json_schema(MagicMock(env=self.env), spec, "importing"),
            {},
        )

    def test_rest_from_params_invalid(self):
        mock = MagicMock(env=self.env)
        serial = Serializer("invalid")
        with self.assertRaises(InternalServerError):
            serial.from_params(mock, {})

        serial = Serializer("testing")
        with self.assertRaises(BadRequest):
            serial.from_params(mock, [])

        serial = Serializer("testing", is_list=True)
        with self.assertRaises(BadRequest):
            serial.from_params(mock, {})

        with self.assertRaises(BadRequest):
            serial.from_params(mock, [[]])

    def test_rest_from_params(self):
        mock = MagicMock(env=self.env)
        self.serializer.field_ids = [self._create_field("name", alias="n")]

        serial = Serializer("testing")
        self.assertEqual(serial.from_params(mock, {"n": "abc"}), {"name": "abc"})

        serial = Serializer("testing", is_list=True)
        self.assertEqual(
            serial.from_params(mock, [{"n": "abc"}, {"n": "b"}]),
            [{"name": "abc"}, {"name": "b"}],
        )

    def test_rest_to_response_invalid(self):
        mock = MagicMock(env=self.env)
        serial = Serializer("invalid")

        self.assertEqual(serial.to_response(mock, None), None)

        with self.assertRaises(InternalServerError):
            serial.to_response(mock, {})

        with self.assertRaises(InternalServerError):
            serial.to_response(mock, self.partner)

        serial = Serializer("testing")
        with self.assertRaises(InternalServerError):
            serial.to_response(mock, self.partner.browse())

    def test_rest_to_response(self):
        mock = MagicMock(env=self.env)
        self.serializer.field_ids = [self._create_field("name", alias="n")]
        serial = Serializer("testing")

        self.assertEqual(
            serial.to_response(mock, self.partner),
            {"n": self.partner.name},
        )

        serial = Serializer("testing", is_list=True)
        self.assertEqual(
            serial.to_response(mock, self.partner),
            [{"n": self.partner.name}],
        )
