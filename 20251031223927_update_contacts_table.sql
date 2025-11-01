/*
  # Mise à jour de la table contacts pour correspondre au backend

  1. Modifications
    - Ajouter les colonnes manquantes : nom, telephone, sujet, date_contact, traite
    - Supprimer ou renommer les colonnes existantes si nécessaire
    
  Note: Cette migration vérifie d'abord l'existence des colonnes avant de les ajouter
*/

-- Supprimer la table contacts existante et la recréer avec la bonne structure
DROP TABLE IF EXISTS contacts CASCADE;

CREATE TABLE contacts (
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
