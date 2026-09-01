/*
 * pd-streamdeck music player -- runs inside an OBS browser source.
 *
 * The server decides *what* plays; this page just plays it, crossfading
 * between two audio elements through Web Audio gain nodes so mood changes
 * don't hard-cut on stream.
 *
 * It reports back over the same socket (playing / progress / ended / error)
 * so the tablet can show what's actually happening rather than what was
 * merely requested.
 */

(function () {
  "use strict";

  var params = new URLSearchParams(location.search);
  var TOKEN = params.get("token") || "";
  var DEBUG = params.get("debug") === "1";

  var ctx = null;
  var decks = [];
  var active = 0;
  var volume = 0.6;
  var defaultFade = 2.0;
  var playToken = 0;         // guards against a stale deck reporting 'ended'
  var socket = null;
  var backoff = 1000;
  var progressTimer = null;

  // -- debug panel ---------------------------------------------------------

  var dom = {};
  if (DEBUG) {
    document.getElementById("debug").classList.remove("hidden");
    ["socket", "state", "mood", "track", "volume", "ctx"].forEach(function (k) {
      dom[k] = document.getElementById("d-" + k);
    });
  }

  function debug(key, value, cls) {
    if (!DEBUG || !dom[key]) return;
    dom[key].textContent = value;
    dom[key].className = cls || "";
  }

  // -- audio ---------------------------------------------------------------

  function makeDeck() {
    var el = new Audio();
    el.crossOrigin = "anonymous";
    el.preload = "auto";
    var source = ctx.createMediaElementSource(el);
    var gain = ctx.createGain();
    gain.gain.value = 0;
    source.connect(gain);
    gain.connect(ctx.destination);
    return { el: el, gain: gain, token: 0 };
  }

  function ensureAudio() {
    if (ctx) return;
    var AudioCtx = window.AudioContext || window.webkitAudioContext;
    ctx = new AudioCtx();
    decks = [makeDeck(), makeDeck()];

    decks.forEach(function (deck, index) {
      deck.el.addEventListener("ended", function () {
        // Only the deck that is currently in front gets to say "ended".
        if (index === active && deck.token === playToken) {
          send({ event: "ended", track: deck.el.src });
        }
      });
      deck.el.addEventListener("error", function () {
        if (index === active) {
          send({ event: "error", message: "audio element failed to load" });
          debug("state", "load error", "error");
        }
      });
    });
  }

  function resumeContext() {
    if (!ctx) return Promise.resolve();
    debug("ctx", ctx.state, ctx.state === "running" ? "ok" : "warn");
    if (ctx.state === "suspended") {
      return ctx.resume().then(function () {
        debug("ctx", ctx.state, "ok");
      }).catch(function () { /* OBS allows autoplay; nothing else to try */ });
    }
    return Promise.resolve();
  }

  function ramp(gain, target, seconds) {
    var now = ctx.currentTime;
    // Anchor at the current value first, or the ramp starts from whatever
    // the last scheduled value was and jumps.
    gain.gain.cancelScheduledValues(now);
    gain.gain.setValueAtTime(gain.gain.value, now);
    if (seconds > 0) {
      gain.gain.linearRampToValueAtTime(target, now + seconds);
    } else {
      gain.gain.setValueAtTime(target, now);
    }
  }

  function play(message) {
    ensureAudio();
    var fade = typeof message.fade === "number" ? message.fade : defaultFade;
    if (typeof message.volume === "number") volume = message.volume;

    var outgoing = decks[active];
    var next = 1 - active;
    var incoming = decks[next];

    playToken += 1;
    incoming.token = playToken;

    var url = message.url;
    if (TOKEN) {
      url += (url.indexOf("?") === -1 ? "?" : "&") + "token=" + encodeURIComponent(TOKEN);
    }

    incoming.el.src = url;
    incoming.gain.gain.cancelScheduledValues(ctx.currentTime);
    incoming.gain.gain.setValueAtTime(0, ctx.currentTime);

    resumeContext().then(function () {
      return incoming.el.play();
    }).then(function () {
      ramp(incoming.gain, volume, fade);
      ramp(outgoing.gain, 0, fade);
      window.setTimeout(function () {
        if (decks[active] !== outgoing) outgoing.el.pause();
      }, Math.max(0, fade * 1000) + 50);

      active = next;
      debug("state", "playing", "ok");
      debug("mood", message.mood || "-");
      debug("track", message.track || "-");
      debug("volume", volume.toFixed(2));

      send({
        event: "playing",
        track: message.track,
        mood: message.mood,
        duration: isFinite(incoming.el.duration) ? incoming.el.duration : 0
      });
      startProgress();
    }).catch(function (err) {
      debug("state", "play failed", "error");
      send({ event: "error", message: String(err) });
    });
  }

  function stop(message) {
    if (!ctx) return;
    var fade = typeof message.fade === "number" ? message.fade : defaultFade;
    playToken += 1;                   // any pending 'ended' is now stale
    var current = decks[active];
    ramp(current.gain, 0, fade);
    window.setTimeout(function () {
      current.el.pause();
    }, Math.max(0, fade * 1000) + 50);
    stopProgress();
    debug("state", "stopped");
    debug("mood", "-");
    debug("track", "-");
  }

  function setVolume(message) {
    volume = message.volume;
    debug("volume", volume.toFixed(2));
    if (!ctx) return;
    ramp(decks[active].gain, volume, message.fade || 0.25);
  }

  // -- progress reporting --------------------------------------------------

  function startProgress() {
    stopProgress();
    progressTimer = window.setInterval(function () {
      var el = decks[active].el;
      if (el.paused) return;
      send({
        event: "progress",
        position: el.currentTime || 0,
        duration: isFinite(el.duration) ? el.duration : 0
      });
    }, 1000);
  }

  function stopProgress() {
    if (progressTimer) {
      window.clearInterval(progressTimer);
      progressTimer = null;
    }
  }

  // -- socket --------------------------------------------------------------

  function send(message) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(message));
    }
  }

  function connect() {
    var scheme = location.protocol === "https:" ? "wss" : "ws";
    var url = scheme + "://" + location.host + "/ws/music";
    if (TOKEN) url += "?token=" + encodeURIComponent(TOKEN);

    socket = new WebSocket(url);
    debug("socket", "connecting", "warn");

    socket.onopen = function () {
      backoff = 1000;
      debug("socket", "connected", "ok");
      ensureAudio();
      resumeContext();
    };

    socket.onmessage = function (event) {
      var message;
      try {
        message = JSON.parse(event.data);
      } catch (err) {
        return;
      }

      switch (message.action) {
        case "play":   play(message); break;
        case "stop":   stop(message); break;
        case "volume": setVolume(message); break;
        case "sync":
          if (typeof message.volume === "number") volume = message.volume;
          if (typeof message.fade === "number") defaultFade = message.fade;
          debug("volume", volume.toFixed(2));
          break;
      }
    };

    socket.onclose = function (event) {
      stopProgress();
      debug("socket", event.code === 4401 ? "bad token" : "reconnecting",
            event.code === 4401 ? "error" : "warn");
      if (event.code === 4401) return;    // a retry won't fix the token
      window.setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 15000);
    };

    socket.onerror = function () {
      debug("socket", "error", "error");
    };
  }

  connect();
})();
