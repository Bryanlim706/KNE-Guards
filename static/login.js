const $ = (id) => document.getElementById(id);

let sb = null;

async function initClient() {
  if (sb) return sb;
  const res = await fetch("/config");
  const cfg = await res.json();
  if (!cfg.supabase_url || !cfg.supabase_anon_key) {
    throw new Error("Supabase not configured on the server.");
  }
  sb = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key);
  return sb;
}

async function startNow() {
  const btn = $("startNow");
  const err = $("authError");
  err.hidden = true;
  btn.disabled = true;
  const label = btn.textContent;
  btn.textContent = "Setting up…";
  try {
    const client = await initClient();
    const { data: existing } = await client.auth.getSession();
    if (!existing.session) {
      const { error } = await client.auth.signInAnonymously();
      if (error) throw error;
    }
    window.location.href = "/";
  } catch (e) {
    err.textContent = e.message || "Could not start a session.";
    err.hidden = false;
    btn.disabled = false;
    btn.textContent = label;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  $("startNow").addEventListener("click", startNow);
  try {
    const client = await initClient();
    const { data } = await client.auth.getSession();
    if (data.session) window.location.href = "/";
  } catch (_) {
    // Stay on the page; the button will retry initialization.
  }
});
