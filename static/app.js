/* Deadline Radar - the only client-side script.
   It posts the pasted text and swaps in the HTML the server rendered, so the
   brief always comes from the same code path as a saved analysis or a tour step.
   In guided-tour mode it also scrolls the focused card into view, which is what
   makes every step of the demo a real frame of the running app. */
(function () {
  "use strict";

  var result = document.getElementById("result");
  var source = document.getElementById("source");
  var button = document.getElementById("analyse");
  var status = document.getElementById("status");
  var mode = document.getElementById("mode");
  var historyBox = document.getElementById("history");

  function setStatus(text) {
    if (status) { status.textContent = text; }
  }

  function refreshHistory() {
    fetch("/api/history").then(function (r) { return r.json(); }).then(function (data) {
      if (historyBox && data.html) { historyBox.innerHTML = data.html; }
    }).catch(function () { /* history is a convenience; never block the brief */ });
  }

  function analyse() {
    var text = (source && source.value || "").trim();
    if (!text) {
      setStatus("Paste some text first.");
      return;
    }
    button.disabled = true;
    setStatus("Reading the page and validating every field...");
    fetch("/api/analyse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, mode: mode ? mode.value : "offline" })
    }).then(function (r) {
      return r.json().then(function (data) { return { ok: r.ok, data: data }; });
    }).then(function (res) {
      button.disabled = false;
      if (!res.ok) {
        setStatus(res.data.error || "The analysis failed.");
        return;
      }
      var data = res.data;
      if (result) { result.innerHTML = data.html; }
      var counts = data.counts || {};
      setStatus("Done in " + data.elapsed_ms + " ms. " + (counts.accepted || 0) +
        " accepted, " + (counts.corrected || 0) + " corrected, " +
        (counts.rejected || 0) + " rejected, " + (counts.missing || 0) + " not stated.");
      window.history.replaceState({}, "", "/analysis/" + data.id);
      refreshHistory();
    }).catch(function (err) {
      button.disabled = false;
      setStatus("Network error: " + err);
    });
  }

  function focusTour() {
    var target = document.body.getAttribute("data-focus");
    if (!target) { return; }
    var el = document.getElementById(target);
    if (!el) { return; }
    var rect = el.getBoundingClientRect();
    var wanted = Math.max(0, window.pageYOffset + rect.top -
      Math.max(24, (window.innerHeight - rect.height) / 2));
    window.scrollTo(0, wanted);
    el.className += " focus";
    var after = el.getBoundingClientRect();
    var top = Math.max(0, after.top);
    var bottom = Math.min(window.innerHeight, after.bottom);
    var visible = after.height > 0 ? Math.max(0, bottom - top) / after.height : 0;
    document.body.setAttribute("data-focus-ready", target);
    document.body.setAttribute("data-metrics", JSON.stringify({
      scrollY: Math.round(window.pageYOffset),
      pageTop: Math.round(window.pageYOffset + after.top),
      viewport: window.innerHeight,
      page: document.body.scrollHeight,
      top: Math.round(after.top),
      height: Math.round(after.height),
      visible: Math.round(visible * 100) / 100
    }));
  }

  if (button) { button.addEventListener("click", analyse); }
  if (source) {
    source.addEventListener("keydown", function (event) {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { analyse(); }
    });
  }
  focusTour();
  refreshHistory();
})();
