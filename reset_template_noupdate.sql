-- Jalankan query ini di database Odoo SEBELUM upgrade modul
-- Tujuan: reset flag noupdate agar template email ikut diupdate saat upgrade
-- 
-- Cara: masuk ke psql atau pgAdmin, pilih database Odoo, lalu jalankan:

UPDATE ir_model_data
SET noupdate = false
WHERE module = 'kodingyuk_helpdesk'
  AND model = 'mail.template'
  AND name IN (
    'email_template_helpdesk_ticket_state_change',
    'email_template_helpdesk_new_ticket_admin'
  );

-- Setelah query ini, jalankan upgrade modul:
-- ./odoo-bin -u kodingyuk_helpdesk -d <nama_database>
