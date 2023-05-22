# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import http, _
from odoo.http import request
from odoo.osv import expression
import os
import base64
import logging
import datetime
from dateutil.relativedelta import relativedelta

import werkzeug.datastructures
import werkzeug.exceptions
import werkzeug.local
import werkzeug.routing
import werkzeug.wrappers
from operator import itemgetter
from werkzeug import urls
from werkzeug.wsgi import wrap_file
from odoo.addons.http_routing.models.ir_http import slug

try:
    from werkzeug.middleware.shared_data import SharedDataMiddleware
except ImportError:
    from werkzeug.wsgi import SharedDataMiddleware

logger = logging.getLogger(__name__)

from odoo.addons.website.controllers.main import QueryURL

from odoo.osv.expression import AND, OR
from odoo.tools import groupby as groupbyelem

from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class WebsiteDocument(portal.CustomerPortal):
    _items_per_page = 20

    def _get_file_response(self, id, field='datas'):
        """ returns the http response to download one file. """
        record = request.env['documents.document'].browse(int(id))

        if not record or not record.exists():
            raise request.not_found()

        return request.env['ir.binary']._get_stream_from(record, field).get_response(as_attachment=True)
    
    # single file download route.
    @http.route(["/research/download/<int:id>"],
                type='http', auth='public')
    def download_research(self, id=None, **kwargs):
        """
        used to download a single file from the portal multi-file page.

        :param id: id of the file
        :param access_token:  token of the share link
        :param share_id: id of the share link
        :return: a portal page to preview and download a single file.
        """
        try:
            document = self._get_file_response(id, field='raw')
            return document or request.not_found()
        except Exception:
            logger.exception("Failed to download document %s" % id)

        return request.not_found()
    
    @http.route(['/researches/view/<model("documents.document"):research>',], type='http', auth="public", website=True, sitemap=True)
    def document_view(self, research, sortby=None, filterby=None, search=None, search_in='all', groupby='none', **kwargs):
        
        query = werkzeug.urls.url_encode({
                    'redirect': '/researches/view/%s' % (slug(research),),
                })
        usr = request.env.user._is_public()
        values = ({
            'doc': research.sudo(),
            'page_name': 'home',
            'default_url': '/researches',
            'search_in': search_in,
            'search': search,
            'sortby': sortby,
            'groupby': groupby,
            'filterby': filterby,
            'public': usr,
            'btn_url': '/web/login?%s' %query if usr else '/research/download/%s'%research.id
        })

        return request.render('altanmia_researches_library.document_info',values)

    @http.route(['/catalog', '/catalog/page/<int:page>'], type='http', auth="public", website=True,
                sitemap=True)
    def show_universities(self, cat=None ,university=None,page=1):
        unversities_search = request.env['res.partner']
        domain = [('is_university','=',True),('university_type','=',cat),  ('parent_id','=',int(university) if university else False)]

        universities_count = unversities_search.search_count(domain)

        print("domain", university, domain, universities_count)

        pager = portal_pager(
            url="/catalog",
            url_args={'university': university, 'cat':cat},
            total=universities_count,
            page=page,
            step=self._items_per_page
        )

        universities = unversities_search.search(domain, order='create_date',limit=self._items_per_page, offset=pager['offset'])
        selected_university = False
        if university:
            selected_university = unversities_search.browse(int(university))
        elif universities_count == 1:
            selected_university = universities[0]
            return request.redirect(f'/catalog?cat={cat}&university={selected_university.id}')

        keep = QueryURL(f'/catalog?cat={cat}&university={university}&page={page}')

        values = {
            'universities': universities,
            'university': selected_university,
            'pager': pager,
            'keep': keep,
            'base_url': '/researches' if university else '/catalog'
        }

        return request.render("altanmia_researches_library.universities_list", values)

    def _research_get_groupby_mapping(self):
        return {
            'university': 'university',
            'college': 'college',
            'year': 'year',
            'domain': 'research_domain',
        }

    @http.route([
        '/researches',
        '/researches/page/<int:page>'
    ], type='http', auth='public', website=True)
    def portal_researches(self,source=None, university=None, doc=None, page=1, sortby=None, filterby=None, search=None, search_in='all', groupby='none', **kwargs):
        values = self._prepare_portal_layout_values()

        research = request.env['documents.document'].sudo()

        universites = request.env['res.partner'].browse(int(university)) if university else \
            request.env['res.partner'].search([('university_type','=',source)])

        domain = self._get_portal_default_domain1()

        # if source and filterby not in ['internal', 'all']:
        #     filterby = 'external'
        #     groupby = 'domain'

        unv = None
        if universites and len(universites) == 1:
            unv = universites.browse(0)
            domain = AND([domain, [('related_id', 'in', unv.get_children_ids())]])

        searchbar_sortings = {
            'create_date': {'label': _('Date'), 'order': 'create_date'},
            'name': {'label': _('Name'), 'order': 'name'},
        }

        searchbar_inputs = {
            'all': {'label': _('Search in All'), 'input': 'all'},
            'name': {'label': _('Search in Name'), 'input': 'name'},
            'keyword': {'label': _('Search in Keywords'), 'input': 'keyword'},
            'abstract': {'label': _('Search in Abstract'), 'input': 'abstract'}
        }

        searchbar_filters = {
            # 'university': {'label': _("Upcoming"), 'domain': [('start', '>=', datetime.today())]},
            # 'past': {'label': _("Past"), 'domain': [('start', '<', datetime.today())]},
            'all': {'label': _("All"), 'domain': []},
            'phd': {'label': _('PHD'), 'domain':[('research_degree', '=', 'phd')]},
            'master': {'label': _('Master'), 'domain':[('research_degree', '=', 'master')]},
            'year_ago': {'label': _('This Year'), 'domain':[('create_date', '>=', datetime.datetime.today() - datetime.timedelta(days=365))]},
            # 'internal': {'label': _('Internal'), 'domain':[('research_nat', '=', 'internal')]},
            # 'external': {'label': _('External'), 'domain':[('research_nat', '=', 'external')]},
        }

        searchbar_groupby = {
            'none': {'label': _('None'), 'input': 'none'},
            'year': {'label': _('Year'), 'input': 'year'},
        }

        if university:
            searchbar_groupby.update({'domain': {'label': _('Domain'), 'input': 'domain'}})
        else:
            searchbar_groupby.update({
                'university': {'label': _('University'), 'input': 'university'},
                'college': {'label': _('College'), 'input': 'college'},
                'domain': {'label': _('Domain'), 'input': 'domain'}
            })

        if not sortby:
            sortby = 'create_date'
        sort_order = searchbar_sortings[sortby]['order']

        groupby_mapping = self._research_get_groupby_mapping()
        groupby_field = groupby_mapping.get(groupby, None)
        if groupby_field is not None and groupby_field not in research._fields:
            raise ValueError(_("The field '%s' does not exist in the targeted model", groupby_field))
        order = '%s, %s' % (groupby_field, sort_order) if groupby_field else sort_order

        #order =  sort_order

        if not filterby:
            filterby = 'all'
        domain = AND([domain, searchbar_filters[filterby]['domain']])

        if search and search_in:
            domain = AND([domain, self._get_research_search_domain(search_in, search)])

        research_count = research.search_count(domain)
        pager = portal_pager(
            url="/researches",
            url_args={'sortby': sortby, 'search_in': search_in, 'search': search, 'groupby': groupby, 'source':source, 'university':university},
            total=research_count,
            page=page,
            step=self._items_per_page
        )
        researches = research.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])


        grouped_researches = False
        # If not False, this will contain a list of tuples (record of groupby, recordset of events):
        # [(res.users(2), calendar.event(1, 2)), (...), ...]
        if groupby_field:
            grouped_researches = [(g, research.concat(*rs)) for g, rs in groupbyelem(researches, itemgetter(groupby_field))]

        keep = QueryURL('/researches', [sortby, filterby, search, search_in, groupby])

        values.update({
            'researches': researches,
            'grouped_researches': grouped_researches,
            'page_name': 'home',
            'pager': pager,
            'default_url': '/researches',
            'searchbar_sortings': searchbar_sortings,
            'search_in': search_in,
            'search': search,
            'sortby': sortby,
            'keep': keep,
            'university': unv,
            'groupby': groupby,
            'filterby': filterby,
            'searchbar_inputs': searchbar_inputs,
            'searchbar_filters': searchbar_filters,
            'searchbar_groupby': searchbar_groupby,
        })
        return request.render("altanmia_researches_library.document_list_layout", values)
    
    def _get_research_search_domain(self, search_in, search):
        search_domain = []
        if search_in in ('all', 'name'):
            search_domain = OR([search_domain, [('name', 'ilike', search)]])
        if search_in in ('all', 'abstract'):
            search_domain = OR([search_domain, [('abstract', 'ilike', search)]])
        if search_in in ('all', 'keyword'):
            search_domain = OR([search_domain, [('keyword_ids.name', 'ilike', search)]])
        return search_domain
     
    def _get_portal_default_domain1(self):
        return [
            ('is_research', '=', True),
            ('is_published', '=', True),
        ]

    @http.route(['/researches/search_fileds'], type="json", auth="public", website=True, sitemap=False)
    def get_fields(self):
        fields =  [
            { 'string': "ID", 'type': "id", 'name': "id" },
            { 'string': "Name", 'type': "char", 'name': "name" },
            {'string': "Created at", 'type': "date", 'name':'create_date'},
            { 'string': "Abstract", 'type': "char", 'name': "abstract" },
            { 'string': "keywords", 'type': "many2many", 'name': "keyword_ids" },
            { 'string': "Specialization", 'type': "many2one", 'name': "related_id" },
            { 'string': "College", 'type': "many2one", 'name': "related_id.parent_id" },
            { 'string': "University", 'type': "many2one", 'name': "related_id.parent_id.parent_id" },
            { 'string': "Degree", 'type': "selection", 'name': "research_degree" , 'selection':[('phd', 'PHD'),('master', 'Master'),('other','Published Researches')]}
        ]
        return  fields
    
    @http.route(['/researches/custom_filter'], type="json", auth="public", website=True, sitemap=False)
    def research_filter(self, conditions):
        domain = self._get_portal_default_domain1()
        for cnd in conditions:
            if len(cnd['or_conditions'])>0:
                andDomain = []
                for d in cnd['domain']:
                    andDomain = AND([andDomain, [tuple(d)]])
                orDomain = andDomain
                for orD in cnd['or_conditions']:
                    andDomain = []
                    for d in orD['domain']:
                        andDomain = AND([andDomain,[tuple(d)] ])
                    orDomain = OR([orDomain,andDomain])

                domain = AND([domain,orDomain])
            else:
                for d in cnd['domain']:
                   domain =  AND([domain, [tuple(d)] ])

        research = request.env['documents.document'].sudo()
        researches = research.search(domain, order='create_date', limit=50)
        keep = QueryURL('/researches', [None, None, None, 'all', 'none'])
        result = request.env['ir.ui.view']._render_template("altanmia_researches_library.researches_list", {
                'researches': researches,
                'keep': keep,
            })
        logger.info("custom filter domain %s"%domain)
        return result
        

        

