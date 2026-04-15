/* Media Library – vanilla JS IIFE */
(function () {
  "use strict";

  var currentPage = 1;
  var currentDetailId = null;

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

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  /* ── Load Media Grid ── */
  function loadGrid() {
    var type = document.getElementById("media-type-filter").value;
    var search = document.getElementById("media-search").value;
    var url = "/api/media?page=" + currentPage;
    if (type) url += "&type=" + type;
    if (search) url += "&search=" + encodeURIComponent(search);

    apiFetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var grid = document.getElementById("media-grid");
        if (!data.items || !data.items.length) {
          grid.innerHTML =
            '<div class="empty-state">' +
              '<svg width="40" height="40" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"><rect x="4" y="4" width="32" height="32" rx="4"/><circle cx="16" cy="16" r="4"/><path d="M36 28l-8-8-16 16"/></svg>' +
              '<h3>No media files</h3>' +
              '<p>Upload images and videos to build your media library.</p>' +
            '</div>';
          document.getElementById("media-pagination").innerHTML = "";
          return;
        }

        var html = "";
        for (var i = 0; i < data.items.length; i++) {
          var m = data.items[i];
          var thumb;
          if (m.media_type === "video") {
            thumb = '<div class="media-grid-thumb video-thumb"><svg width="24" height="24" fill="none" stroke="#fff" stroke-width="2"><polygon points="5,3 19,12 5,21"/></svg></div>';
          } else {
            thumb = '<img class="media-grid-thumb" src="/api/upload-file?path=' + encodeURIComponent(m.file_path) + '" alt="' + escHtml(m.alt_text || m.filename) + '" onerror="this.style.display=\'none\'" />';
          }
          html += '<div class="media-grid-item" data-id="' + m.id + '">';
          html += thumb;
          html += '<div class="media-grid-info">';
          html += '<span class="media-grid-name" title="' + escHtml(m.filename) + '">' + escHtml(m.filename) + '</span>';
          html += '<span class="media-grid-meta">' + escHtml(m.media_type) + ' &middot; ' + formatSize(m.file_size) + '</span>';
          if (m.tags && m.tags.length) {
            html += '<div class="media-grid-tags">';
            for (var t = 0; t < m.tags.length; t++) {
              html += '<span class="ai-tag">' + escHtml(m.tags[t]) + '</span>';
            }
            html += '</div>';
          }
          html += '</div>';
          html += '</div>';
        }
        grid.innerHTML = html;

        // Click to open detail
        grid.querySelectorAll(".media-grid-item").forEach(function (el) {
          el.addEventListener("click", function () {
            openDetail(parseInt(this.dataset.id), data.items);
          });
        });

        // Pagination
        var pagEl = document.getElementById("media-pagination");
        if (data.pages <= 1) { pagEl.innerHTML = ""; return; }
        var pHtml = "";
        for (var p = 1; p <= data.pages; p++) {
          pHtml += '<button class="btn btn-sm ' + (p === data.page ? "btn-primary" : "btn-outline") + ' page-btn" data-page="' + p + '">' + p + '</button> ';
        }
        pagEl.innerHTML = pHtml;
        pagEl.querySelectorAll(".page-btn").forEach(function (btn) {
          btn.addEventListener("click", function () {
            currentPage = parseInt(this.dataset.page);
            loadGrid();
          });
        });
      });
  }

  /* ── Open Detail Modal ── */
  function openDetail(id, items) {
    var item = null;
    for (var i = 0; i < items.length; i++) {
      if (items[i].id === id) { item = items[i]; break; }
    }
    if (!item) return;

    currentDetailId = id;
    document.getElementById("media-detail-name").textContent = item.filename;

    var body = document.getElementById("media-detail-body");
    var html = "";
    if (item.media_type === "image") {
      html += '<img src="/api/upload-file?path=' + encodeURIComponent(item.file_path) + '" style="width:100%;max-height:300px;object-fit:contain;border-radius:8px;margin-bottom:12px;" onerror="this.style.display=\'none\'" />';
    }
    html += '<div class="form-group"><label>Type</label><p>' + escHtml(item.media_type) + ' &middot; ' + formatSize(item.file_size) + '</p></div>';
    html += '<div class="form-group"><label>Alt Text</label><input type="text" id="detail-alt-text" value="' + escHtml(item.alt_text || "") + '" placeholder="Describe this image..." /></div>';
    html += '<div class="form-group"><label>Tags (comma-separated)</label><input type="text" id="detail-tags" value="' + escHtml((item.tags || []).join(", ")) + '" placeholder="e.g. product, social, banner" /></div>';
    body.innerHTML = html;

    document.getElementById("media-detail-modal").style.display = "flex";
  }

  /* ── Upload ── */
  function uploadFiles(files) {
    var promises = [];
    for (var i = 0; i < files.length; i++) {
      var fd = new FormData();
      fd.append("file", files[i]);
      promises.push(
        apiFetch("/api/media/upload", { method: "POST", body: fd })
          .then(function (r) { return r.json(); })
      );
    }
    Promise.all(promises).then(function () {
      loadGrid();
    });
  }

  /* ── Init ── */
  document.addEventListener("DOMContentLoaded", function () {
    var fileInput = document.getElementById("media-file-input");
    var btnUpload = document.getElementById("btn-media-upload");
    var dropZone = document.getElementById("media-upload-zone");

    if (btnUpload) {
      btnUpload.addEventListener("click", function () { fileInput.click(); });
    }
    if (fileInput) {
      fileInput.addEventListener("change", function () {
        if (fileInput.files.length) uploadFiles(fileInput.files);
        fileInput.value = "";
      });
    }
    if (dropZone) {
      dropZone.addEventListener("dragover", function (e) { e.preventDefault(); dropZone.classList.add("dragover"); });
      dropZone.addEventListener("dragleave", function () { dropZone.classList.remove("dragover"); });
      dropZone.addEventListener("drop", function (e) {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer && e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
      });
    }

    // Filters
    var typeFilter = document.getElementById("media-type-filter");
    var searchInput = document.getElementById("media-search");
    if (typeFilter) typeFilter.addEventListener("change", function () { currentPage = 1; loadGrid(); });
    if (searchInput) {
      var searchTimer;
      searchInput.addEventListener("input", function () {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () { currentPage = 1; loadGrid(); }, 300);
      });
    }

    // Detail modal
    var closeBtn = document.getElementById("media-detail-close");
    if (closeBtn) closeBtn.addEventListener("click", function () {
      document.getElementById("media-detail-modal").style.display = "none";
    });

    var deleteBtn = document.getElementById("media-detail-delete");
    if (deleteBtn) deleteBtn.addEventListener("click", function () {
      if (!currentDetailId || !confirm("Delete this file?")) return;
      apiFetch("/api/media/" + currentDetailId, { method: "DELETE" })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) {
            document.getElementById("media-detail-modal").style.display = "none";
            loadGrid();
          }
        });
    });

    var saveTagsBtn = document.getElementById("media-detail-save-tags");
    if (saveTagsBtn) saveTagsBtn.addEventListener("click", function () {
      if (!currentDetailId) return;
      var tagsInput = document.getElementById("detail-tags");
      var altInput = document.getElementById("detail-alt-text");
      var tags = tagsInput.value.split(",").map(function (t) { return t.trim(); }).filter(Boolean);
      var altText = altInput.value.trim();
      apiFetch("/api/media/" + currentDetailId + "/tags", {
        method: "PUT",
        body: JSON.stringify({ tags: tags, alt_text: altText }),
      }).then(function (r) { return r.json(); }).then(function (data) {
        if (data.ok) {
          document.getElementById("media-detail-modal").style.display = "none";
          loadGrid();
        }
      });
    });

    // Modal overlay click to close
    var modal = document.getElementById("media-detail-modal");
    if (modal) modal.addEventListener("click", function (e) {
      if (e.target === this) this.style.display = "none";
    });

    loadGrid();
  });
})();
