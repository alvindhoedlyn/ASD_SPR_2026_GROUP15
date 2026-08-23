// Wayfare — shared API base URLs
// Each student's frontend imports this file so backend ports/hosts
// are changed in exactly one place, not five.
//
// In Docker Compose, service names resolve as hostnames on the shared
// network, e.g. http://student-3-backend:5000
// In local (non-docker) dev, use http://localhost:<port> instead.

// const API_CONFIG = {
//     routes: "http://localhost:5001",  // Student 1 — Route Planner
//     budget: "http://localhost:5002",  // Student 2 — Budget Tracker
//     stays: "http://localhost:5003",  // Student 3 — Accommodation Recommender
//     places: "http://localhost:5004",  // Student 4 — Location Recommender
//     flights: "http://localhost:5005",  // Student 5 — Flight Recommender

//     aiMode: "http://localhost:11434",
//     mcpServer: "http://localhost:8100",
//     ragServer: "http://localhost:8200",
//     multiAgent: "http://localhost:8300"
// };

// // Node/CommonJS export (for backend use, if needed) — no-op in the browser
// if (typeof module !== "undefined" && module.exports) {
//     module.exports = API_CONFIG;
// }

const AUTH_KEY = "wayfare_logged_in";
const AUTH_USER_KEY = "wayfare_username";

function isLoggedIn() {
    return localStorage.getItem(AUTH_KEY) === "true";
}

function logIn(username) {
    localStorage.setItem(AUTH_KEY, "true");
    localStorage.setItem(AUTH_USER_KEY, username);
}

function logOut() {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
}

document.addEventListener("DOMContentLoaded", () => {

    // ---- Top bar auth link (Log in / Log out toggle) ----
    const authLink = document.getElementById("auth-link");
    if (authLink) {
        updateAuthLink(authLink);
        authLink.addEventListener("click", (e) => {
            if (isLoggedIn()) {
                e.preventDefault();
                logOut();
                updateAuthLink(authLink);
                alert("You've been logged out.");
            }
            // if not logged in, let it navigate to login.html normally
        });
    }

    // ---- "New trip" placeholder ----
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

    // ---- Feature cards: require login before navigating out ----
    document.querySelectorAll("[data-requires-login]").forEach((card) => {
        card.addEventListener("click", (e) => {
            if (!isLoggedIn()) {
                e.preventDefault();
                alert("Please log in to use this feature.");
                window.location.href = "login.html";
            }
            // if logged in, let the link navigate normally
        });
    });

    // ---- Login form (login.html) ----
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const username = document.getElementById("username").value.trim();
            const password = document.getElementById("password").value.trim();
            const errorEl = document.getElementById("login-error");

            if (!username || !password) {
                errorEl.hidden = false;
                return;
            }
            errorEl.hidden = true;

            logIn(username);
            window.location.href = "index.html";
        });

        // Clear error as soon as the user edits either field
        ["username", "password"].forEach((id) => {
            document.getElementById(id).addEventListener("input", () => {
                document.getElementById("login-error").hidden = true;
            });
        });
    }
});

function updateAuthLink(authLink) {
    if (isLoggedIn()) {
        const username = localStorage.getItem(AUTH_USER_KEY) || "account";
        authLink.textContent = `Log out (${username})`;
        authLink.setAttribute("href", "#");
    } else {
        authLink.textContent = "Log in";
        authLink.setAttribute("href", "login.html");
    }
}