/*
 * Tablet deck UI.
 *
 * Deliberately dumb: it renders whatever /api/config describes and posts the
 * button's action object back to /api/action. Adding a new action type needs
 * no change in this file.
 *
 * State (which scene is live, what's playing, whether we're recording) comes
 * from /ws/deck, which is fed by OBS's own events -- so switching scenes in
 * the OBS window updates the tablet too.
 */

(function () {
  "use strict";

  var TOKEN_KEY = "pd-streamdeck-token";
  var token = "";
  var config = null;
  var state = null;
  var activePage = 0;
  var socket = null;
  var backoff = 1000;
  var confirmTimer = null;
  var confirmingId = null;
  var toastTimer = null;
  var wakeLock = null;
  var volDragging = false;
  var volSendTimer = null;
  var volPending = null;

  var grid = document.getElementById("grid");
  var tabs = document.getElementById("tabs");
  var toast = document.getElementById("toast");
  var gate = document.getElementById("gate");

  // -- token ---------------------------------------------------------------

  function loadToken() {
    var params = new URLSearchParams(location.search);
    var fromUrl = params.get("token");
    if (fromUrl) {
      // Bookmark the URL with ?token=... once; after that it lives in
      // localStorage and the URL stays clean.
      try { localStorage.setItem(TOKEN_KEY, fromUrl); } catch (e) { /* private mode */ }
      history.replaceState(null, "", location.pathname);
      return fromUrl;
    }
    try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (e) { return ""; }
  }

  function showGate() {
    gate.classList.remove("hidden");
    document.getElementById("gate-input").focus();
  }

  document.getElementById("gate-save").addEventListener("click", function () {
    var value = document.getElementById("gate-input").value.trim();
    if (!value) return;
    try { localStorage.setItem(TOKEN_KEY, value); } catch (e) { /* ignore */ }
    location.reload();
  });

  // -- helpers -------------------------------------------------------------

  function api(path, body) {
    return fetch(path, {
      method: body ? "POST" : "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Deck-Token": token
      },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) {
          throw new Error(data.error || data.detail || ("HTTP " + response.status));
        }
        return data;
      });
    });
  }

  function showToast(message, kind) {
    toast.textContent = message;
    toast.className = kind === "info" ? "info" : "";
    toast.classList.remove("hidden");
    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      toast.classList.add("hidden");
    }, 3200);
  }

  function buzz(ms) {
    if (navigator.vibrate) navigator.vibrate(ms);
  }

  function formatTime(seconds) {
    if (!seconds || !isFinite(seconds)) return "0:00";
    var m = Math.floor(seconds / 60);
    var s = Math.floor(seconds % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  // -- rendering -----------------------------------------------------------

  function renderTabs() {
    tabs.innerHTML = "";
    config.pages.forEach(function (page, index) {
      var button = document.createElement("button");
      button.textContent = page.name;
      if (index === activePage) button.className = "active";
      button.addEventListener("click", function () {
        activePage = index;
        renderTabs();
        renderGrid();
      });
      tabs.appendChild(button);
    });
  }

  function renderGrid() {
    var page = config.pages[activePage];
    if (!page) return;

    grid.style.gridTemplateColumns = "repeat(" + (page.columns || 4) + ", 1fr)";
    grid.innerHTML = "";

    page.buttons.forEach(function (button) {
      var el = document.createElement("button");
      el.className = "btn " + button.color;
      el.dataset.id = button.id;

      var icon = document.createElement("span");
      icon.className = "icon";
      icon.textContent = button.icon || "";

      var label = document.createElement("span");
      label.className = "label";
      label.textContent = button.label;

      el.appendChild(icon);
      el.appendChild(label);

      if (button.problem) {
        el.classList.add("broken");
        el.title = button.problem;
      }

      el.addEventListener("click", function () { press(button, el); });
      grid.appendChild(el);
    });

    applyState();
  }

  /* Highlight whichever buttons match reality. */
  function applyState() {
    if (!state) return;
    var page = config.pages[activePage];
    if (!page) return;

    var obs = state.obs || {};
    var music = state.music || {};

    Array.prototype.forEach.call(grid.children, function (el, index) {
      var button = page.buttons[index];
      if (!button) return;

      el.classList.remove("on", "live");
      var p = button.params || {};

      if (button.action === "obs.scene") {
        if (p.scene && p.scene === obs.current_scene) el.classList.add("on");
      } else if (button.action === "music.mood") {
        if (music.playing && p.mood === music.mood) el.classList.add("on");
      } else if (button.indicator === "mute") {
        if (obs.muted && obs.muted[p.input]) el.classList.add("on");
      } else if (button.indicator === "record") {
        if (obs.recording) el.classList.add("live");
      } else if (button.indicator === "stream") {
        if (obs.streaming) el.classList.add("live");
      }
    });
  }

  function renderStatus() {
    if (!state) return;

    setDot("dot-obs", state.obs && state.obs.connected);
    setDot("dot-bus", state.bus && state.bus.connected);
    setDot("dot-player", state.music && state.music.page_connected);

    var music = state.music || {};
    var track = document.getElementById("np-track");
    var icon = document.getElementById("np-icon");

    if (music.playing && music.track) {
      track.textContent = music.track;
      track.classList.remove("idle");
      icon.classList.remove("idle");
      document.getElementById("np-mood").textContent = music.mood ? "· " + music.mood : "";
      setScore(music.score);
      document.getElementById("np-time").textContent =
        formatTime(music.position) + " / " + formatTime(music.duration);
      var pct = music.duration ? (music.position / music.duration) * 100 : 0;
      document.getElementById("np-progress").style.width = Math.min(100, pct) + "%";
    } else {
      track.textContent = "No music";
      track.classList.add("idle");
      icon.classList.add("idle");
      document.getElementById("np-mood").textContent = "";
      setScore(0);
      document.getElementById("np-time").textContent = "";
      document.getElementById("np-progress").style.width = "0%";
    }

    // Never yank the slider out from under a thumb that's mid-drag.
    if (!volDragging && typeof music.volume === "number") {
      setVolumeDisplay(Math.round(music.volume * 100));
    }
  }

  // -- track picker --------------------------------------------------------

  /* The picker is the one part of the deck that needs to know the library's
     contents, so it's fetched rather than described by /api/config. Reloaded
     after a rating so the scores shown next to each track stay honest. */
  function loadTracks() {
    return api("/api/music/tracks").then(function (data) {
      var picker = document.getElementById("picker");
      picker.innerHTML = "";

      var placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Pick a track…";
      picker.appendChild(placeholder);

      Object.keys(data.tracks || {}).sort().forEach(function (mood) {
        var group = document.createElement("optgroup");
        group.label = mood;
        data.tracks[mood].forEach(function (track) {
          var option = document.createElement("option");
          // Filenames can't contain a slash, so the first one always splits
          // mood from track cleanly on the way back.
          option.value = mood + "/" + track.name;
          option.textContent = track.score
            ? track.name + "  " + formatScore(track.score)
            : track.name;
          group.appendChild(option);
        });
        picker.appendChild(group);
      });
    }).catch(function (err) {
      showToast("Could not load track list: " + err.message);
    });
  }

  function formatScore(score) {
    return (score > 0 ? "+" : "") + score;
  }

  function initPicker() {
    document.getElementById("picker").addEventListener("change", function () {
      var value = this.value;
      // Snap back to the placeholder straight away: the select shows what you
      // are about to play, not what is playing -- the now-playing line owns
      // that, and it updates itself when the track actually starts.
      this.selectedIndex = 0;
      if (!value) return;

      var split = value.indexOf("/");
      buzz(15);
      api("/api/music/play", {
        mood: value.slice(0, split),
        track: value.slice(split + 1)
      }).catch(function (err) {
        showToast(err.message);
        buzz([50, 80, 50]);
      });
    });
  }

  // -- volume slider -------------------------------------------------------

  function setScore(score) {
    var el = document.getElementById("np-score");
    if (!score) {
      el.classList.add("hidden");
      return;
    }
    el.textContent = formatScore(score);
    el.className = "np-score " + (score > 0 ? "liked" : "disliked");
  }

  function setVolumeDisplay(percent) {
    document.getElementById("vol").value = percent;
    document.getElementById("vol-pct").textContent = percent + "%";
  }

  /* Dragging fires 'input' continuously. Throttle the network to ~10/s and
     always send the value the finger landed on, so the server ends up in
     sync without a request per pixel. */
  function sendVolume(percent) {
    volPending = percent / 100;
    if (volSendTimer) return;
    volSendTimer = window.setTimeout(function () {
      volSendTimer = null;
      var level = volPending;
      volPending = null;
      api("/api/music/volume", { level: level }).catch(function (err) {
        showToast(err.message);
      });
    }, 100);
  }

  function initVolume() {
    var slider = document.getElementById("vol");

    slider.addEventListener("input", function () {
      var percent = parseInt(slider.value, 10);
      document.getElementById("vol-pct").textContent = percent + "%";
      sendVolume(percent);
    });

    ["pointerdown", "touchstart"].forEach(function (evt) {
      slider.addEventListener(evt, function () { volDragging = true; });
    });

    ["pointerup", "pointercancel", "touchend", "touchcancel", "change"].forEach(
      function (evt) {
        slider.addEventListener(evt, function () {
          volDragging = false;
          // Flush the final position immediately rather than waiting on the
          // throttle, so releasing the thumb is what the server hears last.
          if (volSendTimer) {
            window.clearTimeout(volSendTimer);
            volSendTimer = null;
          }
          api("/api/music/volume", { level: parseInt(slider.value, 10) / 100 })
            .catch(function (err) { showToast(err.message); });
        });
      }
    );
  }

  function setDot(id, up) {
    var el = document.getElementById(id);
    el.className = "dot " + (up ? "up" : "down");
  }

  // -- pressing ------------------------------------------------------------

  function press(button, el) {
    if (button.problem) {
      showToast(button.problem);
      buzz([40, 60, 40]);
      return;
    }

    // Two-tap guard for anything that would be embarrassing to hit by
    // accident, like ending the stream.
    if (button.confirm && confirmingId !== button.id) {
      clearConfirm();
      confirmingId = button.id;
      el.classList.add("confirming");
      buzz(20);
      confirmTimer = window.setTimeout(clearConfirm, 3000);
      return;
    }
    clearConfirm();

    el.classList.add("pending");
    buzz(15);

    api("/api/action", { action: button.action, params: button.params })
      .then(function () {
        el.classList.remove("pending");
        // A rating changes the scores shown in the picker, so refresh it.
        if (button.action === "music.rate") loadTracks();
      })
      .catch(function (err) {
        el.classList.remove("pending");
        showToast(err.message);
        buzz([50, 80, 50]);
      });
  }

  function clearConfirm() {
    if (confirmTimer) window.clearTimeout(confirmTimer);
    confirmTimer = null;
    confirmingId = null;
    Array.prototype.forEach.call(
      grid.querySelectorAll(".confirming"),
      function (el) { el.classList.remove("confirming"); }
    );
  }

  // -- socket --------------------------------------------------------------

  function connect() {
    var scheme = location.protocol === "https:" ? "wss" : "ws";
    var url = scheme + "://" + location.host + "/ws/deck";
    if (token) url += "?token=" + encodeURIComponent(token);

    socket = new WebSocket(url);

    socket.onopen = function () {
      backoff = 1000;
      showToast("Connected", "info");
    };

    socket.onmessage = function (event) {
      var message;
      try { message = JSON.parse(event.data); } catch (e) { return; }

      if (message.type === "hello") {
        config = message.config;
        state = message.state;
        renderTabs();
        renderGrid();
        renderStatus();
      } else if (message.type === "state") {
        state = message.state;
        applyState();
        renderStatus();
      }
    };

    socket.onclose = function (event) {
      if (event.code === 4401) {
        showGate();
        return;
      }
      setDot("dot-obs", false);
      setDot("dot-bus", false);
      setDot("dot-player", false);
      window.setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 10000);
    };
  }

  // Keepalive: some tablet WiFi stacks drop an idle socket without telling
  // either end, and the deck going stale mid-stream is the worst failure.
  window.setInterval(function () {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send("ping");
  }, 20000);

  // -- screen wake ---------------------------------------------------------

  function requestWakeLock() {
    if (!("wakeLock" in navigator)) return;
    navigator.wakeLock.request("screen").then(function (lock) {
      wakeLock = lock;
      lock.addEventListener("release", function () { wakeLock = null; });
    }).catch(function () { /* denied; fall back to the OS setting */ });
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && !wakeLock) requestWakeLock();
  });

  // -- boot ----------------------------------------------------------------

  token = loadToken();
  initVolume();
  initPicker();
  loadTracks();
  requestWakeLock();
  connect();
})();
