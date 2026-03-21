/**
 * VAA Dashboard — static data from data/board.json (+ optional data/metrics_overrides.json)
 */

const PAGE_SIZE = 6;

const I18N = {
  en: {
    brandTitle: "VAA",
    brandSub: "Ascend Adaptation",
    officialWebsite: "Repository",
    headerTitle: "vLLM Ascend Adaptation Board",
    headerDesc:
      "Track adaptation, benchmark, and optimization pipeline status (exported from vllm_board.db).",
    lastUpdated: "Last updated",
    sortLabel: "Sort",
    sortNewestFirst: "Newest first",
    sortOldestFirst: "Oldest first",
    sortNameAz: "Name A–Z",
    sortNameZa: "Name Z–A",
    sortByStatus: "By adaptation status",
    sortDurationLongest: "Longest duration",
    sortDurationShortest: "Shortest duration",
    teamTitle: "Team",
    teamDesc: "Agent heartbeats and current tasks (via board_ops heartbeat).",
    statsTitle: "Statistics",
    statsDesc: "Aggregated from the current model list.",
    statTotal: "Total",
    statusCompleted: "Adaptation done",
    statAvgDuration: "Avg. duration",
    statusInProgress: "In progress",
    statNeedsAuth: "Needs auth",
    statusNotApplicable: "N/A",
    statSkipped: "Skipped",
    pipelineLegendTitle: "Pipeline",
    dryRunBadge: "Adaptation",
    benchmarkCompleted: "Benchmark",
    optimizationCompleted: "Optimization",
    modelsHeading: "Models",
    modelsDesc: "Adaptation tasks and pipeline stages (from exported JSON).",
    loading: "Loading…",
    noResults: "No models",
    noActiveAgents: "No agents",
    prevPage: "Previous",
    nextPage: "Next",
    owner: "Owner",
    throughput: "Throughput (NPU)",
    latency: "Latency",
    memory: "Memory",
    errorLogs: "Errors",
    updated: "Updated",
    duration: "Duration",
    downloadSource: "Source",
    source: "Notes",
    optTooltipSpeedup: "Speedup",
    optTooltipOptimizations: "Opts",
    optTooltipBaseline: "Baseline",
    optTooltipPerf: "Optimized",
    optTooltipLatencyReduction: "Latency Δ",
    optTooltipCosine: "Cosine",
    optTooltipUnavailable: "No optimization metrics",
    footerTagline: "Accelerating LLM inference on Ascend NPU",
    disclaimerTitle: "Disclaimer",
    disclaimer:
      "This board is for development coordination; refer to benchmarks and repo docs for authoritative metrics.",
    pipeAdapt: "Adapt",
    pipeBench: "Benchmark",
    pipeOpt: "Optimize",
    statusLabels: {
      pending: "Pending",
      in_progress: "In progress",
      completed: "Completed",
      needs_authorization: "Needs auth",
      not_applicable: "N/A",
      skipped: "Skipped",
      "": "—",
    },
    benchLabels: {
      pending: "Pending",
      in_progress: "In progress",
      completed: "Completed",
      skipped: "Skipped",
      not_applicable: "N/A",
      "": "—",
    },
    optLabels: {
      pending: "Pending",
      in_progress: "In progress",
      completed: "Completed",
      skipped: "Skipped",
      not_applicable: "N/A",
      "": "—",
    },
    agentStatus: {
      active: "Active",
      idle: "Idle",
      offline: "Offline",
    },
    roleAdapter: "Adapter agent",
    roleBenchmark: "Benchmark runner",
    roleOptimizer: "Performance optimizer",
    roleTeamLead: "Team lead",
    roleUnknown: "Agent",
  },
  zh: {
    brandTitle: "VAA",
    brandSub: "Ascend 适配",
    officialWebsite: "项目仓库",
    headerTitle: "vLLM Ascend 适配看板",
    headerDesc: "跟踪适配、Benchmark 与性能优化流水线状态（数据来自 vllm_board.db 导出）。",
    lastUpdated: "最后更新",
    sortLabel: "排序",
    sortNewestFirst: "最新优先",
    sortOldestFirst: "最旧优先",
    sortNameAz: "名称 A–Z",
    sortNameZa: "名称 Z–A",
    sortByStatus: "按适配状态",
    sortDurationLongest: "耗时最长",
    sortDurationShortest: "耗时最短",
    teamTitle: "团队",
    teamDesc: "Agent 心跳与当前任务（由 board_ops heartbeat 写入）。",
    statsTitle: "统计",
    statsDesc: "基于当前模型列表聚合。",
    statTotal: "模型总数",
    statusCompleted: "适配完成",
    statAvgDuration: "平均耗时",
    statusInProgress: "进行中",
    statNeedsAuth: "需授权",
    statusNotApplicable: "不适用",
    statSkipped: "已跳过",
    pipelineLegendTitle: "流水线",
    dryRunBadge: "适配",
    benchmarkCompleted: "基准",
    optimizationCompleted: "优化",
    modelsHeading: "模型",
    modelsDesc: "适配任务与流水线阶段（数据来自导出 JSON）。",
    loading: "加载中…",
    noResults: "无模型数据",
    noActiveAgents: "暂无 Agent 记录",
    prevPage: "上一页",
    nextPage: "下一页",
    owner: "负责人",
    throughput: "吞吐 (NPU)",
    latency: "延迟",
    memory: "显存/内存",
    errorLogs: "错误信息",
    updated: "更新",
    duration: "耗时",
    downloadSource: "来源",
    source: "备注",
    optTooltipSpeedup: "加速比",
    optTooltipOptimizations: "优化项",
    optTooltipBaseline: "基线",
    optTooltipPerf: "优化后",
    optTooltipLatencyReduction: "延迟降幅",
    optTooltipCosine: "余弦相似度",
    optTooltipUnavailable: "无优化指标",
    footerTagline: "在昇腾 NPU 上加速大模型推理",
    disclaimerTitle: "免责声明",
    disclaimer: "本看板为开发协作状态展示，指标与日志请以实际评测与仓库文档为准。",
    pipeAdapt: "适配",
    pipeBench: "基准",
    pipeOpt: "优化",
    statusLabels: {
      pending: "待处理",
      in_progress: "进行中",
      completed: "已完成",
      needs_authorization: "需授权",
      not_applicable: "不适用",
      skipped: "已跳过",
      "": "—",
    },
    benchLabels: {
      pending: "待处理",
      in_progress: "进行中",
      completed: "已完成",
      skipped: "已跳过",
      not_applicable: "不适用",
      "": "—",
    },
    optLabels: {
      pending: "待处理",
      in_progress: "进行中",
      completed: "已完成",
      skipped: "已跳过",
      not_applicable: "不适用",
      "": "—",
    },
    agentStatus: {
      active: "活跃",
      idle: "空闲",
      offline: "离线",
    },
    roleAdapter: "适配 Agent",
    roleBenchmark: "基准测试",
    roleOptimizer: "性能优化",
    roleTeamLead: "团队协调",
    roleUnknown: "Agent",
  },
};

let lang = localStorage.getItem("vaa-lang") || "zh";
let boardData = null;
let metricsOverrides = null;
let sortedModels = [];
let currentPage = 1;
let sortMode = "newest";

function t(key) {
  const bundle = I18N[lang] || I18N.zh;
  return bundle[key] ?? key;
}

function tStatus(kind, status) {
  const bundle = I18N[lang] || I18N.zh;
  const mapKey = kind === "adapt" ? "statusLabels" : kind === "bench" ? "benchLabels" : "optLabels";
  const m = bundle[mapKey] || {};
  const s = (status || "").trim().toLowerCase();
  return m[s] ?? status ?? "—";
}

function applyLang() {
  const bundle = I18N[lang] || I18N.zh;
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const k = el.getAttribute("data-i18n");
    if (k && bundle[k]) el.textContent = bundle[k];
  });
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === lang);
  });
  // option labels
  const sortSelect = document.getElementById("sortSelect");
  if (sortSelect) {
    sortSelect.querySelectorAll("option").forEach((opt) => {
      const k = opt.getAttribute("data-i18n");
      if (k && bundle[k]) opt.textContent = bundle[k];
    });
  }
  renderAll();
}

function parseTime(s) {
  if (!s || !String(s).trim()) return null;
  const x = String(s).trim().slice(0, 19);
  const d = new Date(x.replace(" ", "T"));
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDurationMs(ms) {
  if (ms == null || ms < 0) return "";
  if (ms < 1000) return `${ms}ms`;
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rs = s % 60;
  if (m < 60) return `${m}m ${rs}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

function modelDurationMs(m) {
  const a = parseTime(m.started_at);
  const b = parseTime(m.last_updated);
  if (!a || !b) return null;
  return Math.max(0, b - a);
}

function statusOrder(s) {
  const order = ["in_progress", "pending", "needs_authorization", "completed", "skipped", "not_applicable"];
  const i = order.indexOf((s || "").toLowerCase());
  return i === -1 ? 99 : i;
}

function sortModels(models, mode) {
  const copy = [...models];
  switch (mode) {
    case "newest":
      copy.sort((a, b) => (parseTime(b.last_updated) || 0) - (parseTime(a.last_updated) || 0));
      break;
    case "oldest":
      copy.sort((a, b) => (parseTime(a.last_updated) || 0) - (parseTime(b.last_updated) || 0));
      break;
    case "nameAz":
      copy.sort((a, b) => String(a.model_id).localeCompare(String(b.model_id)));
      break;
    case "nameZa":
      copy.sort((a, b) => String(b.model_id).localeCompare(String(a.model_id)));
      break;
    case "status":
      copy.sort((a, b) => statusOrder(a.status) - statusOrder(b.status));
      break;
    case "durLong":
      copy.sort((a, b) => (modelDurationMs(b) || 0) - (modelDurationMs(a) || 0));
      break;
    case "durShort":
      copy.sort((a, b) => (modelDurationMs(a) || Infinity) - (modelDurationMs(b) || Infinity));
      break;
    default:
      break;
  }
  return copy;
}

function mergeMetrics(model) {
  const ovr = metricsOverrides && metricsOverrides[model.model_id];
  if (!ovr) return model;
  return {
    ...model,
    throughput_npu: ovr.throughput_npu ?? model.throughput_npu,
    latency_npu: ovr.latency_npu ?? model.latency_npu,
    memory_usage_npu: ovr.memory_usage_npu ?? model.memory_usage_npu,
    optimization_metrics: ovr.optimization ?? model.optimization_metrics,
  };
}

function computeStats(models) {
  const total = models.length;
  let completed = 0;
  let inProgress = 0;
  let needsAuth = 0;
  let na = 0;
  let skipped = 0;
  let benchDone = 0;
  let optDone = 0;
  const durs = [];

  for (const m of models) {
    const st = (m.status || "").toLowerCase();
    if (st === "completed") completed++;
    if (st === "in_progress") inProgress++;
    if (st === "needs_authorization") needsAuth++;
    if (st === "not_applicable") na++;
    if (st === "skipped") skipped++;
    if ((m.benchmark_status || "").toLowerCase() === "completed") benchDone++;
    if ((m.optimization_status || "").toLowerCase() === "completed") optDone++;
    if (st === "completed") {
      const d = modelDurationMs(m);
      if (d != null) durs.push(d);
    }
  }

  const avgDurationMs = durs.length ? durs.reduce((a, b) => a + b, 0) / durs.length : null;

  return {
    total,
    completed,
    inProgress,
    needsAuth,
    na,
    skipped,
    benchDone,
    optDone,
    avgDurationMs,
  };
}

function statusPillClass(status) {
  const s = (status || "").toLowerCase();
  if (s === "completed") return "status-pill ok";
  if (s === "in_progress") return "status-pill run";
  if (s === "pending") return "status-pill pend";
  if (s === "needs_authorization") return "status-pill warn";
  return "status-pill muted";
}

function renderAgents(agents) {
  const grid = document.getElementById("teamGrid");
  const empty = document.getElementById("noAgents");
  grid.innerHTML = "";
  if (!agents || !agents.length) {
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  for (const a of agents) {
    const card = document.createElement("div");
    card.className = "agent-card";
    const badgeClass =
      {
        primary: "badge-primary",
        info: "badge-info",
        success: "badge-success",
        warning: "badge-warning",
        muted: "badge-muted",
      }[a.badge?.variant] || "badge-muted";
    const st = (a.status || "offline").toLowerCase();
    const stLabel = (I18N[lang].agentStatus || {})[st] || st;
    card.innerHTML = `
      <div class="agent-head">
        <span class="agent-name">${escapeHtml(a.name || a.id)}</span>
        <span class="badge ${badgeClass}">${escapeHtml(a.badge?.text || "")}</span>
      </div>
      <div class="agent-role">${escapeHtml(t(a.roleKey) || "")}</div>
      <div class="agent-status ${escapeHtml(st)}">${escapeHtml(stLabel)}</div>
      <div class="agent-task">${a.current_task ? escapeHtml(a.current_task) : "—"}</div>
    `;
    grid.appendChild(card);
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderStats(models) {
  const stats = computeStats(models);
  const grid = document.getElementById("statsGrid");
  const legend = document.getElementById("pipelineLegend");

  const items = [
    { label: "statTotal", value: stats.total },
    { label: "statusCompleted", value: stats.completed },
    {
      label: "statAvgDuration",
      value: stats.avgDurationMs != null ? formatDurationMs(stats.avgDurationMs) : "—",
    },
    { label: "statusInProgress", value: stats.inProgress },
    { label: "statNeedsAuth", value: stats.needsAuth },
    { label: "statusNotApplicable", value: stats.na },
    { label: "statSkipped", value: stats.skipped },
  ];

  grid.innerHTML = items
    .map(
      (it) => `
    <div class="stat-card">
      <div class="stat-label">${escapeHtml(t(it.label))}</div>
      <div class="stat-value">${escapeHtml(String(it.value))}</div>
    </div>
  `
    )
    .join("");

  legend.innerHTML = `
    <span><strong>${escapeHtml(t("pipelineLegendTitle"))}:</strong></span>
    <span>${escapeHtml(t("dryRunBadge"))}: <strong>${stats.completed}</strong></span>
    <span>${escapeHtml(t("benchmarkCompleted"))}: <strong>${stats.benchDone}</strong></span>
    <span>${escapeHtml(t("optimizationCompleted"))}: <strong>${stats.optDone}</strong></span>
  `;
}

function pipeClass(st) {
  const s = (st || "").toLowerCase();
  if (s === "completed") return "pipe done";
  if (s === "in_progress") return "pipe run";
  return "pipe skip";
}

function renderOptimizationBlock(m) {
  const om = m.optimization_metrics;
  if (!om || typeof om !== "object") {
    return `<div class="opt-block">${escapeHtml(t("optTooltipUnavailable"))}</div>`;
  }
  const sp = om.speedup != null ? `${Number(om.speedup).toFixed(2)}×` : "—";
  const lines = [];
  lines.push(`<strong>${escapeHtml(t("optTooltipSpeedup"))}</strong> ${escapeHtml(sp)}`);
  if (om.baseline_latency_s != null && om.perf_latency_s != null) {
    lines.push(
      `${escapeHtml(t("optTooltipBaseline"))} ${Number(om.baseline_latency_s).toFixed(4)}s · ${escapeHtml(t("optTooltipPerf"))} ${Number(om.perf_latency_s).toFixed(4)}s`
    );
  }
  if (om.latency_reduction_pct != null) {
    lines.push(`${escapeHtml(t("optTooltipLatencyReduction"))} ${Number(om.latency_reduction_pct).toFixed(1)}%`);
  }
  if (om.cosine_similarity != null) {
    lines.push(`${escapeHtml(t("optTooltipCosine"))} ${Number(om.cosine_similarity).toFixed(4)}`);
  }
  if (om.optimizations != null) {
    lines.push(`${escapeHtml(t("optTooltipOptimizations"))}: ${escapeHtml(String(om.optimizations))}`);
  }
  return `<div class="opt-block">${lines.map((l) => `<div>${l}</div>`).join("")}</div>`;
}

function renderModelsPage() {
  const grid = document.getElementById("modelsGrid");
  const loading = document.getElementById("loading");
  const noResults = document.getElementById("noResults");
  const pager = document.getElementById("pager");

  if (!boardData) {
    loading.classList.remove("hidden");
    noResults.classList.add("hidden");
    grid.innerHTML = "";
    pager.classList.add("hidden");
    return;
  }
  loading.classList.add("hidden");

  const models = sortedModels.map(mergeMetrics);
  if (!models.length) {
    noResults.classList.remove("hidden");
    grid.innerHTML = "";
    pager.classList.add("hidden");
    return;
  }
  noResults.classList.add("hidden");

  const totalPages = Math.max(1, Math.ceil(models.length / PAGE_SIZE));
  if (currentPage > totalPages) currentPage = totalPages;
  const start = (currentPage - 1) * PAGE_SIZE;
  const slice = models.slice(start, start + PAGE_SIZE);

  grid.innerHTML = slice
    .map((m) => {
      const shortName = (m.model_id && m.model_id.split("/").pop()) || "—";
      const org = (m.model_id && m.model_id.includes("/") && m.model_id.split("/")[0]) || "";
      const path = (m.adaptation_path || "").replace(/^adaptations\//, "");
      const adaptSt = (m.status || "").toLowerCase();
      const benchSt = (m.benchmark_status || "").toLowerCase();
      const optSt = (m.optimization_status || "").toLowerCase();

      const dur = formatDurationMs(modelDurationMs(m)) || "n/a";
      const updated = m.last_updated ? String(m.last_updated).slice(0, 10) : "TBD";

      const tp = m.throughput_npu || "—";
      const lat = m.latency_npu || "—";
      const mem = m.memory_usage_npu || "—";

      const err = (m.failure_reason || "").trim();

      return `
      <article class="model-card">
        <div class="model-title-row">
          <div>
            <h3 class="model-title">${escapeHtml(shortName)}</h3>
            <p class="model-org">${escapeHtml(org)}</p>
          </div>
          <span class="${statusPillClass(m.status)}">${escapeHtml(tStatus("adapt", m.status))}</span>
        </div>
        <div class="path-pill" title="${escapeHtml(m.adaptation_path || "")}">${escapeHtml(path || "—")}</div>
        <div class="pipeline-row">
          <span class="${pipeClass(m.status)}">${escapeHtml(t("pipeAdapt"))}: ${escapeHtml(tStatus("adapt", m.status))}</span>
          <span class="${pipeClass(m.benchmark_status)}">${escapeHtml(t("pipeBench"))}: ${escapeHtml(tStatus("bench", m.benchmark_status))}</span>
          <span class="${pipeClass(m.optimization_status)}">${escapeHtml(t("pipeOpt"))}: ${escapeHtml(tStatus("opt", m.optimization_status))}</span>
        </div>
        ${renderOptimizationBlock(m)}
        <p class="model-org" style="margin:0">${escapeHtml(m.description || t("source"))}</p>
        <div class="metrics-grid">
          <div class="metric"><div class="metric-label">${escapeHtml(t("throughput"))}</div><div class="metric-value">${escapeHtml(tp)}</div></div>
          <div class="metric"><div class="metric-label">${escapeHtml(t("latency"))}</div><div class="metric-value">${escapeHtml(lat)}</div></div>
          <div class="metric"><div class="metric-label">${escapeHtml(t("memory"))}</div><div class="metric-value">${escapeHtml(mem)}</div></div>
        </div>
        ${err ? `<div class="error-box"><strong>${escapeHtml(t("errorLogs"))}</strong> ${escapeHtml(err)}</div>` : ""}
        <div class="model-footer">
          <span>${escapeHtml(t("owner"))}: ${escapeHtml(m.owner || "—")}</span>
          <span>${escapeHtml(t("updated"))}: ${escapeHtml(updated)}</span>
          <span>${escapeHtml(t("duration"))}: ${escapeHtml(dur)}</span>
          <span>${escapeHtml(t("downloadSource"))}: ${escapeHtml(m.source || "huggingface")}</span>
        </div>
      </article>
    `;
    })
    .join("");

  if (models.length > PAGE_SIZE) {
    pager.classList.remove("hidden");
    document.getElementById("pageIndicator").textContent = `${currentPage} / ${totalPages}`;
    document.getElementById("prevPage").disabled = currentPage <= 1;
    document.getElementById("nextPage").disabled = currentPage >= totalPages;
  } else {
    pager.classList.add("hidden");
  }
}

function renderAll() {
  if (!boardData) return;
  const meta = boardData.meta || {};
  document.getElementById("lastUpdated").textContent = meta.lastUpdated || "—";
  const proj = document.getElementById("linkProject");
  if (proj && meta.projectUrl) proj.href = meta.projectUrl;

  renderAgents(boardData.agents || []);
  const models = boardData.models || [];
  renderStats(models);
  sortedModels = sortModels(models, sortMode);
  renderModelsPage();
}

async function loadJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url} ${res.status}`);
  return res.json();
}

async function init() {
  document.getElementById("year").textContent = String(new Date().getFullYear());

  try {
    boardData = await loadJson("data/board.json");
  } catch (e) {
    console.error(e);
    boardData = { meta: {}, agents: [], models: [] };
  }
  try {
    metricsOverrides = await loadJson("data/metrics_overrides.json");
  } catch {
    metricsOverrides = null;
  }

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      lang = btn.dataset.lang || "zh";
      localStorage.setItem("vaa-lang", lang);
      applyLang();
    });
  });

  document.getElementById("sortSelect").addEventListener("change", (e) => {
    sortMode = e.target.value;
    currentPage = 1;
    renderAll();
  });

  document.getElementById("prevPage").addEventListener("click", () => {
    currentPage = Math.max(1, currentPage - 1);
    renderAll();
  });
  document.getElementById("nextPage").addEventListener("click", () => {
    const n = boardData?.models?.length || 0;
    const totalPages = Math.max(1, Math.ceil(n / PAGE_SIZE));
    currentPage = Math.min(totalPages, currentPage + 1);
    renderAll();
  });

  applyLang();
}

init();
