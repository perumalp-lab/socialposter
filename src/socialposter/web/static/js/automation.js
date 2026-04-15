/* Automation Rules – vanilla JS IIFE */
(function () {
  "use strict";

  function apiFetch(url, opts) {
    opts = opts || {};
    var headers = opts.headers || {};
    var token = localStorage.getItem("sp_auth_token");
    if (token) headers["Authorization"] = "Bearer " + token;
    if (opts.body && !(opts.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    opts.headers = headers;
    return fetch((window.SOCIALPOSTER_API_BASE || "") + url, opts);
  }

  function escHtml(s) {
    var d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  /* ── Load Rules ── */
  function loadRules() {
    apiFetch("/api/automation/rules")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var list = document.getElementById("rules-list");
        if (!data.length) {
          list.innerHTML =
            '<div class="empty-state">' +
              '<svg width="40" height="40" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"><path d="M12 4v4M12 28v4M4.93 8.93l2.83 2.83M24.24 24.24l1.42 1.42M4 20h4M28 20h4M4.93 31.07l2.83-2.83M24.24 15.76l1.42-1.42"/><circle cx="18" cy="20" r="8"/></svg>' +
              '<h3>No automation rules</h3>' +
              '<p>Create rules to automate actions like notifications when posts go viral, or content suggestions when you haven\'t posted.</p>' +
            '</div>';
          return;
        }

        var html = "";
        for (var i = 0; i < data.length; i++) {
          var r = data[i];
          var triggerLabel = r.trigger_type === "engagement_threshold" ? "Engagement Threshold" : "No Post Interval";
          var actionsStr = (r.actions || []).map(function (a) { return a.type; }).join(", ");
          var lastRun = r.last_triggered_at ? new Date(r.last_triggered_at).toLocaleString() : "Never";

          html += '<div class="automation-rule-row">';
          html += '<div class="automation-rule-info">';
          html += '<div class="automation-rule-name">' + escHtml(r.name) + '</div>';
          html += '<div class="automation-rule-meta">';
          html += '<span class="draft-status-badge ' + (r.enabled ? "badge-approved" : "badge-draft") + '">' + (r.enabled ? "Enabled" : "Disabled") + '</span> ';
          html += '<span>' + escHtml(triggerLabel) + '</span> &rarr; <span>' + escHtml(actionsStr) + '</span>';
          html += '</div>';
          html += '<div style="font-size:.72rem;color:var(--text-muted);">Triggered ' + r.trigger_count + ' times &middot; Last: ' + escHtml(lastRun) + '</div>';
          html += '</div>';
          html += '<div class="automation-rule-actions">';
          html += '<button class="btn btn-sm btn-outline btn-toggle" data-id="' + r.id + '">' + (r.enabled ? "Disable" : "Enable") + '</button>';
          html += '<button class="btn btn-sm btn-outline btn-logs" data-id="' + r.id + '">Logs</button>';
          html += '<button class="btn btn-sm btn-danger btn-delete-rule" data-id="' + r.id + '">Delete</button>';
          html += '</div>';
          html += '</div>';
        }
        list.innerHTML = html;

        // Bind actions
        list.querySelectorAll(".btn-toggle").forEach(function (btn) {
          btn.addEventListener("click", function () {
            apiFetch("/api/automation/rules/" + this.dataset.id + "/toggle", { method: "POST" })
              .then(function () { loadRules(); });
          });
        });

        list.querySelectorAll(".btn-delete-rule").forEach(function (btn) {
          btn.addEventListener("click", function () {
            if (!confirm("Delete this rule?")) return;
            apiFetch("/api/automation/rules/" + this.dataset.id, { method: "DELETE" })
              .then(function () { loadRules(); });
          });
        });

        list.querySelectorAll(".btn-logs").forEach(function (btn) {
          btn.addEventListener("click", function () {
            loadLogs(this.dataset.id);
          });
        });
      });
  }

  /* ── Load Logs ── */
  function loadLogs(ruleId) {
    apiFetch("/api/automation/rules/" + ruleId + "/logs")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var body = document.getElementById("logs-body");
        if (!data.length) {
          body.innerHTML = '<p style="color:var(--text-muted);">No execution logs yet.</p>';
        } else {
          var html = "";
          for (var i = 0; i < data.length; i++) {
            var l = data[i];
            var date = l.triggered_at ? new Date(l.triggered_at).toLocaleString() : "";
            html += '<div class="modal-event-item">';
            html += '<div style="display:flex;justify-content:space-between;align-items:center;">';
            html += '<span>' + escHtml(date) + '</span>';
            html += '<span class="draft-status-badge ' + (l.success ? "badge-success" : "badge-failed") + '">' + (l.success ? "Success" : "Failed") + '</span>';
            html += '</div>';
            if (l.error_message) {
              html += '<div style="color:var(--danger);font-size:.8rem;margin-top:4px;">' + escHtml(l.error_message) + '</div>';
            }
            if (l.actions_taken && l.actions_taken.length) {
              html += '<div style="font-size:.78rem;color:var(--text-secondary);margin-top:4px;">Actions: ' + escHtml(JSON.stringify(l.actions_taken)) + '</div>';
            }
            html += '</div>';
          }
          body.innerHTML = html;
        }
        document.getElementById("logs-modal").style.display = "flex";
      });
  }

  /* ── Init ── */
  document.addEventListener("DOMContentLoaded", function () {
    loadRules();

    // Trigger type toggle conditions
    var triggerSelect = document.getElementById("rule-trigger");
    if (triggerSelect) {
      triggerSelect.addEventListener("change", function () {
        document.getElementById("cond-engagement").style.display =
          this.value === "engagement_threshold" ? "block" : "none";
        document.getElementById("cond-nopost").style.display =
          this.value === "no_post_interval" ? "block" : "none";
      });
    }

    // New rule modal
    var btnNew = document.getElementById("btn-new-rule");
    if (btnNew) {
      btnNew.addEventListener("click", function () {
        document.getElementById("rule-modal").style.display = "flex";
      });
    }
    var btnClose = document.getElementById("modal-close-rule");
    var btnCancel = document.getElementById("btn-cancel-rule");
    function closeModal() { document.getElementById("rule-modal").style.display = "none"; }
    if (btnClose) btnClose.addEventListener("click", closeModal);
    if (btnCancel) btnCancel.addEventListener("click", closeModal);

    var ruleModal = document.getElementById("rule-modal");
    if (ruleModal) ruleModal.addEventListener("click", function (e) {
      if (e.target === this) closeModal();
    });

    // Save rule
    var btnSave = document.getElementById("btn-save-rule");
    if (btnSave) {
      btnSave.addEventListener("click", function () {
        var name = document.getElementById("rule-name").value.trim();
        var triggerType = document.getElementById("rule-trigger").value;
        var actionType = document.getElementById("rule-action").value;
        var actionMsg = document.getElementById("action-message").value.trim();

        if (!name) { alert("Rule name is required"); return; }

        var conditions = {};
        if (triggerType === "engagement_threshold") {
          conditions.threshold = parseInt(document.getElementById("cond-threshold").value) || 100;
          conditions.platform = document.getElementById("cond-platform").value.trim();
          conditions.days = parseInt(document.getElementById("cond-days").value) || 7;
        } else if (triggerType === "no_post_interval") {
          conditions.hours = parseInt(document.getElementById("cond-hours").value) || 24;
          conditions.platform = document.getElementById("cond-nopost-platform").value.trim();
        }

        var actions = [{ type: actionType, params: {} }];
        if (actionType === "notify" && actionMsg) {
          actions[0].params.message = actionMsg;
        } else if (actionType === "ai_generate" && actionMsg) {
          actions[0].params.topic = actionMsg;
        } else if (actionType === "repost" && actionMsg) {
          actions[0].params.platforms = actionMsg.split(",").map(function (s) { return s.trim(); });
        }

        apiFetch("/api/automation/rules", {
          method: "POST",
          body: JSON.stringify({
            name: name,
            trigger_type: triggerType,
            conditions: conditions,
            actions: actions,
          }),
        }).then(function (r) { return r.json(); }).then(function (data) {
          if (data.ok) { closeModal(); loadRules(); }
          else alert(data.error || "Failed");
        });
      });
    }

    // Logs modal close
    var logsClose = document.getElementById("logs-modal-close");
    if (logsClose) logsClose.addEventListener("click", function () {
      document.getElementById("logs-modal").style.display = "none";
    });
    var logsModal = document.getElementById("logs-modal");
    if (logsModal) logsModal.addEventListener("click", function (e) {
      if (e.target === this) this.style.display = "none";
    });
  });
})();
