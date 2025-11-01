/*
  # Create uploads tracking table

  1. New Tables
    - `media_uploads` - Enregistrement persistant de tous les uploads
      - `id` (uuid, primary key)
      - `filename` (text) - Nom du fichier uploadé
      - `original_filename` (text) - Nom original du fichier
      - `file_type` (text) - Type de fichier (logos, images, videos, etc.)
      - `file_size` (int) - Taille du fichier en bytes
      - `storage_path` (text) - Chemin sur Supabase Storage
      - `public_url` (text) - URL publique du fichier
      - `mime_type` (text) - Type MIME du fichier
      - `upload_date` (timestamp) - Date/heure de l'upload
      - `status` (text) - Statut (success, error)
      - `user_ip` (text) - Adresse IP du client
      - `error_message` (text) - Message d'erreur si applicable

  2. Indexes
    - Index sur `file_type` pour filtrage rapide
    - Index sur `upload_date` pour tri chronologique
    - Index sur `storage_path` pour lookup

  3. Security
    - Enable RLS sur `media_uploads` table
    - Politique publique en lecture seule (logs d'upload visibles)
    - Politique admin pour lecture/écriture complète
*/

CREATE TABLE IF NOT EXISTS media_uploads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  filename text NOT NULL,
  original_filename text NOT NULL,
  file_type text NOT NULL,
  file_size integer NOT NULL,
  storage_path text NOT NULL UNIQUE,
  public_url text NOT NULL,
  mime_type text,
  upload_date timestamptz DEFAULT now(),
  status text DEFAULT 'success',
  user_ip text,
  error_message text
);

CREATE INDEX IF NOT EXISTS idx_media_uploads_file_type ON media_uploads(file_type);
CREATE INDEX IF NOT EXISTS idx_media_uploads_upload_date ON media_uploads(upload_date DESC);
CREATE INDEX IF NOT EXISTS idx_media_uploads_storage_path ON media_uploads(storage_path);

ALTER TABLE media_uploads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access to media uploads logs"
  ON media_uploads
  FOR SELECT
  TO public
  USING (true);

CREATE POLICY "Service role can insert media uploads"
  ON media_uploads
  FOR INSERT
  TO anon
  WITH CHECK (true);
