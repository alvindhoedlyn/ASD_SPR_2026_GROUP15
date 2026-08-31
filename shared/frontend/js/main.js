const JB_HOME = "http://localhost:8080";
const TOKEN_KEY = "jb_token";
const USER_KEY = "jb_username";
const ROLE_KEY = "jb_role";

function isLoggedIn() {
    return !!localStorage.getItem(TOKEN_KEY);
}
function getUsername() {
    return localStorage.getItem(USER_KEY) || "account";
}
function getRole() {
    return localStorage.getItem(ROLE_KEY) || "client";
}
function isAdmin() {
    return isLoggedIn() && getRole() === "admin";
}

function storeSession(token, username, role) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, username);
    localStorage.setItem(ROLE_KEY, role);
}
function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(ROLE_KEY);
}

async function logOut() {
    const token = localStorage.getItem(TOKEN_KEY);
    clearSession();
    if (token) {
        try {
            await fetch(`${JB_HOME}/api/logout`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token })
            });
        } catch (e) { /* best-effort — local session is already cleared */ }
    }
}

function requireAdmin() {
    if (!isLoggedIn()) {
        alert("Please log in to use this feature.");
        window.location.href = `${JB_HOME}/login.html`;
        return false;
    }
    if (!isAdmin()) {
        alert("This area is for admin accounts only.");
        return false;
    }
    return true;
}

function withToken(url) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return url;
    const u = new URL(url, window.location.href);
    u.searchParams.set("token", token);
    return u.toString();
}

window.jbSessionReady = (async function initSession() {
    const isSharedPage = document.getElementById("auth-link") || document.getElementById("login-form");
    const urlToken = new URLSearchParams(window.location.search).get("token");

    if (urlToken) {
        try {
            const res = await fetch(`${JB_HOME}/api/verify-session?token=${encodeURIComponent(urlToken)}`);
            if (res.ok) {
                const session = await res.json();
                storeSession(urlToken, session.username, session.role);
            }
        } catch (e) { /* fall through to the isLoggedIn() check below */ }

        const cleanUrl = window.location.pathname;
        window.history.replaceState(null, "", cleanUrl);
    }

    if (!isSharedPage && !isLoggedIn()) {
        alert("Please log in to use this feature.");
        window.location.href = `${JB_HOME}/login.html`;
    }
})();

document.addEventListener("DOMContentLoaded", () => {
    const authLink = document.getElementById("auth-link");
    if (authLink) {
        updateAuthLink(authLink);
        authLink.addEventListener("click", async (e) => {
            if (isLoggedIn()) {
                e.preventDefault();
                await logOut();
                updateAuthLink(authLink);
                alert("You've been logged out.");
            }
        });
    }
    const newTripLink = document.getElementById("new-trip-link");
    if (newTripLink) {
        newTripLink.addEventListener("click", (e) => {
            e.preventDefault();
            if (!isLoggedIn()) {
                alert("Please log in to start a new trip.");
                window.location.href = "login.html";
                return;
            }
            alert("New trip flow not implemented yet.");
        });
    }
    document.querySelectorAll("[data-requires-login]").forEach((card) => {
        card.addEventListener("click", (e) => {
            e.preventDefault();
            if (!isLoggedIn()) {
                alert("Please log in to use this feature.");
                window.location.href = "login.html";
                return;
            }
            window.location.href = withToken(card.href);
        });
    });

    const loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const username = document.getElementById("username").value.trim();
            const password = document.getElementById("password").value.trim();
            const errorEl = document.getElementById("login-error");
            const submitBtn = loginForm.querySelector("button[type=submit]");

            submitBtn.disabled = true;
            try {
                const res = await fetch("/api/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username, password })
                });

                if (!res.ok) {
                    errorEl.hidden = false;
                    submitBtn.disabled = false;
                    return;
                }

                const session = await res.json();
                errorEl.hidden = true;
                storeSession(session.token, session.username, session.role);
                window.location.href = "index.html";
            } catch (err) {
                errorEl.textContent = "Could not reach the server. Try again.";
                errorEl.hidden = false;
                submitBtn.disabled = false;
            }
        });

        ["username", "password"].forEach((id) => {
            document.getElementById(id).addEventListener("input", () => {
                document.getElementById("login-error").hidden = true;
            });
        });
    }
});

function updateAuthLink(authLink) {
    if (isLoggedIn()) {
        authLink.textContent = `Log out (${getUsername()} · ${getRole()})`;
        authLink.setAttribute("href", "#");
    } else {
        authLink.textContent = "Log in";
        authLink.setAttribute("href", "login.html");
    }
}