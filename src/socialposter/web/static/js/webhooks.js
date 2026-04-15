/* Webhooks page logic */
(function () {
  const endpointsList = document.getElementById("endpoints-list");
  const tokensList = document.getElementById("tokens-list");

  // -- Endpoints --
  async function loadEndpoints() {
    const resp = await fetch("/api/webhooks");
    const data = await resp.json();
    if (!data.length) {
      endpointsList.innerHTML = '<p style="color:var(--text-secondary)">No outbound endpoints configured.</p>';
      return;
    }
    endpointsList.innerHTML = data.map(ep => `
      <div class="rule-card" style="margin-bottom:10px;padding:12px;border:1px solid var(--border);border-radius:8px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <strong>${ep.name}</strong>
            <span style="opacity:.6;margin-left:8px;font-size:.85rem">${ep.url}</span>
          </div>
          <div style="display:flex;gap:6px">
            <button class="btn btn-outline btn-sm" onclick="testEndpoint(${ep.id})">Test</button>
            <button class="btn btn-outline btn-sm" onclick="viewLogs(${ep.id})">Logs</button>
            <button class="btn btn-outline btn-sm" onclick="deleteEndpoint(${ep.id})">Delete</button>
          </div>
        </div>
        <div style="margin-top:6px;font-size:.8rem;color:var(--text-secondary)">
          Events: ${ep.events && ep.events.length ? ep.events.join(", ") : "all"}
          &middot; ${ep.is_active ? "Active" : "Inactive"}
        </div>
      </div>
    `).join("");
  }

  window.testEndpoint = async function (id) {
    await fetch(`/api/webhooks/${id}/test`, { method: "POST" });
    alert("Test webhook sent!");
  };

  window.viewLogs = async function (id) {
    const resp = await fetch(`/api/webhooks/${id}/logs`);
    const logs = await resp.json();
    const body = document.getElementById("logs-body");
    if (!logs.length) {
      body.innerHTML = "<p>No delivery logs yet.</p>";
    } else {
      body.innerHTML = logs.map(l => `
        <div style="padding:8px 0;border-bottom:1px solid var(--border)">
          <strong>${l.event}</strong>
          <span style="margin-left:8px">${l.success ? "OK" : "FAIL"}</span>
          <span style="margin-left:8px;opacity:.6">${l.response_status || ""}</span>
          <span style="float:right;font-size:.8rem;opacity:.6">${l.created_at || ""}</span>
          ${l.error_message ? `<div style="color:var(--danger);font-size:.85rem;margin-top:4px">${l.error_message}</div>` : ""}
        </div>
      `).join("");
    }
    document.getElementById("logs-modal").style.display = "flex";
  };

  window.deleteEndpoint = async function (id) {
    if (!confirm("Delete this endpoint?")) return;
    await fetch(`/api/webhooks/${id}`, { method: "DELETE" });
    loadEndpoints();
  };

  // -- Inbound Tokens --
  async function loadTokens() {
    const resp = await fetch("/api/webhooks/inbound-tokens");
    const data = await resp.json();
    if (!data.length) {
      tokensList.innerHTML = '<p style="color:var(--text-secondary)">No inbound tokens created.</p>';
      return;
    }
    tokensList.innerHTML = data.map(t => `
      <div class="rule-card" style="margin-bottom:10px;padding:12px;border:1px solid var(--border);border-radius:8px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <strong>${t.name}</strong>
            <code style="margin-left:8px;font-size:.8rem;background:var(--surface);padding:2px 6px;border-radius:4px">${t.token.slice(0, 12)}...</code>
          </div>
          <button class="btn btn-outline btn-sm" onclick="deleteToken(${t.id})">Revoke</button>
        </div>
        <div style="margin-top:4px;font-size:.8rem;color:var(--text-secondary)">
          Last used: ${t.last_used_at || "never"}
        </div>
      </div>
    `).join("");
  }

  window.deleteToken = async function (id) {
    if (!confirm("Revoke this token?")) return;
    await fetch(`/api/webhooks/inbound-tokens/${id}`, { method: "DELETE" });
    loadTokens();
  };

  // -- Modals --
  document.getElementById("btn-new-endpoint").onclick = () => {
    document.getElementById("endpoint-modal").style.display = "flex";
  };
  document.getElementById("modal-close-endpoint").onclick =
    document.getElementById("btn-cancel-endpoint").onclick = () => {
      document.getElementById("endpoint-modal").style.display = "none";
    };

  document.getElementById("btn-save-endpoint").onclick = async () => {
    const events = [...document.querySelectorAll(".ep-event:checked")].map(e => e.value);
    const resp = await fetch("/api/webhooks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.getElementById("ep-name").value,
        url: document.getElementById("ep-url").value,
        events,
      }),
    });
    const data = await resp.json();
    if (data.ok) {
      document.getElementById("endpoint-modal").style.display = "none";
      loadEndpoints();
    } else {
      alert(data.error || "Failed to create endpoint");
    }
  };

  document.getElementById("btn-new-token").onclick = async () => {
    const name = prompt("Token name:");
    if (!name) return;
    await fetch("/api/webhooks/inbound-tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    loadTokens();
  };

  document.getElementById("logs-modal-close").onclick = () => {
    document.getElementById("logs-modal").style.display = "none";
  };

  // Init
  loadEndpoints();
  loadTokens();
})();
