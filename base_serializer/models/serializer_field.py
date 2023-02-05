# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SerializerField(models.Model):
    _name = "ir.serializer.field"
    _description = _("Serializer Field")

    serializer_id = fields.Many2one("ir.serializer", ondelete="cascade", required=True)
    name = fields.Char(
        help="The name of the field used in the converted data. If not set the "
        "name of the field will be used",
    )
    model_id = fields.Many2one(related="serializer_id.model_id", store=True, index=True)
    related = fields.Boolean(compute="_compute_related", store=True)
    field_id = fields.Many2one(
        "ir.model.fields",
        domain="[('model_id', '=', model_id)]",
        ondelete="cascade",
        required=True,
    )
    ttype = fields.Selection(related="field_id.ttype")
    related_serializer_id = fields.Many2one(
        "ir.serializer",
        help="Select a specific serializer to use otherwise a matching serializer "
        "will be used as default",
    )
    importing = fields.Boolean("Import", default=True)
    exporting = fields.Boolean("Export", default=True)

    _sql_constraints = [
        (
            "sync_field_uniq",
            "UNIQUE(serializer_id, field_id)",
            _("A field can only be mapped once"),
        )
    ]

    @api.depends("field_id")
    def _compute_related(self):
        for rec in self:
            rec.related = bool(rec.field_id.relation)

    def _serialize(self, record, visited):
        self.ensure_one()

        fname = self.field_id.name
        if self.ttype in (
            "boolean",
            "char",
            "float",
            "html",
            "integer",
            "monetary",
            "selection",
            "text",
        ):
            return record[fname]

        if self.ttype in ("date", "datetime"):
            return record._fields[fname].to_string(record[fname])

        if not self.related:
            raise NotImplementedError()

        if self.ttype in ("many2one",):
            return self.related_serializer_id._serialize(record[fname], visited)

        if self.ttype in ("many2many", "one2many"):
            result = []
            for r in record[fname]:
                data = self.related_serializer_id._serialize(r, visited)
                if data:
                    result.append(data)

            if result:
                return result

            return [] if self.env.context.get("include_empty_keys") else None

        raise NotImplementedError()

    def _deserialize(self, value):
        self.ensure_one()
        if self.ttype in (
            "boolean",
            "char",
            "float",
            "html",
            "integer",
            "monetary",
            "selection",
            "text",
        ):
            return value

        if self.ttype == "date":
            return fields.Date.to_date(value)
        if self.ttype == "datetime":
            return fields.Datetime.to_datetime(value)

        if not self.related:
            raise NotImplementedError(f"Field type {self.ttype} is not supported")

        if self.ttype in ("many2one",):
            return self.related_serializer_id._deserialize(value)

        if self.ttype in ("many2many", "one2many"):
            return list(map(self.related_serializer_id._deserialize, value))

        raise NotImplementedError(f"Field type {self.ttype} is not supported")
