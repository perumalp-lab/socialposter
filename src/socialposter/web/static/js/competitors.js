/* Competitors page logic */
(function () {
  const listEl = document.getElementById("competitors-list");
  const analysisEl = document.getElementById("analysis-output");
  const comparisonEl = document.getElementById("comparison-data");

  async function loadCompetitors() {
    const resp = await fetch("/api/competitors");
    const data = await resp.json();
    if (!data.length) {
      listEl.innerHTML = '<p style="color:var(--text-secondary)">No competitors tracked yet.</p>';
      return;
    }
    listEl.innerHTML = data.map(c => `
      <div class="rule-card" style="margin-bottom:10px;padding:12px;border:1px solid var(--border);border-radius:8px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <strong>@${c.handle}</strong>
            <span style="opacity:.6;margin-left:8px;font-size:.85rem">${c.platform}</span>
            ${c.display_name && c.display_name !== c.handle ? `<span style="margin-left:8px">${c.display_name}</span>` : ""}
          </div>
          <div style="display:flex;gap:6px">
            <button class="btn btn-outline btn-sm" onclick="fetchPosts(${c.id})">Fetch</button>
            <button class="btn btn-outline btn-sm" onclick="viewPosts(${c.id})">Posts</button>
            <button class="btn btn-outline btn-sm" onclick="deleteCompetitor(${c.id})">Remove</button>
          </div>
        </div>
        <div style="margin-top:4px;font-size:.8rem;color:var(--text-secondary)">
          Last fetched: ${c.last_fetched_at || "never"}
        </div>
      </div>
    `).join("");
  }

  window.fetchPosts = async function (id) {
    const resp = await fetch(`/api/competitors/${id}/fetch`, { method: "POST" });
    const data = await resp.json();
    if (data.ok) {
      alert(`Fetched ${data.new_posts} new posts`);
      loadCompetitors();
    } else {
      alert(data.error || "Fetch failed");
    }
  };

  window.viewPosts = async function (id) {
    const resp = await fetch(`/api/competitors/${id}/posts`);
    const posts = await resp.json();
    const body = document.getElementById("posts-body");
    if (!posts.length) {
      body.innerHTML = "<p>No posts fetched yet.</p>";
    } else {
      body.innerHTML = posts.map(p => `
        <div style="padding:10px 0;border-bottom:1px solid var(--border)">
          <p style="margin:0 0 6px">${p.text.slice(0, 200)}${p.text.length > 200 ? "..." : ""}</p>
          <div style="font-size:.8rem;color:var(--text-secondary)">
            ${p.likes} likes &middot; ${p.comments} comments &middot; ${p.shares} shares
            ${p.views ? ` &middot; ${p.views} views` : ""}
            <span style="float:right">${p.posted_at || ""}</span>
          </div>
        </div>
      `).join("");
    }
    document.getElementById("posts-modal").style.display = "flex";
  };

  window.deleteCompetitor = async function (id) {
    if (!confirm("Remove this competitor?")) return;
    await fetch(`/api/competitors/${id}`, { method: "DELETE" });
    loadCompetitors();
  };

  // -- AI Analysis --
  document.getElementById("btn-run-analysis").onclick = async () => {
    analysisEl.textContent = "Generating analysis...";
    const resp = await fetch("/api/competitors/analysis");
    const data = await resp.json();
    analysisEl.textContent = data.analysis || data.error || "No analysis available.";
  };

  // -- Engagement Comparison --
  async function loadComparison() {
    const resp = await fetch("/api/competitors/compare");
    const data = await resp.json();
    if (!data.competitors || !data.competitors.length) {
      comparisonEl.innerHTML = '<p style="color:var(--text-secondary)">Track competitors to see engagement comparison.</p>';
      return;
    }
    let html = `
      <table style="width:100%;border-collapse:collapse;font-size:.9rem">
        <tr style="border-bottom:2px solid var(--border)">
          <th style="text-align:left;padding:6px">Account</th>
          <th style="text-align:right;padding:6px">Posts</th>
          <th style="text-align:right;padding:6px">Likes</th>
          <th style="text-align:right;padding:6px">Comments</th>
          <th style="text-align:right;padding:6px">Shares</th>
        </tr>
        <tr style="border-bottom:1px solid var(--border);background:var(--surface)">
          <td style="padding:6px"><strong>You</strong></td>
          <td style="text-align:right;padding:6px">${data.user.posts}</td>
          <td style="text-align:right;padding:6px">${data.user.likes}</td>
          <td style="text-align:right;padding:6px">${data.user.comments}</td>
          <td style="text-align:right;padding:6px">${data.user.shares}</td>
        </tr>
    `;
    data.competitors.forEach(c => {
      html += `
        <tr style="border-bottom:1px solid var(--border)">
          <td style="padding:6px">@${c.handle} <span style="opacity:.6">(${c.platform})</span></td>
          <td style="text-align:right;padding:6px">${c.posts}</td>
          <td style="text-align:right;padding:6px">${c.likes}</td>
          <td style="text-align:right;padding:6px">${c.comments}</td>
          <td style="text-align:right;padding:6px">${c.shares}</td>
        </tr>
      `;
    });
    html += "</table>";
    comparisonEl.innerHTML = html;
  }

  // -- Modals --
  document.getElementById("btn-add-competitor").onclick = () => {
    document.getElementById("competitor-modal").style.display = "flex";
  };
  document.getElementById("modal-close-competitor").onclick =
    document.getElementById("btn-cancel-competitor").onclick = () => {
      document.getElementById("competitor-modal").style.display = "none";
    };

  document.getElementById("btn-save-competitor").onclick = async () => {
    const resp = await fetch("/api/competitors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        platform: document.getElementById("comp-platform").value,
        handle: document.getElementById("comp-handle").value,
        display_name: document.getElementById("comp-display").value,
      }),
    });
    const data = await resp.json();
    if (data.ok) {
      document.getElementById("competitor-modal").style.display = "none";
      loadCompetitors();
    } else {
      alert(data.error || "Failed to add competitor");
    }
  };

  document.getElementById("posts-modal-close").onclick = () => {
    document.getElementById("posts-modal").style.display = "none";
  };

  // Init
  loadCompetitors();
  loadComparison();
})();
