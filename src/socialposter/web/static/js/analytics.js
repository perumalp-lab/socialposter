/* Analytics Dashboard – vanilla JS IIFE */
(function () {
  "use strict";

  var currentDays = 30;
  var currentPage = 1;

  function apiFetch(url, opts) {
    opts = opts || {};
    var headers = opts.headers || {};
    var token = localStorage.getItem("sp_auth_token");
    if (token) headers["Authorization"] = "Bearer " + token;
    if (!(opts.body instanceof FormData)) headers["Content-Type"] = "application/json";
    opts.headers = headers;
    return fetch((window.SOCIALPOSTER_API_BASE || "") + url, opts);
  }

  function escHtml(s) {
    var d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
  }

  /* ── Load Summary ── */
  function loadSummary() {
    apiFetch("/api/analytics/summary?days=" + currentDays)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        document.getElementById("stat-total").textContent = data.total;
        document.getElementById("stat-rate").textContent = data.success_rate + "%";
        document.getElementById("stat-platform").textContent = capitalize(data.top_platform) || "—";
        document.getElementById("stat-successes").textContent = data.successes;

        // Platform breakdown bars
        var container = document.getElementById("platform-bars");
        if (!container) return;
        var maxCount = Math.max.apply(null, Object.values(data.platform_breakdown).concat([1]));
        var html = "";
        var entries = Object.entries(data.platform_breakdown).sort(function (a, b) { return b[1] - a[1]; });
        for (var i = 0; i < entries.length; i++) {
          var name = entries[i][0];
          var count = entries[i][1];
          var pct = Math.round((count / maxCount) * 100);
          html += '<div class="platform-bar-row">' +
            '<span class="platform-bar-label">' + escHtml(capitalize(name)) + '</span>' +
            '<div class="platform-bar-track"><div class="platform-bar-fill pi-' + escHtml(name) + '" style="width:' + pct + '%"></div></div>' +
            '<span class="platform-bar-count">' + count + '</span>' +
            '</div>';
        }
        container.innerHTML = html || '<div class="empty-state"><p>No platform data yet. <a href="/">Compose your first post</a> to see analytics.</p></div>';
      });
  }

  /* ── Load Timeline ── */
  function loadTimeline() {
    apiFetch("/api/analytics/timeline?days=" + currentDays)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var container = document.getElementById("chart-bars");
        if (!container) return;
        var timeline = data.timeline || [];
        if (!timeline.length) {
          container.innerHTML = '<div class="empty-state"><svg width="40" height="40" fill="none" stroke="#94a3b8" stroke-width="1.5"><path d="M4 36V12M14 36V6M24 36v-10M34 36v-16"/></svg><p>No posting activity yet. <a href="/">Create a post</a> to start tracking.</p></div>';
          return;
        }
        var maxCount = Math.max.apply(null, timeline.map(function (d) { return d.count; }).concat([1]));
        var html = "";
        for (var i = 0; i < timeline.length; i++) {
          var d = timeline[i];
          var h = Math.max(4, Math.round((d.count / maxCount) * 160));
          var label = d.date.slice(5); // MM-DD
          html += '<div class="chart-bar-col" title="' + escHtml(d.date) + ': ' + d.count + ' posts">' +
            '<div class="chart-bar" style="height:' + h + 'px"></div>' +
            '<span class="chart-bar-label">' + escHtml(label) + '</span>' +
            '</div>';
        }
        container.innerHTML = html;
      });
  }

  /* ── Load History ── */
  function loadHistory() {
    var platform = document.getElementById("filter-platform").value;
    var success = document.getElementById("filter-success").value;
    var url = "/api/analytics/history?page=" + currentPage;
    if (platform) url += "&platform=" + platform;
    if (success) url += "&success=" + success;

    apiFetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var container = document.getElementById("history-table");
        if (!data.items.length) {
          container.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;">No posts found</p>';
          document.getElementById("history-pagination").innerHTML = "";
          return;
        }
        var html = '<table class="history-tbl"><thead><tr><th>Platform</th><th>Text</th><th>Status</th><th>Date</th></tr></thead><tbody>';
        for (var i = 0; i < data.items.length; i++) {
          var h = data.items[i];
          var statusCls = h.success ? "badge-success" : "badge-failed";
          var statusText = h.success ? "Success" : "Failed";
          var textCol = h.post_url
            ? '<a href="' + escHtml(h.post_url) + '" target="_blank">' + escHtml(h.text) + '</a>'
            : escHtml(h.text);
          var date = h.created_at ? new Date(h.created_at).toLocaleDateString() : "";
          html += '<tr>' +
            '<td><span class="draft-status-badge badge-' + escHtml(h.platform) + '">' + escHtml(capitalize(h.platform)) + '</span></td>' +
            '<td class="history-text-cell">' + textCol + '</td>' +
            '<td><span class="draft-status-badge ' + statusCls + '">' + statusText + '</span></td>' +
            '<td>' + escHtml(date) + '</td>' +
            '</tr>';
        }
        html += '</tbody></table>';
        container.innerHTML = html;

        // Pagination
        var pagEl = document.getElementById("history-pagination");
        if (data.pages <= 1) { pagEl.innerHTML = ""; return; }
        var pHtml = "";
        for (var p = 1; p <= data.pages; p++) {
          pHtml += '<button class="btn btn-sm ' + (p === data.page ? "btn-primary" : "btn-outline") + ' page-btn" data-page="' + p + '">' + p + '</button> ';
        }
        pagEl.innerHTML = pHtml;
        pagEl.querySelectorAll(".page-btn").forEach(function (btn) {
          btn.addEventListener("click", function () {
            currentPage = parseInt(this.dataset.page);
            loadHistory();
          });
        });
      });
  }

  /* ── Load Engagement Overview ── */
  function loadEngagement() {
    apiFetch("/api/analytics/engagement?days=" + currentDays)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var t = data.totals || {};
        document.getElementById("eng-likes").textContent = t.likes || 0;
        document.getElementById("eng-comments").textContent = t.comments || 0;
        document.getElementById("eng-shares").textContent = t.shares || 0;
        document.getElementById("eng-views").textContent = t.views || 0;

        // Platform comparison bars
        var container = document.getElementById("engagement-comparison");
        if (!container) return;
        var platforms = data.platforms || {};
        var entries = Object.entries(platforms).sort(function (a, b) {
          return (b[1].likes + b[1].comments + b[1].shares) - (a[1].likes + a[1].comments + a[1].shares);
        });
        if (!entries.length) {
          container.innerHTML = '<div class="empty-state"><p>No engagement data yet. Engagement metrics will appear as platforms report data.</p></div>';
          return;
        }
        var maxTotal = Math.max.apply(null, entries.map(function (e) { return e[1].likes + e[1].comments + e[1].shares; }).concat([1]));
        var html = "";
        for (var i = 0; i < entries.length; i++) {
          var name = entries[i][0];
          var m = entries[i][1];
          var total = m.likes + m.comments + m.shares;
          var pct = Math.round((total / maxTotal) * 100);
          html += '<div class="platform-bar-row">' +
            '<span class="platform-bar-label">' + escHtml(capitalize(name)) + '</span>' +
            '<div class="platform-bar-track"><div class="platform-bar-fill pi-' + escHtml(name) + '" style="width:' + pct + '%"></div></div>' +
            '<span class="platform-bar-count" title="Likes: ' + m.likes + ' Comments: ' + m.comments + ' Shares: ' + m.shares + '">' + total + '</span>' +
            '</div>';
        }
        container.innerHTML = html;
      });
  }

  /* ── Load Best Times ── */
  function loadBestTimes() {
    apiFetch("/api/analytics/best-times")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var container = document.getElementById("best-times-grid");
        if (!container) return;
        var hours = data.hours || [];
        if (!hours.length) {
          container.innerHTML = '<div class="empty-state"><p>Not enough data to determine best posting times yet.</p></div>';
          return;
        }
        // Build a 24-hour heatmap
        var byHour = {};
        for (var i = 0; i < hours.length; i++) byHour[hours[i].hour] = hours[i];
        var maxPosts = Math.max.apply(null, hours.map(function (h) { return h.post_count; }).concat([1]));
        var html = "";
        for (var h = 0; h < 24; h++) {
          var entry = byHour[h] || { hour: h, post_count: 0, avg_engagement_rate: 0 };
          var intensity = Math.round((entry.post_count / maxPosts) * 100);
          var label = (h < 10 ? "0" : "") + h + ":00";
          html += '<div class="best-time-cell" style="opacity:' + Math.max(0.15, intensity / 100) + '" title="' + label + ': ' + entry.post_count + ' posts, ' + entry.avg_engagement_rate + '% engagement">' +
            '<span class="best-time-hour">' + label + '</span>' +
            '<span class="best-time-count">' + entry.post_count + '</span>' +
            '</div>';
        }
        container.innerHTML = html;
      });
  }

  /* ── Load Top Posts ── */
  function loadTopPosts() {
    apiFetch("/api/analytics/top-posts?days=" + currentDays)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var container = document.getElementById("top-posts-list");
        if (!container) return;
        var posts = data.posts || [];
        if (!posts.length) {
          container.innerHTML = '<div class="empty-state"><p>No top posts data available yet.</p></div>';
          return;
        }
        var html = "";
        for (var i = 0; i < posts.length; i++) {
          var p = posts[i];
          var total = (p.likes || 0) + (p.comments || 0) + (p.shares || 0);
          html += '<div class="top-post-item">';
          html += '<div class="top-post-rank">#' + (i + 1) + '</div>';
          html += '<div class="top-post-body">';
          html += '<span class="draft-status-badge badge-' + escHtml(p.platform) + '">' + escHtml(capitalize(p.platform)) + '</span> ';
          if (p.post_url) {
            html += '<a href="' + escHtml(p.post_url) + '" target="_blank">' + escHtml(p.text_preview || "View post") + '</a>';
          } else {
            html += '<span>' + escHtml(p.text_preview || "—") + '</span>';
          }
          html += '<div class="top-post-stats">';
          html += '<span title="Likes">&hearts; ' + (p.likes || 0) + '</span>';
          html += '<span title="Comments">&#128172; ' + (p.comments || 0) + '</span>';
          html += '<span title="Shares">&#8634; ' + (p.shares || 0) + '</span>';
          if (p.views) html += '<span title="Views">&#128065; ' + p.views + '</span>';
          html += '</div>';
          html += '</div>';
          html += '<div class="top-post-total">' + total + '</div>';
          html += '</div>';
        }
        container.innerHTML = html;
      });
  }

  function loadAll() {
    loadSummary();
    loadTimeline();
    loadEngagement();
    loadBestTimes();
    loadTopPosts();
    currentPage = 1;
    loadHistory();
  }

  /* ── Init ── */
  document.addEventListener("DOMContentLoaded", function () {
    // Period toggle
    document.querySelectorAll(".period-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.querySelectorAll(".period-btn").forEach(function (b) { b.classList.remove("active"); });
        this.classList.add("active");
        currentDays = parseInt(this.dataset.days);
        loadAll();
      });
    });

    // Filters
    var fp = document.getElementById("filter-platform");
    var fs = document.getElementById("filter-success");
    if (fp) fp.addEventListener("change", function () { currentPage = 1; loadHistory(); });
    if (fs) fs.addEventListener("change", function () { currentPage = 1; loadHistory(); });

    loadAll();
  });
})();
