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

    // ---------- Elements ----------
    const form = document.getElementById("promptForm");
    const input = document.getElementById("promptInput");
    const sendBtn = document.getElementById("sendBtn");
    const finalLog = document.getElementById("finalLog");
    const finalStatus = document.getElementById("finalStatus");
    const agents = ["planner", "worker", "reviewer"];

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

    function setBusy(busy) {
        sendBtn.disabled = busy;
        input.disabled = busy;
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

        setBusy(true);
        finalStatus.textContent = "Running…";
        setLog(finalLog, "Waiting for the agents to finish…", { empty: true });
        resetLogs();

        let data;
        try {
            const res = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: prompt })
            });
            if (!res.ok) throw new Error("Server responded with " + res.status);
            data = await res.json();
            finalStatus.textContent = "Done";
        } catch (err) {
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

        setBusy(false);
        input.focus();
    });
})();