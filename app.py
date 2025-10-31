import os
import json
import hashlib
import secrets
import logging
from io import BytesIO
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from supabase import create_client, Client
import requests
from werkzeug.utils import secure_filename
from pathlib import Path

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]}})

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('VITE_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY') or os.getenv('VITE_SUPABASE_ANON_KEY')

supabase: Client = None

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("[ERROR] SUPABASE_URL and SUPABASE_KEY must be set in environment variables")
else:
    try:
        from supabase import create_client, Client, ClientOptions

options = ClientOptions()  # Crée un objet d’options vide compatible
supabase = create_client(SUPABASE_URL, SUPABASE_KEY, options)
        logger.info("[INFO] Supabase connection established successfully")
    except Exception as e:
        logger.error(f"[ERROR] Supabase initialization failed: {e}")

UPLOAD_FOLDER = Path('uploads')
UPLOAD_FOLDER.mkdir(exist_ok=True)

LINKEDIN_CLIENT_ID = os.getenv('LINKEDIN_CLIENT_ID', '')
LINKEDIN_CLIENT_SECRET = os.getenv('LINKEDIN_CLIENT_SECRET', '')
LINKEDIN_REDIRECT_URI = os.getenv('LINKEDIN_REDIRECT_URI', 'http://localhost:5000/api/linkedin_callback')

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}
MAX_FILE_SIZE = 50 * 1024 * 1024


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def generate_session_token():
    return secrets.token_urlsafe(32)


def authenticate_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if supabase is None:
            return jsonify({'error': 'Service temporarily unavailable'}), 503

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401

        token = auth_header.split(' ')[1]

        try:
            response = supabase.table('users').select('*').eq('id', token).maybeSingle().execute()
            if not response.data:
                return jsonify({'error': 'Invalid token'}), 401

            request.current_user = response.data
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return jsonify({'error': 'Authentication failed'}), 401

    return decorated_function


def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'current_user'):
                return jsonify({'error': 'Authentication required'}), 401

            if request.current_user.get('role') not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'status': 'API AE2I Backend Operational',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat()
    }), 200


@app.route('/api/health', methods=['GET'])
def health_check():
    supabase_status = 'connected' if supabase is not None else 'disconnected'
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'supabase': supabase_status
    }), 200


@app.route('/api/auth/register', methods=['POST'])
def register():
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        data = request.json
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        full_name = data.get('full_name', '').strip()
        role = data.get('role', 'Lecteur')

        if not email or not password or not full_name:
            return jsonify({'error': 'Missing required fields: email, password, full_name'}), 400

        if role not in ['Admin', 'Recruteur', 'Lecteur']:
            return jsonify({'error': 'Invalid role'}), 400

        password_hash = hash_password(password)

        result = supabase.table('users').insert({
            'email': email,
            'password_hash': password_hash,
            'full_name': full_name,
            'role': role,
            'created_at': datetime.now().isoformat()
        }).execute()

        if result.data:
            user = result.data[0]
            return jsonify({
                'success': True,
                'user': {
                    'id': user.get('id'),
                    'email': user.get('email'),
                    'full_name': user.get('full_name'),
                    'role': user.get('role')
                }
            }), 201
        else:
            return jsonify({'error': 'Registration failed'}), 500

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': f'Registration error: {str(e)}'}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        data = request.json
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()

        if not email or not password:
            return jsonify({'error': 'Missing credentials'}), 400

        password_hash = hash_password(password)

        response = supabase.table('users').select('*').eq('email', email).eq('password_hash', password_hash).maybeSingle().execute()

        if not response.data:
            return jsonify({'error': 'Invalid credentials'}), 401

        user = response.data

        try:
            supabase.table('users').update({'last_login': datetime.now().isoformat()}).eq('id', user['id']).execute()
        except Exception as e:
            logger.warning(f"Could not update last_login: {e}")

        return jsonify({
            'success': True,
            'token': user['id'],
            'user': {
                'id': user['id'],
                'email': user['email'],
                'full_name': user['full_name'],
                'role': user['role']
            }
        }), 200

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': f'Login error: {str(e)}'}), 500


@app.route('/api/candidates', methods=['GET'])
@authenticate_request
def get_candidates():
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        response = supabase.table('candidates').select('*').order('created_at', desc=True).execute()
        return jsonify({'success': True, 'candidates': response.data}), 200
    except Exception as e:
        logger.error(f"Get candidates error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/candidates', methods=['POST'])
@authenticate_request
@require_role('Admin', 'Recruteur')
def create_candidate():
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        data = request.json

        candidate_data = {
            'full_name': data.get('full_name'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'position': data.get('position'),
            'linkedin_url': data.get('linkedin_url'),
            'linkedin_data': data.get('linkedin_data'),
            'cv_url': data.get('cv_url'),
            'pdf_summary_url': data.get('pdf_summary_url'),
            'skills': data.get('skills', []),
            'status': data.get('status', 'nouveau'),
            'created_by': request.current_user['id'],
            'created_at': datetime.now().isoformat()
        }

        result = supabase.table('candidates').insert(candidate_data).execute()

        if result.data:
            return jsonify({'success': True, 'candidate': result.data[0]}), 201
        else:
            return jsonify({'error': 'Failed to create candidate'}), 500

    except Exception as e:
        logger.error(f"Create candidate error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/candidates/<candidate_id>', methods=['PUT'])
@authenticate_request
@require_role('Admin', 'Recruteur')
def update_candidate(candidate_id):
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        data = request.json
        data['updated_at'] = datetime.now().isoformat()

        result = supabase.table('candidates').update(data).eq('id', candidate_id).execute()

        if result.data:
            return jsonify({'success': True, 'candidate': result.data[0]}), 200
        else:
            return jsonify({'error': 'Candidate not found'}), 404

    except Exception as e:
        logger.error(f"Update candidate error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/candidates/<candidate_id>', methods=['DELETE'])
@authenticate_request
@require_role('Admin')
def delete_candidate(candidate_id):
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        result = supabase.table('candidates').delete().eq('id', candidate_id).execute()

        if result.data or len(result.data) > 0:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Candidate not found'}), 404

    except Exception as e:
        logger.error(f"Delete candidate error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
@authenticate_request
@require_role('Admin', 'Recruteur')
def upload_file():
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        file_type = request.form.get('file_type', 'image')

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

        if file.content_length and file.content_length > MAX_FILE_SIZE:
            return jsonify({'error': 'File size exceeds limit (50MB)'}), 400

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        unique_filename = f"{timestamp}_{filename}"

        file_path = UPLOAD_FOLDER / unique_filename
        file.save(str(file_path))

        file_size = os.path.getsize(file_path)
        file_url = f"/api/download/{unique_filename}"

        result = supabase.table('media_files').insert({
            'file_name': unique_filename,
            'file_type': file_type,
            'file_url': file_url,
            'file_size': file_size,
            'uploaded_by': request.current_user['id'],
            'metadata': {'original_name': filename},
            'uploaded_at': datetime.now().isoformat()
        }).execute()

        if result.data:
            return jsonify({
                'success': True,
                'file': result.data[0]
            }), 201
        else:
            return jsonify({'error': 'Failed to save file metadata'}), 500

    except Exception as e:
        logger.error(f"Upload file error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        safe_filename = secure_filename(filename)
        file_path = UPLOAD_FOLDER / safe_filename

        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        return send_file(str(file_path), as_attachment=True, download_name=safe_filename)

    except Exception as e:
        logger.error(f"Download file error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/media', methods=['GET'])
@authenticate_request
def get_media_files():
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        file_type = request.args.get('type')

        query = supabase.table('media_files').select('*').order('uploaded_at', desc=True)

        if file_type:
            query = query.eq('file_type', file_type)

        response = query.execute()

        return jsonify({'success': True, 'files': response.data}), 200

    except Exception as e:
        logger.error(f"Get media files error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/linkedin_auth', methods=['GET'])
def linkedin_auth():
    try:
        if not LINKEDIN_CLIENT_ID or not LINKEDIN_CLIENT_SECRET:
            return jsonify({'error': 'LinkedIn credentials not configured'}), 400

        state = secrets.token_urlsafe(16)

        auth_url = (
            f"https://www.linkedin.com/oauth/v2/authorization"
            f"?response_type=code"
            f"&client_id={LINKEDIN_CLIENT_ID}"
            f"&redirect_uri={LINKEDIN_REDIRECT_URI}"
            f"&state={state}"
            f"&scope=openid%20profile%20email"
        )

        return jsonify({'success': True, 'auth_url': auth_url, 'state': state}), 200

    except Exception as e:
        logger.error(f"LinkedIn auth error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/linkedin_callback', methods=['GET'])
def linkedin_callback():
    try:
        code = request.args.get('code')
        state = request.args.get('state')

        if not code:
            return jsonify({'error': 'Authorization code not provided'}), 400

        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': LINKEDIN_REDIRECT_URI,
            'client_id': LINKEDIN_CLIENT_ID,
            'client_secret': LINKEDIN_CLIENT_SECRET
        }

        token_response = requests.post(token_url, data=token_data, timeout=10)
        token_json = token_response.json()

        if 'access_token' not in token_json:
            return jsonify({'error': 'Failed to obtain access token'}), 400

        access_token = token_json['access_token']

        profile_url = "https://api.linkedin.com/v2/userinfo"
        headers = {'Authorization': f'Bearer {access_token}'}
        profile_response = requests.get(profile_url, headers=headers, timeout=10)
        profile_data = profile_response.json()

        return jsonify({
            'success': True,
            'access_token': access_token,
            'profile': profile_data
        }), 200

    except requests.exceptions.Timeout:
        logger.error("LinkedIn callback timeout")
        return jsonify({'error': 'LinkedIn service timeout'}), 503
    except Exception as e:
        logger.error(f"LinkedIn callback error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/linkedin_profile', methods=['POST'])
@authenticate_request
def save_linkedin_profile():
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        data = request.json
        access_token = data.get('access_token')

        if not access_token:
            return jsonify({'error': 'Access token required'}), 400

        expires_at = datetime.now() + timedelta(days=60)

        result = supabase.table('linkedin_tokens').upsert({
            'user_id': request.current_user['id'],
            'access_token': access_token,
            'refresh_token': data.get('refresh_token'),
            'expires_at': expires_at.isoformat(),
            'created_at': datetime.now().isoformat()
        }).execute()

        if result.data:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Failed to save token'}), 500

    except Exception as e:
        logger.error(f"Save LinkedIn profile error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings', methods=['GET'])
@authenticate_request
def get_settings():
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        response = supabase.table('site_settings').select('*').execute()

        settings = {}
        for setting in response.data:
            settings[setting['setting_key']] = setting['setting_value']

        return jsonify({'success': True, 'settings': settings}), 200

    except Exception as e:
        logger.error(f"Get settings error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings', methods=['POST'])
@authenticate_request
@require_role('Admin')
def update_settings():
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        data = request.json

        for key, value in data.items():
            supabase.table('site_settings').upsert({
                'setting_key': key,
                'setting_value': value,
                'updated_by': request.current_user['id'],
                'updated_at': datetime.now().isoformat()
            }).execute()

        return jsonify({'success': True}), 200

    except Exception as e:
        logger.error(f"Update settings error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/cv/<candidate_id>', methods=['GET'])
@authenticate_request
def get_candidate_cv(candidate_id):
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        response = supabase.table('candidates').select('cv_url').eq('id', candidate_id).maybeSingle().execute()

        if not response.data or not response.data.get('cv_url'):
            return jsonify({'error': 'CV not found'}), 404

        cv_url = response.data['cv_url']
        filename = cv_url.split('/')[-1]

        file_path = UPLOAD_FOLDER / secure_filename(filename)

        if not file_path.exists():
            return jsonify({'error': 'File not found on server'}), 404

        return send_file(str(file_path), as_attachment=True, download_name=f"CV_{candidate_id}.pdf")

    except Exception as e:
        logger.error(f"Get candidate CV error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/pdf_summary/<candidate_id>', methods=['GET'])
@authenticate_request
def get_candidate_pdf_summary(candidate_id):
    if supabase is None:
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        response = supabase.table('candidates').select('pdf_summary_url').eq('id', candidate_id).maybeSingle().execute()

        if not response.data or not response.data.get('pdf_summary_url'):
            return jsonify({'error': 'PDF summary not found'}), 404

        pdf_url = response.data['pdf_summary_url']
        filename = pdf_url.split('/')[-1]

        file_path = UPLOAD_FOLDER / secure_filename(filename)

        if not file_path.exists():
            return jsonify({'error': 'File not found on server'}), 404

        return send_file(str(file_path), as_attachment=True, download_name=f"Summary_{candidate_id}.pdf")

    except Exception as e:
        logger.error(f"Get PDF summary error: {e}")
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(403)
def forbidden(error):
    return jsonify({'error': 'Forbidden'}), 403


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"[INFO] Flask app starting on port {port}")
    if supabase is None:
        logger.warning("[WARNING] Starting without Supabase connection")
    app.run(host='0.0.0.0', port=port, debug=False)
