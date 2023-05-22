from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class University(models.Model):
    _inherit = "res.partner"

    def name_get(self):
        name_array = []

        hierarchical_naming = self.env.context.get('path', True)
        internation_dep = self.env.context.get("international", False)
        print("context", self.env.context, internation_dep)
        for record in self:
            if hierarchical_naming and record.parent_id and not internation_dep:
                node = record.parent_id
                name = record.name
                while node:
                    name = "%s / %s"%(node.name, name)
                    node= node.parent_id
                name_array.append((record.id,name))
            else:
                name_array.append((record.id, record.name))
        return name_array
        
    is_university = fields.Boolean("Is a university", default=False)

    is_international = fields.Boolean("Is International", default=False)

    university_type = fields.Selection([
        ('national','National Universities'),
        ('foreign', 'Foreign Universities'),
        ('references', 'Scientific References'),
        ('library', 'Library'),
    ], string="Catalog type")

    @api.constrains('university_type', 'parent_id')
    def _check_university_type_required(self):
        for record in self:
            if not record.parent_id and not record.university_type:
                raise ValidationError("Catalog type is required.")

    description = fields.Html(string="Description", translate=True)

    children_count = fields.Integer(compute='_compute_children_count', string='ch count')

    tree_depth = fields.Integer(compute='_compute_tree_depth', string="Tree Depth")

    research_count = fields.Integer(compute='_compute_research_count', string='Research Count')

    def _compute_research_count(self):
        for rec in self:
            rec.research_count = rec.env['documents.document'].search_count([('related_id', 'in', rec.get_children_ids())])

    def _compute_children_count(self):
        self.children_count = len(self.child_ids)

    def get_children_ids(self):
        ids = [self.id]
        for c in self.child_ids:
            ids = ids + c.get_children_ids()
        return ids
    
    def _compute_tree_depth(self):
        depth = 1
        node = self.sudo().parent_id
        while node:
            depth +=1
            node = node.parent_id
        self.tree_depth = depth

    @api.model
    def create(self, vals):
        if vals.get('parent_id', False):
            parent = self.env['res.partner'].browse(vals['parent_id'])
            vals['university_type'] = parent.university_type

        return super().create(vals)
