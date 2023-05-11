from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from datetime import datetime


class HRLeave(models.Model):
    _inherit = 'hr.leave'

    employee_total_leaves = fields.Integer(string='إجمالي الإجازات المرضية من بداية السنة',
                                           compute='_compute_employee_leaves', store=True)

    @api.onchange('employee_ids')
    def onchange_employee_id(self):
        domain = ['|', ('requires_allocation', '=', 'no'),
                  ('has_valid_allocation', '=', True),
                  '|', ('allowed_gender', '=', 'both'), ('allowed_gender', '=', self.employee_id.gender),
                  '|', ('marital_status', '=', 'both'), ('marital_status', '=', self.employee_id.marital)
                  ]
        print(domain)
        if self.employee_id:
            print('gender', self.employee_ids[0].gender)
            print('marital', self.employee_ids[0].marital)
        # self.compute_employee_service_days()
        print('prorata', self.calculate_days_based_on_pro_rata())
        return {'domain': {'holiday_status_id': domain}}

    def compute_employee_service_days(self, leave_start_date):
        if self.employee_ids:
            employee_contract_date = self.env['hr.employee'].search(
                [('id', '=', self.employee_ids[0]._origin.id)]).first_contract_date
            employee_service_days = leave_start_date.date() - employee_contract_date
            print('employee_service_days', employee_service_days.days)
            if employee_service_days.days >= 0:
                print('in if', employee_service_days.days)
                return employee_service_days.days
            else:
                print('in else', employee_service_days.days)
                return 0

    def compute_total_leaves_custom_type(self, leave_type):
        global total
        total_leaves = 0
        now = str(fields.Datetime.now())
        year = now[0:4]
        for rec in self:
            total = self.env['hr.leave'].search(
                [('employee_ids', 'in', rec.employee_ids[0]),
                 ('state', 'not in', ['refuse']),
                 ('holiday_status_id.name', '=', leave_type)])
        for rec in total:
            total_leaves += rec.number_of_days

    def compute_non_repeated_leaves_total(self):
        for rec in self:
            print('employee name in repeated', rec.employee_ids[0].id)
            non_repeated_leaves = self.env['hr.leave'].search(
                [('holiday_status_id.is_repeated', '=', False), ('employee_id', '=', rec.employee_ids[0].id),
                 ('holiday_status_id.is_sick_leave', '=', False), ('holiday_status_id', '=', rec.holiday_status_id.id)])
            print('non_repeated_leaves', non_repeated_leaves)
            if len(non_repeated_leaves) > 1:
                return len(non_repeated_leaves)
        return 0

    def compute_total_employee_leaves(self, holiday_type):
        employee_leaves = self.env['hr.leave'].search(
            [('employee_id', '=', self.employee_ids[0].id), ('holiday_status_id', '=', holiday_type.id)])
        total_leave_days = 0
        for leave in employee_leaves:
            total_leave_days += leave.number_of_days
        print('total leaves', total_leave_days)
        return total_leave_days

    def _compute_number_of_days(self):
        super(HRLeave, self)._compute_number_of_days()
        if self.holiday_status_id.is_configurable:
            for holiday in self:
                if holiday.holiday_status_id.is_connected_days:
                    unusaldays = holiday.employee_id._get_unusual_days(holiday.date_from, holiday.date_to)
                    print('unusaldays', unusaldays)
                    if unusaldays:
                        holiday.number_of_days = holiday.number_of_days + len(
                            [elem for elem in unusaldays.values() if elem])

    @api.constrains('holiday_status_id')
    def check_leave_if_specified_to_employee(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.customized_to == 'employee':
                test = self.env['hr.leave.type'].search(
                    [('id', '=', self.holiday_status_id.id), ('specified_employees', 'in', self.employee_ids[0].id)])
                print('test', test)
                if not test:
                    raise ValidationError('هذه الإجازة غير مخصصة لك')

    @api.constrains('holiday_status_id')
    def check_leave_if_specified_to_shift(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.customized_to == 'shift':
                test = self.env['hr.leave.type'].search(
                    [('id', '=', self.holiday_status_id.id),
                     ('shift_ids', 'in', self.employee_ids[0].resource_calendar_id.id)])
                print('test', test)
                if not test:
                    raise ValidationError('هذه الإجازة غير مخصصة لك')

    @api.constrains('holiday_status_id')
    def check_repeated_leaves(self):
        if self.holiday_status_id.is_configurable:
            print('compute_non_repeated_leaves_total()', self.compute_non_repeated_leaves_total())
            print('balance type', self.holiday_status_id.balance_type)
            print('employee : ', self.employee_ids[0].name)
            if self.compute_non_repeated_leaves_total() >= 1 and self.holiday_status_id.balance_type != 'new_balance':
                raise ValidationError('هذا الموظف قد قام بالفعل بأخذ إجازة من هذا النوع و هو لا يحق له أكثر من مرة')
            return True

    @api.constrains('holiday_status_id')
    def check_if_exceeded_allowed_days(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.is_repeated and self.holiday_status_id.balance_type == 'new_balance':
                if self.number_of_days > self.calculate_days_based_on_pro_rata():
                    raise ValidationError('لقد تجاوز هذا الموظف الحد المسموح له من أيام هذا النوع من الإجازات')
            elif self.holiday_status_id.is_repeated and self.holiday_status_id.balance_type == 'old_balance':
                if self.compute_total_employee_leaves(self.holiday_status_id) > self.calculate_days_based_on_pro_rata():
                    raise ValidationError('لقد تجاوز هذا الموظف الحد المسموح له من أيام هذا النوع من الإجازات')
            else:
                if self.number_of_days > self.calculate_days_based_on_pro_rata():
                    raise ValidationError('لقد تجاوز هذا الموظف الحد المسموح له من أيام هذا النوع من الإجازات')

    # @api.constrains('holiday_status_id')
    # def check_if_exceeded_allowed_days_prorata(self):
    #     if self.holiday_status_id.is_configurable:
    #         print('hiiiiiii', self.compute_total_employee_leaves(self.holiday_status_id))
    #         if self.compute_total_employee_leaves(
    #                 self.holiday_status_id) > self.calculate_days_based_on_pro_rata() and not self.check_repeated_leaves():
    #             raise ValidationError('لقد تجاوز هذا الموظف الحد المسموح له من أيام هذا النوع من الإجازات')

    @api.constrains('holiday_status_id')
    def check_if_required_days_are_met(self):
        if self.holiday_status_id.is_configurable:
            required_work_days = self.holiday_status_id.number_of_required_work_days
            print('required work days')
            print(required_work_days)
            print(self.compute_employee_service_days(self.date_from))
            if required_work_days > self.compute_employee_service_days(self.date_from):
                print('lol 1', required_work_days)
                print('lol 2', self.compute_employee_service_days(self.date_from))
                raise ValidationError('هذا النوع من الإجازات لا يحق لهذا الموظف بعد')
            else:
                pass

    def calculate_normal_days(self):
        return self.holiday_status_id.number_of_allowed_days

    # for pro rata leaves
    def calculate_days_based_on_pro_rata(self):
        if self.employee_ids:
            if self.holiday_status_id.apply_pro_rata:
                employee_contract_date = self.env['hr.employee'].search(
                    [('id', '=', self.employee_ids[0]._origin.id)]).first_contract_date
                now = str(self.date_from)
                year = now[0:4]
                current_month = now[5:7]
                contract_year = str(employee_contract_date)[0:4]
                print('current year', year, 'contract year', contract_year)
                contract_month = str(employee_contract_date)[5:7]
                print('contract in last year', str(int(contract_year) + 1), str(employee_contract_date))
                print('month ', contract_month, current_month)
                if year == contract_year:
                    diff = 12 - int(contract_month)
                    # if diff != 12:
                    print('diff', diff)
                    # if diff < 11:
                    allowed_days_for_this_employee = self.holiday_status_id.number_of_allowed_days - (self.holiday_status_id.number_of_allowed_days * (
                            diff / 12))
                    print('allowed days', round(allowed_days_for_this_employee))
                    return round(allowed_days_for_this_employee)
                else:
                    return self.holiday_status_id.number_of_allowed_days
            else:
                return self.holiday_status_id.number_of_allowed_days

    # sick leaves
    @api.model_create_multi
    def create(self, vals_list):
        holidays = super(HRLeave, self.with_context(mail_create_nosubscribe=True)).create(vals_list)
        print('vals list')
        print(vals_list)
        self.env['hr.employee'].search([('id', '=', vals_list[0]['employee_ids'][0][0])]).compute_total_leaves()
        return holidays

    def write(self, values):
        result = super(HRLeave, self).write(values)
        self.env['hr.employee'].search([('id', '=', self.employee_ids[0].id)]).compute_total_leaves()
        # if self.holiday_status_id.is_configurable:
        #     self.check_leave_if_specified_to_employee()
        #     self.check_employees_number_configurable_leave()
        #     # self.check_repeated_leaves()
        #     self.check_leave_if_specified_to_shift()
        #     self.check_employees_total_leaves()
        #     self.check_if_exceeded_allowed_days()
        #     self.check_if_required_days_are_met()
        #     self.check_matching_gender()
        #     self.check_matching_marital_status()
        return result

    @api.depends('employee_ids')
    def _compute_employee_leaves(self):
        for rec in self:
            if rec.employee_ids:
                rec.employee_total_leaves = rec.employee_ids[0]._origin.total_sick_leaves
                print('emp total')
                print(rec.employee_ids[0]._origin.total_sick_leaves)
                print(rec.employee_total_leaves)

    def read(self, fields=None, load='_classic_read'):
        res = super(HRLeave, self).read(fields=fields, load=load)
        for rec in self:
            rec._compute_employee_leaves()
            self.env['hr.employee'].search([('id', '=', rec.employee_ids[0].id)]).compute_total_leaves()
        return res

    @api.constrains('holiday_status_id')
    def check_employees_number_configurable_leave(self):
        if self.holiday_status_id.is_configurable and len(self.employee_ids) > 1:
            raise ValidationError('لا يمكن أن يتم اختيار أكثر من موظف عند تقديم هذا النوع من الإجازات')

    @api.constrains('holiday_status_id')
    def check_employees_total_leaves(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.is_sick_leave:
                print('constraint entered')
                print(self.holiday_status_id.leave_date_to)
                print(self.employee_total_leaves + self.number_of_days)
                print(self.holiday_status_id.leave_date_from)
                if not (
                        self.holiday_status_id.leave_date_to >=
                        self.employee_total_leaves + self.number_of_days >= self.holiday_status_id.leave_date_from \
                        and self.holiday_status_id.leave_date_to != 0 \
                        and self.holiday_status_id.leave_date_from <= self.employee_total_leaves):
                    raise ValidationError('لا يحق للموظف أخذ هذا النوع من الإجازة المرضية')

    @api.constrains('holiday_status_id')
    def check_matching_gender(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.allowed_gender != self.employee_ids[
                0].gender and self.holiday_status_id.allowed_gender != 'both':
                raise ValidationError('هذا النوع من الإجازات لا يحق لهذا الموظف')

    @api.constrains('holiday_status_id')
    def check_matching_marital_status(self):
        if self.holiday_status_id.is_configurable:
            if self.holiday_status_id.marital_status != self.employee_ids[
                0].marital and self.holiday_status_id.marital_status != 'both':
                raise ValidationError('هذا النوع من الإجازات لا يحق لهذا الموظف')
