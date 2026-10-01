/* js/rag_script.js — drives rag_frontend.html
 * Same pattern as mcp_script.js: a toggle to show/hide the panel, a
 * refresh action, and a search action that displays raw JSON output.
 * Wrapped in an IIFE so it can't collide with globals in script.js.
 */
(function () {
  // Relative path: goes through the frontend container's nginx proxy
  // (which needs a /rag/ block forwarding to the backend, same as the
  // existing /api/ and /mcp/ blocks). A hardcoded localhost:5001 would
  // bypass that proxy and break once this is served over Docker.
  const API_BASE = "";

  const toggle = document.getElementById("ragToggle");
  const statusEl = document.getElementById("ragStatus");
  const refreshBtn = document.getElementById("ragRefresh");
  const offNote = document.getElementById("ragOffNote");
  const panel = document.getElementById("ragPanel");
  const questionInput = document.getElementById("ragQuestion");
  const searchBtn = document.getElementById("ragSearchBtn");
  const out = document.getElementById("ragOut");
  const meta = document.getElementById("ragMeta");
  const callLog = document.getElementById("ragLog");

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

  function showOut(text, isError, metaText) {
    out.textContent = text;
    out.className = "mcp-out show" + (isError ? " error" : "");
    meta.textContent = metaText || "";
  }

  function ragHeaders(extra) {
    return Object.assign(
      {
        "Content-Type": "application/json",
        "X-RAG-Mode": toggle.checked ? "on" : "off",
        "Authorization": "Bearer " + (localStorage.getItem("jb_token") || ""),
      },
      extra || {}
    );
  }

  // main.js's initSession() may still be verifying a ?token= from the URL
  // and writing it to localStorage - wait for that to finish so ragHeaders()
  // doesn't read jb_token before it's actually stored.
  async function waitForSession() {
    if (window.jbSessionReady) await window.jbSessionReady;
  }

  // ---------- Refresh corpus ----------
  async function refreshCorpus() {
    refreshBtn.disabled = true;
    refreshBtn.textContent = "Refreshing…";
    setStatus("Refreshing corpus…", "warn");
    try {
      await waitForSession();
      const resp = await fetch(API_BASE + "/rag/refresh", {
        method: "POST",
        headers: ragHeaders(),
        body: JSON.stringify({ caller: "student" }),
      });
      const data = await resp.json();
      if (!resp.ok || data.status !== "success") {
        throw new Error(data.error || "HTTP " + resp.status);
      }
      setStatus("RAG mode on — corpus refreshed (" + data.chunk_count + " chunks)", "ok");
      logCall("Corpus refreshed: " + data.chunk_count + " chunks");
    } catch (err) {
      setStatus("Corpus refresh failed", "err");
      logCall("ERROR refreshing corpus: " + err.message);
    } finally {
      refreshBtn.disabled = false;
      refreshBtn.textContent = "Refresh corpus";
    }
  }

  // ---------- Search (top-5 retrieval) ----------
  async function runSearch() {
    const query = questionInput.value.trim();
    if (!query) {
      showOut("Please enter a question.", true);
      return;
    }

    searchBtn.disabled = true;
    searchBtn.textContent = "Searching…";
    const started = performance.now();
    try {
      await waitForSession();
      const resp = await fetch(API_BASE + "/rag/retrieve", {
        method: "POST",
        headers: ragHeaders(),
        body: JSON.stringify({ query: query, k: 5, caller: "student" }),
      });
      const data = await resp.json();
      const ms = Math.round(performance.now() - started);

      if (!resp.ok || data.status !== "success") {
        throw new Error(data.error || "HTTP " + resp.status);
      }

      showOut(
        JSON.stringify(data.results, null, 2),
        false,
        "HTTP " + resp.status + " · " + ms + " ms · " + data.results.length + " result(s)"
      );
      logCall('Search "' + query + '" → ' + data.results.length + " result(s) (" + ms + " ms)");
    } catch (err) {
      showOut(err.message, true);
      logCall('Search "' + query + '" FAILED: ' + err.message);
    } finally {
      searchBtn.disabled = false;
      searchBtn.textContent = "Search";
    }
  }

  // ---------- Toggle ----------
  function applyMode() {
    if (toggle.checked) {
      offNote.hidden = true;
      panel.hidden = false;
      refreshBtn.hidden = false;
      setStatus("RAG mode on", "ok");
      logCall("RAG mode turned on");
    } else {
      offNote.hidden = false;
      panel.hidden = true;
      refreshBtn.hidden = true;
      setStatus("RAG mode off", "off");
      logCall("RAG mode turned off");
      out.className = "mcp-out";
      out.textContent = "";
      meta.textContent = "";
    }
  }

  toggle.addEventListener("change", applyMode);
  refreshBtn.addEventListener("click", refreshCorpus);
  searchBtn.addEventListener("click", runSearch);
  questionInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") runSearch();
  });
})();