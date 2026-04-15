/* Content Calendar – vanilla JS IIFE */
(function () {
  "use strict";

  var now = new Date();
  var currentYear = now.getFullYear();
  var currentMonth = now.getMonth() + 1; // 1-based
  var events = [];

  var MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];

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

  function daysInMonth(year, month) {
    return new Date(year, month, 0).getDate();
  }

  function firstDayOfWeek(year, month) {
    return new Date(year, month - 1, 1).getDay(); // 0=Sun
  }

  function renderGrid() {
    var grid = document.getElementById("calendar-grid");
    var title = document.getElementById("cal-title");
    title.textContent = MONTH_NAMES[currentMonth] + " " + currentYear;

    var totalDays = daysInMonth(currentYear, currentMonth);
    var startDay = firstDayOfWeek(currentYear, currentMonth);
    var today = new Date();
    var todayStr = today.getFullYear() + "-" +
      String(today.getMonth() + 1).padStart(2, "0") + "-" +
      String(today.getDate()).padStart(2, "0");

    // Build event map: date -> events[]
    var eventMap = {};
    for (var i = 0; i < events.length; i++) {
      var e = events[i];
      if (!eventMap[e.date]) eventMap[e.date] = [];
      eventMap[e.date].push(e);
    }

    var html = "";
    // Empty cells before first day
    for (var d = 0; d < startDay; d++) {
      html += '<div class="cal-cell cal-empty"></div>';
    }
    for (var day = 1; day <= totalDays; day++) {
      var dateStr = currentYear + "-" +
        String(currentMonth).padStart(2, "0") + "-" +
        String(day).padStart(2, "0");
      var isToday = dateStr === todayStr ? " cal-today" : "";
      var dayEvents = eventMap[dateStr] || [];

      html += '<div class="cal-cell' + isToday + '" data-date="' + dateStr + '">';
      html += '<div class="cal-day-num">' + day + '</div>';

      // Show up to 3 event chips
      for (var j = 0; j < Math.min(dayEvents.length, 3); j++) {
        var ev = dayEvents[j];
        var chipClass = "cal-event-chip";
        if (ev.type === "scheduled") chipClass += " cal-scheduled";
        else if (ev.success === true) chipClass += " cal-success";
        else if (ev.success === false) chipClass += " cal-failed";
        var label = ev.type === "scheduled"
          ? escHtml(ev.name || ev.platform)
          : escHtml(capitalize(ev.platform));
        html += '<div class="' + chipClass + '">' + label + '</div>';
      }
      if (dayEvents.length > 3) {
        html += '<div class="cal-more">+' + (dayEvents.length - 3) + ' more</div>';
      }
      html += '</div>';
    }
    grid.innerHTML = html;

    // Click handlers
    grid.querySelectorAll(".cal-cell:not(.cal-empty)").forEach(function (cell) {
      cell.addEventListener("click", function () {
        showDayModal(this.dataset.date, eventMap[this.dataset.date] || []);
      });
    });
  }

  function showDayModal(dateStr, dayEvents) {
    var modal = document.getElementById("day-modal");
    document.getElementById("modal-date-title").textContent = dateStr;

    var body = document.getElementById("modal-events");
    if (!dayEvents.length) {
      body.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;">No events on this day.</p>';
    } else {
      var html = "";
      for (var i = 0; i < dayEvents.length; i++) {
        var ev = dayEvents[i];
        var badgeClass = ev.type === "scheduled" ? "badge-scheduled" :
          (ev.success ? "badge-success" : "badge-failed");
        var statusLabel = ev.type === "scheduled" ? "Scheduled" :
          (ev.success ? "Published" : "Failed");
        html += '<div class="modal-event-item">';
        html += '<span class="draft-status-badge ' + badgeClass + '">' + statusLabel + '</span> ';
        html += '<strong>' + escHtml(capitalize(ev.platform)) + '</strong> ';
        if (ev.time) html += '<span style="color:var(--text-muted);font-size:.8rem;">' + escHtml(ev.time) + '</span>';
        html += '<div style="font-size:.85rem;color:var(--text-secondary);margin-top:4px;">' + escHtml(ev.text) + '</div>';
        if (ev.post_url) {
          html += '<a href="' + escHtml(ev.post_url) + '" target="_blank" style="font-size:.8rem;">View post</a>';
        }
        html += '</div>';
      }
      body.innerHTML = html;
    }
    modal.style.display = "flex";
  }

  function loadEvents() {
    apiFetch("/api/calendar/events?year=" + currentYear + "&month=" + currentMonth)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        events = data.events || [];
        renderGrid();
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("cal-prev").addEventListener("click", function () {
      currentMonth--;
      if (currentMonth < 1) { currentMonth = 12; currentYear--; }
      loadEvents();
    });
    document.getElementById("cal-next").addEventListener("click", function () {
      currentMonth++;
      if (currentMonth > 12) { currentMonth = 1; currentYear++; }
      loadEvents();
    });
    document.getElementById("modal-close").addEventListener("click", function () {
      document.getElementById("day-modal").style.display = "none";
    });
    document.getElementById("day-modal").addEventListener("click", function (e) {
      if (e.target === this) this.style.display = "none";
    });

    loadEvents();
  });
})();
