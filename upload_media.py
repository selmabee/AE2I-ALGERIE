"""
Module de gestion d'uploads pour AE2I
Blueprint Flask autonome avec intégration Supabase Storage
"""

import os
import uuid
import logging
from datetime import datetime
from typing import List, Tuple
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify
from supabase import create_client, Client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://uisxrkzkqtbapnxnyuod.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVpc3hya3prcXRiYXBueG55dW9kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjE5MDA0MTksImV4cCI6MjA3NzQ3NjQxOX0.lySWXQnIUDdCtrYVRrgoBMCIKWsKuqN8b-ipl3qSDwg")
BUCKET_NAME = "ae2i-files"

MAX_FILE_SIZE = 50 * 1024 * 1024
FORBIDDEN_EXTENSIONS = {'.exe', '.bat', '.js', '.php', '.sh'}
ALLOWED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp',
    '.mp4', '.mov', '.avi', '.mkv',
    '.pdf', '.docx', '.xlsx', '.pptx', '.zip', '.rar'
}

CATEGORY_MAP = {
    'image/jpeg': 'images',
    'image/jpg': 'images',
    'image/png': 'images',
    'image/gif': 'images',
    'image/webp': 'images',
    'video/mp4': 'videos',
    'video/quicktime': 'videos',
    'video/x-msvideo': 'videos',
    'video/x-matroska': 'videos',
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'documents',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'documents',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'documents',
    'application/zip': 'documents',
    'application/x-rar-compressed': 'documents',
}

upload_bp = Blueprint('upload', __name__)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Connexion Supabase établie avec succès")
except Exception as e:
    logger.error(f"Erreur de connexion Supabase: {str(e)}")
    supabase = None


def ensure_bucket_exists():
    """
    Vérifie et crée le bucket ae2i-files s'il n'existe pas
    """
    try:
        buckets = supabase.storage.list_buckets()
        bucket_names = [bucket.name for bucket in buckets]

        if BUCKET_NAME not in bucket_names:
            logger.info(f"Création du bucket {BUCKET_NAME}")
            supabase.storage.create_bucket(
                BUCKET_NAME,
                options={"public": True}
            )
            logger.info(f"Bucket {BUCKET_NAME} créé avec succès")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la vérification/création du bucket: {str(e)}")
        return False


def validate_file(file) -> Tuple[bool, str]:
    """
    Valide un fichier uploadé
    Returns: (is_valid, error_message)
    """
    if not file:
        return False, "Aucun fichier fourni"

    if file.filename == '':
        return False, "Nom de fichier vide"

    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext in FORBIDDEN_EXTENSIONS:
        return False, f"Extension interdite: {file_ext}"

    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"Extension non autorisée: {file_ext}"

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        return False, f"Fichier trop volumineux (max 50 Mo)"

    if file_size == 0:
        return False, "Fichier vide"

    return True, ""


def get_category(mime_type: str, custom_category: str = None) -> str:
    """
    Détermine la catégorie d'un fichier
    """
    if custom_category:
        return custom_category

    return CATEGORY_MAP.get(mime_type, 'documents')


def generate_unique_filename(original_filename: str) -> str:
    """
    Génère un nom de fichier unique avec UUID et timestamp
    """
    file_ext = os.path.splitext(original_filename)[1].lower()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    return f"{timestamp}_{unique_id}{file_ext}"


def upload_to_supabase(file, category: str) -> dict:
    """
    Upload un fichier vers Supabase Storage et log dans la base
    """
    try:
        is_valid, error_msg = validate_file(file)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg
            }

        if not ensure_bucket_exists():
            return {
                "success": False,
                "error": "Impossible de vérifier/créer le bucket"
            }

        original_filename = secure_filename(file.filename)
        unique_filename = generate_unique_filename(original_filename)
        mime_type = file.content_type or 'application/octet-stream'
        category = get_category(mime_type, category)

        storage_path = f"{category}/{unique_filename}"

        file.seek(0)
        file_content = file.read()
        file_size = len(file_content)

        result = supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": mime_type}
        )

        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(storage_path)

        uploaded_at = datetime.utcnow().isoformat() + 'Z'

        log_data = {
            "id": str(uuid.uuid4()),
            "created_at": uploaded_at,
            "original_filename": original_filename,
            "unique_filename": unique_filename,
            "file_type": mime_type,
            "size": file_size,
            "category": category,
            "public_url": public_url,
            "storage_path": storage_path,
            "status": "success",
            "error_message": None
        }

        try:
            supabase.table('media_uploads').insert(log_data).execute()
        except Exception as log_error:
            logger.warning(f"Erreur de journalisation (upload réussi): {str(log_error)}")

        return {
            "success": True,
            "message": "Fichier uploadé avec succès",
            "public_url": public_url,
            "storage_path": storage_path,
            "file_type": mime_type,
            "uploaded_at": uploaded_at
        }

    except Exception as e:
        error_message = str(e)
        logger.error(f"Erreur upload: {error_message}")

        try:
            supabase.table('media_uploads').insert({
                "id": str(uuid.uuid4()),
                "created_at": datetime.utcnow().isoformat() + 'Z',
                "original_filename": file.filename if file else "unknown",
                "status": "error",
                "error_message": error_message
            }).execute()
        except:
            pass

        return {
            "success": False,
            "error": error_message
        }


@upload_bp.route('/upload-file', methods=['POST'])
def upload_file():
    """
    Upload d'un fichier unique
    """
    if not supabase:
        return jsonify({"success": False, "error": "Service Supabase non disponible"}), 503

    if 'file' not in request.files:
        return jsonify({"success": False, "error": "Aucun fichier fourni"}), 400

    file = request.files['file']
    category = request.form.get('category')

    result = upload_to_supabase(file, category)

    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code


@upload_bp.route('/upload-multiple', methods=['POST'])
def upload_multiple():
    """
    Upload de plusieurs fichiers
    """
    if not supabase:
        return jsonify({"success": False, "error": "Service Supabase non disponible"}), 503

    if 'files' not in request.files:
        return jsonify({"success": False, "error": "Aucun fichier fourni"}), 400

    files = request.files.getlist('files')
    category = request.form.get('category')

    results = []
    success_count = 0
    error_count = 0

    for file in files:
        result = upload_to_supabase(file, category)
        results.append(result)

        if result.get('success'):
            success_count += 1
        else:
            error_count += 1

    return jsonify({
        "success": error_count == 0,
        "message": f"{success_count} fichier(s) uploadé(s), {error_count} erreur(s)",
        "total": len(files),
        "success_count": success_count,
        "error_count": error_count,
        "results": results
    }), 200


@upload_bp.route('/list-files', methods=['GET'])
def list_files():
    """
    Liste les fichiers d'un dossier spécifique
    """
    if not supabase:
        return jsonify({"success": False, "error": "Service Supabase non disponible"}), 503

    folder = request.args.get('folder', '')

    try:
        files = supabase.storage.from_(BUCKET_NAME).list(folder)

        file_list = []
        for file in files:
            if file.get('name'):
                storage_path = f"{folder}/{file['name']}" if folder else file['name']
                public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(storage_path)

                file_list.append({
                    "name": file['name'],
                    "storage_path": storage_path,
                    "public_url": public_url,
                    "size": file.get('metadata', {}).get('size'),
                    "created_at": file.get('created_at'),
                    "updated_at": file.get('updated_at')
                })

        return jsonify({
            "success": True,
            "folder": folder,
            "count": len(file_list),
            "files": file_list
        }), 200

    except Exception as e:
        logger.error(f"Erreur listage fichiers: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@upload_bp.route('/delete-file', methods=['DELETE'])
def delete_file():
    """
    Supprime un fichier via son storage_path
    """
    if not supabase:
        return jsonify({"success": False, "error": "Service Supabase non disponible"}), 503

    data = request.get_json()

    if not data or 'storage_path' not in data:
        return jsonify({"success": False, "error": "storage_path requis"}), 400

    storage_path = data['storage_path']

    try:
        supabase.storage.from_(BUCKET_NAME).remove([storage_path])

        logger.info(f"Fichier supprimé: {storage_path}")

        return jsonify({
            "success": True,
            "message": "deleted",
            "storage_path": storage_path
        }), 200

    except Exception as e:
        logger.error(f"Erreur suppression: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@upload_bp.route('/upload-stats', methods=['GET'])
def upload_stats():
    """
    Retourne des statistiques sur les uploads
    """
    if not supabase:
        return jsonify({"success": False, "error": "Service Supabase non disponible"}), 503

    try:
        response = supabase.table('media_uploads').select('*').execute()

        total_uploads = len(response.data)
        success_uploads = len([r for r in response.data if r.get('status') == 'success'])
        error_uploads = total_uploads - success_uploads

        total_size = sum([r.get('size', 0) for r in response.data if r.get('size')])

        types_count = {}
        for record in response.data:
            file_type = record.get('file_type', 'unknown')
            types_count[file_type] = types_count.get(file_type, 0) + 1

        categories_count = {}
        for record in response.data:
            category = record.get('category', 'unknown')
            categories_count[category] = categories_count.get(category, 0) + 1

        return jsonify({
            "success": True,
            "stats": {
                "total_uploads": total_uploads,
                "success_uploads": success_uploads,
                "error_uploads": error_uploads,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_types": types_count,
                "categories": categories_count
            }
        }), 200

    except Exception as e:
        logger.error(f"Erreur stats: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@upload_bp.route('/upload-health', methods=['GET'])
def upload_health():
    """
    Vérifie la santé du service
    """
    supabase_connected = False
    bucket_exists = False
    table_exists = False

    try:
        if supabase:
            buckets = supabase.storage.list_buckets()
            supabase_connected = True
            bucket_exists = any(b.name == BUCKET_NAME for b in buckets)

            try:
                supabase.table('media_uploads').select('id').limit(1).execute()
                table_exists = True
            except:
                table_exists = False
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")

    status = "ok" if (supabase_connected and bucket_exists) else "degraded"

    return jsonify({
        "status": status,
        "supabase_connected": supabase_connected,
        "bucket_exists": bucket_exists,
        "table_exists": table_exists,
        "bucket_name": BUCKET_NAME,
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }), 200 if status == "ok" else 503
