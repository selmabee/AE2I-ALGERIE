"""
Netlify Function: Upload Media
FIX: secure-file-upload
ADD: upload-media-endpoint
ADD: file-validation-security

Permet le téléversement sécurisé de fichiers (images, vidéos, documents, CV)
avec validation stricte du type MIME et de la taille.
"""

import json
import os
import base64
import mimetypes
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs

# Configuration
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_MIME_TYPES = [
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/webp',
    'video/mp4',
    'video/quicktime',
    'application/pdf'
]
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov', '.pdf']
FORBIDDEN_EXTENSIONS = ['.exe', '.bat', '.sh', '.cmd', '.com', '.scr', '.js', '.jar']
UPLOADS_DIR = '/tmp/uploads'


def handler(event, context):
    """
    Handler principal pour le téléversement de fichiers
    """

    # Vérifier la méthode HTTP
    if event['httpMethod'] != 'POST':
        return {
            'statusCode': 405,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({
                'status': 'error',
                'message': 'Method not allowed. Use POST.'
            })
        }

    # Gérer les requêtes OPTIONS (CORS preflight)
    if event['httpMethod'] == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': ''
        }

    try:
        # Créer le dossier uploads s'il n'existe pas
        os.makedirs(UPLOADS_DIR, exist_ok=True)

        # Parser le body (multipart/form-data)
        content_type = event.get('headers', {}).get('content-type', '')

        if 'multipart/form-data' not in content_type:
            return error_response(
                400,
                'Invalid content type. Use multipart/form-data.'
            )

        # Extraire le boundary
        boundary = None
        for part in content_type.split(';'):
            if 'boundary=' in part:
                boundary = part.split('boundary=')[1].strip()
                break

        if not boundary:
            return error_response(400, 'No boundary found in content-type.')

        # Décoder le body (base64 si isBase64Encoded=True)
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body).decode('latin-1')

        # Parser les parties du multipart
        parts = body.split('--' + boundary)

        file_data = None
        filename = None
        content_type_file = None

        for part in parts:
            if 'Content-Disposition' in part and 'filename=' in part:
                # Extraire les headers et le contenu
                headers_end = part.find('\r\n\r\n')
                if headers_end == -1:
                    headers_end = part.find('\n\n')

                if headers_end == -1:
                    continue

                headers_section = part[:headers_end]
                file_content = part[headers_end + 4:]  # +4 pour sauter \r\n\r\n

                # Extraire le filename
                for line in headers_section.split('\n'):
                    if 'filename=' in line:
                        filename_part = line.split('filename=')[1]
                        filename = filename_part.strip().strip('"').strip("'")
                        filename = filename.split('\r')[0].split('\n')[0]

                    if 'Content-Type:' in line:
                        content_type_file = line.split('Content-Type:')[1].strip()

                # Nettoyer le contenu (enlever les \r\n finaux)
                if file_content.endswith('\r\n'):
                    file_content = file_content[:-2]
                elif file_content.endswith('\n'):
                    file_content = file_content[:-1]

                file_data = file_content.encode('latin-1')
                break

        # Valider que le fichier a été trouvé
        if not file_data or not filename:
            return error_response(400, 'No file found in request.')

        # Valider l'extension
        file_ext = os.path.splitext(filename)[1].lower()

        if file_ext in FORBIDDEN_EXTENSIONS:
            return error_response(
                400,
                f'Forbidden file type: {file_ext}. Executable files are not allowed.'
            )

        if file_ext not in ALLOWED_EXTENSIONS:
            return error_response(
                400,
                f'Invalid file extension: {file_ext}. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'
            )

        # Valider le MIME type
        if content_type_file and content_type_file not in ALLOWED_MIME_TYPES:
            return error_response(
                400,
                f'Invalid MIME type: {content_type_file}. Allowed: {", ".join(ALLOWED_MIME_TYPES)}'
            )

        # Valider la taille
        file_size = len(file_data)
        if file_size > MAX_FILE_SIZE:
            return error_response(
                400,
                f'File too large: {file_size} bytes. Max: {MAX_FILE_SIZE} bytes (20 MB).'
            )

        if file_size == 0:
            return error_response(400, 'Empty file.')

        # Générer un nom unique
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        safe_filename = ''.join(c for c in filename if c.isalnum() or c in '._- ')
        unique_filename = f"{timestamp}_{safe_filename}"

        # Sauvegarder le fichier
        file_path = os.path.join(UPLOADS_DIR, unique_filename)

        with open(file_path, 'wb') as f:
            f.write(file_data)

        # Construire l'URL du fichier
        base_url = event.get('headers', {}).get('host', '')
        protocol = 'https://' if 'netlify.app' in base_url or 'ae2i' in base_url else 'http://'
        file_url = f"{protocol}{base_url}/uploads/{unique_filename}"

        # Log de succès
        print(f"[SUCCESS] File uploaded: {unique_filename} ({file_size} bytes)")

        # Retourner le succès
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({
                'status': 'success',
                'file_url': file_url,
                'filename': unique_filename,
                'size': file_size,
                'message': 'File uploaded successfully'
            })
        }

    except Exception as e:
        # Log de l'erreur
        print(f"[ERROR] Upload failed: {str(e)}")
        import traceback
        traceback.print_exc()

        return error_response(500, f'Internal server error: {str(e)}')


def error_response(status_code, message):
    """
    Génère une réponse d'erreur standardisée
    """
    print(f"[ERROR {status_code}] {message}")

    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        },
        'body': json.dumps({
            'status': 'error',
            'message': message
        })
    }
