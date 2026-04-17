/* ===================================================================
   KRYPTAMS – Web UI JavaScript
   =================================================================== */

// ─── Service Worker Registration ───
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js").then(function (reg) {
      console.log("[KRYPTAMS] SW registered, scope:", reg.scope);
    }).catch(function (err) {
      console.warn("[KRYPTAMS] SW registration failed:", err);
    });
  });
}

// ─── API Base URL & Auth Helper ───
var API_BASE = window.SOCIALPOSTER_API_BASE || "";
var isCapacitor = typeof window.Capacitor !== "undefined";

function apiFetch(path, options) {
  options = options || {};
  var url = API_BASE + path;
  if (!options.headers) options.headers = {};

  // Add JWT Bearer token if available (mobile / Capacitor)
  var token = localStorage.getItem("sp_auth_token");
  if (token) {
    options.headers["Authorization"] = "Bearer " + token;
  }

  // Ensure JSON content-type for non-FormData requests
  if (options.body && !(options.body instanceof FormData) && !options.headers["Content-Type"]) {
    options.headers["Content-Type"] = "application/json";
  }

  return fetch(url, options);
}

(function () {
  "use strict";

  // ─── State ───
  const state = {
    platforms: [],
    selectedPlatforms: [],
    mediaFiles: [],
    activePreviewTab: null,
  };

  // ─── Platform icon letters & colors ───
  const PLATFORM_META = {
    linkedin:  { letter: "in", cssClass: "pi-linkedin",  brandColor: "#0A66C2" },
    youtube:   { letter: "YT", cssClass: "pi-youtube",   brandColor: "#FF0000" },
    instagram: { letter: "IG", cssClass: "pi-instagram", brandColor: "#E4405F" },
    facebook:  { letter: "fb", cssClass: "pi-facebook",  brandColor: "#1877F2" },
    twitter:   { letter: "X",  cssClass: "pi-twitter",   brandColor: "#000000" },
    whatsapp:  { letter: "WA", cssClass: "pi-whatsapp",  brandColor: "#25D366" },
  };

  // ─── DOM refs (resolved after DOMContentLoaded) ───
  var platformGrid, postText, charCounter, uploadZone, fileInput, browseBtn;
  var uploadPlaceholder, mediaPreviewList, overridesCard, overridesContainer;
  var previewTabs, previewBody, btnPublish, btnDryRun;
  var resultsCard, resultsBody, loadingOverlay, loadingText, toastContainer;

  function cacheDom() {
    platformGrid      = document.getElementById("platform-grid");
    postText          = document.getElementById("post-text");
    charCounter       = document.getElementById("char-counter");
    uploadZone        = document.getElementById("upload-zone");
    fileInput         = document.getElementById("file-input");
    browseBtn         = document.getElementById("browse-btn");
    uploadPlaceholder = document.getElementById("upload-placeholder");
    mediaPreviewList  = document.getElementById("media-preview-list");
    overridesCard     = document.getElementById("overrides-card");
    overridesContainer= document.getElementById("overrides-container");
    previewTabs       = document.getElementById("preview-tabs");
    previewBody       = document.getElementById("preview-body");
    btnPublish        = document.getElementById("btn-publish");
    btnDryRun         = document.getElementById("btn-dry-run");
    resultsCard       = document.getElementById("results-card");
    resultsBody       = document.getElementById("results-body");
    loadingOverlay    = document.getElementById("loading-overlay");
    loadingText       = document.getElementById("loading-text");
    toastContainer    = document.getElementById("toast-container");
  }

  // ─── AI DOM refs ───
  var btnAIGenerate, btnAIOptimize, aiPromptRow, aiTopicInput, btnAISubmit, btnAICancel;
  var aiStructuredForm, aiResultsPanel;

  // ─── AI Selection State ───
  function getAISelection() {
    var modelSelect = document.getElementById("ai-model-select");
    var slider = document.getElementById("ai-creativity-slider");
    var sel = modelSelect ? modelSelect.value : "";
    var parts = sel ? sel.split("|") : ["", ""];
    return {
      provider: parts[0] || null,
      model: parts[1] || null,
      temperature: slider ? parseFloat(slider.value) / 100 : null,
    };
  }

  // ─── Init ───
  async function init() {
    cacheDom();
    console.log("[KRYPTAMS] DOM cached, loading platforms...");
    await loadPlatforms();
    bindEvents();
    initAI();
    loadAIModels();
    initAISlider();
    console.log("[KRYPTAMS] Ready.");
  }

  async function loadAIModels() {
    try {
      var resp = await apiFetch("/api/ai/models");
      if (!resp.ok) return;
      var models = await resp.json();
      var select = document.getElementById("ai-model-select");
      if (!select || !models.length) return;
      for (var i = 0; i < models.length; i++) {
        var m = models[i];
        var opt = document.createElement("option");
        opt.value = m.provider + "|" + m.model_id;
        opt.textContent = m.display_name + " (" + m.provider_display + ")";
        if (m.is_default) opt.selected = true;
        select.appendChild(opt);
      }
    } catch (e) {
      console.warn("[SocialPoster] Failed to load AI models:", e);
    }
  }

  function initAISlider() {
    var slider = document.getElementById("ai-creativity-slider");
    var label = document.getElementById("ai-creativity-label");
    if (!slider || !label) return;
    slider.addEventListener("input", function () {
      label.textContent = (parseFloat(slider.value) / 100).toFixed(1);
    });
  }

  // ─── Load Platforms ───
  async function loadPlatforms() {
    try {
      var resp = await apiFetch("/api/platforms");
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      state.platforms = await resp.json();
      console.log("[SocialPoster] Loaded platforms:", state.platforms.map(function(p){return p.name;}));
      renderPlatformGrid();
    } catch (e) {
      console.error("[SocialPoster] Failed to load platforms:", e);
      toast("Failed to load platforms: " + e.message, "error");
    }
  }

  // ─── Render Platform Grid ───
  function renderPlatformGrid() {
    platformGrid.innerHTML = "";

    // "Select All Connected" toggle
    var connectedPlatforms = state.platforms.filter(function(p) { return p.connected; });

    if (connectedPlatforms.length === 0 && state.platforms.length > 0) {
      platformGrid.innerHTML =
        '<div class="empty-state">' +
          '<svg width="40" height="40" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"><rect x="4" y="4" width="32" height="32" rx="6" stroke-dasharray="4 3"/><path d="M20 14v12M14 20h12"/></svg>' +
          '<h3>No platforms connected</h3>' +
          '<p>Connect your social media accounts to start publishing.</p>' +
          '<a href="/connections" class="btn btn-primary btn-sm">Go to Connections</a>' +
        '</div>';
      return;
    }
    if (connectedPlatforms.length > 1) {
      var toggleRow = document.createElement("div");
      toggleRow.className = "platform-select-all-row";
      var toggleBtn = document.createElement("button");
      toggleBtn.type = "button";
      toggleBtn.className = "btn btn-outline btn-sm platform-select-all-btn";
      toggleBtn.textContent = "Select All Connected";
      toggleBtn.addEventListener("click", function() {
        var allSelected = connectedPlatforms.every(function(p) {
          return state.selectedPlatforms.indexOf(p.name) >= 0;
        });
        if (allSelected) {
          // Deselect all
          state.selectedPlatforms = [];
          toggleBtn.textContent = "Select All Connected";
        } else {
          // Select all connected
          state.selectedPlatforms = connectedPlatforms.map(function(p) { return p.name; });
          toggleBtn.textContent = "Deselect All";
        }
        // Update chip classes
        var chips = platformGrid.querySelectorAll(".platform-chip");
        for (var i = 0; i < chips.length; i++) {
          var pname = chips[i].getAttribute("data-platform");
          if (state.selectedPlatforms.indexOf(pname) >= 0) {
            chips[i].classList.add("selected");
          } else {
            chips[i].classList.remove("selected");
          }
        }
        updateOverrides();
        updatePreview();
        updateCharCounter();
      });
      toggleRow.appendChild(toggleBtn);
      platformGrid.parentNode.insertBefore(toggleRow, platformGrid);
    }

    state.platforms.forEach(function(p) {
      var meta = PLATFORM_META[p.name] || { letter: p.name[0].toUpperCase(), cssClass: "", brandColor: "#6366f1" };
      var isConnected = p.connected;
      var chip = document.createElement("div");
      chip.className = "platform-chip" + (isConnected ? "" : " disconnected");
      chip.setAttribute("data-platform", p.name);

      var badge = isConnected
        ? '<span class="conn-status-badge connected">Connected</span>'
        : '<span class="conn-status-badge disconnected">Not connected</span>';

      chip.innerHTML =
        '<div class="platform-icon ' + meta.cssClass + '">' + meta.letter + '</div>' +
        '<div>' +
          '<div class="platform-label">' + p.display_name + '</div>' +
          badge +
        '</div>';

      if (isConnected) {
        chip.addEventListener("click", function() { togglePlatform(p.name); });
      } else {
        chip.addEventListener("click", function() {
          toast(p.display_name + " is not connected. Go to Connections to link your account.", "info");
        });
      }
      platformGrid.appendChild(chip);
    });
  }

  // ─── Toggle Platform ───
  function togglePlatform(name) {
    var idx = state.selectedPlatforms.indexOf(name);
    if (idx >= 0) {
      state.selectedPlatforms.splice(idx, 1);
    } else {
      state.selectedPlatforms.push(name);
    }
    var chips = platformGrid.querySelectorAll(".platform-chip");
    for (var i = 0; i < chips.length; i++) {
      var chip = chips[i];
      var pname = chip.getAttribute("data-platform");
      if (state.selectedPlatforms.indexOf(pname) >= 0) {
        chip.classList.add("selected");
      } else {
        chip.classList.remove("selected");
      }
    }
    updateOverrides();
    updatePreview();
    updateCharCounter();
    updateSelectAllBtn();
  }

  function updateSelectAllBtn() {
    var btn = document.querySelector(".platform-select-all-btn");
    if (!btn) return;
    var connectedPlatforms = state.platforms.filter(function(p) { return p.connected; });
    var allSelected = connectedPlatforms.length > 0 && connectedPlatforms.every(function(p) {
      return state.selectedPlatforms.indexOf(p.name) >= 0;
    });
    btn.textContent = allSelected ? "Deselect All" : "Select All Connected";
  }

  // ─── Bind Events ───
  function bindEvents() {
    postText.addEventListener("input", function() {
      updateCharCounter();
      updatePreview();
      autoFillYouTube();
    });

    browseBtn.addEventListener("click", function(e) {
      e.preventDefault();
      e.stopPropagation();
      fileInput.click();
    });
    fileInput.addEventListener("change", function() {
      if (fileInput.files && fileInput.files.length > 0) {
        handleFiles(fileInput.files);
      }
    });

    uploadZone.addEventListener("dragover", function(e) {
      e.preventDefault();
      uploadZone.classList.add("dragover");
    });
    uploadZone.addEventListener("dragleave", function() {
      uploadZone.classList.remove("dragover");
    });
    uploadZone.addEventListener("drop", function(e) {
      e.preventDefault();
      uploadZone.classList.remove("dragover");
      if (e.dataTransfer && e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files);
      }
    });

    btnPublish.addEventListener("click", function() {
      console.log("[SocialPoster] Publish clicked");
      publish(false);
    });
    btnDryRun.addEventListener("click", function() {
      console.log("[SocialPoster] Dry Run clicked");
      publish(true);
    });
  }

  // ─── Handle File Uploads ───
  async function handleFiles(files) {
    for (var i = 0; i < files.length; i++) {
      var file = files[i];
      var formData = new FormData();
      formData.append("file", file);
      try {
        var resp = await apiFetch("/api/upload", { method: "POST", body: formData });
        if (!resp.ok) {
          var errData = await resp.json();
          toast(errData.error || "Upload failed", "error");
          continue;
        }
        var data = await resp.json();
        data.localUrl = URL.createObjectURL(file);
        state.mediaFiles.push(data);
        toast("Uploaded: " + data.filename, "success");
      } catch (e) {
        console.error("[SocialPoster] Upload error:", e);
        toast("Upload failed: " + e.message, "error");
      }
    }
    renderMediaPreviews();
    updatePreview();
    uploadPlaceholder.style.display = state.mediaFiles.length ? "none" : "block";
  }

  // ─── Render Media Previews ───
  function renderMediaPreviews() {
    mediaPreviewList.innerHTML = "";
    state.mediaFiles.forEach(function(m, idx) {
      var item = document.createElement("div");
      item.className = "media-preview-item";
      var isVideo = m.media_type === "video";
      var mediaEl = isVideo
        ? '<video src="' + m.localUrl + '" muted></video>'
        : '<img src="' + m.localUrl + '" alt="' + escAttr(m.filename) + '" />';
      item.innerHTML =
        '<span class="media-badge ' + m.media_type + '">' + m.media_type + '</span>' +
        mediaEl +
        '<div class="media-info" title="' + escAttr(m.filename) + '">' + escHtml(m.filename) + '</div>' +
        '<button class="media-remove" data-index="' + idx + '">&times;</button>';
      mediaPreviewList.appendChild(item);
    });

    var removeBtns = mediaPreviewList.querySelectorAll(".media-remove");
    for (var i = 0; i < removeBtns.length; i++) {
      removeBtns[i].addEventListener("click", function(e) {
        var idx = parseInt(e.currentTarget.getAttribute("data-index"));
        URL.revokeObjectURL(state.mediaFiles[idx].localUrl);
        state.mediaFiles.splice(idx, 1);
        renderMediaPreviews();
        updatePreview();
        uploadPlaceholder.style.display = state.mediaFiles.length ? "none" : "block";
      });
    }
  }

  // ─── Character Counter ───
  function updateCharCounter() {
    var len = postText.value.length;
    charCounter.textContent = String(len);
    charCounter.classList.remove("warn", "over");

    var minLimit = Infinity;
    state.selectedPlatforms.forEach(function(name) {
      var p = findPlatform(name);
      if (p && p.max_text_length) minLimit = Math.min(minLimit, p.max_text_length);
    });

    if (minLimit < Infinity) {
      charCounter.textContent = len + " / " + minLimit;
      if (len > minLimit) charCounter.classList.add("over");
      else if (len > minLimit * 0.9) charCounter.classList.add("warn");
    }
  }

  // ─── Overrides ───
  function updateOverrides() {
    overridesContainer.innerHTML = "";
    if (state.selectedPlatforms.length === 0) {
      overridesCard.style.display = "none";
      return;
    }
    overridesCard.style.display = "block";

    state.selectedPlatforms.forEach(function(name) {
      var section = document.createElement("div");
      section.className = "override-section";
      var meta = PLATFORM_META[name] || { letter: "?", brandColor: "#6366f1" };
      var p = findPlatform(name);
      var displayName = p ? p.display_name : name;

      var fields = getOverrideFields(name);

      section.innerHTML =
        '<div class="override-header" data-toggle="' + name + '">' +
          '<span class="arrow">&#9654;</span>' +
          '<span style="display:inline-block;width:18px;height:18px;border-radius:4px;background:' + meta.brandColor + ';"></span> ' +
          displayName +
        '</div>' +
        '<div class="override-body" id="override-body-' + name + '">' + fields + '</div>';
      overridesContainer.appendChild(section);
    });

    // Toggle collapse
    var headers = overridesContainer.querySelectorAll(".override-header");
    for (var i = 0; i < headers.length; i++) {
      headers[i].addEventListener("click", function(e) {
        var toggleName = e.currentTarget.getAttribute("data-toggle");
        var body = document.getElementById("override-body-" + toggleName);
        e.currentTarget.classList.toggle("open");
        body.classList.toggle("open");
      });
    }

    // Listen to field changes for preview
    var fields = overridesContainer.querySelectorAll("input, textarea, select");
    for (var j = 0; j < fields.length; j++) {
      fields[j].addEventListener("input", updatePreview);
    }

    bindHashtagButtons();
    bindRecipientsBulk();
    bindTagsBulk();
    autoFillYouTube();
  }

  // ─── Parse Recipients Helper ───
  function parseRecipients(raw) {
    if (!raw) return [];
    var parts = raw.split(/[,;\n\r]+/);
    var seen = {};
    var result = [];
    for (var i = 0; i < parts.length; i++) {
      var num = parts[i].replace(/[^\d+]/g, "").trim();
      if (num && !seen[num]) {
        seen[num] = true;
        result.push(num);
      }
    }
    return result;
  }

  function updateRecipientsCount() {
    var textarea = document.getElementById("wa-recipients-textarea");
    var badge = document.getElementById("wa-recipients-count");
    if (!textarea || !badge) return;
    var nums = parseRecipients(textarea.value);
    badge.textContent = nums.length + " number" + (nums.length !== 1 ? "s" : "") + " loaded";
    badge.style.display = nums.length > 0 ? "inline-block" : "none";
  }

  function handleRecipientsFileUpload(e) {
    var file = e.target.files && e.target.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function(ev) {
      var textarea = document.getElementById("wa-recipients-textarea");
      if (!textarea) return;
      var existing = textarea.value.trim();
      var newContent = ev.target.result;
      textarea.value = existing ? existing + "\n" + newContent : newContent;
      // Deduplicate in-place
      var nums = parseRecipients(textarea.value);
      textarea.value = nums.join("\n");
      updateRecipientsCount();
      updatePreview();
    };
    reader.readAsText(file);
    // Reset file input so re-uploading same file triggers change
    e.target.value = "";
  }

  // ─── Parse Tags Helper ───
  function parseTags(raw) {
    if (!raw) return [];
    var parts = raw.split(/[,;\n\r]+/);
    var seen = {};
    var result = [];
    for (var i = 0; i < parts.length; i++) {
      var tag = parts[i].trim().replace(/^#/, "");
      if (tag && !seen[tag.toLowerCase()]) {
        seen[tag.toLowerCase()] = true;
        result.push(tag);
      }
    }
    return result;
  }

  function updateTagsCount() {
    var textarea = document.getElementById("yt-tags-textarea");
    var badge = document.getElementById("yt-tags-count");
    if (!textarea || !badge) return;
    var tags = parseTags(textarea.value);
    badge.textContent = tags.length + " tag" + (tags.length !== 1 ? "s" : "");
    badge.style.display = tags.length > 0 ? "inline-block" : "none";
  }

  function getOverrideFields(name) {
    var hashtagBtn = '<button type="button" class="ai-hashtag-btn" data-platform="' + name + '"># Suggest Hashtags</button>';
    if (name === "youtube") {
      return '<label>Video Title</label>' +
        '<input type="text" data-platform="' + name + '" data-field="title" placeholder="Enter YouTube video title" />' +
        '<label>Description</label>' +
        '<textarea data-platform="' + name + '" data-field="description" placeholder="Video description" rows="3"></textarea>' +
        '<label>Tags</label>' +
        '<div class="tags-bulk">' +
          '<textarea id="yt-tags-textarea" data-platform="' + name + '" data-field="tags" placeholder="Paste tags here — one per line, comma-separated, or semicolons" rows="3"></textarea>' +
          '<div class="tags-bulk-actions">' +
            '<span class="tags-count" id="yt-tags-count" style="display:none">0 tags</span>' +
          '</div>' +
        '</div>' +
        '<label>Privacy</label>' +
        '<select data-platform="' + name + '" data-field="privacy">' +
          '<option value="public">Public</option>' +
          '<option value="unlisted">Unlisted</option>' +
          '<option value="private">Private</option>' +
        '</select>' +
        hashtagBtn;
    } else if (name === "linkedin") {
      return '<label>Custom Text (optional)</label>' +
        '<textarea data-platform="' + name + '" data-field="text" placeholder="Override default text for LinkedIn" rows="3"></textarea>' +
        '<label>Visibility</label>' +
        '<select data-platform="' + name + '" data-field="visibility">' +
          '<option value="public">Public</option>' +
          '<option value="connections">Connections Only</option>' +
        '</select>' +
        hashtagBtn;
    } else if (name === "instagram") {
      return '<label>Custom Caption (optional)</label>' +
        '<textarea data-platform="' + name + '" data-field="text" placeholder="Override default text for Instagram" rows="3"></textarea>' +
        '<label>Post Type</label>' +
        '<select data-platform="' + name + '" data-field="post_type">' +
          '<option value="feed">Feed Post</option>' +
          '<option value="reel">Reel</option>' +
          '<option value="story">Story</option>' +
        '</select>' +
        hashtagBtn;
    } else if (name === "facebook") {
      return '<label>Custom Text (optional)</label>' +
        '<textarea data-platform="' + name + '" data-field="text" placeholder="Override default text for Facebook" rows="3"></textarea>' +
        '<label>Link (optional)</label>' +
        '<input type="url" data-platform="' + name + '" data-field="link" placeholder="https://example.com" />' +
        hashtagBtn;
    } else if (name === "twitter") {
      return '<label>Custom Text (optional)</label>' +
        '<textarea data-platform="' + name + '" data-field="text" placeholder="Override default text for X / Twitter (280 chars)" rows="2" maxlength="280"></textarea>' +
        hashtagBtn;
    } else if (name === "whatsapp") {
      return '<label>Custom Message (optional)</label>' +
        '<textarea data-platform="' + name + '" data-field="text" placeholder="Override default text for WhatsApp" rows="2"></textarea>' +
        '<label>Recipients</label>' +
        '<div class="recipients-bulk">' +
          '<textarea id="wa-recipients-textarea" data-platform="' + name + '" data-field="recipients" placeholder="Paste phone numbers here — one per line, comma-separated, or semicolon-separated" rows="5"></textarea>' +
          '<div class="recipients-bulk-actions">' +
            '<label class="recipients-upload-btn">' +
              '<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 1v10M3 5l4-4 4 4"/><path d="M1 10v2a1 1 0 001 1h10a1 1 0 001-1v-2"/></svg>' +
              ' Upload CSV/TXT' +
              '<input type="file" id="wa-recipients-file" accept=".csv,.txt,.tsv,text/plain,text/csv" hidden />' +
            '</label>' +
            '<span class="recipients-count" id="wa-recipients-count" style="display:none">0 numbers loaded</span>' +
          '</div>' +
        '</div>' +
        hashtagBtn;
    }
    return "";
  }

  // ─── Collect Overrides ───
  function collectOverrides() {
    var overrides = {};
    var els = overridesContainer.querySelectorAll("[data-platform]");
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      var pname = el.getAttribute("data-platform");
      var field = el.getAttribute("data-field");
      if (!overrides[pname]) overrides[pname] = {};
      if (field === "recipients") {
        overrides[pname][field] = parseRecipients(el.value);
      } else if (field === "tags") {
        overrides[pname][field] = parseTags(el.value);
      } else {
        overrides[pname][field] = el.value;
      }
    }
    return overrides;
  }

  // ─── Live Preview ───
  function updatePreview() {
    previewTabs.innerHTML = "";
    if (state.selectedPlatforms.length === 0) {
      previewBody.innerHTML =
        '<div class="preview-empty">' +
          '<svg width="48" height="48" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round">' +
            '<circle cx="24" cy="24" r="20"/><path d="M16 20h16M16 28h8"/>' +
          '</svg>' +
          '<p>Select platforms and start typing to see a preview</p>' +
        '</div>';
      return;
    }

    if (!state.activePreviewTab || state.selectedPlatforms.indexOf(state.activePreviewTab) < 0) {
      state.activePreviewTab = state.selectedPlatforms[0];
    }

    state.selectedPlatforms.forEach(function(name) {
      var p = findPlatform(name);
      var tab = document.createElement("button");
      tab.className = "preview-tab" + (name === state.activePreviewTab ? " active" : "");
      tab.textContent = p ? p.display_name : name;
      tab.addEventListener("click", function() {
        state.activePreviewTab = name;
        updatePreview();
      });
      previewTabs.appendChild(tab);
    });

    renderPreviewPost(state.activePreviewTab);
  }

  function renderPreviewPost(platformName) {
    var meta = PLATFORM_META[platformName] || { letter: "?", brandColor: "#6366f1" };
    var p = findPlatform(platformName);
    var displayName = p ? p.display_name : platformName;
    var maxLen = p ? p.max_text_length : null;

    var overrides = collectOverrides();
    var ov = overrides[platformName] || {};
    var text = ov.text || postText.value || "";
    var charLen = text.length;
    var isOver = maxLen && charLen > maxLen;

    // Build media HTML
    var mediaHtml = "";
    if (state.mediaFiles.length > 0) {
      var first = state.mediaFiles[0];
      if (first.media_type === "video") {
        mediaHtml = '<div class="preview-post-media"><video src="' + first.localUrl + '" controls muted style="width:100%;max-height:240px;"></video></div>';
      } else {
        mediaHtml = '<div class="preview-post-media"><img src="' + first.localUrl + '" alt="preview" /></div>';
      }
    }

    // YouTube special preview
    if (platformName === "youtube") {
      var title = ov.title || "Untitled Video";
      var desc = ov.description || text;
      var tagsArr = ov.tags || [];
      var tagsHtml = tagsArr.map(function(t) {
        return '<span style="display:inline-block;background:#f1f5f9;padding:2px 8px;border-radius:4px;font-size:.72rem;margin:2px;">#' + escHtml(t) + '</span>';
      }).join(" ");

      var ytMedia = "";
      if (state.mediaFiles.length > 0) {
        var f = state.mediaFiles[0];
        ytMedia = '<div class="preview-post-media">' +
          (f.media_type === "video"
            ? '<video src="' + f.localUrl + '" controls muted style="width:100%;max-height:240px;"></video>'
            : '<img src="' + f.localUrl + '" alt="thumbnail" />')
          + '</div>';
      }

      previewBody.innerHTML =
        '<div class="preview-post">' +
          ytMedia +
          '<div style="padding:12px;">' +
            '<div style="font-weight:700;font-size:.95rem;margin-bottom:4px;">' + escHtml(title) + '</div>' +
            '<div style="font-size:.8rem;color:#64748b;margin-bottom:8px;">0 views &middot; Just now</div>' +
            '<div style="font-size:.85rem;line-height:1.5;white-space:pre-wrap;">' + escHtml(desc).slice(0, 200) + (desc.length > 200 ? "..." : "") + '</div>' +
            (tagsHtml ? '<div style="margin-top:8px;">' + tagsHtml + '</div>' : "") +
          '</div>' +
        '</div>';
      return;
    }

    // Generic social post preview
    previewBody.innerHTML =
      '<div class="preview-post">' +
        '<div class="preview-post-header">' +
          '<div class="preview-post-avatar" style="background:' + meta.brandColor + '">' + meta.letter + '</div>' +
          '<div>' +
            '<div class="preview-post-name">Your Name</div>' +
            '<div class="preview-post-handle">' + escHtml(displayName) + ' &middot; Just now</div>' +
          '</div>' +
        '</div>' +
        '<div class="preview-post-text">' + (escHtml(text) || '<span style="color:#94a3b8;">Your post text will appear here...</span>') + '</div>' +
        mediaHtml +
        '<div class="preview-post-footer">' +
          '<span>&#9825; Like</span>' +
          '<span>&#128172; Comment</span>' +
          '<span>&#8634; Share</span>' +
        '</div>' +
      '</div>' +
      (maxLen ? '<div class="preview-char-info' + (isOver ? " over" : "") + '">' + charLen + ' / ' + maxLen + ' characters' + (isOver ? " (over limit!)" : "") + '</div>' : "");
  }

  // ─── Publish ───
  async function publish(dryRun) {
    console.log("[SocialPoster] publish() called, dryRun=" + dryRun);
    console.log("[SocialPoster] selectedPlatforms:", state.selectedPlatforms);
    console.log("[SocialPoster] text length:", postText.value.length, "media count:", state.mediaFiles.length);

    if (state.selectedPlatforms.length === 0) {
      toast("Please select at least one platform", "error");
      return;
    }
    if (!postText.value.trim() && state.mediaFiles.length === 0) {
      toast("Please add some content or media", "error");
      return;
    }

    // Show loading
    loadingText.textContent = dryRun ? "Running validation..." : "Publishing to platforms...";
    loadingOverlay.style.display = "flex";

    // Disable buttons
    btnPublish.disabled = true;
    btnDryRun.disabled = true;

    var payload = {
      text: postText.value,
      platforms: state.selectedPlatforms,
      media: state.mediaFiles.map(function(m) {
        return { path: m.path, media_type: m.media_type };
      }),
      overrides: collectOverrides(),
      dry_run: dryRun,
    };

    console.log("[SocialPoster] Sending payload:", JSON.stringify(payload));

    try {
      var resp = await apiFetch("/api/post", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      console.log("[SocialPoster] Response status:", resp.status);
      var data = await resp.json();
      console.log("[SocialPoster] Response data:", data);

      if (data.error) {
        toast(data.error, "error");
        return;
      }

      renderResults(data.results, dryRun);

      var allOk = true;
      for (var i = 0; i < data.results.length; i++) {
        if (!data.results[i].success) { allOk = false; break; }
      }
      toast(
        dryRun ? "Dry run complete!" : "Published!",
        allOk ? "success" : "info"
      );
    } catch (e) {
      console.error("[SocialPoster] Publish error:", e);
      toast("Request failed: " + e.message, "error");
    } finally {
      // Always hide loading and re-enable buttons
      loadingOverlay.style.display = "none";
      btnPublish.disabled = false;
      btnDryRun.disabled = false;
    }
  }

  // ─── Render Results ───
  function renderResults(results, dryRun) {
    resultsCard.style.display = "block";
    resultsBody.innerHTML = "";

    for (var i = 0; i < results.length; i++) {
      var r = results[i];
      var meta = PLATFORM_META[r.platform] || { letter: "?", brandColor: "#999" };
      var isOk = r.success;
      var detail;
      if (isOk) {
        if (r.post_url) {
          detail = '<a href="' + escAttr(r.post_url) + '" target="_blank">' + escHtml(r.post_url) + '</a>';
        } else {
          detail = dryRun ? "Validation passed" : "Posted successfully";
        }
      } else {
        detail = escHtml(r.error || "Unknown error");
      }

      var badge = '<span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:' +
        meta.brandColor + ';color:#fff;text-align:center;font-size:10px;font-weight:700;line-height:20px;margin-right:8px;">' +
        meta.letter + '</span>';

      resultsBody.innerHTML +=
        '<div class="result-item">' +
          '<div class="result-icon ' + (isOk ? "success" : "fail") + '">' + (isOk ? "&#10003;" : "&#10007;") + '</div>' +
          '<div class="result-info">' +
            '<div class="result-platform">' + badge + capitalize(r.platform) + '</div>' +
            '<div class="result-detail">' + detail + '</div>' +
          '</div>' +
        '</div>';
    }

    // Scroll results into view
    resultsCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ─── Utilities ───
  function escHtml(str) {
    if (!str) return "";
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function escAttr(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function capitalize(str) {
    if (!str) return "";
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  function findPlatform(name) {
    for (var i = 0; i < state.platforms.length; i++) {
      if (state.platforms[i].name === name) return state.platforms[i];
    }
    return null;
  }

  function toast(message, type) {
    type = type || "info";
    console.log("[SocialPoster] Toast [" + type + "]:", message);
    var el = document.createElement("div");
    el.className = "toast " + type;
    var icons = { success: "&#10003;", error: "&#10007;", info: "&#8505;" };
    el.innerHTML = '<span>' + (icons[type] || "") + '</span> ' + escHtml(message);
    toastContainer.appendChild(el);
    setTimeout(function() {
      el.style.transition = "opacity 0.3s";
      el.style.opacity = "0";
      setTimeout(function() { el.remove(); }, 300);
    }, 4000);
  }

  // ─── AI Features ───
  function initAI() {
    btnAIGenerate = document.getElementById("btn-ai-generate");
    btnAIOptimize = document.getElementById("btn-ai-optimize");
    aiPromptRow   = document.getElementById("ai-prompt-row");
    aiTopicInput  = document.getElementById("ai-topic-input");
    btnAISubmit   = document.getElementById("btn-ai-submit");
    btnAICancel   = document.getElementById("btn-ai-cancel");
    aiStructuredForm = document.getElementById("ai-structured-form");
    aiResultsPanel = document.getElementById("ai-results-panel");

    if (!btnAIGenerate) return;

    btnAIGenerate.addEventListener("click", toggleAIStructuredForm);
    btnAIOptimize.addEventListener("click", optimizeAllPlatforms);
    btnAISubmit.addEventListener("click", doAIGenerate);
    btnAICancel.addEventListener("click", function () {
      aiPromptRow.style.display = "none";
      aiTopicInput.value = "";
    });
    aiTopicInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); doAIGenerate(); }
    });

    // Structured form
    var btnStructSubmit = document.getElementById("btn-ai-struct-submit");
    var btnStructCancel = document.getElementById("btn-ai-struct-cancel");
    var btnResultsClose = document.getElementById("btn-ai-results-close");
    if (btnStructSubmit) btnStructSubmit.addEventListener("click", doAIStructuredGenerate);
    if (btnStructCancel) btnStructCancel.addEventListener("click", function () {
      aiStructuredForm.style.display = "none";
    });
    if (btnResultsClose) btnResultsClose.addEventListener("click", function () {
      aiResultsPanel.style.display = "none";
    });
    var structTopic = document.getElementById("ai-struct-topic");
    if (structTopic) structTopic.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); doAIStructuredGenerate(); }
    });
  }

  function toggleAIPrompt() {
    var visible = aiPromptRow.style.display !== "none";
    aiPromptRow.style.display = visible ? "none" : "flex";
    if (!visible) aiTopicInput.focus();
  }

  function toggleAIStructuredForm() {
    if (!aiStructuredForm) { toggleAIPrompt(); return; }
    var visible = aiStructuredForm.style.display !== "none";
    aiStructuredForm.style.display = visible ? "none" : "block";
    aiPromptRow.style.display = "none";
    if (!visible) {
      var topicInput = document.getElementById("ai-struct-topic");
      if (topicInput) topicInput.focus();
    }
  }

  async function doAIStructuredGenerate() {
    var topic = (document.getElementById("ai-struct-topic").value || "").trim();
    if (!topic) { toast("Enter a topic first", "info"); return; }

    var audience = document.getElementById("ai-struct-audience").value;
    var goal = document.getElementById("ai-struct-goal").value;
    var tone = document.getElementById("ai-struct-tone").value;

    var btn = document.getElementById("btn-ai-struct-submit");
    btn.disabled = true;
    btn.textContent = "Generating...";
    try {
      var aiSel = getAISelection();
      var resp = await apiFetch("/api/ai/generate-structured", {
        method: "POST",
        body: JSON.stringify({
          topic: topic,
          platforms: state.selectedPlatforms,
          audience: audience,
          goal: goal,
          tone: tone,
          provider: aiSel.provider,
          model: aiSel.model,
          temperature: aiSel.temperature,
        }),
      });
      var data = await resp.json();
      if (data.error) { toast(data.error, "error"); return; }

      // Set the caption as post text
      if (data.caption) {
        postText.value = data.caption;
        updateCharCounter();
        updatePreview();
        autoFillYouTube();
      }

      showAIResults(data);
      aiStructuredForm.style.display = "none";
      toast("Structured content generated!", "success");
    } catch (e) {
      toast("AI generate failed: " + e.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Generate Content";
    }
  }

  function showAIResults(data) {
    if (!aiResultsPanel) return;
    var body = document.getElementById("ai-results-body");
    var html = "";

    if (data.hashtags && data.hashtags.length) {
      html += '<div class="ai-result-section"><label>Hashtags</label><div class="ai-tag-list">';
      for (var i = 0; i < data.hashtags.length; i++) {
        html += '<span class="ai-tag">' + escHtml(data.hashtags[i]) + '</span>';
      }
      html += '</div><button type="button" class="btn btn-outline btn-sm ai-add-btn" data-action="hashtags">Add to post</button></div>';
    }

    if (data.image_idea) {
      html += '<div class="ai-result-section"><label>Image Idea</label><p class="ai-result-text">' + escHtml(data.image_idea) + '</p></div>';
    }

    if (data.cta) {
      html += '<div class="ai-result-section"><label>Call to Action</label><p class="ai-result-text">' + escHtml(data.cta) + '</p><button type="button" class="btn btn-outline btn-sm ai-add-btn" data-action="cta">Add to post</button></div>';
    }

    body.innerHTML = html;
    aiResultsPanel.style.display = "block";

    // Bind "Add to post" buttons
    body.querySelectorAll(".ai-add-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var action = this.dataset.action;
        var current = postText.value.trim();
        if (action === "hashtags" && data.hashtags) {
          postText.value = current + (current ? "\n\n" : "") + data.hashtags.join(" ");
        } else if (action === "cta" && data.cta) {
          postText.value = current + (current ? "\n\n" : "") + data.cta;
        }
        updateCharCounter();
        updatePreview();
        toast("Added to post!", "success");
      });
    });
  }

  async function doAIGenerate() {
    var topic = aiTopicInput.value.trim();
    if (!topic) { toast("Enter a topic first", "info"); return; }

    btnAISubmit.disabled = true;
    btnAISubmit.textContent = "...";
    try {
      var aiSel = getAISelection();
      var resp = await apiFetch("/api/ai/generate", {
        method: "POST",
        body: JSON.stringify({ topic: topic, platforms: state.selectedPlatforms, provider: aiSel.provider, model: aiSel.model, temperature: aiSel.temperature }),
      });
      var data = await resp.json();
      if (data.error) { toast(data.error, "error"); return; }
      postText.value = data.text;
      updateCharCounter();
      updatePreview();
      autoFillYouTube();
      aiPromptRow.style.display = "none";
      aiTopicInput.value = "";
      toast("Content generated!", "success");
    } catch (e) {
      toast("AI generate failed: " + e.message, "error");
    } finally {
      btnAISubmit.disabled = false;
      btnAISubmit.textContent = "Go";
    }
  }

  async function optimizeAllPlatforms() {
    var text = postText.value.trim();
    if (!text) { toast("Write some text first", "info"); return; }
    if (state.selectedPlatforms.length === 0) { toast("Select at least one platform", "info"); return; }

    btnAIOptimize.disabled = true;
    btnAIOptimize.textContent = "Optimizing...";
    try {
      var aiSel = getAISelection();
      var resp = await apiFetch("/api/ai/optimize", {
        method: "POST",
        body: JSON.stringify({ text: text, platforms: state.selectedPlatforms, provider: aiSel.provider, model: aiSel.model, temperature: aiSel.temperature }),
      });
      var data = await resp.json();
      if (data.error) { toast(data.error, "error"); return; }

      // Fill each platform's override text field
      var optimized = data.optimized || {};
      for (var pname in optimized) {
        var textField = overridesContainer.querySelector(
          'textarea[data-platform="' + pname + '"][data-field="text"]'
        );
        // For YouTube, try the description field instead
        if (!textField && pname === "youtube") {
          textField = overridesContainer.querySelector(
            'textarea[data-platform="youtube"][data-field="description"]'
          );
        }
        if (textField) {
          textField.value = optimized[pname];
          // Prevent auto-fill from overwriting AI-optimized content
          textField.dataset.userEdited = "1";
          // Open the override section so the user can see it
          var header = overridesContainer.querySelector('.override-header[data-toggle="' + pname + '"]');
          var body = document.getElementById("override-body-" + pname);
          if (header && body && !body.classList.contains("open")) {
            header.classList.add("open");
            body.classList.add("open");
          }
        }
      }
      updatePreview();
      toast("Text optimized for " + Object.keys(optimized).length + " platform(s)!", "success");
    } catch (e) {
      toast("AI optimize failed: " + e.message, "error");
    } finally {
      btnAIOptimize.disabled = false;
      btnAIOptimize.textContent = "Optimize All";
    }
  }

  async function suggestHashtags(platform) {
    var textField = overridesContainer.querySelector(
      'textarea[data-platform="' + platform + '"][data-field="text"]'
    );
    if (!textField && platform === "youtube") {
      textField = overridesContainer.querySelector(
        'textarea[data-platform="youtube"][data-field="description"]'
      );
    }
    var text = (textField ? textField.value : "") || postText.value;
    if (!text.trim()) { toast("No text to analyze for hashtags", "info"); return; }

    var btn = overridesContainer.querySelector('.ai-hashtag-btn[data-platform="' + platform + '"]');
    if (btn) { btn.disabled = true; btn.textContent = "..."; }

    try {
      var aiSel = getAISelection();
      var resp = await apiFetch("/api/ai/hashtags", {
        method: "POST",
        body: JSON.stringify({ text: text.trim(), platform: platform, provider: aiSel.provider, model: aiSel.model, temperature: aiSel.temperature }),
      });
      var data = await resp.json();
      if (data.error) { toast(data.error, "error"); return; }

      var tags = (data.hashtags || []).join(" ");
      if (textField && tags) {
        textField.value = textField.value.trim() + (textField.value.trim() ? "\n" : "") + tags;
        // Prevent auto-fill from overwriting AI-added hashtags
        textField.dataset.userEdited = "1";
        updatePreview();
      }
      toast("Hashtags added!", "success");
    } catch (e) {
      toast("Hashtag suggestion failed: " + e.message, "error");
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "# Suggest Hashtags"; }
    }
  }

  function autoFillYouTube() {
    if (state.selectedPlatforms.indexOf("youtube") < 0) return;
    var mainText = postText.value.trim();

    var descField = overridesContainer.querySelector('textarea[data-platform="youtube"][data-field="description"]');

    // Bind user-edit detection once per field lifecycle
    if (descField && !descField.dataset.autoFillBound) {
      descField.dataset.autoFillBound = "1";
      descField.addEventListener("input", function() { descField.dataset.userEdited = "1"; });
    }

    if (!mainText) return;

    // Keep syncing description from full text until user manually edits it
    if (descField && !descField.dataset.userEdited) {
      descField.value = mainText;
    }
  }

  function bindTagsBulk() {
    var textarea = document.getElementById("yt-tags-textarea");
    if (textarea) {
      textarea.addEventListener("input", updateTagsCount);
      updateTagsCount();
    }
  }

  function bindRecipientsBulk() {
    var fileInput = document.getElementById("wa-recipients-file");
    var textarea = document.getElementById("wa-recipients-textarea");
    if (fileInput) {
      fileInput.addEventListener("change", handleRecipientsFileUpload);
    }
    if (textarea) {
      textarea.addEventListener("input", updateRecipientsCount);
      updateRecipientsCount();
    }
  }

  function bindHashtagButtons() {
    var btns = overridesContainer.querySelectorAll(".ai-hashtag-btn");
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener("click", (function (pname) {
        return function () { suggestHashtags(pname); };
      })(btns[i].getAttribute("data-platform")));
    }
  }

  // ─── Hamburger Menu Toggle ───
  function initHamburger() {
    var btn = document.getElementById("hamburger-btn");
    var nav = document.getElementById("topbar-nav");
    if (!btn || !nav) return;
    btn.addEventListener("click", function () {
      btn.classList.toggle("open");
      nav.classList.toggle("open");
    });
    // Close when clicking a nav link
    var links = nav.querySelectorAll("a");
    for (var i = 0; i < links.length; i++) {
      links[i].addEventListener("click", function () {
        btn.classList.remove("open");
        nav.classList.remove("open");
      });
    }
  }

  // ─── Camera Button Handler ───
  function initCamera() {
    var cameraBtn = document.getElementById("camera-btn");
    var cameraInput = document.getElementById("camera-input");
    if (!cameraBtn || !cameraInput) return;

    // Show camera button on mobile
    var isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) || isCapacitor;
    if (isMobile) {
      cameraBtn.style.display = "inline-flex";
    }

    cameraBtn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (isCapacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Camera) {
        // Use Capacitor Camera plugin
        window.Capacitor.Plugins.Camera.getPhoto({
          quality: 90,
          resultType: "uri",
        }).then(function (photo) {
          toast("Photo captured", "success");
          // Fetch the photo URI and upload it
          fetch(photo.webPath).then(function (r) { return r.blob(); }).then(function (blob) {
            var file = new File([blob], "camera_photo.jpg", { type: "image/jpeg" });
            handleFiles([file]);
          });
        }).catch(function (err) {
          console.warn("[SocialPoster] Camera error:", err);
        });
      } else {
        cameraInput.click();
      }
    });
    cameraInput.addEventListener("change", function () {
      if (cameraInput.files && cameraInput.files.length > 0) {
        handleFiles(cameraInput.files);
      }
    });
  }

  // ─── Mobile Publish Button ───
  function initMobilePublish() {
    var mobileBtn = document.getElementById("mobile-publish-btn");
    if (!mobileBtn) return;
    mobileBtn.addEventListener("click", function () {
      publish(false);
    });
  }

  // ─── Pull-to-Refresh ───
  function initPullToRefresh() {
    var startY = 0;
    var pulling = false;
    var indicator = document.createElement("div");
    indicator.className = "pull-to-refresh-indicator";
    indicator.innerHTML = '<div class="ptr-spinner"></div> Refreshing...';
    document.body.appendChild(indicator);

    document.addEventListener("touchstart", function (e) {
      if (window.scrollY === 0 && e.touches.length === 1) {
        startY = e.touches[0].clientY;
        pulling = true;
      }
    }, { passive: true });

    document.addEventListener("touchmove", function (e) {
      if (!pulling) return;
      var dy = e.touches[0].clientY - startY;
      if (dy > 80 && window.scrollY === 0) {
        indicator.classList.add("visible");
      }
    }, { passive: true });

    document.addEventListener("touchend", function () {
      if (indicator.classList.contains("visible")) {
        indicator.classList.remove("visible");
        location.reload();
      }
      pulling = false;
    }, { passive: true });
  }

  // ─── Capacitor Deep Link Handler ───
  function initCapacitor() {
    if (!isCapacitor) return;
    console.log("[SocialPoster] Running in Capacitor");

    // Configure StatusBar if available
    if (window.Capacitor.Plugins && window.Capacitor.Plugins.StatusBar) {
      window.Capacitor.Plugins.StatusBar.setBackgroundColor({ color: "#6366f1" });
      window.Capacitor.Plugins.StatusBar.setStyle({ style: "LIGHT" });
    }

    // Handle deep links (socialposter://oauth/complete)
    if (window.Capacitor.Plugins && window.Capacitor.Plugins.App) {
      window.Capacitor.Plugins.App.addListener("appUrlOpen", function (data) {
        console.log("[SocialPoster] Deep link:", data.url);
        if (data.url && data.url.indexOf("socialposter://oauth/complete") === 0) {
          window.location.href = "/connections";
        }
      });
    }
  }

  // ─── Boot ───
  document.addEventListener("DOMContentLoaded", function () {
    initHamburger();
    initMobilePublish();
    initPullToRefresh();
    initCapacitor();
    // Only run main init on pages that have the compose UI
    if (document.getElementById("platform-grid")) {
      init();
      initCamera();
    }
  });

})();
