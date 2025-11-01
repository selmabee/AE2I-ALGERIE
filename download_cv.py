"""
Netlify Function: Download CV
FIX: pdf-download
ADD: secure-cv-access

Permet le téléchargement sécurisé des CV PDF (originaux et résumés générés)
avec vérification de l'existence et protection contre les path traversal.
"""

import json
import os
import base64
from pathlib import Path
from urllib.parse import parse_qs, unquote

# Configuration
UPLOADS_DIR = '/tmp/uploads'
ALLOWED_EXTENSIONS = ['.pdf']


def handler(event, context):
    """
    Handler principal pour le téléchargement de fichiers PDF
    """

    # Vérifier la méthode HTTP
    if event['httpMethod'] not in ['GET', 'OPTIONS']:
        return error_response(405, 'Method not allowed. Use GET.')

    # Gérer les requêtes OPTIONS (CORS preflight)
    if event['httpMethod'] == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': ''
        }

    try:
        # Extraire le paramètre filename de la query string
        query_params = event.get('queryStringParameters', {})

        if not query_params or 'filename' not in query_params:
            return error_response(400, 'Missing filename parameter.')

        filename = unquote(query_params['filename'])

        # Valider le filename (pas de path traversal)
        if '..' in filename or '/' in filename or '\\' in filename:
            return error_response(
                400,
                'Invalid filename. Path traversal attempts are not allowed.'
            )

        # Valider l'extension
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return error_response(
                400,
                f'Invalid file type. Only PDF files are allowed.'
            )

        # Construire le chemin complet
        file_path = os.path.join(UPLOADS_DIR, filename)

        # Vérifier que le fichier existe
        if not os.path.exists(file_path):
            return error_response(404, f'File not found: {filename}')

        # Vérifier que c'est bien dans le dossier uploads (double sécurité)
        real_path = os.path.realpath(file_path)
        real_uploads = os.path.realpath(UPLOADS_DIR)

        if not real_path.startswith(real_uploads):
            return error_response(
                403,
                'Access denied. File must be in uploads directory.'
            )

        # Lire le fichier
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Encoder en base64 pour la transmission
        file_base64 = base64.b64encode(file_content).decode('utf-8')

        # Log de succès
        print(f"[SUCCESS] File downloaded: {filename} ({len(file_content)} bytes)")

        # Retourner le fichier
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/pdf',
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Expose-Headers': 'Content-Disposition'
            },
            'body': file_base64,
            'isBase64Encoded': True
        }

    except FileNotFoundError:
        return error_response(404, 'File not found.')

    except PermissionError:
        return error_response(403, 'Permission denied.')

    except Exception as e:
        # Log de l'erreur
        print(f"[ERROR] Download failed: {str(e)}")
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
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        },
        'body': json.dumps({
            'status': 'error',
            'message': message
        })
    }
