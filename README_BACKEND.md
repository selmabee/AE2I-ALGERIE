# AE2I Backend - Guide de Déploiement Render.com

## Architecture

Ce backend Flask fournit une API REST complète pour le site AE2I Algérie avec :

- **Authentification** : Système de rôles (Admin, Recruteur, Lecteur)
- **Gestion des candidatures** : CRUD complet avec statuts
- **Upload/Download** : Gestion sécurisée des médias (CV, images, vidéos, PDF)
- **LinkedIn OAuth2** : Connexion et récupération des profils
- **Base de données Supabase** : Persistance complète avec RLS

## Endpoints API

### Authentification

#### POST `/api/auth/register`
Inscription d'un nouvel utilisateur
```json
{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "Nom Complet",
  "role": "Lecteur"
}
```

#### POST `/api/auth/login`
Connexion utilisateur
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

Retourne un token à utiliser dans l'en-tête `Authorization: Bearer <token>`

### Candidatures

#### GET `/api/candidates`
Liste toutes les candidatures (authentification requise)

#### POST `/api/candidates`
Crée une nouvelle candidature (Admin/Recruteur uniquement)
```json
{
  "full_name": "Jean Dupont",
  "email": "jean@example.com",
  "phone": "+213 555 123 456",
  "position": "Ingénieur",
  "linkedin_url": "https://linkedin.com/in/jean",
  "skills": ["Python", "React", "Docker"],
  "cv_url": "/api/download/cv_123.pdf"
}
```

#### PUT `/api/candidates/<id>`
Met à jour une candidature (Admin/Recruteur uniquement)

#### DELETE `/api/candidates/<id>`
Supprime une candidature (Admin uniquement)

### Upload/Download

#### POST `/api/upload`
Upload un fichier (Admin/Recruteur uniquement)
- Form-data avec `file` et `file_type` (image|video|pdf|cv)
- Retourne l'URL de téléchargement

#### GET `/api/download/<filename>`
Télécharge un fichier (public)

#### GET `/api/cv/<candidate_id>`
Télécharge le CV d'un candidat (authentification requise)

#### GET `/api/pdf_summary/<candidate_id>`
Télécharge le PDF résumé d'un candidat (authentification requise)

#### GET `/api/media`
Liste tous les fichiers médias (authentification requise)
- Query param optionnel : `?type=image|video|pdf|cv`

### LinkedIn OAuth2

#### GET `/api/linkedin_auth`
Obtient l'URL d'autorisation LinkedIn
- Retourne `auth_url` à ouvrir dans un navigateur

#### GET `/api/linkedin_callback`
Callback LinkedIn après autorisation
- Récupère le code et échange contre un token
- Retourne le profil utilisateur

#### POST `/api/linkedin_profile`
Sauvegarde le token LinkedIn (authentification requise)
```json
{
  "access_token": "linkedin_access_token",
  "refresh_token": "optional_refresh_token"
}
```

### Paramètres du site

#### GET `/api/settings`
Récupère tous les paramètres (authentification requise)

#### POST `/api/settings`
Met à jour les paramètres (Admin uniquement)
```json
{
  "site_name": "AE2I Algérie",
  "maintenance_mode": false
}
```

## Configuration Render.com

### 1. Créer un nouveau Web Service

Sur Render.com :
1. Connectez votre dépôt GitHub
2. Sélectionnez "New +" → "Web Service"
3. Choisissez votre repository

### 2. Configuration

- **Name** : `ae2i-backend`
- **Environment** : `Python`
- **Build Command** : `pip install -r requirements.txt`
- **Start Command** : `gunicorn app:app`
- **Instance Type** : Starter (ou supérieur)

### 3. Variables d'environnement

Dans l'onglet "Environment", ajoutez :

```
VITE_SUPABASE_URL=https://votre-projet.supabase.co
VITE_SUPABASE_ANON_KEY=votre_cle_anon_supabase

LINKEDIN_CLIENT_ID=votre_client_id_linkedin
LINKEDIN_CLIENT_SECRET=votre_client_secret_linkedin
LINKEDIN_REDIRECT_URI=https://votre-app.onrender.com/api/linkedin_callback

PORT=5000
```

### 4. Disque persistant

Dans l'onglet "Disks", ajoutez :
- **Name** : `uploads`
- **Mount Path** : `/opt/render/project/src/uploads`
- **Size** : 5 GB (ajustez selon vos besoins)

### 5. Déployer

Cliquez sur "Create Web Service" - le déploiement démarre automatiquement.

## Configuration LinkedIn OAuth2

### 1. Créer une application LinkedIn

1. Allez sur [LinkedIn Developers](https://www.linkedin.com/developers/)
2. Créez une nouvelle application
3. Dans les paramètres OAuth 2.0 :
   - **Authorized redirect URLs** : `https://votre-app.onrender.com/api/linkedin_callback`
   - **Scopes** : `openid`, `profile`, `email`

### 2. Obtenir les credentials

- **Client ID** : Visible dans l'onglet "Auth"
- **Client Secret** : Généré dans l'onglet "Auth"

### 3. Configurer dans Render

Ajoutez les variables d'environnement sur Render avec vos credentials LinkedIn.

## Utilisation depuis le frontend

### Exemple : Login

```javascript
const response = await fetch('https://votre-app.onrender.com/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'user@example.com', password: 'pass123' })
});

const data = await response.json();
const token = data.token;
```

### Exemple : Upload fichier

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('file_type', 'cv');

const response = await fetch('https://votre-app.onrender.com/api/upload', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData
});

const data = await response.json();
const fileUrl = data.file.file_url;
```

### Exemple : LinkedIn Auth

```javascript
const authResponse = await fetch('https://votre-app.onrender.com/api/linkedin_auth');
const authData = await authResponse.json();

window.location.href = authData.auth_url;
```

## Sécurité

- Tous les endpoints sensibles nécessitent une authentification
- Les rôles sont strictement contrôlés (Admin, Recruteur, Lecteur)
- Les fichiers sont validés (type, taille)
- RLS activé sur toutes les tables Supabase
- Tokens LinkedIn stockés de manière sécurisée
- CORS configuré pour accepter les requêtes du frontend

## Limites

- Taille max fichier : 50 MB
- Extensions autorisées : pdf, png, jpg, jpeg, gif, mp4, mov, avi
- Stockage disque : 5 GB (configurable)

## Maintenance

### Logs

Consultez les logs dans le dashboard Render :
- Onglet "Logs" du service

### Redémarrage

En cas de problème, redémarrez le service :
- Bouton "Manual Deploy" → "Clear build cache & deploy"

### Base de données

Gérez la base via [Supabase Dashboard](https://app.supabase.com)
- Vérifiez les tables, RLS policies, et données

## Support

Pour toute question ou problème :
1. Vérifiez les logs Render
2. Vérifiez les variables d'environnement
3. Testez les endpoints avec Postman ou curl
4. Vérifiez la configuration Supabase (RLS, policies)
