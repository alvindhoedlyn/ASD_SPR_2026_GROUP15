(function () {
    "use strict";

    // ---------- Configuration ----------
    // Backend routes (same origin as the page; nginx must proxy /multi-agent/ to the backend).
    //   POST WORKFLOW_URL                      { question }          -> workflow record
    //   POST WORKFLOW_URL/<id>/decision        { decision, note }    -> updated record
    const WORKFLOW_URL = "/multi-agent/workflow";

    // The agents run three local models one after another, so a run can take minutes.
    // Keep this above the backend's own wait (600 s).
    const REQUEST_TIMEOUT_MS = 11 * 60 * 1000;

    // Where the session token is kept (written by main.js once the session is verified).
    // The backend requires "Authorization: Bearer <token>", same as script.js's authHeaders().
    const TOKEN_KEY = "jb_token";

    // Remembers a workflow that is waiting for a human decision, so a refresh doesn't lose it.
    const PENDING_KEY = "mas_pending_workflow";

    // Button -> decision name used by the multi-agent server.
    const SERVER_DECISION = { approve: "accept", partial: "partial", reject: "reject" };

    // ---------- Elements ----------
    const form = document.getElementById("promptForm");
    const input = document.getElementById("promptInput");
    const sendBtn = document.getElementById("sendBtn");
    const finalLog = document.getElementById("finalLog");
    const finalStatus = document.getElementById("finalStatus");
    const agents = ["planner", "worker", "reviewer"];
    const serverToggle = document.getElementById("serverToggle");
    const serverStatus = document.getElementById("serverStatus");
    const testBtns = document.querySelectorAll(".test-prompt");
    const approvalStatus = document.getElementById("approvalStatus");
    const approvalFeedback = document.getElementById("approvalFeedback");
    const approvalBtns = document.querySelectorAll(".approval-btn");

    // ---------- State ----------
    // Starts OFF. While off, nothing is ever sent to the backend.
    let serverOn = false;
    let busy = false;          // a workflow request is in flight
    let deciding = false;      // a decision request is in flight
    let pending = null;        // workflow record waiting for a human decision
    let controller = null;     // lets us cancel an in-flight request
    let timedOut = false;

    function applyServerState() {
        const locked = busy || !!pending;
        serverToggle.checked = serverOn;
        serverToggle.setAttribute("aria-checked", String(serverOn));
        serverStatus.textContent = serverOn ? "Server on" : "Server off";
        serverStatus.className = "mcp-status " + (serverOn ? "ok" : "off");
        sendBtn.disabled = !serverOn || locked;
        input.disabled = locked;
        testBtns.forEach(function (b) { b.disabled = !serverOn || locked; });
        input.placeholder = serverOn
            ? "Enter a prompt for the multi-agent workflow…"
            : "Server is off — turn it on to send prompts";
    }

    function setApprovalControls(enabled) {
        approvalFeedback.disabled = !enabled;
        approvalBtns.forEach(function (b) { b.disabled = !enabled; });
    }

    // ---------- Helpers ----------
    function toText(v) {
        if (Array.isArray(v)) return v.join("\n");
        if (v == null) return "";
        return typeof v === "string" ? v : JSON.stringify(v, null, 2);
    }

    function setLog(el, text, opts) {
        opts = opts || {};
        el.textContent = text;
        el.classList.toggle("empty", !!opts.empty);
        el.classList.toggle("error", !!opts.error);
    }

    function setAgentState(name, state, title) {
        const dot = document.getElementById("dot-" + name);
        dot.className = "agent-dot" + (state ? " " + state : "");
        if (title) dot.title = title; else dot.removeAttribute("title");
    }

    function setBusy(state) {
        busy = state;
        applyServerState();
    }

    function resetLogs() {
        agents.forEach(function (a) {
            setLog(document.getElementById("log-" + a), "Waiting…", { empty: true });
            setAgentState(a, "running");
        });
    }

    function clearAgentLogs(text, state) {
        agents.forEach(function (a) {
            setLog(document.getElementById("log-" + a), text, { empty: true });
            setAgentState(a, state || "");
        });
    }

    function resetApproval(statusText) {
        approvalFeedback.value = "";
        setApprovalControls(false);
        approvalStatus.textContent = statusText || "Awaiting output";
    }

    function getToken() {
        try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
    }

    // main.js may still be verifying a ?token= from the URL and writing it to localStorage.
    // Wait for that before reading the token, exactly as script.js's init() does.
    async function sessionReady() {
        if (window.jbSessionReady) {
            try { await window.jbSessionReady; } catch (e) { /* no session: the request will 401 */ }
        }
    }

    function savePending(id) {
        try { sessionStorage.setItem(PENDING_KEY, id); } catch (e) { /* optional convenience */ }
    }

    function savedPending() {
        try { return sessionStorage.getItem(PENDING_KEY); } catch (e) { return null; }
    }

    function clearPending() {
        try { sessionStorage.removeItem(PENDING_KEY); } catch (e) { /* ignore */ }
    }

    async function api(method, url, payload, signal) {
        await sessionReady();
        const headers = {
            "Content-Type": "application/json",
            "X-Multi-Agent-Mode": serverOn ? "on" : "off"
        };
        const token = getToken();
        if (token) headers["Authorization"] = "Bearer " + token;

        const res = await fetch(url, {
            method: method,
            headers: headers,
            body: payload ? JSON.stringify(payload) : undefined,
            signal: signal
        });
        let body = null;
        try { body = await res.json(); } catch (e) { /* non-JSON error page */ }
        return { ok: res.ok, status: res.status, body: body };
    }

    function errorMessage(r) {
        if (r.status === 401) return "Please log in again (your session is missing or has expired).";
        if (r.body && r.body.error) return r.body.error;
        return "Server responded with " + r.status;
    }

    // ---------- Rendering a workflow record ----------
    function stepText(step) {
        if (!step) return "";
        let text = toText(step.output);
        if (step.status === "fallback") {
            text = "[Fallback answer" + (step.error ? " — " + step.error : "") + "]\n" + text;
        }
        return text;
    }

    function workerText(record) {
        let text = stepText(record.steps.worker);
        const missing = record.locations_without_weather || [];
        if (missing.length) {
            text += "\n\nNote: weather unknown for " + missing.join(", ") + ".";
        }
        return text;
    }

    function reviewerText(step) {
        if (!step) return "";
        let text = stepText(step);
        if (step.checks && step.checks.length) {
            text += "\n\nAutomated checks:\n- " + step.checks.join("\n- ");
        }
        if (step.verified && step.verified.length) {
            text += "\n\nVerified by rules:\n- " + step.verified.join("\n- ");
        }
        return text;
    }

    function renderRecord(record) {
        const steps = record.steps || {};
        const texts = {
            planner: stepText(steps.planner),
            worker: workerText(record),
            reviewer: reviewerText(steps.reviewer)
        };
        agents.forEach(function (a) {
            const step = steps[a];
            const text = texts[a];
            setLog(document.getElementById("log-" + a), text || "No output returned.", { empty: !text });
            if (step && step.status === "fallback") {
                setAgentState(a, "error", "This step used its fallback answer");
            } else {
                setAgentState(a, "done");
            }
        });
    }

    // The agents have finished; nothing is final until a human decides.
    function awaitApproval(record) {
        pending = record;
        savePending(record.workflow_id);
        setLog(finalLog, "Awaiting human approval.\nReview the agent logs below, then choose a decision.", { empty: true });
        finalStatus.textContent = "Awaiting approval";
        approvalFeedback.value = "";
        setApprovalControls(true);
        approvalStatus.textContent = "Awaiting your decision";
        applyServerState();
    }

    function finishApproval(decision, note) {
        const workerOutput = toText(pending.steps && pending.steps.worker && pending.steps.worker.output);
        let text, label;

        if (decision === "approve") {
            label = "Approved";
            text = workerOutput || "(no worker output)";
        } else if (decision === "partial") {
            label = "Partially approved";
            text = (workerOutput || "(no worker output)") + "\n\nReviewer feedback (partially approved):\n" + note;
        } else {
            label = "Rejected";
            text = "Rejected. No answer was accepted.\n\nFeedback:\n" + note;
        }

        setLog(finalLog, text, { error: decision === "reject" });
        finalStatus.textContent = label;
        resetApproval(label);
        pending = null;
        clearPending();
        applyServerState();
        input.focus();
    }

    // ---------- Human decision ----------
    async function submitDecision(decision) {
        if (!pending || deciding) return;

        if (!serverOn) {
            approvalStatus.textContent = "Server is off — turn it on to submit your decision";
            return;
        }

        const note = approvalFeedback.value.trim();
        if ((decision === "partial" || decision === "reject") && !note) {
            approvalStatus.textContent = "Feedback is required for Partially Approve and Reject";
            approvalFeedback.focus();
            return;
        }

        deciding = true;
        setApprovalControls(false);
        approvalStatus.textContent = "Submitting…";

        try {
            const url = WORKFLOW_URL + "/" + encodeURIComponent(pending.workflow_id) + "/decision";
            const r = await api("POST", url, { decision: SERVER_DECISION[decision], note: note });

            if (r.ok) {
                finishApproval(decision, note);
            } else if (r.status === 409) {
                // Already decided elsewhere (for example in another tab).
                pending = null;
                clearPending();
                finalStatus.textContent = "Already decided";
                resetApproval("This workflow already has a decision");
                applyServerState();
            } else {
                approvalStatus.textContent = "Could not submit: " + errorMessage(r);
                setApprovalControls(true);
            }
        } catch (err) {
            approvalStatus.textContent = "Could not submit: " + err.message;
            setApprovalControls(true);
        }

        deciding = false;
    }

    approvalBtns.forEach(function (btn) {
        btn.addEventListener("click", function () {
            submitDecision(btn.dataset.decision);
        });
    });

    // ---------- Restore a workflow that was waiting for a decision ----------
    async function restorePending() {
        const id = savedPending();
        if (!id || pending || busy || !serverOn) return;

        setBusy(true);
        finalStatus.textContent = "Restoring pending workflow…";
        try {
            const r = await api("GET", WORKFLOW_URL + "/" + encodeURIComponent(id));
            if (r.ok && r.body && r.body.status === "pending_human_review") {
                input.value = r.body.user_request || "";
                renderRecord(r.body);
                setBusy(false);
                awaitApproval(r.body);
                return;
            }
            clearPending();   // decided, deleted or not ours: nothing to restore
            finalStatus.textContent = "Idle";
            resetApproval();
        } catch (err) {
            finalStatus.textContent = "Could not restore pending workflow";
        }
        setBusy(false);
    }

    // ---------- Server on/off ----------
    serverToggle.addEventListener("change", function () {
        serverOn = serverToggle.checked;
        if (!serverOn && controller) {
            controller.abort();   // drop any request already in flight
        }
        applyServerState();
        if (!serverOn) {
            finalStatus.textContent = "Server off";
        } else if (pending) {
            finalStatus.textContent = "Awaiting approval";
        } else if (!busy) {
            finalStatus.textContent = "Idle";
            restorePending();
        }
    });

    // ---------- Test prompt buttons ----------
    document.querySelectorAll(".test-prompt").forEach(function (btn) {
        btn.addEventListener("click", function () {
            input.value = btn.dataset.prompt;
            input.focus();
        });
    });

    // ---------- Submit ----------
    form.addEventListener("submit", async function (e) {
        e.preventDefault();
        const prompt = input.value.trim();
        if (!prompt || pending) return;

        // Hard block: with the server off, no request leaves the page.
        if (!serverOn) {
            finalStatus.textContent = "Server off";
            return;
        }

        controller = new AbortController();
        timedOut = false;
        const timer = setTimeout(function () { timedOut = true; controller.abort(); }, REQUEST_TIMEOUT_MS);
        setBusy(true);
        finalStatus.textContent = "Running…";
        setLog(finalLog, "Waiting for the agents to finish…", { empty: true });
        resetLogs();
        resetApproval();

        let r;
        try {
            r = await api("POST", WORKFLOW_URL, { question: prompt }, controller.signal);
        } catch (err) {
            clearTimeout(timer);
            controller = null;
            if (err.name === "AbortError" && !timedOut) {
                // Switched off mid-request: cancel quietly.
                finalStatus.textContent = "Cancelled (server off)";
                setLog(finalLog, "Request cancelled because the server was switched off.", { empty: true });
                clearAgentLogs("Cancelled.");
            } else {
                const msg = timedOut ? "The agents took too long to answer." : err.message;
                finalStatus.textContent = "Error";
                setLog(finalLog, "Request failed: " + msg, { error: true });
                clearAgentLogs("No output.", "error");
            }
            setBusy(false);
            return;
        }
        clearTimeout(timer);
        controller = null;

        const body = r.body || {};

        if (r.status === 422 && body.status === "insufficient_context") {
            // The prompt did not name a journey or place the backend knows.
            const journeys = body.available_journeys || [];
            let text = body.error || "Not enough context to answer.";
            if (journeys.length) {
                text += "\n\nTry mentioning one of these journeys or a place on it:\n- " + journeys.join("\n- ");
            }
            finalStatus.textContent = "Insufficient context";
            setLog(finalLog, text);
            clearAgentLogs("Not run.");
        } else if (!r.ok) {
            finalStatus.textContent = "Error";
            setLog(finalLog, "Request failed: " + errorMessage(r), { error: true });
            clearAgentLogs("No output.", "error");
        } else {
            renderRecord(body);
            setBusy(false);
            awaitApproval(body);
            return;
        }

        setBusy(false);
        input.focus();
    });

    // ---------- Initial render (server starts off) ----------
    applyServerState();
    resetApproval(savedPending() ? "A workflow is waiting for your decision — turn the server on to restore it" : "Awaiting output");
    finalStatus.textContent = "Server off";
})();