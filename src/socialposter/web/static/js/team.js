/* Team Management – vanilla JS */
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

  function showMsg(elId, msg, type) {
    var el = document.getElementById(elId);
    if (!el) return;
    el.innerHTML = '<div class="alert alert-' + (type || "info") + '">' + msg + '</div>';
    setTimeout(function () { el.innerHTML = ""; }, 4000);
  }

  document.addEventListener("DOMContentLoaded", function () {
    // Create team
    var btnCreate = document.getElementById("btn-create-team");
    if (btnCreate) {
      btnCreate.addEventListener("click", function () {
        var name = document.getElementById("team-name").value.trim();
        if (!name) { showMsg("team-msg", "Team name is required", "error"); return; }
        btnCreate.disabled = true;
        apiFetch("/team/create", {
          method: "POST",
          body: JSON.stringify({ name: name }),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.ok) {
              window.location.reload();
            } else {
              showMsg("team-msg", data.error || "Failed", "error");
            }
          })
          .catch(function () { showMsg("team-msg", "Network error", "error"); })
          .finally(function () { btnCreate.disabled = false; });
      });
    }

    // Invite user
    var btnInvite = document.getElementById("btn-invite");
    if (btnInvite) {
      btnInvite.addEventListener("click", function () {
        var email = document.getElementById("invite-email").value.trim();
        var role = document.getElementById("invite-role").value;
        if (!email) { showMsg("invite-msg", "Email is required", "error"); return; }
        btnInvite.disabled = true;
        apiFetch("/team/invite", {
          method: "POST",
          body: JSON.stringify({ email: email, role: role }),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.ok) {
              showMsg("invite-msg", "Invited " + data.display_name, "success");
              setTimeout(function () { window.location.reload(); }, 1500);
            } else {
              showMsg("invite-msg", data.error || "Failed", "error");
            }
          })
          .catch(function () { showMsg("invite-msg", "Network error", "error"); })
          .finally(function () { btnInvite.disabled = false; });
      });
    }

    // Role change
    document.querySelectorAll(".role-select").forEach(function (sel) {
      sel.addEventListener("change", function () {
        var memberId = this.dataset.memberId;
        apiFetch("/team/members/" + memberId + "/role", {
          method: "POST",
          body: JSON.stringify({ role: this.value }),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (!data.ok) alert(data.error || "Failed to update role");
          });
      });
    });

    // Site admin toggle
    document.querySelectorAll(".site-admin-toggle").forEach(function (cb) {
      cb.addEventListener("change", function () {
        var userId = this.dataset.userId;
        var checked = this.checked;
        apiFetch("/team/members/" + userId + "/site-admin", {
          method: "POST",
          body: JSON.stringify({ is_admin: checked }),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (!data.ok) { alert(data.error || "Failed"); cb.checked = !checked; }
          })
          .catch(function () { cb.checked = !checked; });
      });
    });

    // Remove member
    document.querySelectorAll(".btn-remove-member").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!confirm("Remove this member?")) return;
        var memberId = this.dataset.memberId;
        apiFetch("/team/members/" + memberId + "/remove", { method: "POST" })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.ok) window.location.reload();
            else alert(data.error || "Failed");
          });
      });
    });
  });
})();
