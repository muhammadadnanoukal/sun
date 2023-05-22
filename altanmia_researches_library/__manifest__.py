# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Researches Library',
    'version': '1.0',
    'category': 'Human Resources/Document',
    'sequence': -50,
    'website': 'https://www.odoo.com/app/approval',
    'description': """
Publish document to wibsite
-------------------------------------------------------------
""",
    'depends': ['website', 'website_mail', 'website_enterprise', 'portal_rating', 'digest','documents'],
    'data': [
        'data/website_data.xml',
        'data/international_university_data.xml',
        'views/document_template.xml',
        'views/folder_view.xml',
        'views/contact_university_view.xml',
        'views/arbitration_view.xml',
        'views/research_keyword_view.xml',
        'views/main_menu.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OEEL-1',

    'assets': {
        'web.assets_frontend': [
            'website_enterprise/static/src/**/*',
            'altanmia_researches_library/static/src/scss/styles.scss',
            'altanmia_researches_library/static/src/js/custom_filter.js',
            'altanmia_researches_library/static/src/xml/custom_filter.xml',
        ],
        'web.assets_backend': [
        ],
        'web.assets_qweb': [
            'altanmia_researches_library/static/src/xml/custom_filter.xml'
        ],
    }
}
