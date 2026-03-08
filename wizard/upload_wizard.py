# -*- coding: utf-8 -*-
import base64
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from ..lib import firebase_service
except ImportError:
    firebase_service = None

HELPDESK_ROOT_PATH = 'helpdesk_attachment'
MAX_FILE_SIZE = 10 * 1024 * 1024 # 10 MB

class HelpdeskUploadWizard(models.TransientModel):
    _name = 'helpdesk.upload.wizard'
    _description = 'Wizard for Uploading Helpdesk Attachments to Firebase'

    ticket_id = fields.Many2one('kodingyuk.helpdesk.ticket', string='Ticket', readonly=True)
    
    file_1 = fields.Binary(string='File 1')
    file_1_name = fields.Char(string='File Name 1')
    file_2 = fields.Binary(string='File 2')
    file_2_name = fields.Char(string='File Name 2')
    
    def _get_mimetype(self, filename):
        if not filename or '.' not in filename:
            return 'application/octet-stream'
        
        ext = filename.split('.')[-1].lower()
        mimetypes = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'mp4': 'video/mp4',
            'mov': 'video/quicktime',
            'avi': 'video/x-msvideo',
        }
        return mimetypes.get(ext, 'application/octet-stream')

    def _is_allowed_file_type(self, mimetype):
        return mimetype.startswith('image/') or mimetype.startswith('video/')

    def action_confirm_upload(self):
        self.ensure_one()
        
        if not firebase_service:
            raise UserError(_("Firebase service not found. Please ensure 'absensi_sekolah' module is installed and configured."))

        ticket = self.ticket_id
        folder_name = f"ticket_{ticket.id}_{ticket.name.replace('/', '_')}"
        
        uploaded_files_count = 0
        file_data_list = []
        for i in range(1, 3):
            file_content = getattr(self, f'file_{i}')
            file_name = getattr(self, f'file_{i}_name')

            if file_content and file_name:
                decoded_content = base64.b64decode(file_content)
                if len(decoded_content) > MAX_FILE_SIZE:
                    raise UserError(_("File '%s' is too large. Max size is 10MB.") % file_name)

                mimetype = self._get_mimetype(file_name)
                if not self._is_allowed_file_type(mimetype):
                    raise UserError(_("File type for '%s' is not allowed. Only photos and videos.") % file_name)

                file_data_list.append({
                    'content_decoded': decoded_content,
                    'name': file_name,
                    'mimetype': mimetype
                })
                uploaded_files_count += 1
        
        if uploaded_files_count == 0:
            raise UserError(_("No files selected for upload."))

        try:
            for file_data in file_data_list:
                destination_path = f"{HELPDESK_ROOT_PATH}/{folder_name}/{file_data['name']}"

                public_url = firebase_service.upload_file_to_firebase(
                    self.env, 
                    file_data['content_decoded'], 
                    file_data['name'], 
                    destination_path,
                    content_type=file_data['mimetype']
                )
                
                if public_url:
                    self.env['helpdesk.firebase.attachment'].sudo().create({
                        'name': file_data['name'],
                        'file_path': destination_path,
                        'url': public_url,
                        'mimetype': file_data['mimetype'],
                        'ticket_id': ticket.id,
                    })
            
            return {'type': 'ir.actions.client', 'tag': 'reload'}

        except Exception as e:
            raise UserError(_("Firebase Upload Error: %s") % str(e))
