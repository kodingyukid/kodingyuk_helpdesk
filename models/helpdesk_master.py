# -*- coding: utf-8 -*-
from odoo import models, fields

class HelpdeskIssueType(models.Model):
    _name = 'helpdesk.issue.type'
    _description = 'Helpdesk Issue Type'
    _order = 'name'

    name = fields.Char(string='Jenis Masalah', required=True)
    active = fields.Boolean(default=True)

class HelpdeskSystemType(models.Model):
    _name = 'helpdesk.system.type'
    _description = 'Helpdesk System'
    _order = 'name'

    name = fields.Char(string='Sistem', required=True)
    active = fields.Boolean(default=True)
