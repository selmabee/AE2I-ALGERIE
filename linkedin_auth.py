"""
Netlify Function: LinkedIn OAuth Authentication
FIX: linkedin-token-exchange
ADD: linkedin-user-profile-fetch

Échange le code OAuth contre un token et récupère les données du profil utilisateur
"""

import json
import os
import urllib.request
import urllib.parse
import urllib.error


def handler(event, context):
    """
    Handler pour l'authentification LinkedIn OAuth
    """

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

    # Vérifier la méthode HTTP
    if event['httpMethod'] != 'POST':
        return error_response(405, 'Method not allowed. Use POST.')

    try:
        # Parser le body
        body = json.loads(event.get('body', '{}'))
        code = body.get('code')

        if not code:
            return error_response(400, 'Missing authorization code')

        # Récupérer les variables d'environnement
        client_id = os.environ.get('LINKEDIN_CLIENT_ID', '')
        client_secret = os.environ.get('LINKEDIN_CLIENT_SECRET', '')

        if not client_id or not client_secret:
            print('[ERROR] LinkedIn credentials not configured')
            return error_response(500, 'LinkedIn not configured. Please contact administrator.')

        # Construire le redirect_uri
        host = event.get('headers', {}).get('host', '')
        protocol = 'https://' if 'netlify.app' in host or 'ae2i' in host else 'http://'
        redirect_uri = f"{protocol}{host}"

        # Échanger le code contre un access token
        token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri
        }

        token_data_encoded = urllib.parse.urlencode(token_data).encode('utf-8')
        token_request = urllib.request.Request(
            token_url,
            data=token_data_encoded,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        try:
            with urllib.request.urlopen(token_request) as response:
                token_response = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f'[ERROR] LinkedIn token exchange failed: {error_body}')
            return error_response(401, 'Failed to authenticate with LinkedIn')

        access_token = token_response.get('access_token')
        if not access_token:
            return error_response(401, 'No access token received')

        # Récupérer les informations du profil utilisateur
        profile_url = 'https://api.linkedin.com/v2/userinfo'
        profile_request = urllib.request.Request(
            profile_url,
            headers={'Authorization': f'Bearer {access_token}'}
        )

        try:
            with urllib.request.urlopen(profile_request) as response:
                profile_data = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f'[ERROR] LinkedIn profile fetch failed: {error_body}')
            return error_response(401, 'Failed to fetch LinkedIn profile')

        # Extraire les données pertinentes
        user_data = {
            'access_token': access_token,
            'sub': profile_data.get('sub', ''),
            'firstName': profile_data.get('given_name', ''),
            'lastName': profile_data.get('family_name', ''),
            'email': profile_data.get('email', ''),
            'profilePicture': profile_data.get('picture', ''),
            'headline': profile_data.get('headline', ''),
            'publicProfileUrl': f"https://www.linkedin.com/in/{profile_data.get('sub', '')}"
        }

        print(f"[SUCCESS] LinkedIn authentication successful for {user_data['firstName']} {user_data['lastName']}")

        # Retourner les données du profil
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps(user_data)
        }

    except json.JSONDecodeError:
        return error_response(400, 'Invalid JSON in request body')

    except Exception as e:
        print(f"[ERROR] LinkedIn authentication failed: {str(e)}")
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
            'error': message
        })
    }
