from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client
import os
from datetime import datetime
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configuration Supabase
SUPABASE_URL = "https://uisxrkzkqtbapnxnyuod.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVpc3hya3prcXRiYXBueG55dW9kIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjE5MDA0MTksImV4cCI6MjA3NzQ3NjQxOX0.lySWXQnIUDdCtrYVTrgoBMCIKWsKuqN8b-ipl3qSDwg"

# Initialisation du client Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def index():
    """Route principale - Affiche index.html"""
    return send_from_directory('public', 'index.html')

@app.route('/health')
def health():
    """Endpoint de santé pour vérifier que l'API fonctionne"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'supabase_connected': True
    })

# ========== GESTION DES CANDIDATURES ==========

@app.route('/api/candidatures', methods=['POST'])
def create_candidature():
    """Créer une nouvelle candidature"""
    try:
        data = request.json
        logger.info(f"Nouvelle candidature reçue: {data.get('email')}")

        # Insertion dans Supabase
        result = supabase.table('candidatures').insert({
            'nom': data.get('nom'),
            'prenom': data.get('prenom'),
            'email': data.get('email'),
            'telephone': data.get('telephone'),
            'poste_souhaite': data.get('poste_souhaite'),
            'poste_actuel': data.get('poste_actuel'),
            'annees_experience': data.get('annees_experience'),
            'en_poste': data.get('en_poste'),
            'dernier_poste_date': data.get('dernier_poste_date'),
            'cv_url': data.get('cv_url'),
            'lettre_motivation': data.get('lettre_motivation'),
            'date_candidature': datetime.now().isoformat(),
            'statut': 'En attente'
        }).execute()

        return jsonify({
            'success': True,
            'message': 'Candidature soumise avec succès',
            'data': result.data
        }), 201

    except Exception as e:
        logger.error(f"Erreur lors de la création de candidature: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/candidatures', methods=['GET'])
def get_candidatures():
    """Récupérer toutes les candidatures"""
    try:
        result = supabase.table('candidatures').select('*').order('date_candidature', desc=True).execute()
        return jsonify({
            'success': True,
            'data': result.data
        })
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des candidatures: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/candidatures/<int:id>', methods=['GET'])
def get_candidature(id):
    """Récupérer une candidature spécifique"""
    try:
        result = supabase.table('candidatures').select('*').eq('id', id).execute()
        if result.data:
            return jsonify({
                'success': True,
                'data': result.data[0]
            })
        return jsonify({
            'success': False,
            'error': 'Candidature non trouvée'
        }), 404
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la candidature: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/candidatures/<int:id>', methods=['PUT'])
def update_candidature(id):
    """Mettre à jour une candidature"""
    try:
        data = request.json
        result = supabase.table('candidatures').update(data).eq('id', id).execute()
        return jsonify({
            'success': True,
            'message': 'Candidature mise à jour',
            'data': result.data
        })
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/candidatures/<int:id>', methods=['DELETE'])
def delete_candidature(id):
    """Supprimer une candidature"""
    try:
        supabase.table('candidatures').delete().eq('id', id).execute()
        return jsonify({
            'success': True,
            'message': 'Candidature supprimée'
        })
    except Exception as e:
        logger.error(f"Erreur lors de la suppression: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== GESTION DES OFFRES D'EMPLOI ==========

@app.route('/api/jobs', methods=['POST'])
def create_job():
    """Créer une nouvelle offre d'emploi"""
    try:
        data = request.json
        result = supabase.table('jobs').insert({
            'titre_fr': data.get('titre_fr'),
            'titre_en': data.get('titre_en'),
            'description_fr': data.get('description_fr'),
            'description_en': data.get('description_en'),
            'type_contrat': data.get('type_contrat'),
            'localisation': data.get('localisation'),
            'salaire': data.get('salaire'),
            'competences': data.get('competences'),
            'date_publication': datetime.now().isoformat(),
            'statut': 'active'
        }).execute()

        return jsonify({
            'success': True,
            'message': 'Offre créée avec succès',
            'data': result.data
        }), 201
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'offre: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    """Récupérer toutes les offres d'emploi actives"""
    try:
        result = supabase.table('jobs').select('*').eq('statut', 'active').order('date_publication', desc=True).execute()
        return jsonify({
            'success': True,
            'data': result.data
        })
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des offres: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/jobs/<int:id>', methods=['GET'])
def get_job(id):
    """Récupérer une offre spécifique"""
    try:
        result = supabase.table('jobs').select('*').eq('id', id).execute()
        if result.data:
            return jsonify({
                'success': True,
                'data': result.data[0]
            })
        return jsonify({
            'success': False,
            'error': 'Offre non trouvée'
        }), 404
    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/jobs/<int:id>', methods=['PUT'])
def update_job(id):
    """Mettre à jour une offre d'emploi"""
    try:
        data = request.json
        result = supabase.table('jobs').update(data).eq('id', id).execute()
        return jsonify({
            'success': True,
            'message': 'Offre mise à jour',
            'data': result.data
        })
    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/jobs/<int:id>', methods=['DELETE'])
def delete_job(id):
    """Supprimer une offre d'emploi"""
    try:
        supabase.table('jobs').delete().eq('id', id).execute()
        return jsonify({
            'success': True,
            'message': 'Offre supprimée'
        })
    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== GESTION DES CONTACTS ==========

@app.route('/api/contacts', methods=['POST'])
def create_contact():
    """Enregistrer un message de contact"""
    try:
        data = request.json
        result = supabase.table('contacts').insert({
            'nom': data.get('nom'),
            'email': data.get('email'),
            'telephone': data.get('telephone'),
            'sujet': data.get('sujet'),
            'message': data.get('message'),
            'date_contact': datetime.now().isoformat(),
            'traite': False
        }).execute()

        return jsonify({
            'success': True,
            'message': 'Message envoyé avec succès',
            'data': result.data
        }), 201
    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    """Récupérer tous les messages de contact"""
    try:
        result = supabase.table('contacts').select('*').order('date_contact', desc=True).execute()
        return jsonify({
            'success': True,
            'data': result.data
        })
    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== GESTION DES UTILISATEURS / ADMINS ==========

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Authentification admin"""
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        # Vérifier dans Supabase
        result = supabase.table('admins').select('*').eq('email', email).execute()

        if result.data and len(result.data) > 0:
            admin = result.data[0]
            # Vérifier le mot de passe (vous devriez utiliser du hashing en production)
            if admin.get('password') == password:
                return jsonify({
                    'success': True,
                    'message': 'Connexion réussie',
                    'user': {
                        'id': admin['id'],
                        'email': admin['email'],
                        'role': admin['role']
                    }
                })

        return jsonify({
            'success': False,
            'error': 'Email ou mot de passe incorrect'
        }), 401

    except Exception as e:
        logger.error(f"Erreur lors de la connexion: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== GESTION DES STATISTIQUES ==========

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Récupérer les statistiques du site"""
    try:
        candidatures_count = supabase.table('candidatures').select('id', count='exact').execute()
        jobs_count = supabase.table('jobs').select('id', count='exact').execute()
        contacts_count = supabase.table('contacts').select('id', count='exact').execute()

        return jsonify({
            'success': True,
            'data': {
                'total_candidatures': len(candidatures_count.data) if candidatures_count.data else 0,
                'total_jobs': len(jobs_count.data) if jobs_count.data else 0,
                'total_contacts': len(contacts_count.data) if contacts_count.data else 0
            }
        })
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
