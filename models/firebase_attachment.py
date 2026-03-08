# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

try:
    from ..lib import firebase_service
except ImportError:
    firebase_service = None

class HelpdeskFirebaseAttachment(models.Model):
    _name = 'helpdesk.firebase.attachment'
    _description = 'Helpdesk Firebase Attachment'

    def unlink(self):
        for rec in self:
            if firebase_service and rec.file_path:
                try:
                    firebase_service.delete_file_from_firebase(self.env, rec.file_path)
                except Exception as e:
                    _logger.warning("Gagal hapus file di Firebase: %s", str(e))
        return super(HelpdeskFirebaseAttachment, self).unlink()

    name = fields.Char(string='File Name', required=True)
    file_path = fields.Char(string='Firebase File Path', required=True)
    url = fields.Char(string='Preview Link')
    mimetype = fields.Char(string='MIME Type')
    
    ticket_id = fields.Many2one(
        'kodingyuk.helpdesk.ticket', 
        string='Ticket',
        ondelete='cascade',
        index=True
    )

    def action_open_link(self):
        self.ensure_one()
        if self.url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.url,
                'target': 'new',
            }
