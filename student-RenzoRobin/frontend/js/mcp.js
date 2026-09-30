// student-RenzoRobin/frontend/js/mcp.js
//
// Talks to the backend's /mcp/* routes (added in backend/app.py).

// Hardcoded to this feature's own backend on purpose — do NOT fall back to
// window.BACKEND_URL here. The shared frontend (loaded via
// http://localhost:3000/js/main.js) may already define a global with that
// same name pointing at shared-backend (port 5000), which would silently
// hijack these requests and send them to the wrong service.
const RENZO_BACKEND_URL = "http://localhost:5003";

const mcpModeToggle = document.getElementById("mcp-mode-toggle");
const mcpModeState = document.getElementById("mcp-mode-state");
const mcpResultPanel = document.getElementById("mcp-result");
const mcpCityForm = document.getElementById("mcp-city-form");
const mcpDetailsForm = document.getElementById("mcp-details-form");

function isMcpEnabled() {
    return mcpModeToggle.checked;
}

function renderMcpState() {
    if (isMcpEnabled()) {
        mcpModeState.textContent = "ON";
        mcpModeState.classList.add("feature-on");
        mcpModeState.classList.remove("feature-off");
    } else {
        mcpModeState.textContent = "OFF";
        mcpModeState.classList.add("feature-off");
        mcpModeState.classList.remove("feature-on");
        mcpResultPanel.textContent = "MCP Mode is OFF. Enable MCP Mode to run MCP tools.";
    }
}

async function callMcp(path, body) {
    if (!isMcpEnabled()) {
        mcpResultPanel.textContent = "MCP Mode is OFF. Enable MCP Mode to run MCP tools.";
        return;
    }

    mcpResultPanel.textContent = "Running tool...";

    try {
        const resp = await fetch(`${RENZO_BACKEND_URL}${path}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-MCP-Mode": isMcpEnabled() ? "on" : "off",
            },
            body: JSON.stringify(body),
        });
        const data = await resp.json();
        mcpResultPanel.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
        mcpResultPanel.textContent = `MCP request failed: ${err}`;
    }
}

mcpModeToggle.addEventListener("change", renderMcpState);

mcpCityForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const city_area = document.getElementById("mcp_city_area").value.trim();
    callMcp("/mcp/accommodations-by-city", { city_area });
});

mcpDetailsForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const id = document.getElementById("mcp_accommodation_id").value.trim();
    callMcp(`/mcp/accommodation-details/${id}`, {});
});

renderMcpState();