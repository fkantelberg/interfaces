# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command, Datetime
from odoo.tests import TransactionCase


class TestSerializer(TransactionCase):
    def setUp(self):
        super().setUp()

        self.serializer = self.env["ir.serializer"].create(
            {
                "name": "Test Serializer",
                "model_id": self.env.ref("base.model_res_partner").id,
                "use_sync_date": True,
                "raise_on_duplicate": True,
            }
        )

        self.parent = self.env["res.partner"].create(
            {
                "name": "Test Parent",
                "ref": "parent",
                "is_company": True,
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "ref": "partner",
                "is_company": False,
                "parent_id": self.parent.id,
                "child_ids": [
                    Command.create({"name": "Child A", "ref": "a"}),
                    Command.create({"name": "Child B", "ref": "b"}),
                ],
            }
        )

    def _create_field(self, name, alias=None, serializer_id=None):
        return Command.create(
            {
                "name": alias,
                "field_id": self.env.ref(f"base.field_res_partner__{name}").id,
                "related_serializer_id": serializer_id,
            }
        )

    def test_active(self):
        self.assertTrue(self.serializer.active)
        self.serializer.importing = False
        self.assertTrue(self.serializer.active)
        self.serializer.exporting = False
        self.assertFalse(self.serializer.active)
        self.serializer.importing = True
        self.assertTrue(self.serializer.active)

    def test_check_domain(self):
        with self.assertRaises(ValidationError):
            self.serializer.import_domain = "{}"
        self.serializer.import_domain = "[]"

        with self.assertRaises(ValidationError):
            self.serializer.import_domain = "[('ref', '=', unknown)]"
        self.serializer.import_domain = "[('ref', '=', ref)]"

    def test_population(self):
        self.serializer.field_ids = [self._create_field("name")]
        self.serializer.action_populate()
        domain = [
            ("model", "=", "res.partner"),
            ("store", "=", True),
            ("relation", "in", (False, "")),
        ]
        self.assertEqual(
            len(self.serializer.field_ids),
            self.env["ir.model.fields"].search_count(domain),
        )

        self.serializer.action_populate_fully()
        domain = [
            ("model", "=", "res.partner"),
            ("store", "=", True),
        ]
        self.assertEqual(
            len(self.serializer.field_ids),
            self.env["ir.model.fields"].search_count(domain),
        )

    def test_check_fields(self):
        with self.assertRaises(ValidationError):
            self.serializer.field_ids = [
                self._create_field("name"),
                self._create_field("ref", "name"),
            ]

        with self.assertRaises(ValidationError):
            self.serializer.field_ids = [
                self._create_field("ref", "name"),
                self._create_field("name"),
            ]

        self.serializer.field_ids = [
            self._create_field("ref", "name"),
            self._create_field("name", "other_name"),
        ]
        self.assertEqual(len(self.serializer.field_ids), 2)

    def test_serialize(self):
        self.serializer.field_ids = [
            self._create_field("name"),
            self._create_field("ref"),
            self._create_field("is_company", "company"),
            self._create_field("write_date"),
            self._create_field("date"),
            self._create_field("parent_id", "parent", self.serializer.id),
        ]

        data = self.serializer._serialize(self.partner)
        self.assertEqual(
            data,
            {
                "name": self.partner.name,
                "ref": self.partner.ref,
                "company": self.partner.is_company,
                "write_date": Datetime.to_string(self.partner.write_date),
                "date": False,
                "sync_date": self.partner.write_date.isoformat(" "),
                "parent": {
                    "name": self.parent.name,
                    "ref": self.parent.ref,
                    "company": True,
                    "write_date": Datetime.to_string(self.parent.write_date),
                    "date": False,
                    "sync_date": self.parent.write_date.isoformat(" "),
                },
            },
        )

    def test_named_mapping(self):
        self.serializer.write(
            {
                "use_sync_date": False,
                "field_ids": [
                    self._create_field("ref", "name"),
                    self._create_field("name", "ref"),
                ],
            }
        )
        self.partner.write({"name": "abc", "ref": "cba"})
        data = self.serializer._serialize(self.partner)
        self.assertEqual(data, {"name": "cba", "ref": "abc"})
        data = self.serializer._deserialize(data)
        self.assertEqual(data, {"name": "abc", "ref": "cba"})

    def test_serialize_loop(self):
        self.serializer.field_ids = [
            self._create_field("name"),
            self._create_field("parent_id", "parent", self.serializer.id),
            self._create_field("child_ids", "childs", self.serializer.id),
        ]

        with self.assertRaises(UserError):
            self.serializer.serialize(self.partner)

        self.serializer.write({"use_sync_date": False, "raise_on_duplicate": False})
        self.assertEqual(
            json.loads(self.serializer.serialize(self.partner)),
            [
                {
                    "name": self.partner.name,
                    "parent": {"name": self.parent.name},
                    "childs": [{"name": c.name} for c in self.partner.child_ids],
                }
            ],
        )

    def test_serialize_config(self):
        self.serializer.field_ids = [
            self._create_field("name"),
            self._create_field("parent_id", "parent", self.serializer.id),
            self._create_field("child_ids", "childs", self.serializer.id),
        ]

        self.serializer.write({"use_sync_date": False, "raise_on_duplicate": False})
        self.assertEqual(
            json.loads(self.serializer.serialize(self.partner)),
            [
                {
                    "name": self.partner.name,
                    "parent": {"name": self.parent.name},
                    "childs": [{"name": c.name} for c in self.partner.child_ids],
                }
            ],
        )

        self.serializer.include_empty_keys = True
        self.assertEqual(
            json.loads(self.serializer.serialize(self.partner)),
            [
                {
                    "name": self.partner.name,
                    "parent": {"name": self.parent.name, "parent": {}, "childs": []},
                    "childs": [
                        {"name": c.name, "parent": {}, "childs": []}
                        for c in self.partner.child_ids
                    ],
                }
            ],
        )

    def test_serialize_snippet(self):
        self.serializer.write(
            {
                "use_snippet": True,
                "field_ids": [self._create_field("name")],
                "export_code": "result['key'] = '%s %s' % (record.name, record.ref)",
                "use_sync_date": False,
            }
        )

        self.assertEqual(
            self.serializer._serialize(self.partner),
            {
                "name": self.partner.name,
                "key": f"{self.partner.name} {self.partner.ref}",
            },
        )

    def test_deserialize_json(self):
        self.serializer.field_ids = [
            self._create_field("name"),
            self._create_field("ref"),
        ]

        with self.assertRaises(UserError):
            self.serializer.deserialize("{}")

        with self.assertRaises(UserError):
            self.serializer.deserialize("[[]]")

        data = self.serializer.deserialize(
            f'[{{"name":"abc","ref":"{self.partner.ref}"}}]'
        )
        self.assertEqual(data, [{"name": "abc", "ref": self.partner.ref}])

    def test_deserialize(self):
        self.serializer.field_ids = [
            self._create_field("name"),
            self._create_field("ref"),
            self._create_field("is_company", "company"),
            self._create_field("write_date"),
            self._create_field("date"),
            self._create_field("parent_id", "parent", self.serializer.id),
        ]

        data = self.serializer._deserialize(
            {
                "name": self.partner.name,
                "ref": self.partner.ref,
                "company": self.partner.is_company,
                "write_date": Datetime.to_string(self.partner.write_date),
                "date": False,
                "sync_date": self.partner.write_date.isoformat(" "),
                "parent": {
                    "name": self.parent.name,
                    "ref": self.parent.ref,
                    "company": True,
                    "write_date": Datetime.to_string(self.parent.write_date),
                    "date": False,
                    "sync_date": self.parent.write_date.isoformat(" "),
                },
            }
        )
        self.assertEqual(
            data,
            {
                "name": self.partner.name,
                "ref": self.partner.ref,
                "is_company": self.partner.is_company,
                "write_date": self.partner.write_date.replace(microsecond=0),
                "date": None,
                "sync_date": self.partner.write_date,
                "parent_id": {
                    "name": self.parent.name,
                    "ref": self.parent.ref,
                    "is_company": True,
                    "write_date": self.parent.write_date.replace(microsecond=0),
                    "date": None,
                    "sync_date": self.parent.write_date,
                },
            },
        )

    def test_deserialize_type_error(self):
        with self.assertRaises(UserError):
            self.serializer._deserialize([])

    def test_deserialize_snippet(self):
        self.serializer.write(
            {
                "use_snippet": True,
                "import_code": "result['abc'] = 'valid'",
            }
        )
        data = self.serializer._deserialize(
            {"sync_date": self.partner.write_date.isoformat(" ")}
        )
        self.assertEqual(data, {"sync_date": self.partner.write_date, "abc": "valid"})

    def test_deserialize_one2many(self):
        self.serializer.write(
            {
                "use_sync_date": False,
                "field_ids": [
                    self._create_field("name", "sth"),
                    self._create_field("child_ids", "childs", self.serializer.id),
                ],
            }
        )

        data = self.serializer._deserialize(
            {
                "sth": self.partner.name,
                "name": "invalid",
                "childs": [
                    {"sth": c.name, "childs": []} for c in self.partner.child_ids
                ],
            }
        )
        self.assertEqual(
            data,
            {
                "name": self.partner.name,
                "child_ids": [
                    {"name": c.name, "child_ids": []} for c in self.partner.child_ids
                ],
            },
        )

    def test_importing(self):
        self.serializer.write(
            {
                "import_domain": "[('ref', '=', ref)]",
                "use_sync_date": False,
                "field_ids": [
                    self._create_field("name"),
                    self._create_field("ref"),
                    self._create_field("parent_id", "parent", self.serializer.id),
                    self._create_field("child_ids", "childs", self.serializer.id),
                ],
            }
        )

        self.assertEqual(self.partner.name, "Test Partner")
        rec = self.serializer.import_deserialized(
            [{"name": "Test", "ref": self.partner.ref}]
        )
        self.assertEqual(self.partner.name, "Test")
        self.assertEqual(rec, self.partner)

        rec = self.serializer.import_deserialized(
            {
                "name": "Test 1",
                "ref": "new",
                "parent_id": {"ref": self.parent.ref},
                "child_ids": [
                    {"ref": self.partner.ref},
                    {"name": "New partner", "ref": "NEW"},
                ],
                "unknown": [],
            }
        )
        self.assertEqual([rec.name, rec.ref], ["Test 1", "new"])
        self.assertNotEqual(rec, self.partner)
        self.assertIn(rec, self.parent.child_ids)
        self.assertEqual(self.partner.parent_id, rec)
        self.assertEqual(len(rec.child_ids), 2)

        with self.assertRaises(UserError):
            self.serializer._import_deserialized([])

    def test_preview(self):
        self.serializer.field_ids = [
            self._create_field("name"),
            self._create_field("ref"),
        ]
        self.serializer.import_domain = "[('ref', '=', ref)]"

        preview = self.env["ir.serializer.preview"].create(
            {"serializer_id": self.serializer.id}
        )
        preview._onchange_serialized()

        preview.resource_ref = f"res.partner,{self.partner.id}"
        preview._onchange_serialized()

        self.assertEqual(
            json.loads(preview.serialized),
            {
                "name": self.partner.name,
                "ref": self.partner.ref,
                "sync_date": self.partner.write_date.isoformat(" "),
            },
        )
        self.assertEqual(
            json.loads(preview.deserialized),
            {
                "name": self.partner.name,
                "ref": self.partner.ref,
                "sync_date": self.partner.write_date.isoformat(" ")[:19],
            },
        )
        self.assertEqual(preview.matching, 1)

        self.serializer.import_domain = False
        preview._onchange_matching()
        self.assertEqual(preview.matching, 0)

        preview.write({"matching": 42, "deserialized": ""})
        preview._onchange_matching()
        self.assertEqual(preview.matching, 0)

        preview.write({"serialized": False, "deserialized": "test"})
        preview._onchange_deserialized()
        self.assertEqual(preview.deserialized, "test")

    def test_preview_defaults(self):
        preview = self.env["ir.serializer.preview"]

        self.assertEqual(preview.default_get(["resource_ref"]), {})
