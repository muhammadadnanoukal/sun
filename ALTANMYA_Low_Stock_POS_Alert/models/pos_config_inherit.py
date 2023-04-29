from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    allow_order_when_product_out_of_stock = fields.Boolean(string='Allow Order when Product is Out Of Stock',
                                                           default=True)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_allow_order_when_product_out_of_stock = fields.Boolean(related='pos_config_id.allow_order_when_product_out_of_stock', readonly=False)

