/* Your Company Site Diary - client layer for diary.html.
   Shares the Supabase session with the training portal (config.js).
   Crew register on index.html with the office signup code; this page
   only checks the session and links back there if it is missing.

   Backend: Apps Script web app. The two values below are wired at
   deploy time from the values setupSandbox() logs. Never commit real
   values until Owner clears go-live. Sandbox deployment only until
   the Step 1 verification gate passes. */
"use strict";

(function () {
  var EXEC_URL = "https://script.google.com/macros/s/AKfycbymmdIA_aqLNiTstH8xOWShCHcQiuWPN9N39AMSgFy9clIfpFYAAH2HC5EEZyfn5DSK/exec";
  var SECRET = "4ab0b481dd4e4cb89ee0732ab3c1b617c3f93be2db604afe";

  var PROJECTS = [
    "Genius Kids STEM Academy (Katy)"
  ];

  // Mirrors the server caps in Code.gs. The server is the enforcer;
  // these checks just fail fast on the phone before a long upload.
  var MAX_FILE_BYTES = 25 * 1024 * 1024;
  var MAX_TOTAL_BYTES = 30 * 1024 * 1024;
  var MAX_FILES = 12;

  function $(id) { return document.getElementById(id); }
  function setMsg(el, cls, text) { el.className = "msg" + (cls ? " " + cls : ""); el.textContent = text; }

  function gateFail(text) {
    $("gatestatus").textContent = text;
    $("gatenote").hidden = false;
  }

  if (!window.NC_SUPABASE_URL || window.NC_SUPABASE_URL.indexOf("__") === 0) {
    console.error("Portal config missing");
    gateFail("Page configuration is missing. Tell Joseph.");
    return;
  }
  if (!window.supabase) {
    gateFail("Could not load the sign-in library. Check your connection and reload.");
    return;
  }
  var sb = window.supabase.createClient(window.NC_SUPABASE_URL, window.NC_SUPABASE_KEY);
  var USER = null;
  var PENDING_ROW = 0;

  // In-page voice recorder. iOS file inputs cannot record audio, so the
  // page records with MediaRecorder when the browser allows it (needs a
  // secure context: https or localhost). The file input below stays as
  // the fallback path.
  var REC = null;
  var REC_CHUNKS = [];
  var REC_BLOB = null;
  var REC_MIME = "";
  var REC_T0 = 0;

  function recSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  }

  function recPickMime() {
    if (window.MediaRecorder.isTypeSupported("audio/mp4")) return "audio/mp4";
    if (window.MediaRecorder.isTypeSupported("audio/webm")) return "audio/webm";
    return "";
  }

  async function toggleRecord() {
    var btn = $("recbtn");
    var hint = $("rechint");
    hint.hidden = false;
    if (REC && REC.state === "recording") {
      REC.stop();
      return;
    }
    REC_BLOB = null;
    REC_CHUNKS = [];
    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      REC_MIME = recPickMime();
      REC = REC_MIME ? new MediaRecorder(stream, { mimeType: REC_MIME }) : new MediaRecorder(stream);
      REC_MIME = REC.mimeType || REC_MIME || "audio/mp4";
      REC.ondataavailable = function (e) { if (e.data && e.data.size) REC_CHUNKS.push(e.data); };
      REC.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        REC_BLOB = new Blob(REC_CHUNKS, { type: REC_MIME });
        var secs = Math.round((Date.now() - REC_T0) / 1000);
        btn.classList.remove("on");
        btn.textContent = "Record again";
        hint.textContent = "Recorded " + secs + "s. It uploads when you submit the entry.";
      };
      REC_T0 = Date.now();
      REC.start();
      btn.classList.add("on");
      btn.textContent = "Stop recording";
      hint.textContent = "Recording. Tap stop when done.";
    } catch (e) {
      hint.textContent = "Microphone not available. Use the file upload below instead.";
    }
  }

  function recExt() {
    return REC_MIME.indexOf("mp4") >= 0 ? ".m4a" : ".webm";
  }

  function recReset() {
    REC_BLOB = null;
    REC_CHUNKS = [];
    if (recSupported()) {
      $("recbtn").textContent = "Record voice note";
      $("rechint").hidden = true;
    }
  }

  function configured() {
    return EXEC_URL.indexOf("http") === 0 && SECRET.indexOf("REPLACE_") !== 0;
  }

  function init() {
    var sel = $("project");
    PROJECTS.forEach(function (p) {
      var o = document.createElement("option");
      o.textContent = p;
      sel.appendChild(o);
    });
    // Local date parts. valueAsDate works in UTC and would prefill
    // tomorrow for any Houston entry after 7pm, the normal end-of-shift
    // window.
    var now = new Date();
    $("date").value = now.getFullYear() + "-" +
      String(now.getMonth() + 1).padStart(2, "0") + "-" +
      String(now.getDate()).padStart(2, "0");
    $("submitbtn").onclick = submitEntry;
    $("approvebtn").onclick = approve;
    $("signoutbtn").onclick = signOut;
    if (recSupported()) {
      // Recorder available: lead with the record button and tuck the
      // file upload behind a link so the two controls cannot collide
      // (the file picker steals focus and closes the mic permission
      // prompt when both sit side by side).
      $("recbtn").hidden = false;
      $("recbtn").onclick = toggleRecord;
      $("uploadwrap").hidden = true;
      $("showupload").hidden = false;
      $("showupload").onclick = function (e) {
        e.preventDefault();
        $("uploadwrap").hidden = false;
        $("showupload").hidden = true;
      };
    }

    sb.auth.getSession().then(function (r) {
      if (!r.data.session) {
        gateFail("You are not signed in.");
        return;
      }
      USER = r.data.session.user;
      $("authgate").hidden = true;
      $("app").hidden = false;
      $("useremail").textContent = USER.email;
      $("who").hidden = false;
      loadPending();
    }).catch(function () {
      gateFail("Could not check your sign in. Check your connection and reload.");
    });
  }

  async function signOut() {
    await sb.auth.signOut();
    location.href = "index.html?next=diary.html";
  }

  async function loadPending() {
    if (!configured()) return;
    try {
      var r = await fetch(EXEC_URL + "?secret=" + encodeURIComponent(SECRET) +
        "&action=pending&supervisor=" + encodeURIComponent(USER.email));
      var j = await r.json();
      if (j.ok && j.row > 0) {
        PENDING_ROW = j.row;
        $("pendingtext").textContent = j.date + " / " + j.project + " / " + j.weather + "\n" + j.summary;
        $("approvebox").style.display = "block";
      }
    } catch (e) { /* pending feed is optional on a bad connection */ }
  }

  async function approve() {
    var btn = $("approvebtn");
    var msg = $("approvemsg");
    btn.disabled = true;
    setMsg(msg, "", "Sending...");
    try {
      var r = await fetch(EXEC_URL, {
        method: "POST",
        body: JSON.stringify({ secret: SECRET, action: "approve", row: PENDING_ROW, supervisor: USER.email })
      });
      var j = await r.json();
      if (j.ok) {
        $("approvebox").style.display = "none";
      } else {
        setMsg(msg, "bad", "Failed: " + j.error);
        btn.disabled = false;
      }
    } catch (e) {
      setMsg(msg, "bad", "No connection. Try again.");
      btn.disabled = false;
    }
  }

  function checkFile(f, kindLabel) {
    if (f.size > MAX_FILE_BYTES) return f.name + " is over the 25 MB limit.";
    var want = kindLabel === "voice" ? "audio/" : "image/";
    if (f.type.indexOf(want) !== 0) {
      return f.name + " is not " + (kindLabel === "voice" ? "an audio file." : "an image.");
    }
    return "";
  }

  function fileToUpload(f, kind) {
    return new Promise(function (res, rej) {
      var rd = new FileReader();
      rd.onload = function () { res({ name: f.name, mime: f.type, kind: kind, data_b64: rd.result.split(",")[1] }); };
      rd.onerror = function () { rej(new Error("could not read " + f.name)); };
      rd.readAsDataURL(f);
    });
  }

  async function submitEntry() {
    var btn = $("submitbtn");
    var msg = $("msg");
    var body = $("body").value.trim();
    if (!body) { setMsg(msg, "bad", "Write the update first."); return; }
    if (!configured()) {
      setMsg(msg, "bad", "Page is not wired to the backend yet. Tell Joseph.");
      return;
    }

    if (REC && REC.state === "recording") {
      setMsg(msg, "bad", "Stop the recording first, then submit.");
      return;
    }
    var photos = Array.prototype.slice.call($("photos").files);
    var voice = $("voice").files[0] || null;
    // A chosen file is the explicit fallback and wins. The in-page
    // recording is used only when no file is picked.
    var recVoice = null;
    if (!voice && REC_BLOB && REC_BLOB.size > 0) {
      recVoice = new File([REC_BLOB], "memo-" + Date.now() + recExt(), { type: REC_MIME });
      voice = recVoice;
    }
    var files = photos.length + (voice ? 1 : 0);
    if (files > MAX_FILES) { setMsg(msg, "bad", "Max " + MAX_FILES + " files per entry."); return; }
    var totalBytes = 0;
    for (var i = 0; i < photos.length; i++) {
      var bad = checkFile(photos[i], "photo");
      if (bad) { setMsg(msg, "bad", bad); return; }
      totalBytes += photos[i].size;
    }
    if (voice) {
      var badv = checkFile(voice, "voice");
      if (badv) { setMsg(msg, "bad", badv); return; }
      totalBytes += voice.size;
    }
    if (totalBytes > MAX_TOTAL_BYTES) {
      setMsg(msg, "bad", "Attachments total over 30 MB. Send some now and the rest in a second entry.");
      return;
    }

    btn.disabled = true;
    setMsg(msg, "", "Sending...");
    try {
      var uploads = [];
      for (var p = 0; p < photos.length; p++) uploads.push(await fileToUpload(photos[p], "photo"));
      if (voice) uploads.push(await fileToUpload(voice, "voice"));

      var r = await fetch(EXEC_URL, {
        method: "POST",
        body: JSON.stringify({
          secret: SECRET,
          sender: USER.email,
          project: $("project").value,
          date: $("date").value,
          weather: $("weather").value,
          body: body,
          voice_note: !!voice,
          uploads: uploads
        })
      });
      var j = await r.json();
      if (j.ok) {
        setMsg(msg, "ok", j.dedupe ? "Already logged this entry. No duplicate made." : "Logged. Thank you.");
        $("body").value = "";
        $("photos").value = "";
        $("voice").value = "";
        recReset();
      } else {
        setMsg(msg, "bad", "Failed: " + j.error);
      }
    } catch (e) {
      setMsg(msg, "bad", "No connection. Entry not sent. Try again.");
    }
    btn.disabled = false;
  }

  init();
})();
