# -*- coding: utf-8 -*-
import logging
import json
from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, storage
except ImportError:
    _logger.warning("Firebase Admin SDK not installed. Please run: pip install firebase-admin")
    firebase_admin = None
    credentials = None
    storage = None

# Parameter kunci untuk menyimpan konfigurasi Firebase di ir.config_parameter
FIREBASE_CREDENTIALS_PARAM = 'firebase.service.account.key'
FIREBASE_BUCKET_NAME_PARAM = 'firebase.storage.bucket.name'

_firebase_app = None

def get_firebase_app(env):
    global _firebase_app
    if _firebase_app:
        return _firebase_app

    if firebase_admin is None:
         raise UserError(_("Firebase Admin SDK tidak ditemukan. Install: pip install firebase-admin"))

    config_params = env['ir.config_parameter'].sudo()
    service_account_key_str = config_params.get_param(FIREBASE_CREDENTIALS_PARAM)
    
    if not service_account_key_str:
        raise UserError(_("Kunci akun layanan Firebase (%s) belum diatur.") % FIREBASE_CREDENTIALS_PARAM)

    try:
        service_account_info = json.loads(service_account_key_str)
        cred = credentials.Certificate(service_account_info)
        bucket_name = config_params.get_param(FIREBASE_BUCKET_NAME_PARAM)
        
        try:
            _firebase_app = firebase_admin.get_app()
        except ValueError:
            _firebase_app = firebase_admin.initialize_app(cred, {'storageBucket': bucket_name})
        return _firebase_app
    except Exception as e:
        raise UserError(_("Gagal menginisialisasi Firebase: %s") % str(e))

def upload_file_to_firebase(env, file_content, file_name, destination_path, content_type=None):
    app = get_firebase_app(env)
    bucket = storage.bucket(app=app)
    blob = bucket.blob(destination_path)
    try:
        blob.metadata = {'Content-Disposition': 'inline'}
        blob.upload_from_string(file_content, content_type=content_type)
        blob.make_public()
        return blob.public_url
    except Exception as e:
        raise UserError(_("Gagal upload ke Firebase: %s") % str(e))

def delete_file_from_firebase(env, file_path):
    app = get_firebase_app(env)
    bucket = storage.bucket(app=app)
    blob = bucket.blob(file_path)
    if blob.exists():
        try:
            blob.delete()
            return True
        except Exception as e:
            raise UserError(_("Gagal hapus dari Firebase: %s") % str(e))
    return False
