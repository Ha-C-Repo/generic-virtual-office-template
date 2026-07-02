/* Your Company Staff Training Portal - shared client layer.
   Auth guard, progress display, and the gating knowledge check.
   All grading happens server-side in submit_quiz(). This file never
   sees a correct answer. */
"use strict";

(function () {
  if (!window.NC_SUPABASE_URL || window.NC_SUPABASE_URL.indexOf("__") === 0) {
    console.error("Portal config missing");
    return;
  }
  var sb = window.supabase.createClient(window.NC_SUPABASE_URL, window.NC_SUPABASE_KEY);
  window.ncSb = sb;

  var ORDER = window.NC_MODULE_ORDER || [];
  var lastProgressError = null;

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  function css() {
    var s = document.createElement("style");
    s.textContent = [
      ".nc-gate{max-width:900px;margin:28px auto 60px;padding:0 20px;font-family:inherit;}",
      ".nc-gate-card{background:#18181b;border:2px solid #3f3f46;border-left:4px solid #ea580c;padding:24px;}",
      ".nc-gate-card h2{color:#fff;margin:0 0 6px;font-size:20px;}",
      ".nc-gate-card .nc-sub{color:#a1a1aa;font-size:13px;margin:0 0 18px;line-height:1.5;}",
      ".nc-q{margin:0 0 18px;}",
      ".nc-q p{color:#e4e4e7;font-size:14px;font-weight:600;margin:0 0 8px;}",
      ".nc-opt{display:block;width:100%;text-align:left;background:#27272a;border:1px solid #3f3f46;color:#d4d4d8;padding:10px 12px;margin:0 0 6px;cursor:pointer;font-size:13px;line-height:1.45;}",
      ".nc-opt:hover{border-color:#ea580c;}",
      ".nc-opt.nc-sel{border-color:#ea580c;background:#2a1c12;color:#fff;}",
      ".nc-opt.nc-wrong{border-color:#dc2626;background:#2a1212;}",
      ".nc-actions{margin-top:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;}",
      ".nc-btn{background:#ea580c;color:#fff;border:0;padding:11px 22px;font-size:14px;font-weight:700;cursor:pointer;}",
      ".nc-btn[disabled]{opacity:.45;cursor:not-allowed;}",
      ".nc-btn.nc-ghost{background:transparent;border:1px solid #3f3f46;color:#d4d4d8;}",
      ".nc-msg{font-size:13px;color:#a1a1aa;}",
      ".nc-msg.nc-ok{color:#22c55e;font-weight:700;}",
      ".nc-msg.nc-err{color:#f87171;}",
      ".nc-gate-locked{color:#a1a1aa;font-size:14px;padding:8px 0;}",
      ".nc-topbar{position:sticky;top:0;z-index:50;background:#0c0c0e;border-bottom:1px solid #27272a;padding:8px 20px;display:flex;justify-content:space-between;align-items:center;font-size:12px;}",
      ".nc-topbar a,.nc-topbar button{color:#ea580c;background:none;border:0;cursor:pointer;font-size:12px;text-decoration:none;font-weight:600;}",
      ".nc-topbar .nc-user{color:#71717a;}",
      ".nc-done-tag{display:inline-block;background:#14532d;color:#86efac;font-size:11px;font-weight:700;padding:2px 8px;margin-left:8px;vertical-align:middle;}"
    ].join("\n");
    document.head.appendChild(s);
  }

  async function requireAuth() {
    var r = await sb.auth.getSession();
    if (!r.data.session) {
      var here = location.pathname.split("/").pop() || "suite.html";
      location.href = "index.html?next=" + encodeURIComponent(here);
      return null;
    }
    return r.data.session;
  }

  async function getProgress() {
    var r = await sb.from("progress").select("module_id,status,updated_at").eq("status", "complete");
    lastProgressError = r.error || null;
    return r.error ? [] : r.data;
  }

  function showProgressError(beforeNode) {
    if (!lastProgressError) return;
    var b = el("div", "nc-msg nc-err");
    b.style.cssText = "max-width:900px;margin:12px auto;padding:10px 20px;border:1px solid #7f1d1d;background:#2a1212;";
    b.textContent = "Could not load your saved progress (" +
      (lastProgressError.message || "connection problem") +
      "). Completed modules may show as locked until this clears. Refresh the page; if it keeps happening, tell Joseph.";
    document.body.insertBefore(b, beforeNode || document.body.firstChild);
  }

  function topbar(session) {
    var bar = el("div", "nc-topbar");
    var left = el("div", "", '<a href="suite.html">&larr; Training Suite</a>');
    var right = el("div");
    var user = el("span", "nc-user", session.user.email + " &nbsp;");
    var out = el("button", "", "Sign out");
    out.onclick = async function () { await sb.auth.signOut(); location.href = "index.html"; };
    right.appendChild(user); right.appendChild(out);
    bar.appendChild(left); bar.appendChild(right);
    document.body.insertBefore(bar, document.body.firstChild);
  }

  /* ---------- module page: gating knowledge check ---------- */
  async function initModulePage() {
    var session = await requireAuth();
    if (!session) return;
    css();
    topbar(session);

    var G = window.NC_GATE; // {module_id, title, next, questions:[{q,options[]}]}
    var host = el("div", "nc-gate");
    var card = el("div", "nc-gate-card");
    host.appendChild(card);
    document.body.appendChild(host);

    var done = await getProgress();
    showProgressError(host);
    var doneIds = done.map(function (d) { return d.module_id; });
    var myIdx = ORDER.indexOf(G.module_id);
    var prevId = myIdx > 0 ? ORDER[myIdx - 1] : null;
    var unlocked = !prevId || doneIds.indexOf(prevId) !== -1;
    var complete = doneIds.indexOf(G.module_id) !== -1;

    var head = '<h2 id="nc-gate-title">Final Knowledge Check' + (complete ? '<span class="nc-done-tag">COMPLETE</span>' : "") + "</h2>" +
      '<p class="nc-sub">Pass all ' + G.questions.length + ' questions to complete this module and unlock the next one. Answers are graded on the server.</p>';
    card.innerHTML = head;

    if (!unlocked) {
      card.appendChild(el("div", "nc-gate-locked",
        "This module is locked. Complete the previous module first. The check below will not grade until then."));
    }

    var sel = {};
    G.questions.forEach(function (q, qi) {
      var qd = el("div", "nc-q");
      qd.appendChild(el("p", "", (qi + 1) + ". " + q.q));
      q.options.forEach(function (opt, oi) {
        var b = el("button", "nc-opt", opt);
        b.setAttribute("data-q", qi); b.setAttribute("data-o", oi);
        b.onclick = function () {
          sel[qi] = oi;
          qd.querySelectorAll(".nc-opt").forEach(function (x) { x.classList.remove("nc-sel", "nc-wrong"); });
          b.classList.add("nc-sel");
          submitBtn.disabled = Object.keys(sel).length !== G.questions.length;
        };
        qd.appendChild(b);
      });
      card.appendChild(qd);
    });

    var actions = el("div", "nc-actions");
    var submitBtn = el("button", "nc-btn", "Submit answers");
    submitBtn.disabled = true;
    var msg = el("span", "nc-msg", "");
    actions.appendChild(submitBtn); actions.appendChild(msg);
    card.appendChild(actions);

    submitBtn.onclick = async function () {
      submitBtn.disabled = true;
      msg.className = "nc-msg"; msg.textContent = "Grading...";
      var answers = G.questions.map(function (_, i) { return sel[i]; });
      var r = await sb.rpc("submit_quiz", { p_module_id: G.module_id, p_answers: answers });
      if (r.error) {
        msg.className = "nc-msg nc-err";
        msg.textContent = r.error.message || "Could not grade. Try again.";
        submitBtn.disabled = false;
        return;
      }
      if (r.data.passed) {
        msg.className = "nc-msg nc-ok";
        msg.textContent = "Passed. Module complete.";
        document.getElementById("nc-gate-title").innerHTML = 'Final Knowledge Check<span class="nc-done-tag">COMPLETE</span>';
        if (G.next) {
          var nxt = el("a", "nc-btn", "Next module &rarr;");
          nxt.href = G.next; nxt.style.textDecoration = "none";
          actions.appendChild(nxt);
        } else {
          actions.appendChild(el("span", "nc-msg nc-ok", "That was the final module. Curriculum complete."));
        }
      } else {
        msg.className = "nc-msg nc-err";
        var wrong = r.data.wrong || [];
        msg.textContent = "Not passed. " + wrong.length + " incorrect. Review the highlighted questions and resubmit.";
        wrong.forEach(function (qi) {
          var b = card.querySelector('.nc-opt.nc-sel[data-q="' + qi + '"]');
          if (b) b.classList.add("nc-wrong");
        });
        submitBtn.disabled = false;
      }
    };
  }

  /* ---------- suite page: locks, ticks, progress ---------- */
  async function initSuitePage() {
    var session = await requireAuth();
    if (!session) return;
    css();
    topbar(session);

    var admin = await sb.from("admins").select("user_id").eq("user_id", session.user.id);
    if (!admin.error && admin.data.length) {
      var bar = document.querySelector(".nc-topbar div");
      if (bar) bar.innerHTML += ' &nbsp;&middot;&nbsp; <a href="admin.html">Admin dashboard</a>';
    }

    var done = await getProgress();
    showProgressError(null);
    var doneIds = done.map(function (d) { return d.module_id; });
    var firstLockedIdx = ORDER.length;
    for (var i = 0; i < ORDER.length; i++) {
      if (doneIds.indexOf(ORDER[i]) === -1) { firstLockedIdx = i + 1; break; }
    }
    // modules 0..firstLockedIdx-1 are open, others locked
    document.querySelectorAll("a.mod-card").forEach(function (a) {
      var id = (a.getAttribute("href") || "").replace(".html", "");
      var idx = ORDER.indexOf(id);
      if (idx === -1) return;
      if (doneIds.indexOf(id) !== -1) {
        var numEl = a.querySelector(".mod-num");
        if (numEl) numEl.innerHTML += ' <span style="color:#22c55e;">&#10003;</span>';
      } else if (idx >= firstLockedIdx) {
        a.style.opacity = "0.45";
        a.style.filter = "grayscale(.6)";
        a.addEventListener("click", function (ev) {
          ev.preventDefault();
          alert("Locked. Complete the previous modules first.");
        });
        var tag = a.querySelector(".mod-tag");
        if (tag) tag.textContent = "LOCKED";
      }
    });

    var statNum = document.querySelector(".hero-stat-num");
    if (statNum) {
      var wrap = statNum.parentElement.parentElement;
      var stat = el("div", "hero-stat",
        '<p class="hero-stat-num" style="color:#22c55e;">' + doneIds.length + "/" + ORDER.length +
        '</p><p class="hero-stat-lbl">Completed</p>');
      wrap.appendChild(stat);
    }
  }

  window.ncInitModulePage = initModulePage;
  window.ncInitSuitePage = initSuitePage;
})();
