# -*- coding: utf-8 -*-
{
    'name': 'KodingYuk Helpdesk',
    'version': '1.0',
    'summary': 'Helpdesk Ticketing System with Firebase Storage',
    'description': 'Modul Helpdesk untuk pengelolaan ticket dengan lampiran ke Firebase Storage.',
    'category': 'Services/Helpdesk',
    'author': 'KodingYuk',
    'website': 'https://kodingyuk.com',
    'depends': ['base', 'mail', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'wizard/upload_wizard_view.xml',
        'views/helpdesk_ticket_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
