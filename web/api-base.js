/*
 * Cross-origin glue: the frontend may be served from Vercel while the API lives
 * on the homelab. This shim (loaded BEFORE app.js) rewrites all /api and /auth
 * requests to window.API_BASE and sends credentials, so the existing relative
 * fetch() calls in app.js keep working unchanged.
 *
 * It also guards the SPA: if auth is enabled and the user isn't logged in,
 * it redirects to the login page.
 */
(function () {
  const BASE = window.API_BASE || "";
  const _fetch = window.fetch.bind(window);
  window.fetch = function (url, opts) {
    opts = opts || {};
    if (typeof url === "string" && (url.startsWith("/api") || url.startsWith("/auth"))) {
      url = BASE + url;
      opts.credentials = "include";
    }
    return _fetch(url, opts);
  };

  // Expose for non-fetch uses (e.g. links, redirects)
  window.apiUrl = (p) => BASE + p;

  // Auth guard — skip on the login page itself.
  const onLoginPage = location.pathname.endsWith("/login.html");
  window.addEventListener("DOMContentLoaded", async () => {
    try {
      const me = await fetch("/api/me").then((r) => r.json());
      window.HV_USER = me;
      if (me.auth_enabled && !me.authenticated && !onLoginPage) {
        location.href = "login.html";
        return;
      }
      // populate a logout link / user name if present in the DOM
      const nameEl = document.getElementById("hv-user-name");
      if (nameEl && me.name) nameEl.textContent = me.name;
    } catch (e) {
      // backend unreachable — leave the page as-is (it will show its own errors)
      console.warn("auth check failed", e);
    }
  });
})();
