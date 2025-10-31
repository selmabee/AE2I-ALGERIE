from flask import Flask, jsonify
from supabase import create_client, Client, ClientOptions
import os

app = Flask(__name__)

# Récupération des variables d'environnement Render
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialisation de Supabase
try:
    options = ClientOptions()  # ✅ objet d’options vide compatible
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY, options)
    print("[OK] Supabase initialized successfully")
except Exception as e:
    print(f"[ERROR] Supabase initialization failed: {e}")

# Route de test pour vérifier le backend
@app.route("/api/health")
def health():
    try:
        data = supabase.table("users").select("*").limit(1).execute()
        return jsonify({
            "status": "ok",
            "supabase": "connected",
            "rows_checked": len(data.data)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Point d'entrée Render
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
