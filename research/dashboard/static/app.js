const app = document.getElementById("app");

const fmt = {
  score(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return `<span class="na">—</span>`;
    return `<span class="mono">${Number(v).toFixed(4)}</span>`;
  },
  delta(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return `<span class="na">—</span>`;
    const n = Number(v);
    const cls = n > 0 ? "pos" : n < 0 ? "neg" : "na";
    const sign = n > 0 ? "+" : "";
    return `<span class="${cls} mono">${sign}${n.toFixed(4)}</span>`;
  },
  usd(v) {
    if (v === null || v === undefined) return `<span class="na">—</span>`;
    return `<span class="mono">$${Number(v).toFixed(4)}</span>`;
  },
  int(v) {
    if (v === null || v === undefined) return `<span class="na">—</span>`;
    return `<span class="mono">${Number(v).toLocaleString()}</span>`;
  },
  text(v) {
    return v === null || v === undefined || v === "" ? `<span class="na">—</span>` : escape(String(v));
  },
};

function escape(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function get(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json();
}

function route() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const parts = hash.split("/").filter(Boolean);
  if (parts[0] === "run" && parts[1]) return { page: "run", name: decodeURIComponent(parts[1]) };
  if (parts[0] === "dataset") return { page: "dataset" };
  if (parts[0] === "experiments") return { page: "experiments" };
  return { page: "overview" };
}

function domainCard(d) {
  if (d.status === "no_run") {
    return `<article class="card">
      <h3>${escape(d.domain)}</h3>
      <p class="empty">No comparison run yet</p>
    </article>`;
  }
  const note = d.status === "no_placebo"
    ? `<p class="muted footnote">Latest run has no placebo arm. No leaderboard-style comparison yet.</p>`
    : "";
  return `<article class="card">
    <h3>${escape(d.domain)} <span class="pill">${escape(d.latest || "")}</span></h3>
    <div class="hero">${fmt.delta(d.net_delta)}</div>
    <div class="kvs">
      <span>Placebo</span><span>${fmt.score(d.placebo)}</span>
      <span>Skill</span><span>${fmt.score(d.skill)}</span>
      <span>Net Δ</span><span>${fmt.delta(d.net_delta)}</span>
      <span>Tasks</span><span>${fmt.int(d.n_tasks)}</span>
      <span>Cost</span><span>${fmt.usd(d.total_cost)}</span>
    </div>
    ${note}
  </article>`;
}

function runRow(r) {
  return `<tr class="clickable" data-run="${escape(r.name)}">
    <td><a href="#/run/${encodeURIComponent(r.name)}">${escape(r.name)}</a></td>
    <td>${fmt.text(r.domain)}</td>
    <td>${fmt.text(r.benchmark)}</td>
    <td>${fmt.text(r.learner)}</td>
    <td>${escape((r.arms || []).join(", ") || "—")}</td>
    <td class="num">${fmt.int(r.n_tasks)}</td>
    <td class="num">${fmt.score(r.placebo)}</td>
    <td class="num">${fmt.score(r.skill)}</td>
    <td class="num">${fmt.delta(r.net_delta)}</td>
    <td class="num">${fmt.int(r.learner_tokens)}</td>
    <td class="num">${fmt.int(r.grader_tokens)}</td>
    <td class="num">${fmt.usd(r.learner_cost)}</td>
    <td class="num">${fmt.usd(r.grader_cost)}</td>
    <td>${fmt.text(r.official_note)}</td>
  </tr>`;
}

function renderOverview(data) {
  const runs = data.runs || [];
  app.innerHTML = `
    <section>
      <h2>Domains</h2>
      <div class="grid domains">${data.domains.map(domainCard).join("")}</div>
    </section>
    <section class="section">
      <h2>Runs <span class="pill">${runs.length}</span></h2>
      <p class="muted footnote">Official rates. Unavailable arms stay blank — they are not zero. Highlighted column is skill − placebo (<code>net_delta</code>).</p>
      <div class="scroll">
        <table>
          <thead>
            <tr>
              <th>Run</th><th>Domain</th><th>Benchmark</th><th>Learner</th><th>Arms</th>
              <th class="num">Tasks</th><th class="num">Placebo</th>
              <th class="num">Skill</th><th class="num">Skill − placebo</th>
              <th class="num">Learner tok</th><th class="num">Grader tok</th>
              <th class="num">Learner $</th><th class="num">Grader $</th><th>Note</th>
            </tr>
          </thead>
          <tbody>${runs.map(runRow).join("") || `<tr><td colspan="14" class="empty">No runs found</td></tr>`}</tbody>
        </table>
      </div>
    </section>`;
}

function attemptRow(a) {
  const theme = a.theme || a.stratum || a.category || a.difficulty || "";
  const v = a.verifier || {};
  const vsum = [
    v.n_rubrics != null ? `rubrics ${v.n_rubrics}` : null,
    v.n_criteria_met != null ? `met ${v.n_criteria_met}/${v.n_rubrics ?? "?"}` : null,
    v.positive_points_met != null ? `+pts ${v.positive_points_met}/${v.positive_points_available}` : null,
  ].filter(Boolean).join(" · ");
  return `<tr>
    <td>${fmt.text(a.task_name)}</td>
    <td>${fmt.text(a.task_id)}</td>
    <td>${fmt.text(a.arm)}</td>
    <td class="num">${fmt.score(a.score)}</td>
    <td>${a.passed === true ? "pass" : a.passed === false ? "fail" : `<span class="na">—</span>`}</td>
    <td>${fmt.text(a.outcome_class)}</td>
    <td>${fmt.text(a.status)}</td>
    <td>${fmt.text(a.error_class)}</td>
    <td class="num">${fmt.int(a.answer_length)}</td>
    <td class="num">${fmt.int(a.n_steps)}</td>
    <td class="num">${fmt.int(a.n_agent_steps)}</td>
    <td class="num">${fmt.int(a.n_tool_calls)}</td>
    <td class="num">${fmt.int(a.n_repeated_tools)}</td>
    <td class="num">${fmt.int(a.agent_prompt_tokens)}</td>
    <td class="num">${fmt.int(a.agent_completion_tokens)}</td>
    <td>${fmt.text(theme)}</td>
    <td>${fmt.text(vsum)}</td>
  </tr>`;
}

function pairRow(p) {
  return `<tr>
    <td>${fmt.text(p.task_name || p.task_id)}</td>
    <td class="num">${fmt.score(p.placebo)}</td>
    <td class="num">${fmt.score(p.skill)}</td>
    <td class="num">${fmt.delta(p.delta)}</td>
    <td>${fmt.text(p.change)}</td>
    <td>${fmt.text(p.stratum)}</td>
  </tr>`;
}

function renderRun(run) {
  const c = run.comparison || {};
  const regs = run.regressions || {};
  const pairs = [...(run.pairs || [])].sort((a, b) => (a.delta ?? 0) - (b.delta ?? 0));
  const hasCompare = (run.arms || []).includes("skill") && (run.arms || []).includes("placebo");
  app.innerHTML = `
    <a class="back" href="#/">← Overview</a>
    <section class="two">
      <article class="card">
        <h3>${escape(run.name)}</h3>
        <div class="hero">${fmt.delta(run.net_delta)}</div>
        <div class="kvs">
          <span>Domain</span><span>${fmt.text(run.domain)} / ${fmt.text(run.benchmark)}</span>
          <span>Learner</span><span>${fmt.text(run.learner)}</span>
          <span>Arms</span><span>${escape((run.arms || []).join(", "))}</span>
          <span>Tasks</span><span>${fmt.int(run.n_tasks)}</span>
          <span>Placebo</span><span>${fmt.score(run.placebo)}</span>
          <span>Skill</span><span>${fmt.score(run.skill)}</span>
          <span>Skill − placebo</span><span>${fmt.delta(run.net_delta)}</span>
          <span>Note</span><span>${fmt.text(run.official_note)}</span>
        </div>
      </article>
      <article class="card">
        <h3>Cost</h3>
        <div class="kvs">
          <span>Learner</span><span>${fmt.usd(run.learner_cost)} · ${fmt.int(run.learner_tokens)} tok</span>
          <span>Grader</span><span>${fmt.usd(run.grader_cost)} · ${fmt.int(run.grader_tokens)} tok</span>
          <span>Total</span><span>${fmt.usd(run.total_cost)}</span>
          <span>Per task</span><span>${fmt.usd(run.cost_per_task)}</span>
        </div>
        <p class="muted footnote">Grader cost often dominates health / HLE / tau3.</p>
        <h3 style="margin-top:1rem">Outcomes</h3>
        <div class="kvs">
          ${Object.entries(run.outcome_counts || {}).map(([k, v]) => `<span>${escape(k)}</span><span>${fmt.int(v)}</span>`).join("") || `<span class="empty">none</span>`}
        </div>
      </article>
    </section>
    <section class="section">
      <h2>Arm comparison</h2>
      <p class="muted footnote">${escape(c.derived_from || "Official rates. Missing arms are unavailable, not zero.")}</p>
      <div class="scroll">
        <table>
          <thead><tr><th>Metric</th><th class="num">Placebo</th><th class="num">Skill</th></tr></thead>
          <tbody>
            <tr><td>Mean score (official)</td><td class="num">${fmt.score(c.mean_score?.placebo)}</td><td class="num">${fmt.score(c.mean_score?.skill)}</td></tr>
            <tr><td>Pass rate (derived)</td><td class="num">${fmt.score(c.pass_rate?.placebo)}</td><td class="num">${fmt.score(c.pass_rate?.skill)}</td></tr>
            <tr><td>Tasks</td><td class="num" colspan="2">${fmt.int(run.n_tasks)}</td></tr>
            <tr><td>Learner tokens / $</td><td class="num" colspan="2">${fmt.int(run.learner_tokens)} · ${fmt.usd(run.learner_cost)}</td></tr>
            <tr><td>Grader tokens / $</td><td class="num" colspan="2">${fmt.int(run.grader_tokens)} · ${fmt.usd(run.grader_cost)}</td></tr>
          </tbody>
        </table>
      </div>
      <p>Skill − placebo: ${fmt.delta(c.skill_minus_placebo)}</p>
    </section>
    ${hasCompare ? `
    <section class="section">
      <h2>Task-level change</h2>
      <p class="muted footnote">Deltas derived from official per-task scores. Infra/grader/parser failures are not counted as regressions.</p>
      <p>Improved ${fmt.int((regs.improved || []).length)} · Regressed ${fmt.int((regs.regressed || []).length)} · Unchanged ${fmt.int((regs.unchanged || []).length)}</p>
      <div class="scroll">
        <table>
          <thead><tr><th>Task</th><th class="num">Placebo</th><th class="num">Skill</th><th class="num">Delta</th><th>Change</th><th>Stratum</th></tr></thead>
          <tbody>${pairs.map(pairRow).join("") || `<tr><td colspan="6" class="empty">No paired skill comparison</td></tr>`}</tbody>
        </table>
      </div>
    </section>
    <section class="section">
      <h2>By stratum</h2>
      <div class="scroll">
        <table>
          <thead><tr><th>Stratum</th><th class="num">N</th><th>Control</th><th class="num">Control mean</th><th class="num">Skill</th><th class="num">Delta</th><th class="num">↑</th><th class="num">↓</th></tr></thead>
          <tbody>${(regs.by_stratum || []).map((s) => `<tr>
            <td>${fmt.text(s.stratum)}</td>
            <td class="num">${fmt.int(s.n_tasks)}</td>
            <td>${fmt.text(s.control)}</td>
            <td class="num">${fmt.score(s.control_mean)}</td>
            <td class="num">${fmt.score(s.skill_mean)}</td>
            <td class="num">${fmt.delta(s.delta)}</td>
            <td class="num pos">${fmt.int(s.improved)}</td>
            <td class="num neg">${fmt.int(s.regressed)}</td>
          </tr>`).join("") || `<tr><td colspan="8" class="empty">No stratum rollup yet</td></tr>`}</tbody>
        </table>
      </div>
    </section>` : `<section class="section"><p class="empty">No placebo/skill pairing in this run — comparison and regression tables stay empty.</p></section>`}
    <section class="section">
      <h2>Attempts <span class="pill">${(run.attempts || []).length}</span></h2>
      <div class="scroll">
        <table>
          <thead>
            <tr>
              <th>Task</th><th>Task ID</th><th>Arm</th><th class="num">Score</th><th>Pass</th>
              <th>Outcome</th><th>Status</th><th>Error</th><th class="num">Ans len</th>
              <th class="num">Steps</th><th class="num">Agent</th><th class="num">Tools</th>
              <th class="num">Repeat</th><th class="num">Prompt tok</th><th class="num">Compl tok</th>
              <th>Theme / stratum</th><th>Verifier</th>
            </tr>
          </thead>
          <tbody>${(run.attempts || []).map(attemptRow).join("")}</tbody>
        </table>
      </div>
    </section>`;
}

function renderDataset(data) {
  app.innerHTML = `
    <a class="back" href="#/">← Overview</a>
    <section>
      <h2>Dataset</h2>
      <p class="muted">${escape(data.task_set?.source_pool || "")} Seed ${fmt.text(data.task_set?.seed)} · ${fmt.text(data.task_set?.version)}</p>
      <div class="grid cards">
        ${(data.domains || []).map((d) => `
          <article class="card">
            <h3>${escape(d.domain || "")}</h3>
            <div class="kvs">
              <span>Train</span><span>${fmt.int(d.n_train)}</span>
              <span>Dev</span><span>${fmt.int(d.n_dev)}</span>
              <span>Validation</span><span>${fmt.int(d.n_validation)}</span>
              <span>Flagged</span><span>${fmt.int(d.n_flagged)}</span>
              <span>Dup groups</span><span>${fmt.int(d.n_duplicate_groups)}</span>
            </div>
            <p class="muted footnote">Strata: ${escape(JSON.stringify(d.stratum_counts || {}))}</p>
            <p class="muted footnote">Flags: ${escape(JSON.stringify(d.flag_counts || {}))}</p>
          </article>`).join("")}
      </div>
    </section>`;
}

function renderExperiments(data) {
  const items = data.experiments || [];
  app.innerHTML = `
    <a class="back" href="#/">← Overview</a>
    <section>
      <h2>Experiments</h2>
      <div class="grid cards">
        ${items.map((e) => `
          <article class="card">
            <h3>${e.linked_run ? `<a href="#/run/${encodeURIComponent(e.linked_run)}">${escape(e.experiment_id)}</a>` : escape(e.experiment_id)}</h3>
            <div class="kvs">
              <span>Date</span><span>${fmt.text(e.date)}</span>
              <span>Domain</span><span>${fmt.text(e.domain)}</span>
              <span>Task set</span><span>${fmt.text(e.task_set)}</span>
              <span>Score</span><span>${fmt.score(e.score)}</span>
              <span>Net Δ</span><span>${fmt.delta(e.net_delta)}</span>
              <span>Cost</span><span>${fmt.usd(e.total_cost)}</span>
            </div>
            ${e.hypothesis ? `<p class="footnote">${escape(e.hypothesis)}</p>` : ""}
            ${e.notes ? `<p class="muted footnote">${escape(e.notes)}</p>` : ""}
            ${e.conclusion ? `<p class="footnote">${escape(e.conclusion)}</p>` : ""}
          </article>`).join("") || `<p class="empty">No experiment manifests yet</p>`}
      </div>
    </section>`;
}

async function render() {
  const r = route();
  app.innerHTML = "Loading…";
  try {
    if (r.page === "run") renderRun(await get(`/api/run/${encodeURIComponent(r.name)}`));
    else if (r.page === "dataset") renderDataset(await get("/api/dataset"));
    else if (r.page === "experiments") renderExperiments(await get("/api/experiments"));
    else renderOverview(await get("/api/overview"));
  } catch (err) {
    app.innerHTML = `<p class="neg">Failed to load: ${escape(err.message)}</p>`;
  }
}

document.getElementById("reload").addEventListener("click", render);
window.addEventListener("hashchange", render);
render();
