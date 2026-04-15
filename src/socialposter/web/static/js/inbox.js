/* Unified Inbox – vanilla JS IIFE */
(function () {
  "use strict";

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

  function loadComments() {
    var platform = document.getElementById("inbox-platform-filter").value;
    var isRead = document.getElementById("inbox-read-filter").value;
    var url = "/api/inbox/comments?page=" + currentPage;
    if (platform) url += "&platform=" + platform;
    if (isRead) url += "&is_read=" + isRead;

    apiFetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var list = document.getElementById("inbox-list");
        if (!data.items || !data.items.length) {
          list.innerHTML =
            '<div class="empty-state">' +
              '<svg width="40" height="40" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"><path d="M6 8l14 10 14-10M6 8v24h28V8"/></svg>' +
              '<h3>Inbox is empty</h3>' +
              '<p>Comments and replies from your published posts will appear here automatically.</p>' +
              '<a href="/" class="btn btn-primary btn-sm">Compose a Post</a>' +
            '</div>';
          document.getElementById("inbox-pagination").innerHTML = "";
          return;
        }

        var html = "";
        for (var i = 0; i < data.items.length; i++) {
          var c = data.items[i];
          var readClass = c.is_read ? "inbox-read" : "inbox-unread";
          var date = c.posted_at ? new Date(c.posted_at).toLocaleString() : (c.fetched_at ? new Date(c.fetched_at).toLocaleString() : "");

          html += '<div class="inbox-item ' + readClass + '" data-id="' + c.id + '">';
          html += '<div class="inbox-item-left">';
          if (c.author_avatar_url) {
            html += '<img class="inbox-avatar" src="' + escHtml(c.author_avatar_url) + '" alt="" />';
          } else {
            html += '<div class="inbox-avatar-placeholder">' + escHtml((c.author_name || "?").charAt(0).toUpperCase()) + '</div>';
          }
          html += '</div>';
          html += '<div class="inbox-item-body">';
          html += '<div class="inbox-item-header">';
          html += '<strong>' + escHtml(c.author_name || "Unknown") + '</strong>';
          html += '<span class="draft-status-badge badge-' + escHtml(c.platform) + '">' + escHtml(capitalize(c.platform)) + '</span>';
          html += '<span style="color:var(--text-muted);font-size:.75rem;margin-left:auto;">' + escHtml(date) + '</span>';
          html += '</div>';
          html += '<div class="inbox-item-text">' + escHtml(c.text) + '</div>';
          html += '<div class="inbox-item-actions">';
          if (!c.is_read) {
            html += '<button class="btn btn-sm btn-outline btn-mark-read" data-id="' + c.id + '">Mark Read</button>';
          }
          html += '<button class="btn btn-sm btn-outline btn-reply" data-id="' + c.id + '">Reply</button>';
          if (c.platform_post_url) {
            html += '<a href="' + escHtml(c.platform_post_url) + '" target="_blank" class="btn btn-sm btn-outline">View Post</a>';
          }
          html += '</div>';
          // Reply input (hidden by default)
          html += '<div class="inbox-reply-form" id="reply-form-' + c.id + '" style="display:none;">';
          html += '<input type="text" class="reply-input" placeholder="Type your reply..." />';
          html += '<button class="btn btn-sm btn-primary btn-send-reply" data-id="' + c.id + '">Send</button>';
          html += '</div>';
          html += '</div>';
          html += '</div>';
        }
        list.innerHTML = html;

        // Bind actions
        list.querySelectorAll(".btn-mark-read").forEach(function (btn) {
          btn.addEventListener("click", function (e) {
            e.stopPropagation();
            var id = this.dataset.id;
            apiFetch("/api/inbox/comments/" + id + "/read", { method: "POST" })
              .then(function () { loadComments(); loadStats(); });
          });
        });

        list.querySelectorAll(".btn-reply").forEach(function (btn) {
          btn.addEventListener("click", function (e) {
            e.stopPropagation();
            var form = document.getElementById("reply-form-" + this.dataset.id);
            form.style.display = form.style.display === "none" ? "flex" : "none";
          });
        });

        list.querySelectorAll(".btn-send-reply").forEach(function (btn) {
          btn.addEventListener("click", function () {
            var id = this.dataset.id;
            var form = document.getElementById("reply-form-" + id);
            var input = form.querySelector(".reply-input");
            var text = input.value.trim();
            if (!text) return;
            this.disabled = true;
            apiFetch("/api/inbox/comments/" + id + "/reply", {
              method: "POST",
              body: JSON.stringify({ text: text }),
            }).then(function (r) { return r.json(); }).then(function (data) {
              if (data.ok) {
                input.value = "";
                form.style.display = "none";
                alert("Reply sent!");
                loadComments();
              } else {
                alert(data.error || "Reply failed");
              }
            }).finally(function () { btn.disabled = false; });
          });
        });

        // Pagination
        var pagEl = document.getElementById("inbox-pagination");
        if (data.pages <= 1) { pagEl.innerHTML = ""; return; }
        var pHtml = "";
        for (var p = 1; p <= data.pages; p++) {
          pHtml += '<button class="btn btn-sm ' + (p === data.page ? "btn-primary" : "btn-outline") + ' page-btn" data-page="' + p + '">' + p + '</button> ';
        }
        pagEl.innerHTML = pHtml;
        pagEl.querySelectorAll(".page-btn").forEach(function (b) {
          b.addEventListener("click", function () {
            currentPage = parseInt(this.dataset.page);
            loadComments();
          });
        });
      });
  }

  function loadStats() {
    apiFetch("/api/inbox/stats")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var badge = document.getElementById("inbox-count-badge");
        var navBadge = document.getElementById("nav-inbox-badge");
        if (data.total_unread > 0) {
          if (badge) { badge.textContent = data.total_unread; badge.style.display = "inline"; }
          if (navBadge) { navBadge.textContent = data.total_unread; navBadge.style.display = "inline"; }
        } else {
          if (badge) badge.style.display = "none";
          if (navBadge) navBadge.style.display = "none";
        }
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var pf = document.getElementById("inbox-platform-filter");
    var rf = document.getElementById("inbox-read-filter");
    if (pf) pf.addEventListener("change", function () { currentPage = 1; loadComments(); });
    if (rf) rf.addEventListener("change", function () { currentPage = 1; loadComments(); });

    var btnMarkAll = document.getElementById("btn-mark-all-read");
    if (btnMarkAll) {
      btnMarkAll.addEventListener("click", function () {
        apiFetch("/api/inbox/comments/mark-read", { method: "POST", body: JSON.stringify({}) })
          .then(function () { loadComments(); loadStats(); });
      });
    }

    loadComments();
    loadStats();

    // Auto-poll stats every 60 seconds
    setInterval(loadStats, 60000);
  });
})();
