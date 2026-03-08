# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class HelpdeskTicket(models.Model):
    _name = 'kodingyuk.helpdesk.ticket'
    _description = 'KodingYuk Helpdesk Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Ticket Number', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    staff_id = fields.Many2one('res.partner', string='Nama Staff', required=True, tracking=True)
    system_id = fields.Many2one('helpdesk.system.type', string='Sistem yang Digunakan', tracking=True)
    issue_type_id = fields.Many2one('helpdesk.issue.type', string='Jenis Masalah', tracking=True)
    
    chronology = fields.Text(string='Kronologi Singkat', required=True)
    data_to_fix = fields.Text(string='Data yang Perlu Diperbaiki', required=True)
    
    date = fields.Datetime(string='Tanggal', default=fields.Datetime.now, readonly=True)
    
    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('solved', 'Solved'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='new', tracking=True)

    attachment_ids = fields.One2many('helpdesk.firebase.attachment', 'ticket_id', string='Lampiran Bukti (Firebase)')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('kodingyuk.helpdesk.ticket') or _('New')
        return super(HelpdeskTicket, self).create(vals_list)

    def write(self, vals):
        res = super(HelpdeskTicket, self).write(vals)
        if 'state' in vals:
            for rec in self:
                rec._send_state_change_email()
        return res

    def _send_state_change_email(self):
        template = self.env.ref('KodingYuk_helpdesk.email_template_helpdesk_ticket_state_change', raise_if_not_found=False)
        if template:
            for rec in self:
                if rec.staff_id and rec.staff_id.email:
                    _logger.info("Sending email for ticket %s (State: %s) to %s", rec.name, rec.state, rec.staff_id.email)
                    rec.message_post_with_source(
                        source_ref=template,
                        subtype_xmlid='mail.mt_comment',
                    )
                else:
                    _logger.warning("Cannot send email for ticket %s: Staff %s has no email address", rec.name, rec.staff_id.name)
        else:
            _logger.warning("Email template KodingYuk_helpdesk.email_template_helpdesk_ticket_state_change not found")

    def action_upload_attachment(self):
        self.ensure_one()
        return {
            'name': _('Upload Attachment to Firebase'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.upload.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ticket_id': self.id}
        }
