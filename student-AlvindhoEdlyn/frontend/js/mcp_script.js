/* js/mcp_script.js — drives mcp_frontend.html
 * Loads the tool list from the backend, renders one form per tool,
 * runs tools one at a time and logs every call.
 * Wrapped in an IIFE so it can't collide with globals in script.js.
 */
(function () {
  // Relative path: goes through the frontend container's nginx proxy
  // (which forwards /mcp/ to the backend). A hardcoded localhost:5001
  // bypasses that proxy and breaks once this is served over Docker.
  const API_BASE = "";

  const toggle = document.getElementById("mcpToggle");
  const statusEl = document.getElementById("mcpStatus");
  const refreshBtn = document.getElementById("mcpRefresh");
  const offNote = document.getElementById("mcpOffNote");
  const panel = document.getElementById("mcpPanel");
  const toolList = document.getElementById("toolList");
  const callLog = document.getElementById("callLog");

  // Populated once per loadTools() call, used to render journey_id as a
  // dropdown of names instead of a raw numeric field the user has to guess.
  let availableJourneys = [];

  function setStatus(text, cls) {
    statusEl.textContent = text;
    statusEl.className = "mcp-status " + cls;
  }

  function logCall(text) {
    if (callLog.children.length === 1 && callLog.firstChild.textContent === "No calls yet.") {
      callLog.innerHTML = "";
    }
    const li = document.createElement("li");
    li.textContent = new Date().toLocaleTimeString() + "  " + text;
    callLog.prepend(li);
  }

  function mcpHeaders() {
    return {
      "Content-Type": "application/json",
      "X-MCP-Mode": toggle.checked ? "on" : "off",
      "Authorization": "Bearer " + (localStorage.getItem("jb_token") || ""),
    };
  }

  // ---------- Load tools ----------
  async function loadTools() {
    setStatus("Loading tools…", "warn");
    toolList.innerHTML = "";
    try {
      // main.js's initSession() may still be verifying a ?token= from the
      // URL and writing it to localStorage - wait for that to finish so
      // mcpHeaders() doesn't read jb_token before it's actually stored.
      if (window.jbSessionReady) await window.jbSessionReady;

      // Fetch journey names up front so any journey_id field can render as
      // a dropdown of labels rather than asking the user to type a raw ID.
      // /api/journeys is a public proxy route - no MCP mode or token needed.
      try {
        const journeysResp = await fetch("/api/journeys");
        availableJourneys = journeysResp.ok ? await journeysResp.json() : [];
      } catch (_) {
        availableJourneys = [];
      }

      const resp = await fetch(API_BASE + "/mcp/tools", { headers: mcpHeaders() });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "HTTP " + resp.status);

      data.tools.forEach((tool) => toolList.appendChild(renderTool(tool)));
      setStatus("MCP mode on — " + data.tools.length + " tools", "ok");
      logCall("Loaded " + data.tools.length + " tools");
    } catch (err) {
      setStatus("Could not load tools", "err");
      logCall("ERROR loading tools: " + err.message);
    }
  }

  // ---------- Render one tool card ----------
  function renderTool(tool) {
    const card = document.createElement("div");
    card.className = "mcp-tool";

    const h2 = document.createElement("h2");
    h2.textContent = tool.name;
    const desc = document.createElement("p");
    desc.className = "mcp-desc";
    desc.textContent = tool.description;

    const fields = document.createElement("div");
    fields.className = "mcp-fields";
    const inputs = {};

    tool.inputs.forEach((f) => {
      const label = document.createElement("label");
      label.className = "mcp-field";
      label.textContent = f.name + (f.required ? " *" : "");

      let input;
      if (f.name === "journey_id") {
        // Dropdown of journey names instead of a raw ID the user has to
        // look up elsewhere - same source and labelling as the main
        // Itinerary page's journey picker.
        input = document.createElement("select");
        if (availableJourneys.length === 0) {
          const opt = document.createElement("option");
          opt.textContent = "No journeys available";
          opt.disabled = true;
          input.appendChild(opt);
        } else {
          availableJourneys.forEach((j) => {
            const opt = document.createElement("option");
            opt.value = j.journey_id;
            opt.textContent = `${j.label} (${j.locations.length} locations)`;
            input.appendChild(opt);
          });
        }
      } else {
        input = document.createElement("input");
        input.type = f.type === "number" ? "number" : "text";
        if (f.default !== undefined) input.value = f.default;
      }

      inputs[f.name] = input;
      label.appendChild(input);
      fields.appendChild(label);
    });

    const runBtn = document.createElement("button");
    runBtn.type = "button";
    runBtn.className = "btn mcp-run";
    runBtn.textContent = "Run tool";

    const out = document.createElement("pre");
    out.className = "mcp-out";
    const meta = document.createElement("div");
    meta.className = "mcp-meta";

    runBtn.addEventListener("click", async () => {
      const payload = {};
      for (const f of tool.inputs) {
        const raw = inputs[f.name].value.trim();
        if (f.required && raw === "") {
          showOut(out, meta, "Missing required field: " + f.name, true);
          return;
        }
        if (raw !== "") payload[f.name] = f.type === "number" ? Number(raw) : raw;
      }

      runBtn.disabled = true;
      runBtn.textContent = "Running…";
      const started = performance.now();
      try {
        const resp = await fetch(API_BASE + tool.endpoint, {
          method: "POST",
          headers: mcpHeaders(),
          body: JSON.stringify(payload),
        });
        const data = await resp.json();
        const ms = Math.round(performance.now() - started);
        showOut(out, meta, JSON.stringify(data, null, 2), !resp.ok, "HTTP " + resp.status + " · " + ms + " ms");
        logCall(tool.name + " " + JSON.stringify(payload) + " → " + resp.status + " (" + ms + " ms)");
      } catch (err) {
        showOut(out, meta, err.message, true);
        logCall(tool.name + " FAILED: " + err.message);
      } finally {
        runBtn.disabled = false;
        runBtn.textContent = "Run tool";
      }
    });

    card.append(h2, desc, fields, runBtn, out, meta);
    return card;
  }

  function showOut(out, meta, text, isError, metaText) {
    out.textContent = text;
    out.className = "mcp-out show" + (isError ? " error" : "");
    meta.textContent = metaText || "";
  }

  // ---------- Toggle ----------
  function applyMode() {
    if (toggle.checked) {
      offNote.hidden = true;
      panel.hidden = false;
      refreshBtn.hidden = false;
      loadTools();
    } else {
      offNote.hidden = false;
      panel.hidden = true;
      refreshBtn.hidden = true;
      toolList.innerHTML = "";
      setStatus("MCP mode off", "off");
      logCall("MCP mode turned off");
    }
  }

  toggle.addEventListener("change", applyMode);
  refreshBtn.addEventListener("click", loadTools);
})();