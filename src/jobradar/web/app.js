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

function gapView(g) {
  const box = el("div");

  const head = el("div", "gaphead");
  // The percentage is deliberately quiet when the posting named too few
  // skills to score. A confident 100% built on one matched word is worse
  // than no number, and the server flags that case rather than hiding it.
  const pct = el("span", "pct" + (g.thin ? " thin" : ""), g.thin ? "—" : g.percent + "%");
  head.append(pct, el("span", "verdict", g.verdict));
  box.append(head);
  if (g.note) box.append(el("div", "gapnote", g.note));

  const column = (title, items, kind) => {
    const wrap = el("div", "gapcol");
    wrap.append(el("div", "gapcoltitle", title + " (" + items.length + ")"));
    if (!items.length) {
      wrap.append(el("div", "gapnone", kind === "have" ? "nothing matched"
                                                       : "nothing missing"));
      return wrap;
    }
    items.slice(0, 12).forEach((n) => {
      const line = el("div", "gapitem " + kind);
      line.append(el("b", null, n.skill));
      const marks = [];
      if (n.in_title) marks.push("in the title");
      if (n.mentions > 1) marks.push(n.mentions + "×");
      if (n.nice) marks.push("nice-to-have");
      if (marks.length) line.append(el("span", "gapwhy", " " + marks.join(" · ")));
      // Evidence, not a tick: "PyTorch" means nothing without the repo that
      // proves it, and that repo is what you cite in the application.
      if (n.proof) line.append(el("span", "gapproof", " ← " + n.proof));
      wrap.append(line);
    });
    return wrap;
  };

  const cols = el("div", "gapcols");
  cols.append(column("You can show", g.have, "have"));
  cols.append(column("Missing from CV + GitHub", g.missing, "missing"));
  box.append(cols);

  box.append(el("div", "gapnote",
    "Compared against " + g.inventory_size + " skills proven across your repos and CV."));
  return box;
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

  // One employer repeating "we sponsor visas" in every posting is true and
  // useless: it put 161 of 170 rows under one name. The extras are folded
  // rather than hidden, and the count says so.
  if (p.more_at_company) {
    node.append(el("div", "where more",
      "+ " + p.more_at_company + " more open at " + p.company + ", folded"));
  }

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

  // The gap report, opened on click. Fetched rather than precomputed: the
  // inventory changes whenever a repo is pushed or the CV is edited, so a
  // score cached at crawl time would go stale against a moving profile.
  if (!p.reason && p.id) {
    const panel = el("div", "gap");
    const toggle = el("button", "gaptoggle", "match against my CV + GitHub ▾");
    let loaded = false;
    toggle.onclick = async () => {
      panel.classList.toggle("open");
      if (loaded) return;
      loaded = true;
      panel.textContent = "reading the posting…";
      try {
        const g = await (await fetch("/api/gap/" + p.id)).json();
        panel.innerHTML = "";
        panel.append(gapView(g));
      } catch (e) {
        panel.textContent = "could not build the report";
      }
    };
    node.append(toggle, panel);
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
  if (f.lines) {
    // Rendered by the pipeline itself, in stage order.
    $("funnel").textContent = f.lines.join("\n") + "\n\nlast run: " + run.at;
    return;
  }
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

// --- YC: company-first, so the row is a company and the jobs sit under it ---

let ycBucket = null;

function company(c) {
  const node = el("div", "row");
  const top = el("div", "top");
  top.append(el("span", "score", String(c.job_count)));
  top.append(el("span", "title", c.name));
  if (c.batch) top.append(el("span", "co", c.batch));
  top.append(el("span", "spacer"));

  const links = [
    c.website && ["website", c.website],
    c.yc_url && ["YC", c.yc_url],
    // Derived from the slug and never verified, because this project does not
    // request LinkedIn. Labelled so a wrong guess is obvious.
    c.linkedin && ["LinkedIn?", c.linkedin],
    c.linkedin_search && ["search", c.linkedin_search],
  ].filter(Boolean);
  links.forEach(([label, href]) => {
    const a = el("a", "apply", label);
    a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
    top.append(a);
  });
  node.append(top);

  if (c.one_liner) node.append(el("div", "where", c.one_liner));
  const facts = [c.age_label, c.location, c.industry,
                 c.team_size ? c.team_size + " people" : null]
    .filter(Boolean).join("  ·  ");
  node.append(el("div", "where", facts));

  if (c.jobs && c.jobs.length) {
    const list = el("div", "why");
    c.jobs.slice(0, 8).forEach((j) => {
      const line = el("div");
      const a = el("a", "apply", j.title);
      a.href = j.url; a.target = "_blank"; a.rel = "noopener noreferrer";
      line.append(a);
      if (j.role_match) line.append(el("span", "badge good", j.role_match));
      if (j.location) line.append(document.createTextNode("  " + j.location));
      list.append(line);
    });
    if (c.jobs.length > 8) {
      list.append(el("div", null, "+ " + (c.jobs.length - 8) + " more"));
    }
    node.append(list);
  } else {
    node.append(el("div", "why",
      "No readable board — funded, hiring, and reachable by email."));
  }

  const badges = el("div", "badges");
  if (c.is_ai) badges.append(badge("ai", "good"));
  if (c.age_bucket) badges.append(badge(c.age_bucket, "good"));
  (c.tags || []).slice(0, 5).forEach((t) => badges.append(badge(t, "")));
  node.append(badges);
  return node;
}

async function loadYC() {
  const url = "/api/yc" + (ycBucket ? "?bucket=" + ycBucket : "");
  const data = await (await fetch(url)).json();
  const counts = data.counts || {};

  const bar = $("ycbuckets");
  bar.className = "";
  bar.id = "ycbuckets";
  bar.innerHTML = "";
  const mk = (key, label, n) => {
    const b = el("button", ycBucket === key ? "on" : "");
    b.append(document.createTextNode(label + " "), el("b", null, String(n ?? 0)));
    b.onclick = () => { ycBucket = key; loadYC(); };
    return b;
  };
  bar.append(mk(null, "all", counts.companies));
  const buckets = counts.buckets || {};
  bar.append(mk("0-3m", "launched < 3 months", buckets["0-3m"]));
  bar.append(mk("3-6m", "3–6 months", buckets["3-6m"]));
  bar.append(mk("6-12m", "6–12 months", buckets["6-12m"]));

  const rows = $("yc").querySelector(".rows");
  rows.innerHTML = "";
  if (!data.companies || !data.companies.length) {
    rows.append(el("div", "empty", "Nothing yet. Run scripts/fetch_yc.py."));
    return;
  }
  data.companies.forEach((c) => rows.append(company(c)));
}

const LOADERS = {
  today: loadToday,
  sponsorship: () => loadSection("sponsorship"),
  remote: () => loadSection("remote"),
  europe: () => loadSection("europe"),
  gulf: () => loadSection("gulf"),
  pakistan: () => loadSection("pakistan"),
  yc: loadYC,
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
