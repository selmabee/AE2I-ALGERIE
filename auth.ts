import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2.39.0";
import * as bcrypt from "https://deno.land/x/bcrypt@v0.4.1/mod.ts";
import { create, verify } from "https://deno.land/x/djwt@v3.0.1/mod.ts";

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

interface User {
  id: string;
  email: string;
  role: string;
  full_name: string;
  profile_photo?: string;
  current_position?: string;
}

function createAccessToken(user: User): Promise<string> {
  return create(
    { alg: "HS256", typ: "JWT" },
    {
      sub: user.id,
      email: user.email,
      role: user.role,
      exp: Math.floor(Date.now() / 1000) + 3600, // 1 hour
    },
    JWT_KEY
  );
}

function createRefreshToken(): string {
  return crypto.randomUUID() + "-" + Date.now();
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
    const path = url.pathname.replace("/auth", "");

    // POST /auth/register - Register new user
    if (path === "/register" && req.method === "POST") {
      const { email, password, full_name, role = "candidat" } = await req.json();

      if (!email || !password || !full_name) {
        return new Response(
          JSON.stringify({ error: "Email, password et nom complet requis" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Check if user exists
      const { data: existingUser } = await supabase
        .from("users")
        .select("id")
        .eq("email", email)
        .maybeSingle();

      if (existingUser) {
        return new Response(
          JSON.stringify({ error: "Un utilisateur avec cet email existe déjà" }),
          { status: 409, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Hash password
      const password_hash = await bcrypt.hash(password);

      // Create user
      const { data: user, error } = await supabase
        .from("users")
        .insert({
          email,
          password_hash,
          full_name,
          role,
          is_active: true,
          email_verified: false,
        })
        .select()
        .single();

      if (error) {
        return new Response(
          JSON.stringify({ error: "Erreur lors de la création de l'utilisateur" }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Create tokens
      const accessToken = await createAccessToken(user);
      const refreshToken = createRefreshToken();

      // Save refresh token
      await supabase.from("refresh_tokens").insert({
        user_id: user.id,
        token: refreshToken,
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      });

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: user.id,
        action: "register",
        entity_type: "user",
        entity_id: user.id,
      });

      return new Response(
        JSON.stringify({
          access_token: accessToken,
          refresh_token: refreshToken,
          user: {
            id: user.id,
            email: user.email,
            full_name: user.full_name,
            role: user.role,
          },
        }),
        { status: 201, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // POST /auth/login - Login user
    if (path === "/login" && req.method === "POST") {
      const { email, password } = await req.json();

      if (!email || !password) {
        return new Response(
          JSON.stringify({ error: "Email et mot de passe requis" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Get user
      const { data: user, error } = await supabase
        .from("users")
        .select("*")
        .eq("email", email)
        .maybeSingle();

      if (!user || !user.password_hash) {
        return new Response(
          JSON.stringify({ error: "Email ou mot de passe incorrect" }),
          { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Verify password
      const validPassword = await bcrypt.compare(password, user.password_hash);
      if (!validPassword) {
        return new Response(
          JSON.stringify({ error: "Email ou mot de passe incorrect" }),
          { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      if (!user.is_active) {
        return new Response(
          JSON.stringify({ error: "Compte désactivé" }),
          { status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Update last login
      await supabase
        .from("users")
        .update({ last_login: new Date().toISOString() })
        .eq("id", user.id);

      // Create tokens
      const accessToken = await createAccessToken(user);
      const refreshToken = createRefreshToken();

      // Save refresh token
      await supabase.from("refresh_tokens").insert({
        user_id: user.id,
        token: refreshToken,
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      });

      // Log activity
      await supabase.from("activity_logs").insert({
        user_id: user.id,
        action: "login",
        entity_type: "user",
        entity_id: user.id,
      });

      return new Response(
        JSON.stringify({
          access_token: accessToken,
          refresh_token: refreshToken,
          user: {
            id: user.id,
            email: user.email,
            full_name: user.full_name,
            role: user.role,
            profile_photo: user.profile_photo,
            current_position: user.current_position,
          },
        }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // POST /auth/refresh - Refresh access token
    if (path === "/refresh" && req.method === "POST") {
      const { refresh_token } = await req.json();

      if (!refresh_token) {
        return new Response(
          JSON.stringify({ error: "Refresh token requis" }),
          { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Get refresh token
      const { data: tokenData, error: tokenError } = await supabase
        .from("refresh_tokens")
        .select("*, users(*)")
        .eq("token", refresh_token)
        .eq("revoked", false)
        .maybeSingle();

      if (!tokenData || tokenError) {
        return new Response(
          JSON.stringify({ error: "Refresh token invalide" }),
          { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      // Check expiration
      if (new Date(tokenData.expires_at) < new Date()) {
        return new Response(
          JSON.stringify({ error: "Refresh token expiré" }),
          { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      const user = tokenData.users;
      const accessToken = await createAccessToken(user);

      return new Response(
        JSON.stringify({ access_token: accessToken }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // POST /auth/logout - Logout user
    if (path === "/logout" && req.method === "POST") {
      const { refresh_token } = await req.json();

      if (refresh_token) {
        await supabase
          .from("refresh_tokens")
          .update({ revoked: true })
          .eq("token", refresh_token);
      }

      return new Response(
        JSON.stringify({ message: "Déconnecté avec succès" }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // GET /auth/me - Get current user
    if (path === "/me" && req.method === "GET") {
      const authHeader = req.headers.get("Authorization");
      if (!authHeader || !authHeader.startsWith("Bearer ")) {
        return new Response(
          JSON.stringify({ error: "Token manquant" }),
          { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      const token = authHeader.replace("Bearer ", "");

      try {
        const payload = await verify(token, JWT_KEY);
        const userId = payload.sub as string;

        const { data: user, error } = await supabase
          .from("users")
          .select("id, email, full_name, role, profile_photo, current_position, is_active")
          .eq("id", userId)
          .maybeSingle();

        if (!user || error) {
          return new Response(
            JSON.stringify({ error: "Utilisateur non trouvé" }),
            { status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" } }
          );
        }

        return new Response(
          JSON.stringify({ user }),
          { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      } catch {
        return new Response(
          JSON.stringify({ error: "Token invalide" }),
          { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }
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