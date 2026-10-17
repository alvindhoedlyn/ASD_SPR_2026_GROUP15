// student-RenzoRobin/frontend/js/multiagent.js
//
// Talks to the backend's /multi-agent/* routes (added in backend/app.py).
// Own constant name on purpose, so it cannot clash with other scripts' globals.
const MULTI_AGENT_BACKEND_URL = "http://localhost:5003";

const maToggle = document.getElementById("multiagent-mode-toggle");
const maState = document.getElementById("multiagent-mode-state");
const maForm = document.getElementById("multiagent-form");
const maSteps = document.getElementById("multiagent-steps");
const maReview = document.getElementById("multiagent-review");
const maDecisionStatus = document.getElementById("multiagent-decision-status");
const maResult = document.getElementById("multiagent-result");

let maWorkflowId = null;

function maEnabled() {
    return maToggle.checked;
}

function renderMaState() {
    if (maEnabled()) {
        maState.textContent = "ON";
        maState.classList.add("feature-on");
        maState.classList.remove("feature-off");
    } else {
        maState.textContent = "OFF";
        maState.classList.add("feature-off");
        maState.classList.remove("feature-on");
        maSteps.textContent = "Multi-Agent Mode is OFF. Enable it to run the agents.";
        maReview.hidden = true;
    }
}

async function maRequest(method, path, body) {
    const resp = await fetch(`${MULTI_AGENT_BACKEND_URL}${path}`, {
        method,
        headers: {
            "Content-Type": "application/json",
            "X-Multi-Agent-Mode": maEnabled() ? "on" : "off",
        },
        body: body ? JSON.stringify(body) : undefined,
    });
    const data = await resp.json();
    return { ok: resp.ok, data };
}

function maAdd(parent, tag, text) {
    const el = document.createElement(tag);
    el.textContent = text;
    parent.appendChild(el);
    return el;
}

function renderWorkflow(record) {
    maSteps.replaceChildren();

    maAdd(maSteps, "p", `Workflow ${record.workflow_id} - ${record.status}`).className = "ma-meta";
    maAdd(maSteps, "p", `Evidence items: ${record.evidence_count} (source: ${record.evidence_source || "unknown"})`).className = "ma-meta";
    if (record.evidence_note) {
        maAdd(maSteps, "p", record.evidence_note).className = "ma-warning";
    }
    if (record.degraded) {
        maAdd(maSteps, "p", "Degraded: the model was unavailable or timed out for at least one step, so a rule-based fallback was used.").className = "ma-warning";
    }

    for (const agent of ["planner", "worker", "reviewer"]) {
        const step = (record.steps || {})[agent];
        if (!step) {
            continue;
        }
        const block = document.createElement("div");
        block.className = "ma-step";

        const heading = maAdd(block, "h3", agent.charAt(0).toUpperCase() + agent.slice(1));
        const badge = maAdd(heading, "span", step.status);
        const modelTag = maAdd(heading, "span", step.model || "");
        modelTag.className = "ma-model";
        badge.className = `ma-badge ma-badge-${step.status}`;

        maAdd(block, "pre", step.output || "");
        const extraChecks = (step.checks || []).filter((check) => !(step.output || "").includes(check));
        if (extraChecks.length) {
            maAdd(block, "p", "Automated checks").className = "ma-checks-title";
            const list = document.createElement("ul");
            for (const check of extraChecks) {
                maAdd(list, "li", check);
            }
            block.appendChild(list);
        }
        maSteps.appendChild(block);
    }
}

maToggle.addEventListener("change", renderMaState);

maForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!maEnabled()) {
        maSteps.textContent = "Multi-Agent Mode is OFF. Enable it to run the agents.";
        return;
    }

    maReview.hidden = true;
    maDecisionStatus.textContent = "";
    maWorkflowId = null;
    maSteps.textContent = "Running Planner, Worker and Reviewer... this can take a minute.";

    try {
        const { ok, data } = await maRequest("POST", "/multi-agent/run", {
            question: document.getElementById("multiagent_question").value.trim(),
            city_area: document.getElementById("multiagent_city").value.trim(),
        });
        maResult.textContent = JSON.stringify(data, null, 2);
        if (!ok) {
            maSteps.textContent = `Error: ${data.error || "request failed"}`;
            return;
        }
        maWorkflowId = data.workflow_id;
        renderWorkflow(data);
        maReview.hidden = false;
        maReview.querySelectorAll("button[data-decision]").forEach((b) => { b.disabled = false; });
    } catch (err) {
        maSteps.textContent = `Multi-Agent request failed: ${err}`;
    }
});

maReview.addEventListener("click", async (e) => {
    const button = e.target.closest("button[data-decision]");
    if (!button || !maWorkflowId) {
        return;
    }
    const decision = button.dataset.decision;
    const corrected = document.getElementById("multiagent-corrected").value.trim();
    if (decision === "correct" && !corrected) {
        maDecisionStatus.textContent = "Type the corrected answer first.";
        return;
    }

    try {
        const { ok, data } = await maRequest("POST", `/multi-agent/${encodeURIComponent(maWorkflowId)}/decision`, {
            decision,
            note: document.getElementById("multiagent-note").value.trim(),
            corrected_output: corrected,
        });
        maResult.textContent = JSON.stringify(data, null, 2);
        if (!ok) {
            maDecisionStatus.textContent = `Error: ${data.error || "request failed"}`;
            return;
        }
        maDecisionStatus.textContent = `Decision recorded: ${data.status}`;
        maReview.querySelectorAll("button[data-decision]").forEach((b) => { b.disabled = true; });
    } catch (err) {
        maDecisionStatus.textContent = `Decision request failed: ${err}`;
    }
});

renderMaState();