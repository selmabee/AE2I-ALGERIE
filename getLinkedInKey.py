"""
Netlify Function: Get LinkedIn OAuth Configuration
FIX: linkedin-backend-auth
ADD: linkedin-config-endpoint

Retourne la configuration OAuth LinkedIn de manière sécurisée
"""

import json
import os


def handler(event, context):
    """
    Handler pour récupérer la configuration LinkedIn OAuth
    """

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

    # Vérifier la méthode HTTP
    if event['httpMethod'] != 'GET':
        return {
            'statusCode': 405,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Method not allowed. Use GET.'
            })
        }

    try:
        # Récupérer les variables d'environnement
        linkedin_client_id = os.environ.get('LINKEDIN_CLIENT_ID', '')

        # Utiliser l'URL du site comme redirect_uri
        host = event.get('headers', {}).get('host', '')
        protocol = 'https://' if 'netlify.app' in host or 'ae2i' in host else 'http://'
        redirect_uri = f"{protocol}{host}"

        # Validation
        if not linkedin_client_id:
            print('[WARNING] LINKEDIN_CLIENT_ID not configured')
            # En développement, utiliser une valeur de test
            linkedin_client_id = 'test_client_id'

        # Retourner la configuration
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            },
            'body': json.dumps({
                'client_id': linkedin_client_id,
                'redirect_uri': redirect_uri
            })
        }

    except Exception as e:
        print(f"[ERROR] Failed to get LinkedIn config: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }
