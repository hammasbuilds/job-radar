"use strict";

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text != null) node.textContent = text;
  return node;
};

// Which verdict values are good news, which are warnings, which are bad.
// The badge colour is the two-second read, so this mapping is the difference
// between a scannable list and a wall of grey pills.
const TONE = {
  global: "good", region: "warn", country: "bad", hybrid: "warn", onsite: "bad",
  sponsors: "good", refuses: "bad", silent: "warn", not_needed: "good",
  relocation_hint: "warn",
  contractor: "good", either: "good", employee: "warn", unstated: "",
  good: "good", partial: "warn", poor: "bad", async: "good",
};

function badge(text, value) {
  const b = el("span", "badge " + (TONE[value] || ""), text);
  return b;
}

function row(p) {
  const v = p.verdict || {};
  const node = el("div", "row");

  const top = el("div", "top");
  top.append(el("span", "score", (p.score ?? 0).toFixed(2)));
  top.append(el("span", "title", p.title));
  top.append(el("span", "co", p.company));
  top.append(el("span", "spacer"));
  if (p.url) {
    const a = el("a", "apply", p.reason ? "view" : "apply →");
    a.href = p.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    top.append(a);
  }
  node.append(top);

  if (p.location) node.append(el("div", "where", p.location));

  // The evidence, quoted. This is the whole point of the row.
  const why = el("div", "why");
  if (p.reason) {
    why.append(el("b", null, "killed: " + p.reason));
    const detail = v.scope_why || v.auth_why;
    if (detail) why.append(document.createTextNode(" — " + detail));
  } else {
    why.append(document.createTextNode(p.evidence || "no evidence recorded"));
  }
  node.append(why);

  // Marking a posting applied is the one thing here a human does rather than
  // the crawl. Without a control it was an endpoint nobody could reach, which
  // is a feature that looks implemented and is not.
  if (!p.reason && p.id) {
    const states = ["applied", "replied", "rejected", "closed"];
    const track = el("div", "track");
    const current = el("span", "state", p.applied ? p.applied : "not applied");
    if (p.applied) current.classList.add("on");
    track.append(current);
    states.forEach((s) => {
      if (s === p.applied) return;
      const b = el("button", "mark", s);
      b.onclick = async () => {
        b.disabled = true;
        await fetch("/api/applied/" + p.id, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ state: s, noted: "" }),
        });
        p.applied = s;
        node.replaceWith(row(p));
      };
      track.append(b);
    });
    node.append(track);
  }

  const badges = el("div", "badges");
  if (v.scope) badges.append(badge(v.scope, v.scope));
  if (v.auth) badges.append(badge(v.auth.replace(/_/g, " "), v.auth));
  if (v.employment && v.employment !== "unstated") {
    badges.append(badge(v.employment, v.employment));
  }
  if (v.timezone && v.timezone !== "unstated") {
    badges.append(badge("tz " + v.timezone, v.timezone));
  }
  if (p.source) badges.append(badge(p.source, ""));
  node.append(badges);
  return node;
}

function fill(container, postings, emptyText) {
  container.innerHTML = "";
  if (!postings || !postings.length) {
    container.append(el("div", "empty", emptyText));
    return;
  }
  postings.forEach((p) => container.append(row(p)));
}

async function loadToday() {
  const data = await (await fetch("/api/today")).json();
  fill($("today").querySelector(".rows"), data.postings,
       "Nothing new. Run scripts/fetch.py.");
}

async function loadSection(name) {
  const data = await (await fetch("/api/section/" + name)).json();
  fill($(name).querySelector(".rows"), data.postings,
       "Nothing in this section yet.");
}

let killReason = null;

async function loadKilled() {
  const url = "/api/killed" + (killReason ? "?reason=" + encodeURIComponent(killReason) : "");
  const data = await (await fetch(url)).json();

  const bar = $("reasons");
  bar.innerHTML = "";
  const all = el("button", killReason ? "" : "on");
  all.append(document.createTextNode("all "), el("b", null,
    String(data.reasons.reduce((n, r) => n + r.n, 0))));
  all.onclick = () => { killReason = null; loadKilled(); };
  bar.append(all);

  data.reasons.forEach((r) => {
    const b = el("button", killReason === r.reason ? "on" : "");
    b.append(document.createTextNode(r.reason + " "), el("b", null, String(r.n)));
    b.onclick = () => { killReason = r.reason; loadKilled(); };
    bar.append(b);
  });

  fill($("killed").querySelector(".rows"), data.postings, "Nothing was killed.");
}

async function loadMarket() {
  const data = await (await fetch("/api/market")).json();
  const run = data.run;
  if (!run) { $("funnel").textContent = "No run recorded yet."; return; }
  const f = run.funnel || {};
  const lines = [];
  lines.push(String(run.fetched).padStart(9) + "  fetched");
  const dedup = f.after_dedup ?? run.fetched;
  lines.push(String(dedup).padStart(9) + "  after dedup  (-" + (f.duplicates || 0) + ")");
  let running = dedup;
  Object.entries(f.killed || {})
    .sort((a, b) => b[1] - a[1])
    .forEach(([reason, n]) => {
      running -= n;
      lines.push(String(running).padStart(9) + "  after " + reason.padEnd(34) + " (-" + n + ")");
    });
  lines.push("");
  Object.entries(f.sections || {}).forEach(([name, n]) => {
    lines.push(String(n).padStart(9) + "  in section: " + name);
  });
  lines.push("");
  lines.push("last run: " + run.at);
  $("funnel").textContent = lines.join("\n");
}

async function loadPipeline() {
  const data = await (await fetch("/api/pipeline")).json();
  fill($("pipeline").querySelector(".rows"), data.postings,
       "Nothing applied to yet. Mark a row on Today or in a section.");
}

const LOADERS = {
  today: loadToday,
  sponsorship: () => loadSection("sponsorship"),
  remote: () => loadSection("remote"),
  killed: loadKilled,
  pipeline: loadPipeline,
  market: loadMarket,
};

document.querySelectorAll("#tabs button").forEach((button) => {
  button.onclick = () => {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("on"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("on"));
    button.classList.add("on");
    $(button.dataset.tab).classList.add("on");
    LOADERS[button.dataset.tab]();
  };
});

loadToday();
