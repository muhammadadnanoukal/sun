{
    'name': 'ALTANMYA POS Low Stock Alert',
    'version': '1.0.0',
    'category': 'Sales/Point of Sale',
    'author': 'ALTANMYA - TECHNOLOGY SOLUTIONS',
    'company': 'ALTANMYA - TECHNOLOGY SOLUTIONS Part of ALTANMYA GROUP',
    'website': "http://tech.altanmya.net",
    'depends': ['base', 'base_setup', 'point_of_sale'],
    'data': ['views/config.xml'],
    'assets': {
            "web.assets_qweb": [],
            "point_of_sale.assets":
                [
                    "web/static/lib/zxing-library/zxing-library.js",
                    "ALTANMYA_Low_Stock_POS_Alert/static/src/js/models.js",
                ]
        },
    'installable': True,
    'auto_install': True,
    'application': False,
    'sequence': 0,
}
