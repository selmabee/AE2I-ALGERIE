import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2.39.0";
import { verify } from "https://deno.land/x/djwt@v3.0.1/mod.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Client-Info, Apikey",
};

const JWT_SECRET = Deno.env.get("JWT_SECRET") || "ae2i-secret-key-change-in-production";
const JWT_KEY = await crypto.subtle.importKey(
  "raw",
  new TextEncoder().encode(JWT_SECRET),
  { name: "HMAC", hash: "SHA-256" },
  false,
  ["sign", "verify"]
);

interface AuthUser {
  sub: string;
  email: string;
  role: string;
}

async function verifyToken(authHeader: string | null): Promise<AuthUser | null> {
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return null;
  }

  const token = authHeader.replace("Bearer ", "");

  try {
    const payload = await verify(token, JWT_KEY);
    return {
      sub: payload.sub as string,
      email: payload.email as string,
      role: payload.role as string,
    };
  } catch {
    return null;
  }
}

function hasRole(user: AuthUser | null, roles: string[]): boolean {
  return user !== null && roles.includes(user.role);
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 200, headers: corsHeaders });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
      {
        auth: {
          autoRefreshToken: false,
          persistSession: false,
        },
      }
    );

    const url = new URL(req.url);
    const path = url.pathname.replace("/candidates", "");
    const authUser = await verifyToken(req.headers.get("Authorization"));

    // POST /candidates - Submit candidacy
    if (path === "" && req.method === "POST") {
      const body = await req.json();
      const {
        nom,
        prenom,
        email,
        telephone,
        wilaya,
        diplome,
        specialite,
        experience_annees = 0,
        competences = [],
        langues = [],
        cv_url,
        lettre_motivation,
        disponibilite = "immédiate",
        pretention_salariale,
      } = body;

      // Validation
      if (!nom || !prenom || !email || !telephone || !wilaya || !diplome || !specialite) {
        return new Response(
          JSON.stringify({ error: "Champs obligatoires manquants" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Map to database column names
      const candidateData: any = {
        first_name: prenom,
        last_name: nom,
        email,
        phone: telephone,
        wilaya,
        diplome,
        experience_years: experience_annees,
        cv_url,
        status: "pending",
      };

      // Add optional fields if they exist as columns
      if (specialite) candidateData.specialite = specialite;
      if (competences) candidateData.competences = JSON.stringify(competences);
      if (langues) candidateData.langues = JSON.stringify(langues);
      if (lettre_motivation) candidateData.lettre_motivation = lettre_motivation;
      if (disponibilite) candidateData.disponibilite = disponibilite;
      if (pretention_salariale) candidateData.pretention_salariale = pretention_salariale;
      if (authUser) candidateData.user_id = authUser.sub;

      const { data: candidate, error } = await supabase
        .from("candidates")
        .insert(candidateData)
        .select()
        .single();

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de l'enregistrement de la candidature", details: error.message }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Log activity
      if (authUser) {
        await supabase.from("activity_logs").insert({
          user_id: authUser.sub,
          action: "create_candidacy",
          entity_type: "candidate",
          entity_id: candidate.id,
        });
      }

      return new Response(
        JSON.stringify({
          success: true,
          candidate_id: candidate.id,
          message: "Candidature soumise avec succès",
        }),
        { status: 201, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // GET /candidates - List candidates (requires auth)
    if (path === "" && req.method === "GET") {
      if (!hasRole(authUser, ["admin", "recruteur", "lecteur"])) {
        return new Response(
          JSON.stringify({ error: "Accès non autorisé" }),
          { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Build query with filters
      let query = supabase.from("candidates").select("*", { count: "exact" });

      const diplome = url.searchParams.get("diplome");
      const wilaya = url.searchParams.get("wilaya");
      const status = url.searchParams.get("status");
      const experience_min = url.searchParams.get("experience_min");
      const limit = parseInt(url.searchParams.get("limit") || "50");
      const offset = parseInt(url.searchParams.get("offset") || "0");

      if (diplome) query = query.eq("diplome", diplome);
      if (wilaya) query = query.eq("wilaya", wilaya);
      if (status) query = query.eq("status", status);
      if (experience_min) query = query.gte("experience_years", parseInt(experience_min));

      query = query.order("created_at", { ascending: false }).range(offset, offset + limit - 1);

      const { data: candidates, error, count } = await query;

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la récupération des candidatures" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({ candidates, total: count }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // GET /candidates/:id - Get single candidate
    if (path.startsWith("/") && req.method === "GET") {
      const id = path.substring(1);

      if (!hasRole(authUser, ["admin", "recruteur", "lecteur"])) {
        return new Response(
          JSON.stringify({ error: "Accès non autorisé" }),
          { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      const { data: candidate, error } = await supabase
        .from("candidates")
        .select("*")
        .eq("id", id)
        .maybeSingle();

      if (!candidate || error) {
        return new Response(
          JSON.stringify({ error: "Candidat non trouvé" }),
          { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({ candidate }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // PUT /candidates/:id - Update candidate
    if (path.startsWith("/") && req.method === "PUT") {
      const id = path.substring(1);

      if (!hasRole(authUser, ["admin", "recruteur"])) {
        return new Response(
          JSON.stringify({ error: "Accès non autorisé" }),
          { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      const body = await req.json();
      const updateData: any = {};

      // Map fields
      if (body.status) updateData.status = body.status;
      if (body.notes !== undefined) updateData.notes = body.notes;
      if (body.pdf_resume_url) updateData.pdf_resume_url = body.pdf_resume_url;

      updateData.updated_at = new Date().toISOString();

      const { data: candidate, error } = await supabase
        .from("candidates")
        .update(updateData)
        .eq("id", id)
        .select()
        .single();

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la mise à jour", details: error.message }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: authUser!.sub,
        action: "update_candidate",
        entity_type: "candidate",
        entity_id: id,
        details: { updated_fields: Object.keys(updateData) },
      });

      return new Response(
        JSON.stringify({ success: true, candidate }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // DELETE /candidates/:id - Delete candidate
    if (path.startsWith("/") && req.method === "DELETE") {
      const id = path.substring(1);

      if (!hasRole(authUser, ["admin"])) {
        return new Response(
          JSON.stringify({ error: "Accès non autorisé. Seuls les admins peuvent supprimer" }),
          { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      const { error } = await supabase.from("candidates").delete().eq("id", id);

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la suppression" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: authUser!.sub,
        action: "delete_candidate",
        entity_type: "candidate",
        entity_id: id,
      });

      return new Response(
        JSON.stringify({ success: true, message: "Candidat supprimé" }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    return new Response(
      JSON.stringify({ error: "Route non trouvée" }),
      { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message || "Erreur serveur" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});