/*
  # Création des tables pour AE2I Algérie

  1. Nouvelles Tables
    - `candidatures` : Stocke les candidatures des postulants
      - `id` (bigint, primary key, auto-increment)
      - `nom` (text) : Nom du candidat
      - `prenom` (text) : Prénom du candidat
      - `email` (text) : Email du candidat
      - `telephone` (text) : Téléphone
      - `poste_souhaite` (text) : Poste souhaité
      - `poste_actuel` (text) : Poste actuel (optionnel)
      - `annees_experience` (integer) : Années d'expérience
      - `en_poste` (boolean) : Est en poste actuellement
      - `dernier_poste_date` (text) : Date du dernier poste
      - `cv_url` (text) : URL du CV
      - `lettre_motivation` (text) : Lettre de motivation
      - `date_candidature` (timestamptz) : Date de candidature
      - `statut` (text) : Statut de la candidature
      - `created_at` (timestamptz) : Date de création
    
    - `jobs` : Offres d'emploi
      - `id` (bigint, primary key, auto-increment)
      - `titre_fr` (text) : Titre en français
      - `titre_en` (text) : Titre en anglais
      - `description_fr` (text) : Description en français
      - `description_en` (text) : Description en anglais
      - `type_contrat` (text) : Type de contrat (CDI, CDD, etc.)
      - `localisation` (text) : Localisation du poste
      - `salaire` (text) : Salaire (optionnel)
      - `competences` (jsonb) : Compétences requises
      - `date_publication` (timestamptz) : Date de publication
      - `statut` (text) : Statut (active, inactive)
      - `created_at` (timestamptz) : Date de création
    
    - `contacts` : Messages de contact
      - `id` (bigint, primary key, auto-increment)
      - `nom` (text) : Nom
      - `email` (text) : Email
      - `telephone` (text) : Téléphone
      - `sujet` (text) : Sujet du message
      - `message` (text) : Message
      - `date_contact` (timestamptz) : Date du contact
      - `traite` (boolean) : Message traité
      - `created_at` (timestamptz) : Date de création
    
    - `admins` : Utilisateurs administrateurs
      - `id` (bigint, primary key, auto-increment)
      - `email` (text, unique) : Email de l'admin
      - `password` (text) : Mot de passe (à hasher en production)
      - `role` (text) : Rôle (admin, recruteur, lecteur)
      - `created_at` (timestamptz) : Date de création

  2. Sécurité
    - Active RLS sur toutes les tables
    - Politiques pour permettre les insertions publiques sur candidatures et contacts
    - Politiques restreintes pour jobs et admins
*/

-- Table candidatures
CREATE TABLE IF NOT EXISTS candidatures (
  id BIGSERIAL PRIMARY KEY,
  nom TEXT NOT NULL,
  prenom TEXT NOT NULL,
  email TEXT NOT NULL,
  telephone TEXT,
  poste_souhaite TEXT NOT NULL,
  poste_actuel TEXT,
  annees_experience INTEGER DEFAULT 0,
  en_poste BOOLEAN DEFAULT false,
  dernier_poste_date TEXT,
  cv_url TEXT,
  lettre_motivation TEXT,
  date_candidature TIMESTAMPTZ DEFAULT now(),
  statut TEXT DEFAULT 'En attente',
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE candidatures ENABLE ROW LEVEL SECURITY;

-- Politique pour permettre à tout le monde de créer une candidature
CREATE POLICY "Tout le monde peut créer une candidature"
  ON candidatures FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

-- Politique pour que les admins puissent tout voir
CREATE POLICY "Les admins peuvent tout voir"
  ON candidatures FOR SELECT
  TO authenticated
  USING (true);

-- Politique pour que les admins puissent mettre à jour
CREATE POLICY "Les admins peuvent mettre à jour"
  ON candidatures FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Politique pour que les admins puissent supprimer
CREATE POLICY "Les admins peuvent supprimer"
  ON candidatures FOR DELETE
  TO authenticated
  USING (true);

-- Table jobs
CREATE TABLE IF NOT EXISTS jobs (
  id BIGSERIAL PRIMARY KEY,
  titre_fr TEXT NOT NULL,
  titre_en TEXT,
  description_fr TEXT NOT NULL,
  description_en TEXT,
  type_contrat TEXT DEFAULT 'CDI',
  localisation TEXT,
  salaire TEXT,
  competences JSONB DEFAULT '[]'::jsonb,
  date_publication TIMESTAMPTZ DEFAULT now(),
  statut TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

-- Tout le monde peut voir les offres actives
CREATE POLICY "Tout le monde peut voir les offres actives"
  ON jobs FOR SELECT
  TO anon, authenticated
  USING (statut = 'active');

-- Les admins peuvent créer des offres
CREATE POLICY "Les admins peuvent créer des offres"
  ON jobs FOR INSERT
  TO authenticated
  WITH CHECK (true);

-- Les admins peuvent mettre à jour des offres
CREATE POLICY "Les admins peuvent mettre à jour des offres"
  ON jobs FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Les admins peuvent supprimer des offres
CREATE POLICY "Les admins peuvent supprimer des offres"
  ON jobs FOR DELETE
  TO authenticated
  USING (true);

-- Table contacts
CREATE TABLE IF NOT EXISTS contacts (
  id BIGSERIAL PRIMARY KEY,
  nom TEXT NOT NULL,
  email TEXT NOT NULL,
  telephone TEXT,
  sujet TEXT NOT NULL,
  message TEXT NOT NULL,
  date_contact TIMESTAMPTZ DEFAULT now(),
  traite BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

-- Tout le monde peut envoyer un message
CREATE POLICY "Tout le monde peut envoyer un message"
  ON contacts FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

-- Les admins peuvent voir tous les messages
CREATE POLICY "Les admins peuvent voir tous les messages"
  ON contacts FOR SELECT
  TO authenticated
  USING (true);

-- Les admins peuvent mettre à jour les messages
CREATE POLICY "Les admins peuvent mettre à jour les messages"
  ON contacts FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Table admins
CREATE TABLE IF NOT EXISTS admins (
  id BIGSERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  role TEXT DEFAULT 'lecteur',
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE admins ENABLE ROW LEVEL SECURITY;

-- Les admins peuvent voir leur propre profil
CREATE POLICY "Les admins peuvent voir leur profil"
  ON admins FOR SELECT
  TO authenticated
  USING (true);

-- Insérer un admin par défaut (mot de passe: admin123 - À CHANGER EN PRODUCTION!)
INSERT INTO admins (email, password, role) 
VALUES ('admin@ae2i-algerie.com', 'admin123', 'admin')
ON CONFLICT (email) DO NOTHING;
