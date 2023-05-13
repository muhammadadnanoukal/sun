# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class ApprovalCategoryApprover(models.Model):
    """ Intermediate model between approval.category and res.users
        To know whether an approver for this category is required or not
    """
    _inherit = 'approval.category.approver'
    _order = 'sequence'
    _rec_name = 'user_id'

    sequence = fields.Integer('Sequence', default=10)
