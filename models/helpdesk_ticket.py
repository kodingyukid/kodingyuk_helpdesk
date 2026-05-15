# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    _name = 'kodingyuk.helpdesk.ticket'
    _description = 'KodingYuk Helpdesk Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Ticket Number', required=True, copy=False,
        readonly=True, default=lambda self: _('New')
    )
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
        ('cancelled', 'Cancelled'),
    ], string='Status', default='new', tracking=True)

    attachment_ids = fields.One2many(
        'helpdesk.firebase.attachment', 'ticket_id',
        string='Lampiran Bukti (Firebase)'
    )

    # ─── Sequence ────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('kodingyuk.helpdesk.ticket')
                    or _('New')
                )
        records = super().create(vals_list)
        # Kirim notifikasi ke admin untuk setiap tiket baru
        for rec in records:
            rec._send_new_ticket_email_to_admin()
        return records

    # ─── State Change ────────────────────────────────────────────────

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            for rec in self:
                rec._send_state_change_email_to_user()
        return res

    # ─── Email: Tiket Baru → Admin ───────────────────────────────────

    def _send_new_ticket_email_to_admin(self):
        """Kirim email ke semua user di grup helpdesk_manager saat tiket baru dibuat."""
        self.ensure_one()
        template = self.env.ref(
            'kodingyuk_helpdesk.email_template_helpdesk_new_ticket_admin',
            raise_if_not_found=False
        )
        if not template:
            _logger.warning("Template email admin tidak ditemukan: email_template_helpdesk_new_ticket_admin")
            return

        # Ambil semua user di grup helpdesk_manager
        manager_group = self.env.ref(
            'kodingyuk_helpdesk.group_helpdesk_manager',
            raise_if_not_found=False
        )
        if not manager_group:
            _logger.warning("Grup helpdesk_manager tidak ditemukan")
            return

        admin_partners = manager_group.users.mapped('partner_id').filtered(
            lambda p: p.email
        )
        if not admin_partners:
            _logger.warning("Tidak ada admin dengan email di grup helpdesk_manager")
            return

        try:
            # Kirim ke setiap admin
            for partner in admin_partners:
                template.with_context(
                    email_to=partner.email,
                ).send_mail(
                    self.id,
                    force_send=True,
                    email_values={'recipient_ids': [(4, partner.id)]},
                )
            _logger.info(
                "Email tiket baru %s dikirim ke %d admin",
                self.name, len(admin_partners)
            )
        except Exception as e:
            # Jangan sampai gagal kirim email menghentikan pembuatan tiket
            _logger.error("Gagal kirim email tiket baru %s: %s", self.name, str(e))

    # ─── Email: State Change → User ──────────────────────────────────

    def _send_state_change_email_to_user(self):
        """Kirim email ke pelapor (staff_id) saat status tiket berubah."""
        self.ensure_one()
        template = self.env.ref(
            'kodingyuk_helpdesk.email_template_helpdesk_ticket_state_change',
            raise_if_not_found=False
        )
        if not template:
            _logger.warning("Template email user tidak ditemukan: email_template_helpdesk_ticket_state_change")
            return

        if not self.staff_id:
            _logger.warning("Tiket %s tidak memiliki staff_id", self.name)
            return

        if not self.staff_id.email:
            _logger.warning(
                "Tidak bisa kirim email untuk tiket %s: Staff '%s' tidak punya email",
                self.name, self.staff_id.name
            )
            return

        try:
            template.send_mail(self.id, force_send=True)
            _logger.info(
                "Email update status tiket %s (state: %s) dikirim ke %s",
                self.name, self.state, self.staff_id.email
            )
        except Exception as e:
            _logger.error(
                "Gagal kirim email update status tiket %s: %s",
                self.name, str(e)
            )

    # ─── Actions ─────────────────────────────────────────────────────

    def action_upload_attachment(self):
        self.ensure_one()
        return {
            'name': _('Upload Attachment to Firebase'),
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.upload.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_ticket_id': self.id},
        }
