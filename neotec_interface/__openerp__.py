# -*- coding: utf-8 -*-
{
    'name': "Neotec Interface",

    'summary': """
        Interfaz Fiscal para la República Dominicana""",

    'description': """
        Interfaz Fiscal con soporte para impresoras de distintos fabricantes incluidos Epson, Bisolon, entre otros.
    """,

    'author': "Grupo Neotec",
    'website': "http://gruponeotec.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Fiscal',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','point_of_sale'],

    # always loaded
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/ncf_types.xml',
        'data/payment_types.xml',
        'data/products.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    'qweb': [
        'static/src/xml/custom_pos.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'external_dependencies': {
        'python': ['paramiko']
    }
}