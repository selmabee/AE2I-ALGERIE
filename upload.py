from flask import Blueprint, request, jsonify
from supabase import create_client, Client
import os
import logging
from werkzeug.utils import secure_filename
import mimetypes

logger = logging.getLogger(__name__)

upload_bp = Blueprint('upload', __name__)

SUPABASE_URL = os.environ.get('SUPABASE_URL', "https://uisxrkzkqtbapnxnyuod.supabase.co")
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVpc3hya3prcXRiYXBueG55dW9kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjE5MDA0MTksImV4cCI6MjA3NzQ3NjQxOX0.lySWXQnIUDdCtrYVTrgoBMCIKWsKuqN8b-ipl3qSDwg")
BUCKET_NAME = "uploads"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

MAX_FILE_SIZE = 50 * 1024 * 1024

FILE_TYPE_CONFIG = {
    'logos': {
        'extensions': ['.png', '.jpg', '.jpeg', '.svg', '.webp'],
        'folder': 'logos'
    },
    'images': {
        'extensions': ['.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif'],
        'folder': 'images'
    },
    'videos': {
        'extensions': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
        'folder': 'videos'
    },
    'brochures': {
        'extensions': ['.pdf', '.doc', '.docx'],
        'folder': 'brochures'
    },
    'certificats': {
        'extensions': ['.pdf', '.jpg', '.jpeg', '.png'],
        'folder': 'certificats'
    },
    'cv': {
        'extensions': ['.pdf', '.doc', '.docx'],
        'folder': 'cv'
    }
}

def get_file_extension(filename):
    return os.path.splitext(filename)[1].lower()

def detect_file_type(filename, requested_type=None):
    ext = get_file_extension(filename)

    if requested_type and requested_type in FILE_TYPE_CONFIG:
        if ext in FILE_TYPE_CONFIG[requested_type]['extensions']:
            return requested_type

    for file_type, config in FILE_TYPE_CONFIG.items():
        if ext in config['extensions']:
            return file_type

    return None

def validate_file(file, file_type):
    if not file or file.filename == '':
        return False, "Aucun fichier fourni"

    ext = get_file_extension(file.filename)

    if file_type not in FILE_TYPE_CONFIG:
        return False, f"Type de fichier non supporté: {file_type}"

    if ext not in FILE_TYPE_CONFIG[file_type]['extensions']:
        allowed = ', '.join(FILE_TYPE_CONFIG[file_type]['extensions'])
        return False, f"Extension non autorisée pour {file_type}. Autorisées: {allowed}"

    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        return False, f"Fichier trop volumineux. Maximum: {MAX_FILE_SIZE / (1024*1024):.0f}MB"

    return True, None

def log_upload_success(filename, original_filename, file_type, file_size, storage_path, public_url, mime_type, user_ip):
    try:
        supabase.table('media_uploads').insert({
            'filename': filename,
            'original_filename': original_filename,
            'file_type': file_type,
            'file_size': file_size,
            'storage_path': storage_path,
            'public_url': public_url,
            'mime_type': mime_type,
            'status': 'success',
            'user_ip': user_ip
        }).execute()
        logger.info(f"Upload enregistré en base: {storage_path}")
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de l'upload: {str(e)}")

def log_upload_error(filename, file_type, error_message, user_ip):
    try:
        supabase.table('media_uploads').insert({
            'filename': filename or 'unknown',
            'original_filename': filename or 'unknown',
            'file_type': file_type or 'unknown',
            'file_size': 0,
            'storage_path': f"error/{filename or 'unknown'}",
            'public_url': '',
            'status': 'error',
            'error_message': error_message,
            'user_ip': user_ip
        }).execute()
        logger.warning(f"Erreur d'upload enregistrée: {filename} - {error_message}")
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de l'erreur: {str(e)}")

@upload_bp.route('/upload-file', methods=['POST'])
def upload_file():
    from datetime import datetime

    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'Aucun fichier dans la requête'
            }), 400

        file = request.files['file']
        requested_type = request.form.get('type', None)

        file_type = detect_file_type(file.filename, requested_type)

        if not file_type:
            log_upload_error(file.filename, file_type, 'Type de fichier non reconnu ou non supporté', request.remote_addr)
            return jsonify({
                'success': False,
                'error': 'Type de fichier non reconnu ou non supporté'
            }), 400

        is_valid, error_message = validate_file(file, file_type)
        if not is_valid:
            log_upload_error(file.filename, file_type, error_message, request.remote_addr)
            return jsonify({
                'success': False,
                'error': error_message
            }), 400

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        unique_filename = f"{timestamp}_{filename}"

        folder = FILE_TYPE_CONFIG[file_type]['folder']
        storage_path = f"{folder}/{unique_filename}"

        file_content = file.read()
        file_size = len(file_content)

        mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

        result = supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": mime_type}
        )

        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(storage_path)

        log_upload_success(unique_filename, file.filename, file_type, file_size, storage_path, public_url, mime_type, request.remote_addr)

        logger.info(f"Fichier uploadé avec succès: {storage_path} (URL: {public_url})")

        return jsonify({
            'success': True,
            'message': 'Fichier uploadé avec succès',
            'url': public_url,
            'type': file_type,
            'filename': unique_filename,
            'path': storage_path,
            'size': file_size
        }), 201

    except Exception as e:
        logger.error(f"Erreur lors de l'upload: {str(e)}")
        log_upload_error(request.files.get('file', {}).filename if 'file' in request.files else 'unknown',
                        request.form.get('type'), str(e), request.remote_addr)
        return jsonify({
            'success': False,
            'error': f"Erreur lors de l'upload: {str(e)}"
        }), 500

@upload_bp.route('/upload-file/types', methods=['GET'])
def get_supported_types():
    types_info = {}
    for file_type, config in FILE_TYPE_CONFIG.items():
        types_info[file_type] = {
            'extensions': config['extensions'],
            'folder': config['folder']
        }

    return jsonify({
        'success': True,
        'types': types_info,
        'max_file_size_mb': MAX_FILE_SIZE / (1024 * 1024)
    })

@upload_bp.route('/upload-file/health', methods=['GET'])
def upload_health():
    try:
        buckets = supabase.storage.list_buckets()
        bucket_exists = any(bucket['name'] == BUCKET_NAME for bucket in buckets)

        return jsonify({
            'success': True,
            'bucket': BUCKET_NAME,
            'bucket_exists': bucket_exists,
            'status': 'operational'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@upload_bp.route('/upload-file/logs', methods=['GET'])
def get_upload_logs():
    try:
        file_type = request.args.get('type', None)
        status = request.args.get('status', 'success')
        limit = int(request.args.get('limit', 50))

        query = supabase.table('media_uploads').select('*')

        if file_type:
            query = query.eq('file_type', file_type)

        if status:
            query = query.eq('status', status)

        result = query.order('upload_date', desc=True).limit(limit).execute()

        return jsonify({
            'success': True,
            'count': len(result.data),
            'uploads': result.data
        })
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@upload_bp.route('/upload-file/stats', methods=['GET'])
def get_upload_stats():
    try:
        by_type = supabase.table('media_uploads').select('file_type, count()', count='exact').where("status = 'success'").group_by('file_type').execute()

        total_size = supabase.table('media_uploads').select('file_size', count='exact').where("status = 'success'").execute()

        stats = {
            'total_uploads': len(total_size.data) if total_size.data else 0,
            'total_size_mb': sum(u.get('file_size', 0) for u in total_size.data) / (1024 * 1024) if total_size.data else 0,
            'by_type': {}
        }

        by_type_result = supabase.table('media_uploads').select('file_type, count()', count='exact').execute()
        for item in by_type_result.data:
            stats['by_type'][item['file_type']] = item.get('count', 0)

        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Erreur lors du calcul des stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
