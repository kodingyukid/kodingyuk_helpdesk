# -*- coding: utf-8 -*-
import re
import secrets
from datetime import date, datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

# Komponen robotik (Capital Case + leetspeak untuk bagian akhir password).
_ROBOTIC_COMPONENTS = (
    'Microbit', 'Pico', 'Bit', 'Makerzoid', 'Arduino', 'Python', 'Wedo','Raspberry','KodingYuk', 'ESP'
)

# Leetspeak: a=4, i=1, e=3, o=0 (huruf besar & kecil).
_LEET_MAP = {
    'a': '4', 'A': '4',
    'e': '3', 'E': '3',
    'i': '1', 'I': '1',
    'o': '0', 'O': '0',
}


def _apply_leetspeak(text):
    """Terapkan substitusi leet per karakter."""
    return ''.join(_LEET_MAP.get(ch, ch) for ch in text)


def _capital_case_token(token):
    """Capital case: huruf pertama kapital, sisanya huruf kecil."""
    if not token:
        return ''
    t = token.lower()
    return t[0].upper() + t[1:] if len(t) > 1 else t.upper()


def _first_four_letters(name):
    """Ambil 4 huruf pertama dari nama (non-huruf diabaikan); pad jika kurang dari 4."""
    clean = re.sub(r'[^a-zA-Z]', '', (name or '') or '')
    if not clean:
        clean = 'xxxx'
    segment = clean[:4].lower()
    if len(segment) < 4:
        segment = (segment + 'xxxx')[:4]
    return segment


def _namaleet_from_name(name):
    """
    NamaLeet: 4 huruf pertama nama → Capital Case → leetspeak.
    Contoh: Aril → Ar1l
    """
    raw = _first_four_letters(name)
    cap = _capital_case_token(raw)
    return _apply_leetspeak(cap)


def _komponen_leet():
    """KomponenLeet: pilih acak dari daftar robotik, Capital Case, lalu leetspeak."""
    word = secrets.choice(_ROBOTIC_COMPONENTS)
    cap = _capital_case_token(word)
    return _apply_leetspeak(cap)


def _as_date(today):
    """Normalisasi ke datetime.date (Odoo context_today bisa str atau date)."""
    if today is None:
        return date.today()
    if isinstance(today, str):
        return datetime.strptime(today, '%Y-%m-%d').date()
    if isinstance(today, datetime):
        return today.date()
    return today


def _generate_secure_readable_password(name, today):
    """
    Format KodingYuk: [NamaLeet][DDMM]-[KomponenLeet]

    - NamaLeet: 4 huruf pertama nama (Capital Case + leet).
    - DDMM: tanggal & bulan (hari pembuatan).
    - KomponenLeet: komponen robotik acak + leet.

    Contoh: Ar1l0104-B1t, D1nd0104-S3rv0
    """
    d = _as_date(today)
    namaleet = _namaleet_from_name(name)
    ddmm = d.strftime('%d%m')
    komponen = _komponen_leet()
    return f'{namaleet}{ddmm}-{komponen}'


class HelpdeskPasswordGeneratorWizard(models.TransientModel):
    _name = 'helpdesk.password.generator.wizard'
    _description = 'Generator Password untuk User (IT)'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Karyawan',
        required=True,
        domain=[('user_id', '!=', False)],
        help='Hanya karyawan yang punya akun pengguna (User) yang bisa dipilih.',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Pengguna',
        related='employee_id.user_id',
        readonly=True,
    )
    generated_password = fields.Char(
        string='Password yang dihasilkan',
        readonly=True,
        copy=False,
    )
    info_html = fields.Html(string='Info', compute='_compute_info_html')

    @api.onchange('employee_id')
    def _onchange_employee_clear_password(self):
        self.generated_password = False

    @api.depends('employee_id', 'generated_password')
    def _compute_info_html(self):
        for rec in self:
            if not rec.employee_id:
                rec.info_html = False
                continue
            if not rec.employee_id.user_id:
                rec.info_html = (
                    '<p class="text-warning">Karyawan ini belum punya akun pengguna (User). '
                    'Hubungkan User di form karyawan terlebih dahulu.</p>'
                )
            elif rec.generated_password:
                rec.info_html = (
                    '<p>Salin password di bawah dan berikan ke karyawan melalui saluran aman. '
                    'Password tidak disimpan di layar ini setelah form ditutup.</p>'
                )
            else:
                rec.info_html = (
                    '<p>Klik <strong>Generate Password</strong> untuk membuat password baru.</p>'
                )

    def action_generate_password(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_('Pilih karyawan terlebih dahulu.'))
        if not self.employee_id.user_id:
            raise UserError(
                _('Karyawan "%s" tidak punya pengguna (User) yang terhubung.')
                % (self.employee_id.name or '')
            )
        today = fields.Date.context_today(self)
        self.generated_password = _generate_secure_readable_password(
            self.employee_id.name,
            today,
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.password.generator.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_apply_to_user(self):
        self.ensure_one()
        if not self.generated_password:
            raise UserError(_('Generate password terlebih dahulu.'))
        if not self.employee_id or not self.employee_id.user_id:
            raise UserError(_('Karyawan tidak valid atau tidak punya akun pengguna.'))
        user = self.employee_id.user_id.sudo()
        user.write({'password': self.generated_password})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Password diperbarui'),
                'message': _('Password akun %s telah diatur.') % (user.login,),
                'sticky': False,
                'type': 'success',
            },
        }
