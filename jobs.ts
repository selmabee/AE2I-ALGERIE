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
    const path = url.pathname.replace("/jobs", "");
    const authUser = await verifyToken(req.headers.get("Authorization"));

    // GET /jobs - List jobs (public for open jobs, all jobs for staff)
    if (path === "" && req.method === "GET") {
      let query = supabase.from("jobs").select("*", { count: "exact" });

      // Filters
      const wilaya = url.searchParams.get("wilaya");
      const contract_type = url.searchParams.get("contract_type");
      const is_active = url.searchParams.get("is_active");
      const limit = parseInt(url.searchParams.get("limit") || "50");
      const offset = parseInt(url.searchParams.get("offset") || "0");

      // If not staff, only show active jobs
      if (!hasRole(authUser, ["admin", "recruteur", "lecteur"])) {
        query = query.eq("is_active", true);
      } else if (is_active !== null && is_active !== undefined) {
        query = query.eq("is_active", is_active === "true");
      }

      if (wilaya) query = query.eq("wilaya", wilaya);
      if (contract_type) query = query.eq("contract_type", contract_type);

      query = query.order("created_at", { ascending: false }).range(offset, offset + limit - 1);

      const { data: jobs, error, count } = await query;

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la récupération des offres" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({ jobs, total: count }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // POST /jobs - Create job (admin/recruiter only)
    if (path === "" && req.method === "POST") {
      if (!hasRole(authUser, ["admin", "recruteur"])) {
        return new Response(
          JSON.stringify({ error: "Accès non autorisé" }),
          { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      const body = await req.json();
      const {
        titre,
        description,
        type_contrat,
        localisation,
        wilaya,
        salaire_min,
        salaire_max,
        experience_requise,
        diplome_requis,
        competences_requises = [],
        date_limite,
      } = body;

      // Validation
      if (!titre || !description || !type_contrat || !localisation || !wilaya || !experience_requise || !diplome_requis) {
        return new Response(
          JSON.stringify({ error: "Champs obligatoires manquants" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Map to database columns
      const jobData: any = {
        title: titre,
        description,
        contract_type: type_contrat,
        location: localisation,
        wilaya,
        is_active: true,
        created_by: authUser!.sub,
      };

      if (salaire_min) jobData.salaire_min = salaire_min;
      if (salaire_max) jobData.salaire_max = salaire_max;
      if (experience_requise) jobData.experience_requise = experience_requise;
      if (diplome_requis) jobData.diplome_requis = diplome_requis;
      if (competences_requises) jobData.competences_requises = JSON.stringify(competences_requises);
      if (date_limite) jobData.date_limite = date_limite;

      const { data: job, error } = await supabase.from("jobs").insert(jobData).select().single();

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la création de l'offre", details: error.message }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: authUser!.sub,
        action: "create_job",
        entity_type: "job",
        entity_id: job.id,
      });

      return new Response(
        JSON.stringify({ success: true, job }),
        { status: 201, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // GET /jobs/:id - Get single job
    if (path.startsWith("/") && req.method === "GET") {
      const id = path.substring(1);

      const { data: job, error } = await supabase.from("jobs").select("*").eq("id", id).maybeSingle();

      if (!job || error) {
        return new Response(
          JSON.stringify({ error: "Offre non trouvée" }),
          { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Check if user can view inactive jobs
      if (!job.is_active && !hasRole(authUser, ["admin", "recruteur", "lecteur"])) {
        return new Response(
          JSON.stringify({ error: "Offre non disponible" }),
          { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({ job }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // PUT /jobs/:id - Update job
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
      if (body.titre) updateData.title = body.titre;
      if (body.description) updateData.description = body.description;
      if (body.type_contrat) updateData.contract_type = body.type_contrat;
      if (body.localisation) updateData.location = body.localisation;
      if (body.wilaya) updateData.wilaya = body.wilaya;
      if (body.salaire_min !== undefined) updateData.salaire_min = body.salaire_min;
      if (body.salaire_max !== undefined) updateData.salaire_max = body.salaire_max;
      if (body.experience_requise) updateData.experience_requise = body.experience_requise;
      if (body.diplome_requis) updateData.diplome_requis = body.diplome_requis;
      if (body.competences_requises) updateData.competences_requises = JSON.stringify(body.competences_requises);
      if (body.date_limite !== undefined) updateData.date_limite = body.date_limite;
      if (body.is_active !== undefined) updateData.is_active = body.is_active;

      updateData.updated_at = new Date().toISOString();

      const { data: job, error } = await supabase.from("jobs").update(updateData).eq("id", id).select().single();

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la mise à jour", details: error.message }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: authUser!.sub,
        action: "update_job",
        entity_type: "job",
        entity_id: id,
        details: { updated_fields: Object.keys(updateData) },
      });

      return new Response(
        JSON.stringify({ success: true, job }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // DELETE /jobs/:id - Delete job
    if (path.startsWith("/") && req.method === "DELETE") {
      const id = path.substring(1);

      if (!hasRole(authUser, ["admin"])) {
        return new Response(
          JSON.stringify({ error: "Accès non autorisé. Seuls les admins peuvent supprimer" }),
          { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      const { error } = await supabase.from("jobs").delete().eq("id", id);

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la suppression" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: authUser!.sub,
        action: "delete_job",
        entity_type: "job",
        entity_id: id,
      });

      return new Response(
        JSON.stringify({ success: true, message: "Offre supprimée" }),
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