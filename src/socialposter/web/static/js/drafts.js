/* Drafts & Approval Workflow – vanilla JS IIFE */
(function () {
  "use strict";

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

  /* ── Drafts List Page ── */
  function loadDraftsList() {
    var list = document.getElementById("drafts-list");
    if (!list) return;

    var status = document.getElementById("filter-status").value;
    var url = "/api/drafts";
    if (status) url += "?status=" + status;

    apiFetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.items || !data.items.length) {
          list.innerHTML =
            '<div class="empty-state">' +
              '<svg width="40" height="40" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"><path d="M8 6h16l6 6v22H8z"/><path d="M20 6v6h6"/><path d="M14 22h12M14 28h8"/></svg>' +
              '<h3>No drafts yet</h3>' +
              '<p>Create a draft to collaborate with your team before publishing.</p>' +
            '</div>';
          return;
        }
        var html = "";
        for (var i = 0; i < data.items.length; i++) {
          var d = data.items[i];
          var badgeClass = "badge-" + d.status.replace("_", "-");
          html += '<a href="/drafts/' + d.id + '" class="draft-row">';
          html += '<div class="draft-row-info">';
          html += '<strong>' + escHtml(d.name) + '</strong>';
          html += '<span style="color:var(--text-muted);font-size:.8rem;"> by ' + escHtml(d.author) + '</span>';
          html += '<div style="font-size:.8rem;color:var(--text-secondary);margin-top:2px;">' + escHtml(d.text) + '</div>';
          html += '</div>';
          html += '<div class="draft-row-meta">';
          html += '<span class="draft-status-badge ' + badgeClass + '">' + escHtml(d.status.replace("_", " ")) + '</span>';
          if (d.platforms && d.platforms.length) {
            html += '<div style="font-size:.75rem;color:var(--text-muted);margin-top:4px;">' +
              d.platforms.map(function (p) { return capitalize(p); }).join(", ") + '</div>';
          }
          html += '</div>';
          html += '</a>';
        }
        list.innerHTML = html;
      });
  }

  /* ── Draft Detail Page ── */
  function initDraftDetail() {
    var main = document.querySelector("main[data-draft-id]");
    if (!main) return;
    var draftId = main.dataset.draftId;

    // Load comments
    loadComments(draftId);

    // Save changes
    var btnSave = document.getElementById("btn-save-changes");
    if (btnSave) {
      btnSave.addEventListener("click", function () {
        var text = document.getElementById("detail-text").value;
        var platforms = document.getElementById("detail-platforms").value
          .split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        apiFetch("/api/drafts/" + draftId, {
          method: "PUT",
          body: JSON.stringify({ text: text, platforms: platforms }),
        }).then(function (r) { return r.json(); }).then(function (data) {
          if (data.ok) alert("Saved!");
          else alert(data.error || "Save failed");
        });
      });
    }

    // Submit for review
    var btnSubmit = document.getElementById("btn-submit-review");
    if (btnSubmit) {
      btnSubmit.addEventListener("click", function () {
        apiFetch("/api/drafts/" + draftId + "/submit", { method: "POST" })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.ok) window.location.reload();
            else alert(data.error || "Failed");
          });
      });
    }

    // Delete
    var btnDelete = document.getElementById("btn-delete-draft");
    if (btnDelete) {
      btnDelete.addEventListener("click", function () {
        if (!confirm("Delete this draft?")) return;
        apiFetch("/api/drafts/" + draftId, { method: "DELETE" })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.ok) window.location.href = "/drafts";
            else alert(data.error || "Failed");
          });
      });
    }

    // Approve
    var btnApprove = document.getElementById("btn-approve");
    if (btnApprove) {
      btnApprove.addEventListener("click", function () {
        var comment = prompt("Optional comment:");
        apiFetch("/api/drafts/" + draftId + "/approve", {
          method: "POST",
          body: JSON.stringify({ comment: comment || "" }),
        }).then(function (r) { return r.json(); }).then(function (data) {
          if (data.ok) window.location.reload();
          else alert(data.error || "Failed");
        });
      });
    }

    // Reject
    var btnReject = document.getElementById("btn-reject");
    if (btnReject) {
      btnReject.addEventListener("click", function () {
        var comment = prompt("Reason for rejection:");
        if (!comment) return;
        apiFetch("/api/drafts/" + draftId + "/reject", {
          method: "POST",
          body: JSON.stringify({ comment: comment }),
        }).then(function (r) { return r.json(); }).then(function (data) {
          if (data.ok) window.location.reload();
          else alert(data.error || "Failed");
        });
      });
    }

    // Publish
    var btnPublish = document.getElementById("btn-publish-draft");
    if (btnPublish) {
      btnPublish.addEventListener("click", function () {
        if (!confirm("Publish this draft now?")) return;
        btnPublish.disabled = true;
        btnPublish.textContent = "Publishing...";
        apiFetch("/api/drafts/" + draftId + "/publish", { method: "POST" })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.ok) {
              alert("Published! Results: " + data.results.map(function (r) {
                return r.platform + ": " + (r.success ? "OK" : r.error);
              }).join(", "));
              window.location.reload();
            } else {
              alert(data.error || "Publish failed");
            }
          })
          .finally(function () { btnPublish.disabled = false; btnPublish.textContent = "Publish Now"; });
      });
    }

    // Add comment
    var btnComment = document.getElementById("btn-add-comment");
    if (btnComment) {
      btnComment.addEventListener("click", function () {
        var input = document.getElementById("comment-input");
        var text = input.value.trim();
        if (!text) return;
        apiFetch("/api/drafts/" + draftId + "/comments", {
          method: "POST",
          body: JSON.stringify({ text: text }),
        }).then(function (r) { return r.json(); }).then(function (data) {
          if (data.ok) {
            input.value = "";
            loadComments(draftId);
          }
        });
      });
    }
  }

  function loadComments(draftId) {
    var list = document.getElementById("comments-list");
    if (!list) return;
    apiFetch("/api/drafts/" + draftId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var comments = data.comments || [];
        if (!comments.length) {
          list.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;">No comments yet.</p>';
          return;
        }
        var html = "";
        for (var i = 0; i < comments.length; i++) {
          var c = comments[i];
          var date = c.created_at ? new Date(c.created_at).toLocaleString() : "";
          html += '<div class="comment-item">';
          html += '<strong>' + escHtml(c.user) + '</strong>';
          html += '<span style="color:var(--text-muted);font-size:.75rem;margin-left:8px;">' + escHtml(date) + '</span>';
          html += '<div style="margin-top:4px;font-size:.85rem;">' + escHtml(c.text) + '</div>';
          html += '</div>';
        }
        list.innerHTML = html;
      });
  }

  /* ── Init ── */
  document.addEventListener("DOMContentLoaded", function () {
    // Drafts list page
    var filterStatus = document.getElementById("filter-status");
    if (filterStatus) {
      filterStatus.addEventListener("change", loadDraftsList);
      loadDraftsList();
    }

    // New draft modal
    var btnNewDraft = document.getElementById("btn-new-draft");
    if (btnNewDraft) {
      btnNewDraft.addEventListener("click", function () {
        document.getElementById("new-draft-modal").style.display = "flex";
      });
    }
    var btnCloseModal = document.getElementById("modal-close-draft");
    if (btnCloseModal) {
      btnCloseModal.addEventListener("click", function () {
        document.getElementById("new-draft-modal").style.display = "none";
      });
    }
    var modalOverlay = document.getElementById("new-draft-modal");
    if (modalOverlay) {
      modalOverlay.addEventListener("click", function (e) {
        if (e.target === this) this.style.display = "none";
      });
    }
    var btnSaveDraft = document.getElementById("btn-save-draft");
    if (btnSaveDraft) {
      btnSaveDraft.addEventListener("click", function () {
        var name = document.getElementById("draft-name").value.trim();
        var text = document.getElementById("draft-text").value;
        var platforms = document.getElementById("draft-platforms").value
          .split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        if (!name) { alert("Name is required"); return; }
        apiFetch("/api/drafts", {
          method: "POST",
          body: JSON.stringify({ name: name, text: text, platforms: platforms }),
        }).then(function (r) { return r.json(); }).then(function (data) {
          if (data.ok) {
            document.getElementById("new-draft-modal").style.display = "none";
            window.location.href = "/drafts/" + data.id;
          } else {
            alert(data.error || "Failed");
          }
        });
      });
    }

    // Draft detail page
    initDraftDetail();
  });
})();
