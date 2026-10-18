(function () {
    // ---------- Configuration ----------
    // Point this at your multi-agent server. Expected request:  POST { "prompt": "..." }
    // Expected JSON response:
    //   { "final": "...", "planner": "...", "worker": "...", "reviewer": "..." }
    // Each log field may be a string or an array of strings (one entry per line).
    const API_URL = "/api/multi-agent";
 
    // If the request fails (e.g. server not running), show a clearly labelled
    // placeholder result so the layout can still be tested.
    const USE_DEMO_FALLBACK = true;

    // Where the human decision is sent. Expected request:
    //   POST { "decision": "approve" | "partial" | "reject", "feedback": "...", "prompt": "..." }
    // Any 2xx response counts as success.
    const APPROVAL_URL = "/api/multi-agent/approval";
 
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
    const approvalFeedback = document.getElementById("approvalFeedback");
    const approvalStatus = document.getElementById("approvalStatus");
    const approvalBtns = document.querySelectorAll(".approval-btn");
 
    // ---------- Server on/off state ----------
    // Starts OFF. While off, nothing is ever sent to the backend.
    let serverOn = true;
    let busy = false;
    let controller = null;   // lets us cancel an in-flight request when switched off

    // Approval state: only usable once a result is on screen, and once per result.
    let hasResult = false;
    let decided = false;
    let approvalBusy = false;
    let approvalController = null;
    let lastPrompt = "";
 
    function applyServerState() {
        serverToggle.checked = serverOn;
        serverToggle.setAttribute("aria-checked", String(serverOn));
        serverStatus.textContent = serverOn ? "Server on" : "Server off";
        serverStatus.className = "mcp-status " + (serverOn ? "ok" : "off");
        sendBtn.disabled = !serverOn || busy || approvalBusy;
        input.disabled = busy;
        testBtns.forEach(function (b) { b.disabled = !serverOn; });
        input.placeholder = serverOn
            ? "Enter a prompt for the multi-agent workflow…"
            : "Server is off — turn it on to send prompts";
        applyApprovalState();
    }
 
    serverToggle.addEventListener("change", function () {
        serverOn = serverToggle.checked;
        if (!serverOn && controller) {
            controller.abort();   // drop any request already in flight
        }
        if (!serverOn && approvalController) {
            approvalController.abort();   // and any approval being sent
        }
        applyServerState();
        refreshApprovalStatus();
        if (!serverOn) {
            finalStatus.textContent = "Server off";
        } else if (!busy) {
            finalStatus.textContent = "Idle";
        }
    });
 
    // ---------- Test prompt buttons ----------
    document.querySelectorAll(".test-prompt").forEach(function (btn) {
        btn.addEventListener("click", function () {
            input.value = btn.dataset.prompt;
            input.focus();
        });
    });
 
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
 
    function setAgentState(name, state) {
        const dot = document.getElementById("dot-" + name);
        dot.className = "agent-dot" + (state ? " " + state : "");
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
 
    function demoResult(prompt) {
        return {
            final: "[DEMO — server unreachable]\nPrompt received:\n" + prompt + "\n\nConnect API_URL to your multi-agent server to see real output.",
            planner: "[DEMO] Break the prompt into sub-tasks.",
            worker: "[DEMO] Execute each sub-task and collect results.",
            reviewer: "[DEMO] Check the combined results for quality."
        };
    }
 
    // ---------- Submit ----------
    form.addEventListener("submit", async function (e) {
        e.preventDefault();
        const prompt = input.value.trim();
        if (!prompt) return;
 
        // Hard block: with the server off, no request leaves the page.
        if (!serverOn) {
            finalStatus.textContent = "Server off";
            return;
        }
 
        // New run: clear any previous approval
        lastPrompt = prompt;
        hasResult = false;
        decided = false;
        approvalFeedback.value = "";
        approvalFeedback.classList.remove("invalid");
        refreshApprovalStatus();

        controller = new AbortController();
        setBusy(true);
        finalStatus.textContent = "Running…";
        setLog(finalLog, "Waiting for the agents to finish…", { empty: true });
        resetLogs();
 
        let data;
        try {
            const res = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: prompt }),
                signal: controller.signal
            });
            if (!res.ok) throw new Error("Server responded with " + res.status);
            data = await res.json();
            finalStatus.textContent = "Done";
        } catch (err) {
            // Switched off mid-request: cancel quietly, no demo fallback.
            if (err.name === "AbortError") {
                finalStatus.textContent = "Cancelled (server off)";
                setLog(finalLog, "Request cancelled because the server was switched off.", { empty: true });
                agents.forEach(function (a) {
                    setLog(document.getElementById("log-" + a), "Cancelled.", { empty: true });
                    setAgentState(a, "");
                });
                controller = null;
                setBusy(false);
                return;
            }
            if (USE_DEMO_FALLBACK) {
                data = demoResult(prompt);
                finalStatus.textContent = "Demo (" + err.message + ")";
            } else {
                finalStatus.textContent = "Error";
                setLog(finalLog, "Request failed: " + err.message, { error: true });
                agents.forEach(function (a) {
                    setLog(document.getElementById("log-" + a), "No output.", { empty: true });
                    setAgentState(a, "error");
                });
                setBusy(false);
                return;
            }
        }
 
        setLog(finalLog, toText(data.final) || "(no final output returned)", { empty: !data.final });
        agents.forEach(function (a) {
            const text = toText(data[a]);
            setLog(document.getElementById("log-" + a), text || "No output returned.", { empty: !text });
            setAgentState(a, "done");
        });
 
        controller = null;
        hasResult = true;   // unlocks the approval section
        setBusy(false);
        refreshApprovalStatus();
        input.focus();
    });
 
    // ---------- Human approval ----------
    const DECISIONS = {
        approve: { text: "Approved", cls: "ok" },
        partial: { text: "Partially approved", cls: "warn" },
        reject:  { text: "Rejected", cls: "err" }
    };

    function setApprovalStatus(text, cls) {
        approvalStatus.textContent = text;
        approvalStatus.className = "approval-status" + (cls ? " " + cls : "");
    }

    // Textbox and buttons are only live when a result exists, the server is on,
    // no decision has been made yet, and nothing is being sent.
    function applyApprovalState() {
        const active = serverOn && hasResult && !decided && !approvalBusy;
        approvalFeedback.disabled = !active;
        approvalBtns.forEach(function (b) { b.disabled = !active; });
    }

    // Idle status text; leaves a final decision or an in-flight send alone.
    function refreshApprovalStatus() {
        if (decided || approvalBusy) return;
        if (!serverOn) setApprovalStatus("Server off", "");
        else if (!hasResult) setApprovalStatus("Awaiting output", "");
        else setApprovalStatus("Awaiting your decision", "");
    }

    approvalFeedback.addEventListener("input", function () {
        approvalFeedback.classList.remove("invalid");
    });

    approvalBtns.forEach(function (btn) {
        btn.addEventListener("click", async function () {
            const decision = btn.dataset.decision;
            const feedback = approvalFeedback.value.trim();

            // Hard block: with the server off, nothing leaves the page.
            if (!serverOn || !hasResult || decided || approvalBusy) return;

            // Partial approval and rejection need an explanation.
            if (decision !== "approve" && !feedback) {
                approvalFeedback.classList.add("invalid");
                setApprovalStatus("Feedback required", "err");
                approvalFeedback.focus();
                return;
            }

            approvalBusy = true;
            approvalController = new AbortController();
            applyServerState();
            setApprovalStatus("Sending…", "");

            try {
                const res = await fetch(APPROVAL_URL, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ decision: decision, feedback: feedback, prompt: lastPrompt }),
                    signal: approvalController.signal
                });
                if (!res.ok) throw new Error("Server responded with " + res.status);
                decided = true;
                setApprovalStatus(DECISIONS[decision].text, DECISIONS[decision].cls);
            } catch (err) {
                if (err.name === "AbortError") {
                    setApprovalStatus("Cancelled (server off)", "err");
                } else {
                    setApprovalStatus("Failed: " + err.message, "err");
                }
            } finally {
                approvalController = null;
                approvalBusy = false;
                applyServerState();
            }
        });
    });

    // Initial render
    applyServerState();
    finalStatus.textContent = serverOn ? "Idle" : "Server off";
    refreshApprovalStatus();
})();