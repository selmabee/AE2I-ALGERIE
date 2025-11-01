import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2.39.0";
import { create } from "https://deno.land/x/djwt@v3.0.1/mod.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Client-Info, Apikey",
};

const LINKEDIN_CLIENT_ID = Deno.env.get("LINKEDIN_CLIENT_ID") || "";
const LINKEDIN_CLIENT_SECRET = Deno.env.get("LINKEDIN_CLIENT_SECRET") || "";
const LINKEDIN_REDIRECT_URI = Deno.env.get("LINKEDIN_REDIRECT_URI") || "";
const JWT_SECRET = Deno.env.get("JWT_SECRET") || "ae2i-secret-key-change-in-production";
const FRONTEND_URL = Deno.env.get("FRONTEND_URL") || "https://ae2i-algerie.netlify.app";

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
      exp: Math.floor(Date.now() / 1000) + 3600,
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
    const path = url.pathname.replace("/linkedin-oauth", "");

    // GET /linkedin-oauth/login - Redirect to LinkedIn
    if (path === "/login" && req.method === "GET") {
      if (!LINKEDIN_CLIENT_ID || !LINKEDIN_REDIRECT_URI) {
        return new Response(
          JSON.stringify({ error: "LinkedIn OAuth non configuré. Vérifiez les variables d'environnement." }),
          { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
        );
      }

      const state = crypto.randomUUID();
      const scope = "openid profile email";

      const authUrl = `https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=${LINKEDIN_CLIENT_ID}&redirect_uri=${encodeURIComponent(LINKEDIN_REDIRECT_URI)}&state=${state}&scope=${encodeURIComponent(scope)}`;

      return new Response(
        JSON.stringify({ auth_url: authUrl, state }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // GET /linkedin-oauth/callback - Handle OAuth callback
    if (path === "/callback" && req.method === "GET") {
      const code = url.searchParams.get("code");
      const state = url.searchParams.get("state");

      if (!code) {
        return new Response(
          `<!DOCTYPE html><html><body><script>window.opener.postMessage({type:'linkedin_error',error:'Code manquant'},"*");window.close();</script></body></html>`,
          { status: 400, headers: { ...corsHeaders, "Content-Type": "text/html" } }
        );
      }

      try {
        // Exchange code for access token
        const tokenResponse = await fetch("https://www.linkedin.com/oauth/v2/accessToken", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            grant_type: "authorization_code",
            code,
            client_id: LINKEDIN_CLIENT_ID,
            client_secret: LINKEDIN_CLIENT_SECRET,
            redirect_uri: LINKEDIN_REDIRECT_URI,
          }),
        });

        if (!tokenResponse.ok) {
          throw new Error("Failed to exchange code for token");
        }

        const tokenData = await tokenResponse.json();
        const accessToken = tokenData.access_token;

        // Get user profile
        const profileResponse = await fetch("https://api.linkedin.com/v2/userinfo", {
          headers: { Authorization: `Bearer ${accessToken}` },
        });

        if (!profileResponse.ok) {
          throw new Error("Failed to fetch user profile");
        }

        const profile = await profileResponse.json();
        const email = profile.email;
        const full_name = profile.name || `${profile.given_name || ""} ${profile.family_name || ""}`.trim();
        const linkedin_id = profile.sub;
        const profile_photo = profile.picture;

        if (!email) {
          throw new Error("Email not provided by LinkedIn");
        }

        // Check if user exists by email or linkedin_id
        const { data: existingUser } = await supabase
          .from("users")
          .select("*")
          .or(`email.eq.${email},linkedin_id.eq.${linkedin_id}`)
          .maybeSingle();

        let user;
        if (existingUser) {
          // Update user with LinkedIn info
          const { data: updatedUser } = await supabase
            .from("users")
            .update({
              linkedin_id,
              profile_photo,
              last_login: new Date().toISOString(),
            })
            .eq("id", existingUser.id)
            .select()
            .single();

          user = updatedUser;

          // Log activity
          await supabase.from("activity_logs").insert({
            user_id: user.id,
            action: "linkedin_login",
            entity_type: "user",
            entity_id: user.id,
          });
        } else {
          // Create new user
          const { data: newUser, error: createError } = await supabase
            .from("users")
            .insert({
              email,
              full_name,
              linkedin_id,
              profile_photo,
              role: "candidat",
              is_active: true,
              email_verified: true,
            })
            .select()
            .single();

          if (createError) {
            throw new Error("Failed to create user");
          }

          user = newUser;

          // Log activity
          await supabase.from("activity_logs").insert({
            user_id: user.id,
            action: "linkedin_register",
            entity_type: "user",
            entity_id: user.id,
          });
        }

        // Create tokens
        const jwtAccessToken = await createAccessToken(user);
        const refreshToken = createRefreshToken();

        // Save refresh token
        await supabase.from("refresh_tokens").insert({
          user_id: user.id,
          token: refreshToken,
          expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
        });

        // Return HTML that sends message to parent window and closes popup
        const userData = {
          id: user.id,
          email: user.email,
          full_name: user.full_name,
          role: user.role,
          profile_photo: user.profile_photo,
        };

        return new Response(
          `<!DOCTYPE html>
          <html>
          <head><title>LinkedIn Auth Success</title></head>
          <body>
            <script>
              window.opener.postMessage({
                type: 'linkedin_success',
                access_token: '${jwtAccessToken}',
                refresh_token: '${refreshToken}',
                user: ${JSON.stringify(userData)}
              }, '*');
              window.close();
            </script>
            <p>Authentification réussie ! Cette fenêtre va se fermer automatiquement...</p>
          </body>
          </html>`,
          { status: 200, headers: { ...corsHeaders, "Content-Type": "text/html" } }
        );
      } catch (error) {
        return new Response(
          `<!DOCTYPE html><html><body><script>window.opener.postMessage({type:'linkedin_error',error:'${error.message}'},"*");window.close();</script></body></html>`,
          { status: 500, headers: { ...corsHeaders, "Content-Type": "text/html" } }
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