const $ = (id) => document.getElementById(id);

let mode = "login";

async function readJson(res) {
  const raw = await res.text();
  if (!raw) return {};

  try {
    return JSON.parse(raw);
  } catch (_) {
    const type = res.headers.get("content-type") || "unknown content type";
    throw new Error(
      `Expected JSON but received ${type} (status ${res.status}).`
    );
  }
}

function setMode(next) {
  mode = next;
  const isLogin = mode === "login";
  $("tabLogin").classList.toggle("active", isLogin);
  $("tabSignup").classList.toggle("active", !isLogin);
  $("authSubmit").textContent = isLogin ? "Log in" : "Create account";
  $("password").setAttribute(
    "autocomplete",
    isLogin ? "current-password" : "new-password"
  );
  $("authError").hidden = true;
}

async function submit(e) {
  e.preventDefault();
  const btn = $("authSubmit");
  const err = $("authError");
  const email = $("email").value.trim();
  const password = $("password").value;

  if (!email || !password) {
    err.textContent = "Email and password are required.";
    err.hidden = false;
    return;
  }
  if (password.length < 8) {
    err.textContent = "Password must be at least 8 characters.";
    err.hidden = false;
    return;
  }

  btn.disabled = true;
  const label = btn.textContent;
  btn.textContent = mode === "login" ? "Signing in…" : "Creating…";
  try {
    const res = await fetch(`/auth/${mode === "login" ? "login" : "signup"}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await readJson(res).catch(() => ({}));
    if (!res.ok) {
      err.textContent = data.error || `Request failed (${res.status}).`;
      err.hidden = false;
      return;
    }
    window.location.href = "/";
  } catch (e) {
    err.textContent = "Network error: " + e.message;
    err.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("tabLogin").addEventListener("click", () => setMode("login"));
  $("tabSignup").addEventListener("click", () => setMode("signup"));
  $("authForm").addEventListener("submit", submit);
});
