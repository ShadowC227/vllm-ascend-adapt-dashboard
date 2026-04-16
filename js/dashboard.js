/**
 * VAA Dashboard — data/board.json（静态文件或本地 serve_live 每次从 SQLite 生成）
 * 可选 data/metrics_overrides.json；本地实时服务下可轮询自动刷新。
 */

const PAGE_SIZE = 6;

/** 与 SQLite models 表列顺序一致（展示用） */
const MODEL_FIELD_ORDER = [
  "model_id",
  "source",
  "priority",
  "status",
  "started_at",
  "last_updated",
  "adaptation_duration_seconds",
  "failure_reason",
  "url",
  "description",
  "notes",
  "adaptation_path",
  "owner",
  "benchmark_status",
  "benchmark_started_at",
  "benchmark_last_updated",
  "benchmark_owner",
  "benchmark_notes",
  "optimization_status",
  "optimization_started_at",
  "optimization_last_updated",
  "optimization_owner",
  "optimization_notes",
];

/** benchmark_results 表列（展示顺序） */
const BENCH_COLS = [
  "id",
  "benchmark_stage",
  "tensor_parallel_size",
  "output_tok_per_s",
  "req_per_s",
  "mean_ttft_ms",
  "mean_tpot_ms",
  "peak_tok_per_s",
  "total_tok_per_s",
  "bench_params",
  "config",
  "log_file",
  "created_at",
  "notes",
];

const ACC_COLS = ["id", "dataset", "benchmark_stage", "accuracy", "total_samples", "correct_samples", "created_at", "notes"];

/** optimization_methods 解析出的标签：以下项不在卡片上展示（环境变量等） */
const OPT_CHIP_HIDE_EXACT = new Set([
  "cudagraph_FULL_DECODE_ONLY",
  "TASK_QUEUE_ENABLE=1",
  "CPU_AFFINITY_CONF=1",
  "OMP_NUM_THREADS=8",
  "jemalloc",
  "PYTORCH_NPU_ALLOC_CONF=expandable_segments:True",
]);

function shouldHideOptChipLabel(chip) {
  const t = String(chip).trim();
  if (OPT_CHIP_HIDE_EXACT.has(t)) return true;
  const underscored = t.replace(/\s+/g, "_");
  return OPT_CHIP_HIDE_EXACT.has(underscored);
}

const I18N = {
  en: {
    brandTitle: "VAA",
    brandSub: "Ascend Adaptation",
    officialWebsite: "Repository",
    headerTitle: "vLLM Ascend Adaptation Board",
    headerDesc:
      "Three stages per model: adaptation, accuracy alignment, and performance optimization. Each card shows optimized performance only, plus speedup vs baseline.",
    headerDescLive:
      "Three stages: adaptation → accuracy alignment → performance optimization; cards show optimized performance only, plus improvement vs baseline. Live from local SQLite via serve_live.py — enable auto-refresh below.",
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
    stagePanelAdaptation: "Adaptation Stage",
    stagePanelBenchmark: "Accuracy Alignment Stage",
    stagePanelOptimization: "Performance Optimization Stage",
    stageCompletedRatio: "Completed",
    stagePendingQueue: "Pending",
    stageActiveQueue: "In progress",
    stageTerminal: "Terminal",
    dryRunBadge: "Adaptation",
    benchmarkCompleted: "Accuracy alignment",
    optimizationCompleted: "Performance optimization",
    modelsHeading: "Models",
    modelsDesc:
      "Pipeline: adaptation → accuracy alignment → performance optimization. Cards show optimized performance only, plus speedup vs baseline.",
    livePollLabel: "Auto refresh",
    pollOff: "Off",
    syncFailed: "Refresh failed",
    loading: "Loading…",
    noResults: "No models",
    noActiveAgents: "No agents",
    prevPage: "Previous",
    nextPage: "Next",
    owner: "Owner",
    throughput: "Throughput (NPU, tok/s)",
    latency: "Latency",
    memory: "Memory",
    errorLogs: "Errors",
    updated: "Updated",
    duration: "Duration",
    adaptDurationLabel: "Adaptation duration",
    adaptDurationRunning: "running",
    downloadSource: "Source",
    source: "Notes",
    optTooltipSpeedup: "Speedup",
    optTooltipOptimizations: "Opts",
    optTooltipBaseline: "Baseline",
    optTooltipPerf: "Optimized",
    optTooltipCosine: "Cosine",
    optTooltipUnavailable: "No optimization metrics",
    optMetricName: "Metric",
    optMetricValue: "Value",
    optMethodLabel: "Optimization method",
    modelsTableTitle: "models (table)",
    accuracyTableTitle: "accuracy_results (table)",
    accuracySectionTitle: "Accuracy",
    accuracyStageOther: "Other",
    modelsTableHint: "Columns match SQLite models table.",
    benchGlobalTitle: "benchmark_results (all rows)",
    benchGlobalDesc:
      "Full export from vllm_board.db. The SQLite table name is benchmark_results. If your schema only defines benchmark, the server maps it into benchmark_results in JSON.",
    benchMetaLine: "($n rows · SQLite table $t)",
    benchGlobalEmpty:
      "No benchmark rows in the loaded JSON. Run export_board_json.py or serve_live.py, and ensure benchmark_results (or benchmark) has rows.",
    benchTableTitle: "benchmark_results (table)",
    benchColStage: "Stage",
    benchColTP: "TP",
    benchColTokS: "tok/s",
    benchColReqS: "req/s",
    benchColTTFT: "TTFT ms",
    benchColTPOT: "TPOT ms",
    benchColPeak: "Peak",
    benchColNotes: "Notes",
    stageBaseline: "baseline",
    stageOptimized: "optimized",
    footerTagline: "Accelerating LLM inference on Ascend NPU",
    disclaimerTitle: "Disclaimer",
    disclaimer:
      "This board is for development coordination; refer to benchmarks and repo docs for authoritative metrics.",
    pipeAdapt: "Adapt",
    pipeBench: "Accuracy alignment",
    pipeOpt: "Performance optimization",
    reviewActionRow: "Review",
    reviewApprove: "Approve",
    schemeALabel: "Latency Priority",
    schemeBLabel: "Throughput Priority",
    schemeBaselineNote: "Shared baseline",
    reviewReject: "Reject",
    reviewApproved: "Approved",
    sendBackLabel: "Send back:",
    sendBackAdaptation: "Adaptation",
    sendBackBenchmark: "Accuracy alignment",
    sendBackOptimization: "Optimization",
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
    roleBenchmark: "Accuracy alignment",
    roleOptimizer: "Performance optimization",
    roleTeamLead: "Team lead",
    roleUnknown: "Agent",
    modelDocsOpen: "Adaptation docs",
    docClose: "Close",
    docLangLegend: "Document language",
    docLangEn: "English",
    docLangZh: "中文",
    docDownloadCurrent: "Download current",
    docDownloadEn: "Download English .md",
    docDownloadZh: "Download Chinese .md",
    docEmpty: "(No document file)",
    docApiUnavailable:
      "Could not load docs: start serve_live.py, or run scripts/export_model_docs.py so data/model_docs.json exists, then hard-refresh.",
    docLoading: "Loading…",
  },
  zh: {
    brandTitle: "VAA",
    brandSub: "Ascend 适配",
    officialWebsite: "项目仓库",
    headerTitle: "vLLM Ascend 适配看板",
    headerDesc:
      "模型分三阶段：适配、精度对齐、性能优化。卡片只展示优化后的性能指标，并展示相对 baseline 的加速比。",
    headerDescLive:
      "模型三阶段：适配、精度对齐、性能优化；卡片只展示优化后的性能指标，并展示相对 baseline 的提升幅度。已通过本地实时服务连接数据库（serve_live.py），开启下方「自动刷新」即可随心跳/任务更新。",
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
    stagePanelAdaptation: "适配阶段",
    stagePanelBenchmark: "精度对齐阶段",
    stagePanelOptimization: "性能优化阶段",
    stageCompletedRatio: "完成率",
    stagePendingQueue: "待处理",
    stageActiveQueue: "进行中",
    stageTerminal: "终态",
    dryRunBadge: "适配",
    benchmarkCompleted: "精度对齐",
    optimizationCompleted: "性能优化",
    modelsHeading: "模型",
    modelsDesc:
      "三阶段流水线：适配 → 精度对齐 → 性能优化；卡片只展示优化后的性能指标，并展示相对 baseline 的加速比。",
    livePollLabel: "自动刷新",
    pollOff: "关闭",
    syncFailed: "刷新失败",
    loading: "加载中…",
    noResults: "无模型数据",
    noActiveAgents: "暂无 Agent 记录",
    prevPage: "上一页",
    nextPage: "下一页",
    owner: "负责人",
    throughput: "吞吐（NPU, tok/s）",
    latency: "延迟",
    memory: "显存/内存",
    errorLogs: "错误信息",
    updated: "更新",
    duration: "耗时",
    adaptDurationLabel: "适配耗时",
    adaptDurationRunning: "进行中",
    downloadSource: "来源",
    source: "备注",
    optTooltipSpeedup: "加速比",
    optTooltipOptimizations: "优化项",
    optTooltipBaseline: "baseline（精度对齐）",
    optTooltipPerf: "optimized（性能优化）",
    optTooltipCosine: "余弦相似度",
    optTooltipUnavailable: "暂无性能优化数据",
    optMetricName: "指标",
    optMetricValue: "值",
    optMethodLabel: "优化手段",
    modelsTableTitle: "models 表字段",
    accuracyTableTitle: "accuracy_results 表",
    accuracySectionTitle: "精度结果",
    accuracyStageOther: "其他",
    modelsTableHint: "字段名与 SQLite 表一致。",
    benchGlobalTitle: "benchmark_results（全表）",
    benchGlobalDesc:
      "以下为库中性能数据全量展示。标准表名为 SQLite 的 benchmark_results；若库里只有名为 benchmark 的表，后端也会映射到此处 JSON 的 benchmark_results 字段。",
    benchMetaLine: "（共 $n 行 · 库表 $t）",
    benchGlobalEmpty:
      "当前加载的 JSON 里没有 benchmark 行。请执行 export 或使用 serve_live，并确认库表 benchmark_results（或 benchmark）中有数据。",
    benchTableTitle: "benchmark_results 表",
    benchColStage: "阶段",
    benchColTP: "TP",
    benchColTokS: "tok/s",
    benchColReqS: "req/s",
    benchColTTFT: "TTFT ms",
    benchColTPOT: "TPOT ms",
    benchColPeak: "Peak",
    benchColNotes: "备注",
    stageBaseline: "baseline",
    stageOptimized: "optimized",
    footerTagline: "在昇腾 NPU 上加速大模型推理",
    disclaimerTitle: "免责声明",
    disclaimer: "本看板为开发协作状态展示，指标与日志请以实际评测与仓库文档为准。",
    pipeAdapt: "适配",
    pipeBench: "精度对齐",
    pipeOpt: "性能优化",
    reviewActionRow: "人工审核",
    reviewApprove: "通过",
    schemeALabel: "延迟优先",
    schemeBLabel: "吞吐优先",
    schemeBaselineNote: "共享基线",
    reviewReject: "打回",
    reviewApproved: "已通过",
    sendBackLabel: "阶段回退:",
    sendBackAdaptation: "适配",
    sendBackBenchmark: "精度对齐",
    sendBackOptimization: "性能优化",
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
    roleBenchmark: "精度对齐",
    roleOptimizer: "性能优化",
    roleTeamLead: "团队协调",
    roleUnknown: "Agent",
    modelDocsOpen: "适配文档",
    docClose: "关闭",
    docLangLegend: "文档语言",
    docLangEn: "English",
    docLangZh: "中文",
    docDownloadCurrent: "下载当前",
    docDownloadEn: "下载英文 MD",
    docDownloadZh: "下载中文 MD",
    docEmpty: "（暂无文档文件）",
    docApiUnavailable:
      "无法加载文档：请用 serve_live.py 启动看板，或在看板目录执行 python3 scripts/export_model_docs.py 生成 data/model_docs.json 后强刷页面。",
    docLoading: "加载中…",
  },
};

let lang = localStorage.getItem("vaa-lang") || "zh";
let boardData = null;
let sortedModels = [];
let currentPage = 1;
let sortMode = "newest";
let pollTimer = null;
/** 仅首屏做一次卡片渐入；轮询/排序/翻页不再触发动画，避免整页反复闪动 */
let didStaggerRevealOnce = false;
let boardRefreshInFlight = false;

/** 适配目录 Markdown：`{stem}.md` 英文、`{stem}_cn.md` 中文（与 vllm-ascend-adapt/adaptations/... 约定一致） */
let docModalState = {
  adaptPath: "",
  stem: "",
  displayTitle: "",
  en: { content: "", exists: false },
  zh: { content: "", exists: false },
  enFile: "",
  zhFile: "",
  docLang: "zh",
  apiReached: false,
};
let mdLibsPromise = null;

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
  const pollSelect = document.getElementById("pollSelect");
  if (pollSelect) {
    pollSelect.querySelectorAll("option[data-i18n]").forEach((opt) => {
      const k = opt.getAttribute("data-i18n");
      if (k && bundle[k]) opt.textContent = bundle[k];
    });
  }
  const heroDesc = document.querySelector('[data-i18n="headerDesc"]');
  if (heroDesc && boardData?.meta?.dataSource === "live") {
    heroDesc.textContent = bundle.headerDescLive || bundle.headerDesc;
  }
  const docModal = document.getElementById("modelDocsModal");
  if (docModal && !docModal.classList.contains("hidden")) {
    const titleEl = document.getElementById("modelDocsTitle");
    if (titleEl) {
      titleEl.textContent = `${t("modelDocsOpen")} · ${docModalState.displayTitle || docModalState.stem || "—"}`;
    }
    updateDocModalBodyFromCache();
  }
  renderAll();
}

function refreshDocModalI18n() {
  const bundle = I18N[lang] || I18N.zh;
  document.querySelectorAll("#modelDocsModal [data-i18n]").forEach((el) => {
    const k = el.getAttribute("data-i18n");
    if (k && bundle[k]) el.textContent = bundle[k];
  });
}

async function ensureMdLibs() {
  if (!mdLibsPromise) {
    mdLibsPromise = Promise.all([
      import("https://cdn.jsdelivr.net/npm/marked@15.0.6/lib/marked.esm.js"),
      import("https://cdn.jsdelivr.net/npm/dompurify@3.1.7/+esm"),
    ]);
  }
  return mdLibsPromise;
}

async function markdownToSafeHtml(md) {
  const text = (md || "").trim();
  if (!text) {
    return `<p class="doc-empty-msg">${escapeHtml(t("docEmpty"))}</p>`;
  }
  try {
    const [{ marked }, domPurifyMod] = await ensureMdLibs();
    const DOMPurify = domPurifyMod.default;
    const raw = marked.parse(text);
    return DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } });
  } catch (e) {
    console.warn(e);
    return `<pre class="doc-fallback-pre">${escapeHtml(text)}</pre>`;
  }
}

function downloadTextAsFile(filename, text) {
  const blob = new Blob([text ?? ""], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename || "document.md";
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  URL.revokeObjectURL(a.href);
  a.remove();
}

async function updateDocModalBodyFromCache() {
  const body = document.getElementById("docModalBody");
  if (!body) return;
  const slot = docModalState.docLang === "en" ? docModalState.en : docModalState.zh;
  const html = await markdownToSafeHtml(slot.content || "");
  body.innerHTML = html;
}

function setDocModalDocLang(which) {
  docModalState.docLang = which === "en" ? "en" : "zh";
  document.querySelectorAll(".doc-lang-btn").forEach((b) => {
    const on = b.dataset.docLang === docModalState.docLang;
    b.classList.toggle("active", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
  updateDocModalBodyFromCache();
}

function normalizeModelDocsPack(pack) {
  const enC = pack.en?.content ?? "";
  const zhC = pack.zh?.content ?? "";
  return {
    en: {
      content: enC,
      exists: !!(pack.en?.exists ?? String(enC).trim()),
    },
    zh: {
      content: zhC,
      exists: !!(pack.zh?.exists ?? String(zhC).trim()),
    },
    enFile: pack.enFile ?? "",
    zhFile: pack.zhFile ?? "",
  };
}

/** 先请求实时 API，失败再读静态 data/model_docs.json（python -m http.server 也可用） */
async function fetchModelDocsPayload(adaptPath, stem) {
  const qs = new URLSearchParams();
  qs.set("adaptPath", adaptPath || "");
  qs.set("stem", stem || "");
  const q = qs.toString();

  const apiUrls = [
    `${window.location.origin}/api/model-docs?${q}`,
    new URL(`api/model-docs?${q}`, window.location.href).href,
  ];
  const triedApi = new Set();
  for (const url of apiUrls) {
    if (triedApi.has(url)) continue;
    triedApi.add(url);
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (res.ok) {
        const raw = await res.json();
        if (raw && typeof raw === "object") return { data: normalizeModelDocsPack(raw), source: "api" };
      }
    } catch {
      /* 继续尝试静态 */
    }
  }

  const staticUrls = [
    new URL("data/model_docs.json", `${window.location.origin}/`).href,
    new URL("data/model_docs.json", window.location.href).href,
  ];
  const triedStatic = new Set();
  for (const url of staticUrls) {
    if (triedStatic.has(url)) continue;
    triedStatic.add(url);
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) continue;
      const idx = await res.json();
      const pack = idx.byStem && idx.byStem[stem];
      if (!pack) continue;
      const norm = normalizeModelDocsPack(pack);
      if (norm.en.exists || norm.zh.exists) return { data: norm, source: "static" };
    } catch {
      /* */
    }
  }
  return null;
}

async function fetchAndShowModelDocs(adaptPath, stem, displayTitle) {
  docModalState = {
    adaptPath,
    stem,
    displayTitle,
    en: { content: "", exists: false },
    zh: { content: "", exists: false },
    enFile: stem ? `${stem}.md` : "",
    zhFile: stem ? `${stem}_cn.md` : "",
    docLang: lang === "en" ? "en" : "zh",
    apiReached: false,
  };
  const modal = document.getElementById("modelDocsModal");
  const loading = document.getElementById("docModalLoading");
  const hint = document.getElementById("docApiHint");
  const titleEl = document.getElementById("modelDocsTitle");
  const bodyEl = document.getElementById("docModalBody");
  if (!modal) return;
  refreshDocModalI18n();
  titleEl.textContent = `${t("modelDocsOpen")} · ${displayTitle || stem || "—"}`;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  loading?.classList.remove("hidden");
  hint?.classList.add("hidden");
  if (bodyEl) bodyEl.innerHTML = "";

  setDocModalDocLang(docModalState.docLang);

  try {
    const result = await fetchModelDocsPayload(adaptPath, stem);
    if (result) {
      docModalState.apiReached = true;
      const data = result.data;
      docModalState.en = data.en || { content: "", exists: false };
      docModalState.zh = data.zh || { content: "", exists: false };
      if (data.enFile) docModalState.enFile = data.enFile;
      if (data.zhFile) docModalState.zhFile = data.zhFile;
    } else {
      docModalState.apiReached = false;
      hint?.classList.remove("hidden");
      refreshDocModalI18n();
    }
  } catch {
    docModalState.apiReached = false;
    hint?.classList.remove("hidden");
    refreshDocModalI18n();
  } finally {
    loading?.classList.add("hidden");
  }
  await updateDocModalBodyFromCache();
  document.getElementById("modelDocsClose")?.focus();
}

function closeModelDocsModal() {
  const modal = document.getElementById("modelDocsModal");
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
}

function initModelDocsModal() {
  const modal = document.getElementById("modelDocsModal");
  if (!modal) return;
  modal.querySelectorAll("[data-doc-modal-dismiss]").forEach((el) => {
    el.addEventListener("click", () => closeModelDocsModal());
  });
  modal.querySelectorAll(".doc-lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => setDocModalDocLang(btn.dataset.docLang));
  });
  document.getElementById("docDownloadCurrent")?.addEventListener("click", () => {
    const isEn = docModalState.docLang === "en";
    const fn = isEn ? docModalState.enFile : docModalState.zhFile;
    const text = isEn ? docModalState.en.content : docModalState.zh.content;
    downloadTextAsFile(fn, text);
  });
  document.getElementById("docDownloadEn")?.addEventListener("click", () => {
    downloadTextAsFile(docModalState.enFile, docModalState.en.content);
  });
  document.getElementById("docDownloadZh")?.addEventListener("click", () => {
    downloadTextAsFile(docModalState.zhFile, docModalState.zh.content);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal && !modal.classList.contains("hidden")) closeModelDocsModal();
  });

  const grid = document.getElementById("modelsGrid");
  grid?.addEventListener("click", (e) => {
    const btn = e.target.closest(".model-docs-btn");
    if (!btn || !grid.contains(btn)) return;
    e.preventDefault();
    const ap = btn.getAttribute("data-adapt-path") || "";
    const stem = btn.getAttribute("data-stem") || "";
    const title = btn.getAttribute("data-title") || stem;
    fetchAndShowModelDocs(ap, stem, title);
  });

  // Review action buttons (approve / reject)
  grid?.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-review");
    if (!btn || !grid.contains(btn)) return;
    e.preventDefault();
    const action = btn.dataset.reviewAction;
    const modelId = btn.dataset.modelId;
    if (!action || !modelId) return;
    const confirmed = confirm(action === "approve" ? "Approve " + modelId + "?" : "Reject (send back) " + modelId + "?");
    if (!confirmed) return;
    btn.disabled = true;
    const apiUrl = window.DASHBOARD_API_URL || "";
    fetch(apiUrl + "/api/human-review/" + encodeURIComponent(modelId), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: action === "approve" ? "completed" : "pending" }),
    })
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(() => { refreshAllData(); })
      .catch((err) => { alert("Review failed: " + err.message); btn.disabled = false; });
  });

  // Send-back buttons
  grid?.addEventListener("click", (e) => {
    const btn = e.target.closest(".send-back-btn");
    if (!btn || !grid.contains(btn)) return;
    e.preventDefault();
    const modelId = btn.dataset.modelId;
    const targetStage = btn.dataset.targetStage;
    if (!modelId || !targetStage) return;
    const stageNames = { adaptation: "\u9002\u914d", benchmark: "\u7cbe\u5ea6\u5bf9\u9f50", optimization: "\u6027\u80fd\u4f18\u5316" };
    const confirmed = confirm("\u786e\u5b9a\u5c06 " + modelId + " \u6253\u56de\u5230\u300c" + (stageNames[targetStage] || targetStage) + "\u300d\uff1f");
    if (!confirmed) return;
    btn.disabled = true;
    const apiUrl = window.DASHBOARD_API_URL || "";
    fetch(apiUrl + "/api/send-back/" + encodeURIComponent(modelId), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_stage: targetStage }),
    })
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(() => { refreshAllData(); })
      .catch((err) => { alert("Send back failed: " + err.message); btn.disabled = false; });
  });
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

/** 适配耗时（毫秒）：优先 `adaptation_duration_seconds`，否则按 `started_at` / `last_updated`；进行中为当前已耗时 */
function adaptationDurationMs(m) {
  const sec = m.adaptation_duration_seconds;
  if (sec != null && sec !== "" && Number.isFinite(Number(sec))) {
    return Math.max(0, Number(sec) * 1000);
  }
  const a = parseTime(m.started_at);
  const st = (m.status || "").toLowerCase();
  if (!a) return null;
  if (st === "in_progress") {
    return Math.max(0, Date.now() - a.getTime());
  }
  const b = parseTime(m.last_updated);
  if (!b) return null;
  return Math.max(0, b - a);
}

function formatAdaptDurationLine(m) {
  const ms = adaptationDurationMs(m);
  if (ms == null) return "—";
  const s = formatDurationMs(ms);
  return s || "—";
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
      copy.sort((a, b) => (adaptationDurationMs(b) || 0) - (adaptationDurationMs(a) || 0));
      break;
    case "durShort":
      copy.sort((a, b) => (adaptationDurationMs(a) || Infinity) - (adaptationDurationMs(b) || Infinity));
      break;
    default:
      break;
  }
  return copy;
}

function normModelId(s) {
  return String(s ?? "").trim().toLowerCase();
}

/** 只保留最终展示所需的三个 benchmark_stage */
const FINAL_BENCH_STAGES = new Set(["baseline", "final_scheme_a", "final_scheme_b"]);

function benchRowsForModel(modelId) {
  const want = normModelId(modelId);
  return (boardData.benchmark_results || []).filter((r) => {
    if (normModelId(r.model_id) !== want) return false;
    const stage = String(r.benchmark_stage || "").trim().toLowerCase();
    return FINAL_BENCH_STAGES.has(stage);
  });
}

function fmtBenchNum(v) {
  if (v == null || v === "") return "—";
  const x = Number(v);
  if (Number.isNaN(x)) return "—";
  return Math.abs(x) >= 100 ? x.toFixed(2) : x.toFixed(2);
}

function fmtAccuracyPct(v) {
  if (v == null || v === "") return "—";
  const x = Number(v);
  if (Number.isNaN(x)) return "—";
  return `${x.toFixed(1)}%`;
}

function mergeMetrics(model) {
  const rows = benchRowsForModel(model.model_id);
  const want = normModelId(model.model_id);
  const accRows = (boardData.accuracy_results || []).filter((r) => normModelId(r.model_id) === want);
  return {
    ...model,
    benchmark_rows: rows,
    accuracy_rows: accRows,
  };
}

function truncateNote(s, maxLen) {
  if (s == null) return "—";
  const t = String(s);
  if (t.length <= maxLen) return t;
  return `${t.slice(0, maxLen)}…`;
}

function escapeHtmlAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/\n/g, " ");
}

function fmtCell(col, v) {
  if (v == null || v === "") return "—";
  if (typeof v === "number" && Number.isFinite(v)) {
    if (
      col === "id" ||
      col === "tensor_parallel_size" ||
      col === "total_samples" ||
      col === "correct_samples" ||
      col === "accuracy" ||
      col === "adaptation_duration_seconds"
    ) {
      return String(v);
    }
    return fmtBenchNum(v);
  }
  return String(v);
}

function renderModelsKvTable(m) {
  const rows = MODEL_FIELD_ORDER.map((key) => {
    const raw = m[key];
    const display = raw == null || raw === "" ? "—" : typeof raw === "number" ? String(raw) : String(raw);
    return `<tr>
      <td class="kv-key"><code>${escapeHtml(key)}</code></td>
      <td class="kv-val" title="${escapeHtmlAttr(display)}">${escapeHtml(display)}</td>
    </tr>`;
  }).join("");
  return `
    <div class="kv-wrap">
      <div class="bench-title">${escapeHtml(t("modelsTableTitle"))} <span class="kv-hint">${escapeHtml(t("modelsTableHint"))}</span></div>
      <div class="bench-scroll">
        <table class="kv-table"><tbody>${rows}</tbody></table>
      </div>
    </div>`;
}

function benchmarkColsForRows(rows) {
  if (!rows.length) return [...BENCH_COLS];
  const union = new Set();
  rows.forEach((r) => {
    Object.keys(r).forEach((k) => union.add(k));
  });
  const preferred = BENCH_COLS.filter((c) => union.has(c));
  const rest = [...union].filter((c) => !BENCH_COLS.includes(c)).sort();
  return [...preferred, ...rest];
}

function renderBenchmarkTable(rows, options = {}) {
  const { showInnerTitle = true } = options;
  if (!rows || !rows.length) return "";
  const cols = benchmarkColsForRows(rows);
  const ths = cols.map((c) => `<th><code>${escapeHtml(c)}</code></th>`).join("");
  const body = rows
    .map((row) => {
      const tds = cols.map((col) => {
        const v = row[col];
        const display = fmtCell(col, v);
        const long =
          col === "bench_params" || col === "config" || col === "notes" || col === "log_file";
        const shown = long ? truncateNote(display, 160) : display;
        return `<td class="${long ? "bench-long" : ""}" title="${escapeHtmlAttr(display)}">${escapeHtml(shown)}</td>`;
      }).join("");
      return `<tr>${tds}</tr>`;
    })
    .join("");
  const titleBlock = showInnerTitle ? `<div class="bench-title">${escapeHtml(t("benchTableTitle"))}</div>` : "";
  return `
    <div class="bench-wrap">
      ${titleBlock}
      <div class="bench-scroll">
        <table class="bench-table">
          <thead><tr>${ths}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </div>`;
}

function pickStageRows(rows, stage) {
  const isBaseline = (s) => {
    const v = String(s || "").trim().toLowerCase();
    // 兼容 baseline、r2_baseline、xxx_baseline_xxx 命名
    return /(^|_)baseline($|_)/.test(v);
  };
  return (rows || []).filter((r) => {
    const v = String(r.benchmark_stage || "").trim().toLowerCase();
    if (!v) return false;
    if (stage === "baseline") return isBaseline(v);
    if (stage === "optimized") return !isBaseline(v);
    return v === stage;
  });
}

function renderReviewActionRow(m) {
  const optSt = (m.optimization_status || "").trim().toLowerCase();
  if (optSt !== "completed") return "";
  const hr = (m.human_review_status || "").trim().toLowerCase();
  const isPending = hr === "pending";
  const isCompleted = hr === "completed";
  if (!isPending && !isCompleted) return "";

  const mid = escapeHtmlAttr(m.model_id || "");
  let content = "";
  if (isPending) {
    content = '<button type="button" class="v31-act-btn v31-act-btn--approve" data-review-action="approve" data-model-id="' + mid + '">'
      + '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
      + escapeHtml(t("reviewApprove")) + "</button>";
  } else {
    content = '<span class="v31-act-done"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>'
      + escapeHtml(t("reviewApproved")) + "</span>"
      + '<button type="button" class="v31-act-btn v31-act-btn--reject" data-review-action="reject" data-model-id="' + mid + '">'
      + '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>'
      + escapeHtml(t("reviewReject")) + "</button>";
  }

  return '<div class="v31-act-row v31-act-row--review">'
    + '<span class="v31-act-label"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="M9 12l2 2 4-4"/></svg>'
    + escapeHtml(t("reviewActionRow")) + "</span>"
    + '<div class="v31-act-buttons">' + content + "</div></div>";
}

function renderSendBackRow(m) {
  const adaptDone = (m.status || "").trim().toLowerCase() === "completed";
  const benchDone = (m.benchmark_status || "").trim().toLowerCase() === "completed";
  const optDone = (m.optimization_status || "").trim().toLowerCase() === "completed";
  if (!adaptDone && !benchDone && !optDone) return "";

  const mid = escapeHtmlAttr(m.model_id || "");
  const stages = [
    { key: "adaptation", label: t("sendBackAdaptation"), done: adaptDone, icon: "adapt" },
    { key: "benchmark", label: t("sendBackBenchmark"), done: benchDone, icon: "bench" },
    { key: "optimization", label: t("sendBackOptimization"), done: optDone, icon: "opt" },
  ];

  const btns = stages.map(s => {
    const dis = s.done ? "" : " disabled";
    return '<button type="button" class="v31-act-btn v31-act-btn--back v31-act-btn--back-' + s.icon + '"'
      + ' data-model-id="' + mid + '" data-target-stage="' + s.key + '"' + dis + '>'
      + '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>'
      + escapeHtml(s.label) + "</button>";
  }).join("");

  return '<div class="v31-act-row v31-act-row--sendback">'
    + '<span class="v31-act-label"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>'
    + escapeHtml(t("sendBackLabel")) + "</span>"
    + '<div class="v31-act-buttons">' + btns + "</div></div>";
}

function renderBenchmarkSummary(rows) {
  if (!rows || !rows.length) return "";

  const toNum = (v) => {
    if (v == null || v === "") return null;
    const x = Number(v);
    return Number.isFinite(x) ? x : null;
  };

  const tpNum = (r) => { const x = Number(r.tensor_parallel_size); return Number.isFinite(x) ? x : Infinity; };

  /* --- Data splitting (new schema: benchmark_stage = baseline / final_scheme_a / final_scheme_b) --- */
  const sharedBaseline = rows.filter((r) => {
    const v = String(r.benchmark_stage || "").trim().toLowerCase();
    return /(^|_)baseline($|_)/.test(v);
  }).slice().sort((a, b) => tpNum(a) - tpNum(b));

  const schemeA = rows.filter((r) => String(r.benchmark_stage || "").trim().toLowerCase() === "final_scheme_a");
  const schemeB = rows.filter((r) => String(r.benchmark_stage || "").trim().toLowerCase() === "final_scheme_b");
  const genericOpt = pickStageRows(rows, "optimized").filter((r) => {
    const v = String(r.benchmark_stage || "").trim().toLowerCase();
    return v !== "final_scheme_a" && v !== "final_scheme_b";
  });

  const hasSchemes = schemeA.length > 0 || schemeB.length > 0;

  /* --- Render helpers --- */
  const benchCell = (val) => {
    if (val == null || val === "") return '<span class="bench-tbd">TBD</span>';
    return escapeHtml(fmtBenchNum(val));
  };

  const titleParts = (r) => [
    "TP=" + (r.tensor_parallel_size ?? "\u2014"),
    "output_tok_per_s=" + (r.output_tok_per_s ?? "\u2014"),
    "req_per_s=" + (r.req_per_s ?? "\u2014"),
    "mean_ttft_ms=" + (r.mean_ttft_ms ?? "\u2014"),
    "mean_tpot_ms=" + (r.mean_tpot_ms ?? "\u2014"),
    "peak_tok_per_s=" + (r.peak_tok_per_s ?? "\u2014"),
    r.notes ? "notes=" + r.notes : "",
  ].filter(Boolean).join("\n");

  const renderTableRow = (r) => {
    const tp = r.tensor_parallel_size ?? "\u2014";
    return '<tr title="' + escapeHtmlAttr(titleParts(r)) + '">'
      + '<td class="bench-td-tp"><div class="bench-tp-cell"><span class="bench-tp-badge">TP' + escapeHtml(String(tp)) + "</span></div></td>"
      + "<td>" + benchCell(r.output_tok_per_s) + "</td>"
      + "<td>" + benchCell(r.req_per_s) + "</td>"
      + "<td>" + benchCell(r.mean_ttft_ms) + " ms</td>"
      + "<td>" + benchCell(r.mean_tpot_ms) + " ms</td>"
      + "</tr>";
  };

  const renderTable = (dataRows, stageKey) => {
    if (!dataRows || !dataRows.length) return "";
    const sorted = dataRows.slice().sort((a, b) => tpNum(a) - tpNum(b));
    const stageLabel = stageKey === "baseline" ? t("stageBaseline") : t("stageOptimized");
    return '<div class="bench-stage bench-stage--' + escapeHtml(stageKey) + '">'
      + '<div class="bench-stage-title">' + escapeHtml(stageLabel) + '</div>'
      + '<div class="bench-scroll"><table class="bench-table">'
      + '<thead><tr><th>TP</th><th>tok/s</th><th>req/s</th><th>TTFT</th><th>TPOT</th></tr></thead>'
      + '<tbody>' + sorted.map(renderTableRow).join("") + '</tbody>'
      + '</table></div></div>';
  };

  /* --- Speedup calc --- */
  const calcSpeedup = (optRows) => {
    if (!optRows || !optRows.length || !sharedBaseline.length) return null;
    const bestOpt = optRows.slice().sort((a, b) => (toNum(b.output_tok_per_s) ?? -Infinity) - (toNum(a.output_tok_per_s) ?? -Infinity))[0];
    const oOut = toNum(bestOpt?.output_tok_per_s);
    if (oOut == null) return null;
    const tp = bestOpt.tensor_parallel_size;
    const matchBaseline = sharedBaseline.find((r) => r.tensor_parallel_size === tp);
    const bOut = toNum(matchBaseline?.output_tok_per_s) ?? toNum(sharedBaseline[0]?.output_tok_per_s);
    if (bOut == null || bOut === 0) return null;
    return { speedup: oOut / bOut, optRow: bestOpt, baseRow: matchBaseline || sharedBaseline[0] };
  };

  const speedupBadge = (sp) => {
    if (sp == null) return "";
    const cls = sp.speedup >= 1 ? "is-good" : "is-bad";
    return '<span class="bench-scheme-speedup ' + cls + '">' + sp.speedup.toFixed(2) + "&times;</span>";
  };

  const chipsHtml = (r) => {
    const txt = String(r?.chips || r?.optimization_methods || "").trim();
    if (!txt) return "";
    const chips = txt.split(/[|,;]+/).map((x) => x.trim()).filter(Boolean)
      .filter((x) => /[A-Za-z_\-\u4e00-\u9fa5]/.test(x))
      .filter((x) => !shouldHideOptChipLabel(x))
      .slice(0, 6);
    if (!chips.length) return "";
    return '<div class="opt-chips">' + chips.map((c) => '<span class="opt-chip">' + escapeHtml(c) + '</span>').join("") + '</div>';
  };

  /* --- Empty state --- */
  if (!sharedBaseline.length && !genericOpt.length && !hasSchemes) {
    return '<div class="bench-summary"><div class="bench-empty">' + escapeHtml(t("optTooltipUnavailable")) + "</div></div>";
  }

  /* --- Layout: shared baseline on top, then scheme panels --- */
  if (hasSchemes) {
    const spA = calcSpeedup(schemeA);
    const spB = calcSpeedup(schemeB);

    const panelA = '<div class="bench-scheme-panel bench-scheme-panel--a">'
      + '<div class="bench-scheme-header"><span class="bench-scheme-label">' + escapeHtml(t("schemeALabel")) + '</span>'
      + '<span class="bench-scheme-baseline-note">' + escapeHtml(t("schemeBaselineNote")) + '</span>'
      + speedupBadge(spA) + '</div>'
      + renderTable(schemeA, "optimized")
      + chipsHtml(spA?.optRow) + '</div>';

    const panelB = '<div class="bench-scheme-panel bench-scheme-panel--b">'
      + '<div class="bench-scheme-header"><span class="bench-scheme-label">' + escapeHtml(t("schemeBLabel")) + '</span>'
      + '<span class="bench-scheme-baseline-note">' + escapeHtml(t("schemeBaselineNote")) + '</span>'
      + speedupBadge(spB) + '</div>'
      + renderTable(schemeB, "optimized")
      + chipsHtml(spB?.optRow) + '</div>';

    return '<div class="bench-summary">'
      + renderTable(sharedBaseline, "baseline")
      + '<div class="bench-schemes-grid">' + panelA + panelB + '</div>'
      + '</div>';
  }

  /* --- No scheme data: original single-column layout --- */
  const bestBaseline = sharedBaseline.length ? sharedBaseline[0] : null;
  const bestOptimized = genericOpt.length ? genericOpt[0] : null;
  const bOut = toNum(bestBaseline?.output_tok_per_s);
  const oOut = toNum(bestOptimized?.output_tok_per_s);
  const speedup = bOut != null && oOut != null && bOut !== 0 ? oOut / bOut : null;
  const speedupClass = speedup == null ? "is-neutral" : speedup >= 1 ? "is-good" : "is-bad";
  const speedupText = speedup != null ? speedup.toFixed(3) + "\u00d7" : "\u2014";

  const optSummary = '<div class="opt-block"><table class="opt-degree-table"><thead><tr>'
    + '<th>' + escapeHtml(t("optMetricName")) + '</th>'
    + '<th>' + escapeHtml(t("optMetricValue")) + '</th></tr></thead><tbody>'
    + '<tr><td>' + escapeHtml(t("optTooltipSpeedup")) + '</td>'
    + '<td><span class="metric-value ' + escapeHtml(speedupClass) + '">' + escapeHtml(speedupText) + '</span></td></tr>'
    + '<tr><td>' + escapeHtml(t("throughput")) + '</td>'
    + '<td><span class="metric-value">' + escapeHtml(bestOptimized && bestOptimized.output_tok_per_s != null ? fmtBenchNum(bestOptimized.output_tok_per_s) : "\u2014") + '</span></td></tr>'
    + '</tbody></table>' + chipsHtml(bestOptimized) + '</div>';

  return '<div class="bench-summary">' + optSummary
    + renderTable(sharedBaseline, "baseline")
    + renderTable(genericOpt, "optimized") + '</div>';
}


/** 模型卡片内：精度结果（accuracy_results），按 benchmark_stage 分组 */
function renderAccuracySummary(rows) {
  if (!rows || !rows.length) return "";

  const sortByDataset = (a, b) => String(a.dataset || "").localeCompare(String(b.dataset || ""));
  const baseline = pickStageRows(rows, "baseline").slice().sort(sortByDataset);
  const optimized = pickStageRows(rows, "optimized").slice().sort(sortByDataset);
  const other = rows
    .filter((r) => {
      const s = String(r.benchmark_stage || "").toLowerCase();
      return s !== "baseline" && s !== "optimized";
    })
    .slice()
    .sort(sortByDataset);

  const accLine = (r) => {
    const ds = r.dataset || "—";
    const acc = fmtAccuracyPct(r.accuracy);
    const pair =
      r.total_samples != null && r.correct_samples != null
        ? `${r.correct_samples}/${r.total_samples}`
        : r.total_samples != null
          ? String(r.total_samples)
          : "—";
    const title = [
      `dataset=${r.dataset ?? ""}`,
      `benchmark_stage=${r.benchmark_stage ?? ""}`,
      `accuracy=${r.accuracy ?? ""}`,
      `correct_samples=${r.correct_samples ?? ""}`,
      `total_samples=${r.total_samples ?? ""}`,
      r.notes ? `notes=${r.notes}` : "",
    ]
      .filter(Boolean)
      .join("\n");
    return `<div class="bench-line acc-line" title="${escapeHtmlAttr(title)}"><span class="acc-dataset">${escapeHtml(String(ds))}</span>: ${escapeHtml(acc)} · ${escapeHtml(pair)}</div>`;
  };

  const stageAccBlock = (stageRows, stageKey) => {
    if (!stageRows.length) return "";
    const stageLabel = stageKey === "baseline" ? t("stageBaseline") : t("stageOptimized");
    return `
      <div class="bench-stage bench-stage--${escapeHtml(stageKey)}">
        <div class="bench-stage-title">${escapeHtml(stageLabel)}</div>
        ${stageRows.map(accLine).join("")}
      </div>
    `;
  };

  const bB = stageAccBlock(baseline, "baseline");
  const bO = stageAccBlock(optimized, "optimized");
  const bOther =
    other.length === 0
      ? ""
      : `
      <div class="bench-stage bench-stage--other">
        <div class="bench-stage-title">${escapeHtml(t("accuracyStageOther"))}</div>
        ${other.map(accLine).join("")}
      </div>
    `;

  if (!bB && !bO && !bOther) return "";

  return `
    <div class="bench-summary acc-summary">
      <div class="acc-summary-heading">${escapeHtml(t("accuracySectionTitle"))}</div>
      ${bB}
      ${bO}
      ${bOther}
    </div>
  `;
}

function renderBenchmarkGlobalSection() {
  const gEl = document.getElementById("benchmarkGlobal");
  const gEmpty = document.getElementById("benchmarkGlobalEmpty");
  const descEl = document.getElementById("benchGlobalDescEl");
  if (!boardData) return;
  const meta = boardData.meta || {};
  const br = boardData.benchmark_results || [];
  const src = meta.benchmarkTableSource || "benchmark_results";
  if (descEl) {
    descEl.textContent = `${t("benchGlobalDesc")} ${t("benchMetaLine").replace("$n", String(br.length)).replace("$t", src)}`;
  }
  if (!gEl || !gEmpty) return;
  if (!br.length) {
    gEl.innerHTML = "";
    gEmpty.classList.remove("hidden");
    return;
  }
  gEmpty.classList.add("hidden");
  gEl.innerHTML = renderBenchmarkTable(br, { showInnerTitle: false });
}

function renderAccuracyTable(rows) {
  if (!rows || !rows.length) return "";
  const ths = ACC_COLS.map((c) => `<th><code>${escapeHtml(c)}</code></th>`).join("");
  const body = rows
    .map((row) => {
      const tds = ACC_COLS.map((col) => {
        const v = row[col];
        const display = fmtCell(col, v);
        const long = col === "notes";
        const shown = long ? truncateNote(display, 120) : display;
        return `<td class="${long ? "bench-long" : ""}" title="${escapeHtmlAttr(display)}">${escapeHtml(shown)}</td>`;
      }).join("");
      return `<tr>${tds}</tr>`;
    })
    .join("");
  return `
    <div class="bench-wrap">
      <div class="bench-title">${escapeHtml(t("accuracyTableTitle"))}</div>
      <div class="bench-scroll">
        <table class="bench-table">
          <thead><tr>${ths}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </div>`;
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
  const norm = (s) => String(s || "").trim().toLowerCase();
  const mkStage = () => ({ eligible: 0, completed: 0, pending: 0, inProgress: 0, terminal: 0 });
  const adaptation = mkStage();
  const benchmark = mkStage();
  const optimization = mkStage();

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
      const d = adaptationDurationMs(m);
      if (d != null) durs.push(d);
    }

    // Stage metrics for SLAI-like breakdown
    adaptation.eligible++;
    if (st === "completed") adaptation.completed++;
    else if (st === "pending") adaptation.pending++;
    else if (st === "in_progress") adaptation.inProgress++;
    else if (st === "needs_authorization" || st === "not_applicable" || st === "skipped") adaptation.terminal++;

    if (st === "completed") {
      benchmark.eligible++;
      const bs = norm(m.benchmark_status);
      if (bs === "completed") benchmark.completed++;
      else if (bs === "pending" || bs === "") benchmark.pending++;
      else if (bs === "in_progress") benchmark.inProgress++;
      else if (bs === "not_applicable" || bs === "skipped") benchmark.terminal++;
    }

    if (st === "completed" && norm(m.benchmark_status) === "completed") {
      optimization.eligible++;
      const os = norm(m.optimization_status);
      if (os === "completed") optimization.completed++;
      else if (os === "pending" || os === "") optimization.pending++;
      else if (os === "in_progress") optimization.inProgress++;
      else if (os === "not_applicable" || os === "skipped") optimization.terminal++;
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
    adaptation,
    benchmark,
    optimization,
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

function renderAgents(agents, animateReveal) {
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
  observeRevealItems(grid, ".agent-card", animateReveal);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderStats(models, animateReveal) {
  const stats = computeStats(models);
  const grid = document.getElementById("statsGrid");
  const legend = document.getElementById("pipelineLegend");
  const stageGrid = document.getElementById("stageStatsGrid");

  const completionRate = stats.total ? ((stats.completed / stats.total) * 100).toFixed(1) : "0.0";

  const kpis = [
    { label: t("statTotal"), value: String(stats.total), variant: "" },
    { label: t("statusCompleted"), value: String(stats.completed), variant: "done", extra: completionRate + "%" },
    { label: t("statusInProgress"), value: String(stats.inProgress), variant: "run" },
    {
      label: t("statAvgDuration"),
      value: stats.avgDurationMs != null ? formatDurationMs(stats.avgDurationMs) : "—",
      variant: "",
    },
  ];

  grid.innerHTML = `
    <div class="v31-kpi-grid">
      ${kpis.map(
        (k) => `
        <div class="v31-kpi${k.variant ? " v31-kpi--" + k.variant : ""}">
          <div class="v31-kpi-num">${escapeHtml(k.value)}</div>
          <div class="v31-kpi-lbl">${escapeHtml(k.label)}</div>
          ${k.extra ? `<div class="v31-kpi-tag">${escapeHtml(k.extra)}</div>` : ""}
        </div>
      `
      ).join("")}
    </div>
    ${_renderSecondaryChips(stats)}
  `;

  observeRevealItems(grid, ".v31-kpi", animateReveal);

  legend.innerHTML = "";

  const stages = [
    { title: t("stagePanelAdaptation"), data: stats.adaptation, color: "adapt" },
    { title: t("stagePanelBenchmark"), data: stats.benchmark, color: "bench" },
    { title: t("stagePanelOptimization"), data: stats.optimization, color: "opt" },
  ];

  if (stageGrid) {
    stageGrid.innerHTML = `
      <div class="v31-pipeline">
        <div class="v31-pipeline-title">${escapeHtml(t("pipelineLegendTitle"))}</div>
        <div class="v31-pipeline-flow">
          ${stages
            .map(
              (s, i) => {
                const pct = s.data.eligible ? Math.round((s.data.completed / s.data.eligible) * 100) : 0;
                const detail = s.data.eligible ? `${s.data.completed}/${s.data.eligible}` : "0/0";
                return `
                <div class="v31-pipe-slot">
                  <div class="v31-pipe-card v31-pipe-card--${s.color}">
                    <div class="v31-pipe-head">
                      <span class="v31-pipe-name">${escapeHtml(s.title)}</span>
                      <span class="v31-pipe-badge">${escapeHtml(detail)}</span>
                    </div>
                    <div class="v31-pipe-bar">
                      <div class="v31-pipe-fill v31-pipe-fill--${s.color}" style="width:${pct}%"></div>
                    </div>
                    <div class="v31-pipe-foot">
                      <span>${pct}% ${escapeHtml(t("stageCompletedRatio"))}</span>
                      <span>${s.data.pending} ${escapeHtml(t("stagePendingQueue"))}</span>
                      <span>${s.data.inProgress} ${escapeHtml(t("stageActiveQueue"))}</span>
                    </div>
                  </div>
                  ${
                    i < stages.length - 1
                      ? '<div class="v31-pipe-arrow" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></div>'
                      : ""
                  }
                </div>
              `;
              }
            )
            .join("")}
        </div>
      </div>
    `;
  }
  observeRevealItems(stageGrid, ".v31-pipe-card", animateReveal);
}

function _renderSecondaryChips(stats) {
  const items = [];
  if (stats.needsAuth > 0) items.push({ label: t("statNeedsAuth"), value: stats.needsAuth, cls: "warn" });
  if (stats.na > 0) items.push({ label: t("statusNotApplicable"), value: stats.na, cls: "muted" });
  if (stats.skipped > 0) items.push({ label: t("statSkipped"), value: stats.skipped, cls: "skip" });
  if (!items.length) return "";
  return `<div class="v31-chips-row">${items
    .map(
      (it) => `
    <div class="v31-chip v31-chip--${it.cls}">
      <span class="v31-chip-val">${it.value}</span>
      <span class="v31-chip-lbl">${escapeHtml(it.label)}</span>
    </div>
  `
    )
    .join("")}</div>`;
}

function pipeClass(st) {
  const s = (st || "").toLowerCase();
  if (s === "completed") return "pipe done";
  if (s === "in_progress") return "pipe run";
  return "pipe skip";
}

/** IntersectionObserver for staggered reveal animations */
const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const el = entry.target;
        const delay = el.dataset.revealDelay || 0;
        setTimeout(() => el.classList.add("visible"), Number(delay));
        revealObserver.unobserve(el);
      }
    });
  },
  { threshold: 0.05, rootMargin: "0px 0px -30px 0px" }
);

function observeRevealItems(container, selector, animateReveal) {
  if (!container) return;
  const items = container.querySelectorAll(selector);
  if (!animateReveal) return;
  items.forEach((el, i) => {
    el.classList.add("reveal-item");
    el.dataset.revealDelay = String(i * 60);
    revealObserver.observe(el);
  });
}

function renderModelsPage(animateReveal) {
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
      const docStem = (m.model_id && m.model_id.split("/").pop()) || "";
      const org = (m.model_id && m.model_id.includes("/") && m.model_id.split("/")[0]) || "";
      const path = (m.adaptation_path || "").replace(/^adaptations\//, "");
      const adaptSt = (m.status || "").toLowerCase();
      const hasStoredAdaptSec =
        m.adaptation_duration_seconds != null &&
        m.adaptation_duration_seconds !== "" &&
        Number.isFinite(Number(m.adaptation_duration_seconds));
      const adaptDurTitle = hasStoredAdaptSec
        ? `adaptation_duration_seconds=${m.adaptation_duration_seconds}`
        : [["started_at", m.started_at], ["last_updated", m.last_updated]]
            .filter(([, v]) => v != null && String(v).trim() !== "")
            .map(([k, v]) => `${k}=${v}`)
            .join(" · ");
      const adaptRunning = adaptSt === "in_progress" && !hasStoredAdaptSec;

      return `
      <article class="model-card">
        <div class="model-title-row">
          <div>
            <h3 class="model-title">${escapeHtml(shortName)}</h3>
            <p class="model-org">${escapeHtml(org)}</p>
          </div>
          <span class="${statusPillClass(m.status)}">${escapeHtml(tStatus("adapt", m.status))}</span>
        </div>
        <div class="model-path-row">
          <div class="path-pill" title="${escapeHtml(m.adaptation_path || "")}">${escapeHtml(path || "—")}</div>
          <button type="button" class="model-docs-btn" data-adapt-path="${escapeHtmlAttr(
            m.adaptation_path || ""
          )}" data-stem="${escapeHtmlAttr(docStem)}" data-title="${escapeHtmlAttr(shortName)}" data-i18n="modelDocsOpen">${escapeHtml(
        t("modelDocsOpen")
      )}</button>
        </div>
        <div class="adapt-duration-row" title="${escapeHtmlAttr(adaptDurTitle || "—")}">
          <span class="adapt-duration-label">${escapeHtml(t("adaptDurationLabel"))}</span>
          <span class="adapt-duration-value ${adaptRunning ? "is-live" : ""}">${escapeHtml(formatAdaptDurationLine(m))}${
        adaptRunning ? ` · ${escapeHtml(t("adaptDurationRunning"))}` : ""
      }</span>
        </div>
        <div class="pipeline-row">
          <span class="${pipeClass(m.status)}">${escapeHtml(t("pipeAdapt"))}: ${escapeHtml(tStatus("adapt", m.status))}</span>
          <span class="${pipeClass(m.benchmark_status)}">${escapeHtml(t("pipeBench"))}: ${escapeHtml(tStatus("bench", m.benchmark_status))}</span>
          <span class="${pipeClass(m.optimization_status)}">${escapeHtml(t("pipeOpt"))}: ${escapeHtml(tStatus("opt", m.optimization_status))}</span>
          <span class="${pipeClass(m.human_review_status || "")}">${escapeHtml(t("pipeHumanReview"))}: ${escapeHtml(tStatus("hr", m.human_review_status))}</span>
        </div>
        ${renderReviewActionRow(m)}
        ${renderSendBackRow(m)}
        ${renderBenchmarkSummary(m.benchmark_rows)}
        ${renderAccuracySummary(m.accuracy_rows)}
      </article>
    `;
    })
    .join("");

  observeRevealItems(grid, ".model-card", animateReveal);

  if (models.length > PAGE_SIZE) {
    pager.classList.remove("hidden");
    document.getElementById("pageIndicator").textContent = `${currentPage} / ${totalPages}`;
    document.getElementById("prevPage").disabled = currentPage <= 1;
    document.getElementById("nextPage").disabled = currentPage >= totalPages;
  } else {
    pager.classList.add("hidden");
  }
}

function renderAll(options = {}) {
  if (!boardData) return;
  const animateReveal = options.animateReveal ?? !didStaggerRevealOnce;
  const meta = boardData.meta || {};
  document.getElementById("lastUpdated").textContent = meta.lastUpdated || "—";
  const proj = document.getElementById("linkProject");
  if (proj && meta.projectUrl) proj.href = meta.projectUrl;

  const liveBadge = document.getElementById("liveBadge");
  if (liveBadge) {
    liveBadge.classList.toggle("hidden", meta.dataSource !== "live");
  }

  renderAgents(boardData.agents || [], animateReveal);
  const models = boardData.models || [];
  renderStats(models, animateReveal);
  sortedModels = sortModels(models, sortMode);
  renderModelsPage(animateReveal);

  if (animateReveal) didStaggerRevealOnce = true;
}

async function loadJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url} ${res.status}`);
  return res.json();
}

function setSyncStatus(text, isError) {
  const el = document.getElementById("syncStatus");
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("is-error", !!isError);
}

async function loadBoardData() {
  const res = await fetch("data/board.json", { cache: "no-store" });
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Invalid JSON (${res.status})`);
  }
  if (!res.ok || data.error) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  boardData = data;
  if (!Array.isArray(boardData.benchmark_results)) boardData.benchmark_results = [];
  if (!Array.isArray(boardData.accuracy_results)) boardData.accuracy_results = [];
}

async function refreshAllData(options = {}) {
  const silent = options.silent === true;
  if (boardRefreshInFlight) return;
  boardRefreshInFlight = true;

  const loading = document.getElementById("loading");
  const isInitial = !boardData;
  if (isInitial) loading?.classList.remove("hidden");
  if (!silent) setSyncStatus(isInitial ? t("loading") : "", false);
  try {
    await loadBoardData();
    if (!silent) setSyncStatus("", false);
  } catch (e) {
    console.error(e);
    setSyncStatus(t("syncFailed"), true);
    if (!boardData) {
      boardData = {
        meta: {},
        agents: [],
        models: [],
        benchmark_results: [],
        accuracy_results: [],
      };
    }
  } finally {
    if (isInitial) loading?.classList.add("hidden");
    boardRefreshInFlight = false;
  }
  renderAll();
}

function startPollLoop() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  const sel = document.getElementById("pollSelect");
  const sec = sel ? parseInt(sel.value, 10) : 0;
  if (sel) localStorage.setItem("vaa-poll-sec", sel.value);
  if (!sec || sec < 0) return;
  pollTimer = setInterval(() => {
    refreshAllData({ silent: true }).catch(console.error);
  }, sec * 1000);
}

async function init() {
  document.getElementById("year").textContent = String(new Date().getFullYear());

  await refreshAllData();

  const pollSelect = document.getElementById("pollSelect");
  if (pollSelect) {
    const u = new URLSearchParams(window.location.search);
    const urlPoll = u.get("poll");
    const saved = localStorage.getItem("vaa-poll-sec");
    if (urlPoll !== null && urlPoll !== "") {
      pollSelect.value = urlPoll;
    } else if (saved !== null && saved !== "") {
      pollSelect.value = saved;
    } else if (boardData?.meta?.dataSource === "live") {
      pollSelect.value = "5";
    }
    pollSelect.addEventListener("change", () => {
      startPollLoop();
    });
    startPollLoop();
  }

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      lang = btn.dataset.lang || "zh";
      localStorage.setItem("vaa-lang", lang);
      applyLang();
    });
  });

  initModelDocsModal();

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
