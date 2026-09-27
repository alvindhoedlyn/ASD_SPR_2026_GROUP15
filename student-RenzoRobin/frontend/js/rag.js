// student-RenzoRobin/frontend/js/rag.js
//
// Talks to the backend's /rag/* routes (added in backend/app.py).
// Hardcoded on purpose, same reasoning as mcp.js: don't rely on any
// global window.BACKEND_URL, since the shared frontend's main.js may
// already define that name for something else.
const RAG_BACKEND_URL = "http://localhost:5003";

const ragModeToggle = document.getElementById("rag-mode-toggle");
const ragModeState = document.getElementById("rag-mode-state");
const ragResultPanel = document.getElementById("rag-result");
const ragAnswerBox = document.getElementById("rag-answer-box");
const ragRefreshForm = document.getElementById("rag-refresh-form");
const ragAnswerForm = document.getElementById("rag-answer-form");

function isRagEnabled() {
    return ragModeToggle.checked;
}

function renderRagState() {
    if (isRagEnabled()) {
        ragModeState.textContent = "ON";
        ragModeState.classList.add("feature-on");
        ragModeState.classList.remove("feature-off");
    } else {
        ragModeState.textContent = "OFF";
        ragModeState.classList.add("feature-off");
        ragModeState.classList.remove("feature-on");
        ragResultPanel.textContent = "RAG Mode is OFF. Enable RAG Mode to run RAG tools.";
        ragAnswerBox.textContent = "RAG Mode is OFF.";
    }
}

async function callRag(path, body) {
    if (!isRagEnabled()) {
        ragResultPanel.textContent = "RAG Mode is OFF. Enable RAG Mode to run RAG tools.";
        return null;
    }

    ragResultPanel.textContent = "Running...";

    try {
        const resp = await fetch(`${RAG_BACKEND_URL}${path}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-RAG-Mode": isRagEnabled() ? "on" : "off",
            },
            body: JSON.stringify(body),
        });
        const data = await resp.json();
        ragResultPanel.textContent = JSON.stringify(data, null, 2);
        return data;
    } catch (err) {
        ragResultPanel.textContent = `RAG request failed: ${err}`;
        return null;
    }
}

function renderAnswer(data) {
    if (!data) return;

    if (data.status === "insufficient_context") {
        ragAnswerBox.textContent = "Insufficient context available to answer this question.";
        return;
    }

    if (data.status !== "success") {
        ragAnswerBox.textContent = `Error: ${data.error || "unknown error"}`;
        return;
    }

    const citations = (data.citations || [])
        .map((c) => c.source_id || c.chunk_id)
        .join(", ");

    ragAnswerBox.innerHTML = `
    <p>${data.answer}</p>
    <p><strong>Confidence:</strong> ${data.confidence_category}</p>
    <p><strong>Sources:</strong> ${citations || "none"}</p>
  `;
}

ragModeToggle.addEventListener("change", renderRagState);

ragRefreshForm.addEventListener("submit", (e) => {
    e.preventDefault();
    callRag("/rag/refresh", {});
});

ragAnswerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = document.getElementById("rag_question").value.trim();
    const data = await callRag("/rag/answer", { query, k: 5 });
    renderAnswer(data);
});

renderRagState();