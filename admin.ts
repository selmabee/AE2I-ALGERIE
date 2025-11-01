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

function isAdmin(user: AuthUser | null): boolean {
  return user !== null && user.role === "admin";
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
    const path = url.pathname.replace("/admin", "");
    const authUser = await verifyToken(req.headers.get("Authorization"));

    // Check admin access for all routes
    if (!isAdmin(authUser)) {
      return new Response(
        JSON.stringify({ error: "Accès non autorisé. Seuls les administrateurs peuvent accéder à cette ressource." }),
        { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // GET /admin/stats - Get platform statistics
    if (path === "/stats" && req.method === "GET") {
      const { count: totalUsers } = await supabase
        .from("users")
        .select("*", { count: "exact", head: true });

      const { count: totalCandidates } = await supabase
        .from("candidates")
        .select("*", { count: "exact", head: true });

      const { count: totalJobs } = await supabase
        .from("jobs")
        .select("*", { count: "exact", head: true });

      const { count: activeJobs } = await supabase
        .from("jobs")
        .select("*", { count: "exact", head: true })
        .eq("is_active", true);

      const { count: pendingCandidates } = await supabase
        .from("candidates")
        .select("*", { count: "exact", head: true })
        .eq("status", "pending");

      return new Response(
        JSON.stringify({
          stats: {
            total_users: totalUsers || 0,
            total_candidates: totalCandidates || 0,
            total_jobs: totalJobs || 0,
            active_jobs: activeJobs || 0,
            pending_candidates: pendingCandidates || 0,
          },
        }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // GET /admin/logs - Get activity logs
    if (path === "/logs" && req.method === "GET") {
      const limit = parseInt(url.searchParams.get("limit") || "100");
      const offset = parseInt(url.searchParams.get("offset") || "0");
      const action = url.searchParams.get("action");
      const entity_type = url.searchParams.get("entity_type");

      let query = supabase
        .from("activity_logs")
        .select("*, users(email, full_name)", { count: "exact" })
        .order("created_at", { ascending: false })
        .range(offset, offset + limit - 1);

      if (action) query = query.eq("action", action);
      if (entity_type) query = query.eq("entity_type", entity_type);

      const { data: logs, error, count } = await query;

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la récupération des logs" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({ logs, total: count }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // POST /admin/export/candidates - Export candidates as JSON
    if (path === "/export/candidates" && req.method === "POST") {
      const { data: candidates, error } = await supabase
        .from("candidates")
        .select("*")
        .order("created_at", { ascending: false });

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de l'export des candidatures" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: authUser!.sub,
        action: "export_candidates",
        entity_type: "candidate",
        details: { count: candidates?.length || 0 },
      });

      return new Response(
        JSON.stringify({
          success: true,
          candidates,
          count: candidates?.length || 0,
          exported_at: new Date().toISOString(),
        }),
        {
          status: 200,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json",
            "Content-Disposition": `attachment; filename="ae2i-candidates-${Date.now()}.json"`,
          },
        }
      );
    }

    // POST /admin/export/jobs - Export jobs as JSON
    if (path === "/export/jobs" && req.method === "POST") {
      const { data: jobs, error } = await supabase
        .from("jobs")
        .select("*")
        .order("created_at", { ascending: false });

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de l'export des offres" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: authUser!.sub,
        action: "export_jobs",
        entity_type: "job",
        details: { count: jobs?.length || 0 },
      });

      return new Response(
        JSON.stringify({
          success: true,
          jobs,
          count: jobs?.length || 0,
          exported_at: new Date().toISOString(),
        }),
        {
          status: 200,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json",
            "Content-Disposition": `attachment; filename="ae2i-jobs-${Date.now()}.json"`,
          },
        }
      );
    }

    // POST /admin/export/all - Export complete database
    if (path === "/export/all" && req.method === "POST") {
      const { data: users } = await supabase.from("users").select("id, email, full_name, role, created_at");
      const { data: candidates } = await supabase.from("candidates").select("*");
      const { data: jobs } = await supabase.from("jobs").select("*");
      const { data: logs } = await supabase.from("activity_logs").select("*").order("created_at", { ascending: false }).limit(1000);

      const exportData = {
        export_date: new Date().toISOString(),
        version: "1.0",
        data: {
          users: users || [],
          candidates: candidates || [],
          jobs: jobs || [],
          activity_logs: logs || [],
        },
        counts: {
          users: users?.length || 0,
          candidates: candidates?.length || 0,
          jobs: jobs?.length || 0,
          logs: logs?.length || 0,
        },
      };

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: authUser!.sub,
        action: "export_all",
        entity_type: "system",
        details: exportData.counts,
      });

      return new Response(
        JSON.stringify(exportData),
        {
          status: 200,
          headers: {
            ...corsHeaders,
            "Content-Type": "application/json",
            "Content-Disposition": `attachment; filename="ae2i-full-export-${Date.now()}.json"`,
          },
        }
      );
    }

    // DELETE /admin/clear/candidates - Clear all candidates (with confirmation)
    if (path === "/clear/candidates" && req.method === "DELETE") {
      const body = await req.json();
      const { confirmation } = body;

      if (confirmation !== "CONFIRMER_SUPPRESSION") {
        return new Response(
          JSON.stringify({ error: "Confirmation requise. Envoyez {confirmation: 'CONFIRMER_SUPPRESSION'}" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Get count before deletion
      const { count } = await supabase.from("candidates").select("*", { count: "exact", head: true });

      const { error } = await supabase.from("candidates").delete().neq("id", "00000000-0000-0000-0000-000000000000");

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la suppression" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: authUser!.sub,
        action: "clear_all_candidates",
        entity_type: "candidate",
        details: { deleted_count: count },
      });

      return new Response(
        JSON.stringify({ success: true, message: `${count} candidatures supprimées`, deleted_count: count }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // GET /admin/users - List all users
    if (path === "/users" && req.method === "GET") {
      const { data: users, error } = await supabase
        .from("users")
        .select("id, email, full_name, role, is_active, email_verified, last_login, created_at")
        .order("created_at", { ascending: false });

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la récupération des utilisateurs" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({ users }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // PUT /admin/users/:id - Update user (role, active status)
    if (path.startsWith("/users/") && req.method === "PUT") {
      const id = path.replace("/users/", "");
      const body = await req.json();
      const updateData: any = {};

      if (body.role) updateData.role = body.role;
      if (body.is_active !== undefined) updateData.is_active = body.is_active;

      const { data: user, error } = await supabase
        .from("users")
        .update(updateData)
        .eq("id", id)
        .select()
        .single();

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la mise à jour de l'utilisateur" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: authUser!.sub,
        action: "update_user",
        entity_type: "user",
        entity_id: id,
        details: updateData,
      });

      return new Response(
        JSON.stringify({ success: true, user }),
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