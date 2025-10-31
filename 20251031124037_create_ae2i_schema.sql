/*
  # Création du schéma complet pour AE2I Algérie

  ## Tables créées
  
  ### 1. users
  - id (uuid, primary key)
  - email (text, unique)
  - password_hash (text)
  - full_name (text)
  - role (text) - Admin, Recruteur, Lecteur
  - created_at (timestamptz)
  - last_login (timestamptz)
  
  ### 2. candidates
  - id (uuid, primary key)
  - full_name (text)
  - email (text)
  - phone (text)
  - position (text)
  - linkedin_url (text)
  - linkedin_data (jsonb) - Données du profil LinkedIn
  - cv_url (text) - URL du CV téléversé
  - pdf_summary_url (text) - URL du PDF résumé généré
  - skills (text[])
  - status (text) - nouveau, en_cours, accepte, refuse
  - created_at (timestamptz)
  - updated_at (timestamptz)
  - created_by (uuid) - référence vers users
  
  ### 3. media_files
  - id (uuid, primary key)
  - file_name (text)
  - file_type (text) - image, video, pdf, cv
  - file_url (text)
  - file_size (bigint)
  - uploaded_by (uuid) - référence vers users
  - uploaded_at (timestamptz)
  - metadata (jsonb)
  
  ### 4. linkedin_tokens
  - id (uuid, primary key)
  - user_id (uuid) - référence vers users
  - access_token (text)
  - refresh_token (text)
  - expires_at (timestamptz)
  - created_at (timestamptz)
  
  ### 5. site_settings
  - id (uuid, primary key)
  - setting_key (text, unique)
  - setting_value (jsonb)
  - updated_at (timestamptz)
  - updated_by (uuid) - référence vers users
  
  ## Sécurité
  - RLS activé sur toutes les tables
  - Policies restrictives basées sur les rôles
  - Authentification requise pour toutes les opérations
*/

-- Table users
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  full_name text NOT NULL,
  role text NOT NULL DEFAULT 'Lecteur' CHECK (role IN ('Admin', 'Recruteur', 'Lecteur')),
  created_at timestamptz DEFAULT now(),
  last_login timestamptz
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
  ON users FOR SELECT
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
  ON users FOR UPDATE
  TO authenticated
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- Table candidates
CREATE TABLE IF NOT EXISTS candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name text NOT NULL,
  email text NOT NULL,
  phone text,
  position text,
  linkedin_url text,
  linkedin_data jsonb,
  cv_url text,
  pdf_summary_url text,
  skills text[],
  status text DEFAULT 'nouveau' CHECK (status IN ('nouveau', 'en_cours', 'accepte', 'refuse')),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  created_by uuid REFERENCES users(id)
);

ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view candidates"
  ON candidates FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Admin and Recruteur can insert candidates"
  ON candidates FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role IN ('Admin', 'Recruteur')
    )
  );

CREATE POLICY "Admin and Recruteur can update candidates"
  ON candidates FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role IN ('Admin', 'Recruteur')
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role IN ('Admin', 'Recruteur')
    )
  );

CREATE POLICY "Only Admin can delete candidates"
  ON candidates FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role = 'Admin'
    )
  );

-- Table media_files
CREATE TABLE IF NOT EXISTS media_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  file_name text NOT NULL,
  file_type text NOT NULL CHECK (file_type IN ('image', 'video', 'pdf', 'cv')),
  file_url text NOT NULL,
  file_size bigint DEFAULT 0,
  uploaded_by uuid REFERENCES users(id),
  uploaded_at timestamptz DEFAULT now(),
  metadata jsonb
);

ALTER TABLE media_files ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view media files"
  ON media_files FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Admin and Recruteur can upload media files"
  ON media_files FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role IN ('Admin', 'Recruteur')
    )
  );

CREATE POLICY "Only Admin can delete media files"
  ON media_files FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role = 'Admin'
    )
  );

-- Table linkedin_tokens
CREATE TABLE IF NOT EXISTS linkedin_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) UNIQUE NOT NULL,
  access_token text NOT NULL,
  refresh_token text,
  expires_at timestamptz,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE linkedin_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own tokens"
  ON linkedin_tokens FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own tokens"
  ON linkedin_tokens FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own tokens"
  ON linkedin_tokens FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Table site_settings
CREATE TABLE IF NOT EXISTS site_settings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  setting_key text UNIQUE NOT NULL,
  setting_value jsonb NOT NULL,
  updated_at timestamptz DEFAULT now(),
  updated_by uuid REFERENCES users(id)
);

ALTER TABLE site_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Everyone can view site settings"
  ON site_settings FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Only Admin can modify site settings"
  ON site_settings FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role = 'Admin'
    )
  );

CREATE POLICY "Only Admin can update site settings"
  ON site_settings FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role = 'Admin'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role = 'Admin'
    )
  );

-- Indexes pour performances
CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(email);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_candidates_created_at ON candidates(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_media_files_type ON media_files(file_type);
CREATE INDEX IF NOT EXISTS idx_media_files_uploaded_at ON media_files(uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Fonction pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour candidates.updated_at
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'update_candidates_updated_at'
  ) THEN
    CREATE TRIGGER update_candidates_updated_at
      BEFORE UPDATE ON candidates
      FOR EACH ROW
      EXECUTE FUNCTION update_updated_at_column();
  END IF;
END $$;

-- Trigger pour site_settings.updated_at
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'update_site_settings_updated_at'
  ) THEN
    CREATE TRIGGER update_site_settings_updated_at
      BEFORE UPDATE ON site_settings
      FOR EACH ROW
      EXECUTE FUNCTION update_updated_at_column();
  END IF;
END $$;