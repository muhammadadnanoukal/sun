from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError

from collections import defaultdict


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'
    _description = 'Approval Request'
    _order = 'name'
    _mail_post_access = 'read'

    _check_company_auto = True

    @api.model
    def _read_group_request_status(self, stages, domain, order):
        request_status_list = dict(self._fields['request_status'].selection).keys()
        return request_status_list

    name = fields.Char(string="Approval Subject", tracking=True)
    category_id = fields.Many2one('approval.category', string="Category", required=True)
    category_image = fields.Binary(related='category_id.image')
    approver_ids = fields.One2many('approval.approver', 'request_id', string="Approvers", check_company=True,
                                   compute='_compute_approver_ids', store=True, readonly=False)
    company_id = fields.Many2one(
        string='Company', related='category_id.company_id',
        store=True, readonly=True, index=True)
    date = fields.Datetime(string="Date")
    date_start = fields.Datetime(string="Date start")
    date_end = fields.Datetime(string="Date end")
    quantity = fields.Float(string="Quantity")
    location = fields.Char(string="Location")
    date_confirmed = fields.Datetime(string="Date Confirmed")
    partner_id = fields.Many2one('res.partner', string="Contact", check_company=True)
    reference = fields.Char(string="Reference")
    amount = fields.Float(string="Amount")
    reason = fields.Html(string="Description")
    request_status = fields.Selection([
        ('new', 'To Submit'),
        ('pending', 'Submitted'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
        ('cancel', 'Cancel'),

    ], default="new", compute="_compute_request_status",
        store=True, tracking=True,
        group_expand='_read_group_request_status')
    request_owner_id = fields.Many2one('res.users', string="Request Owner",
                                       check_company=True, domain="[('company_ids', 'in', company_id)]")
    user_status = fields.Selection([
        ('new', 'New'),
        ('pending', 'To Approve'),
        ('waiting', 'Waiting'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
        ('cancel', 'Cancel'),], compute="_compute_user_status")
    is_user_notified = fields.Boolean(compute="_compute_user_notified_status")
    has_access_to_request = fields.Boolean(string="Has Access To Request", compute="_compute_has_access_to_request")
    change_request_owner = fields.Boolean(string='Can Change Request Owner', compute='_compute_has_access_to_request')
    attachment_number = fields.Integer('Number of Attachments', compute='_compute_attachment_number')
    product_line_ids = fields.One2many('approval.product.line', 'approval_request_id', check_company=True)

    has_date = fields.Selection(related="category_id.has_date")
    has_period = fields.Selection(related="category_id.has_period")
    has_quantity = fields.Selection(related="category_id.has_quantity")
    has_amount = fields.Selection(related="category_id.has_amount")
    has_reference = fields.Selection(related="category_id.has_reference")
    has_partner = fields.Selection(related="category_id.has_partner")
    has_payment_method = fields.Selection(related="category_id.has_payment_method")
    has_location = fields.Selection(related="category_id.has_location")
    has_product = fields.Selection(related="category_id.has_product")
    requirer_document = fields.Selection(related="category_id.requirer_document")
    approval_minimum = fields.Integer(related="category_id.approval_minimum")
    approval_type = fields.Selection(related="category_id.approval_type")
    approver_sequence = fields.Boolean(related="category_id.approver_sequence")
    automated_sequence = fields.Boolean(related="category_id.automated_sequence")
    done_indicator = fields.Boolean(default=False)
    current_approver = fields.Many2one('approval.approver', compute='compute_current_approver')
    notified_user = fields.Many2many('res.users')

    @api.onchange('approver_ids.status')
    def compute_current_approver(self):
        approver = self.mapped('approver_ids').filtered(
            lambda approver: approver.user_id == self.env.user
        )
        self.current_approver = approver

    @api.depends('request_owner_id')
    @api.depends_context('uid')
    def _compute_has_access_to_request(self):
        is_approval_user = self.env.user.has_group('approvals.group_approval_user')
        self.change_request_owner = is_approval_user
        for request in self:
            request.has_access_to_request = request.request_owner_id == self.env.user and is_approval_user

    def _compute_attachment_number(self):
        domain = [('res_model', '=', 'approval.request'), ('res_id', 'in', self.ids)]
        attachment_data = self.env['ir.attachment'].read_group(domain, ['res_id'], ['res_id'])
        attachment = dict((data['res_id'], data['res_id_count']) for data in attachment_data)
        for request in self:
            request.attachment_number = attachment.get(request.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            category = 'category_id' in vals and self.env['approval.category'].browse(vals['category_id'])
            # if category and category.automated_sequence:
            #    vals['name'] = category.sequence_id.next_by_id()
        return super().create(vals_list)

    def action_get_attachment_view(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window']._for_xml_id('base.action_attachment')
        res['domain'] = [('res_model', '=', 'approval.request'), ('res_id', 'in', self.ids)]
        res['context'] = {'default_res_model': 'approval.request', 'default_res_id': self.id}
        return res

    def action_confirm(self):
        # make sure that the manager is present in the list if he is required
        self.ensure_one()
        # I need to implement the line managers logic
        if self.category_id.manager_approval == 'required':
            employee = self.env['hr.employee'].search([('user_id', '=', self.request_owner_id.id)], limit=1)
            if not employee.parent_id:
                raise UserError(
                    _('This request needs to be approved by your manager. There is no manager linked to your employee profile.'))
            if not employee.parent_id.user_id:
                raise UserError(
                    _('This request needs to be approved by your manager. There is no user linked to your manager.'))
            if not self.approver_ids.filtered(lambda a: a.user_id.id == employee.parent_id.user_id.id):
                raise UserError(
                    _('This request needs to be approved by your manager. Your manager is not in the approvers list.'))

        if self.category_id.line_manager_approval == 'required':
            employee = self.env['hr.employee'].search([('user_id', '=', self.request_owner_id.id)], limit=1)
            direct_manager = employee.parent_id.parent_id
            while direct_manager:
                # if not direct_manager:
                #     raise UserError(_('This request needs to be approved by your manager. There is no manager linked to your employee profile.'))
                if not direct_manager.user_id:
                    raise UserError(
                        _(f'This request needs to be approved by your manager {direct_manager.name}. There is no user linked to his profile.'))
                if not self.approver_ids.filtered(lambda a: a.user_id.id == direct_manager.user_id.id):
                    raise UserError(
                        _(f'This request needs to be approved by your manager {direct_manager.name}. Your manager is not in the approvers list.'))
                direct_manager = direct_manager.parent_id

        if len(self.approver_ids) < self.approval_minimum:
            raise UserError(_("You have to add at least %s approvers to confirm your request.", self.approval_minimum))
        if self.requirer_document == 'required' and not self.attachment_number:
            raise UserError(_("You have to attach at lease one document."))

        approvers = self.approver_ids
        if self.approver_sequence:
            approvers = approvers.filtered(lambda a: a.status in ['new', 'pending', 'waiting'])
            print('approvers', approvers)

            approvers[1:].status = 'waiting'
            approvers = approvers[0] if approvers and approvers[0].status != 'pending' else self.env[
                'approval.approver']
            for app in approvers:
                print('approver status', app.status)
        else:
            print('entered else')
            approvers = approvers.filtered(lambda a: a.status == 'new')
            print(approvers)

        approvers._create_activity()
        users_ids = []
        for approver in approvers:
            users_ids.append(approver.user_id.id)
            self.notified_user = [(4, approver.user_id.id)]
        print('users ids', users_ids)
        print('approvers to create activity', approvers)
        approvers.write({'status': 'pending'})
        print('approvers', approvers)
        self.write({'date_confirmed': fields.Datetime.now()})

    def _get_user_approval_activities(self, user):
        domain = [
            ('res_model', '=', 'approval.request'),
            ('res_id', 'in', self.ids),
            ('activity_type_id', '=', self.env.ref('approvals.mail_activity_data_approval').id),
            ('user_id', '=', user.id)
        ]
        activities = self.env['mail.activity'].search(domain)
        print('activities', activities)
        return activities

    def _ensure_can_approve(self):
        if any(approval.approver_sequence and approval.user_status == 'waiting' for approval in self):
            raise ValidationError(_('You cannot approve before the previous approver.'))

    def _update_next_approvers(self, new_status, approver, only_next_approver, cancel_activities=False):
        approvers_updated = self.env['approval.approver']

        for approval in self.filtered('approver_sequence'):
            current_approver = approval.approver_ids & approver
            print('approvers before filtering', approval.approver_ids)
            approvers_to_update = approval.approver_ids.filtered(lambda a: a.status not in ['approved', 'refused'] and (
                    a.sequence > current_approver.sequence or (
                    a.sequence == current_approver.sequence and a.id > current_approver.id)))
            for s in approvers_to_update:
                print('comparison', s.sequence, current_approver.sequence)
                print(s.id, current_approver.id)
            print('approvers to update', approvers_to_update)
            for ap in approvers_to_update:
                print('approver sequence', ap.sequence)
            # print('category_approver', approvers_to_update[0].category_approver)
            if only_next_approver and approvers_to_update and approvers_to_update[0].category_approver:
                approvers_to_update = approvers_to_update[0]
                print('entered condition', approvers_to_update)
            approvers_updated |= approvers_to_update
            print('approvers_updated', approvers_updated)
        print('status', new_status)
        approvers_updated.sudo().status = new_status
        if new_status == 'pending':
            approvers_updated._create_activity()
            users_ids = []
            for approver in approvers_updated:
                # users_ids.append(approver.user_id.id)
                self.notified_user = [(4, approver.user_id.id)]
        if cancel_activities:
            # self.notified_user = [(6, 0, [])]
            approvers_updated.request_id._cancel_activities()
        if new_status == 'refused' and self.category_id.notify_even_when_refused:
            if len(approvers_updated) >= 1:
                print('zaid', approvers_updated[0])
                approvers_updated[0]._create_activity()
                users_ids = []
                users_ids.append(approvers_updated[0].user_id.id)
                self.notified_user = [(4, approvers_updated[0].user_id.id)]
                print('next approver', approvers_updated[0])
                approvers_updated[0].is_notified = True

    def _cancel_activities(self):
        approval_activity = self.env.ref('approvals.mail_activity_data_approval')
        activities = self.activity_ids.filtered(lambda a: a.activity_type_id == approval_activity)
        activities.unlink()

    def action_approve(self, approver=None):
        self._ensure_can_approve()

        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
        approver.write({'status': 'approved'})
        self.sudo()._update_next_approvers('pending', approver, only_next_approver=True)
        self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()

    def action_refuse(self, approver=None):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
        approver.write({'status': 'refused'})
        self.sudo()._update_next_approvers('refused', approver, only_next_approver=False, cancel_activities=True)
        self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()
        print('user in refuse', self.env.user)

    def mark_done(self):
        approver = self.mapped('approver_ids').filtered(
            lambda approver: approver.user_id == self.env.user
        )
        approver.request_id._cancel_activities()
        # self.notified_user = [(6, 0, [])]
        # approver.is_notified = False
        self.done_indicator = True
        print('DONE')

    def action_withdraw(self, approver=None):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
        self.sudo()._update_next_approvers('waiting', approver, only_next_approver=False, cancel_activities=True)
        approver.write({'status': 'pending'})

    def action_draft(self):
        self.mapped('approver_ids').write({'status': 'new'})

    def action_cancel(self):
        self.sudo()._get_user_approval_activities(user=self.env.user).unlink()
        self.mapped('approver_ids').write({'status': 'cancel'})

    @api.depends_context('uid')
    @api.depends('approver_ids.status')
    def _compute_user_status(self):
        for approval in self:
            approval.user_status = approval.approver_ids.filtered(
                lambda approver: approver.user_id == self.env.user).status
            print('approval status', approval.user_status)

    @api.depends_context('uid')
    @api.depends('user_status')
    def _compute_user_notified_status(self):
        for approval in self:
            approval.is_user_notified = approval.approver_ids.filtered(
                lambda approver: approver.user_id == self.env.user).is_notified
            print('is_user_notified', approval.is_user_notified)

    @api.depends('approver_ids.status', 'approver_ids.required')
    def _compute_request_status(self):
        for request in self:
            status_lst = request.mapped('approver_ids.status')
            required_approved = all(a.status == 'approved' for a in request.approver_ids.filtered('required'))
            minimal_approver = request.approval_minimum if len(status_lst) >= request.approval_minimum else len(
                status_lst)
            print('status least', status_lst)
            if status_lst:
                if status_lst.count('cancel'):
                    status = 'cancel'
                elif status_lst.count('refused'):
                    print('refused', status_lst.count('refused'))
                    status = 'refused'
                elif status_lst.count('new'):
                    status = 'new'
                elif status_lst.count('approved') >= minimal_approver and required_approved:
                    status = 'approved'
                else:
                    status = 'pending'
            else:
                status = 'new'
            request.request_status = status

        self.filtered_domain([('request_status', 'in', ['approved', 'refused', 'cancel'])])._cancel_activities()

    @api.depends('category_id', 'request_owner_id')
    def _compute_approver_ids(self):
        for request in self:
            # Don't remove manually added approvers
            users_to_approver = defaultdict(lambda: self.env['approval.approver'])
            new_users = self.env['res.users']
            if self.category_id.priority_type == 'high':
                for approver in request.approver_ids:
                    users_to_approver[approver.user_id.id] |= approver
                users_to_category_approver = defaultdict(lambda: self.env['approval.category.approver'])
                for approver in request.category_id.approver_ids:
                    users_to_category_approver[approver.user_id.id] |= approver
                new_users = request.category_id.user_ids
                print('new users', new_users)

            manager_user = 0
            line_manager_users = []
            if request.category_id.manager_approval:
                print('request.category_id.manager_approval', request.category_id.manager_approval)
                employee = self.env['hr.employee'].search([('user_id', '=', request.request_owner_id.id)], limit=1)
                print('request', request.request_owner_id.id)
                if employee.parent_id.user_id:
                    new_users |= employee.parent_id.user_id
                    manager_user = employee.parent_id.user_id.id
            if request.category_id.line_manager_approval:
                employee = self.env['hr.employee'].search([('user_id', '=', request.request_owner_id.id)], limit=1)
                line_managers = []
                direct_parent = employee.parent_id.parent_id
                while direct_parent:
                    if direct_parent.user_id:
                        line_managers.append(direct_parent.user_id)
                        line_manager_users.append(direct_parent.user_id.id)
                    else:
                        break
                    direct_parent = direct_parent.parent_id
                for emp in line_managers:
                    new_users |= emp
                print('line managers', line_managers)
            print('updated new users', new_users)

            if self.category_id.priority_type == 'low':
                for approver in request.approver_ids:
                    users_to_approver[approver.user_id.id] |= approver
                users_to_category_approver = defaultdict(lambda: self.env['approval.category.approver'])
                for approver in request.category_id.approver_ids:
                    users_to_category_approver[approver.user_id.id] |= approver
                new_users |= request.category_id.user_ids
                print('new users', new_users)

            approver_id_vals = []
            i = 0
            for user in new_users:
                print('new single user', user)
                # Force require on the manager if he is explicitely in the list
                required = users_to_category_approver[user.id].required or (
                    request.category_id.manager_approval == 'required' if manager_user == user.id else False) or (
                               request.category_id.line_manager_approval == 'required' if user.id in line_manager_users else False)
                current_approver = users_to_approver[user.id]
                if current_approver and current_approver.required != required:
                    approver_id_vals.append(Command.update(current_approver.id, {'required': required}))
                elif not current_approver:
                    print('sequence? ', request.approver_sequence)
                    sequence = (users_to_category_approver[
                                    user.id].sequence or 1000 + i) if request.approver_sequence else 10
                    approver_id_vals.append(Command.create({
                        'user_id': user.id,
                        'status': 'new',
                        'required': required,
                        'sequence': sequence,
                    }))
                i += 1
            print('approver_id_vals', approver_id_vals)
            request.update({'approver_ids': approver_id_vals})
            for a in request.approver_ids:
                print('saved sequence')
                print(a.sequence)

    def write(self, vals):
        res = super().write(vals)

        if 'approver_ids' in vals:
            to_resequence = self.filtered_domain([('approver_sequence', '=', True), ('request_status', '=', 'pending')])
            for approval in to_resequence:
                if not approval.approver_ids.filtered(lambda a: a.status == 'pending'):
                    approver = approval.approver_ids.filtered(lambda a: a.status == 'waiting')
                    if approver:
                        approver[0].status = 'pending'
                        approver[0]._create_activity()

        return res


class ApprovalApprover(models.Model):
    _inherit = 'approval.approver'
    _description = 'Approver'
    _order = 'sequence, id'

    _check_company_auto = True

    sequence = fields.Integer('Sequence', default=10)
    user_id = fields.Many2one('res.users', string="User", required=True, check_company=True,
                              domain="[('id', 'not in', existing_request_user_ids)]")
    existing_request_user_ids = fields.Many2many('res.users', compute='_compute_existing_request_user_ids')
    status = fields.Selection([
        ('new', 'New'),
        ('pending', 'To Approve'),
        ('waiting', 'Waiting'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
        ('cancel', 'Cancel')], string="Status", default="new", readonly=True)
    is_notified = fields.Boolean(default=False)
    request_id = fields.Many2one('approval.request', string="Request",
                                 ondelete='cascade', check_company=True)
    company_id = fields.Many2one(
        string='Company', related='request_id.company_id',
        store=True, readonly=True, index=True)
    required = fields.Boolean(default=False, readonly=True)
    category_approver = fields.Boolean(compute='_compute_category_approver')
    can_edit = fields.Boolean(compute='_compute_can_edit')

    def action_approve(self):
        self.request_id.action_approve(self)

    def action_refuse(self):
        self.request_id.action_refuse(self)

    def _create_activity(self):
        for approver in self:
            print('approver to notify', approver)
            approver.request_id.activity_schedule(
                'approvals.mail_activity_data_approval',
                user_id=approver.user_id.id)

    @api.depends('request_id.request_owner_id', 'request_id.approver_ids.user_id')
    def _compute_existing_request_user_ids(self):
        for approver in self:
            approver.existing_request_user_ids = \
                self.mapped('request_id.approver_ids.user_id')._origin \
                | self.request_id.request_owner_id._origin

    @api.depends('category_approver', 'user_id')
    def _compute_category_approver(self):
        for approval in self:
            for r in approval.request_id.category_id.approver_ids:
                print('user id', r.user_id)
            print('approval id', approval.user_id)
            approval.category_approver = approval.user_id in approval.request_id.category_id.approver_ids.user_id or approval.required or approval.status == 'waiting'
            print('approval.category_approver', approval.category_approver)

    @api.depends_context('uid')
    @api.depends('user_id', 'category_approver')
    def _compute_can_edit(self):
        is_user = self.env.user.has_group('approvals.group_approval_user')
        for approval in self:
            approval.can_edit = not approval.user_id or not approval.category_approver or is_user
