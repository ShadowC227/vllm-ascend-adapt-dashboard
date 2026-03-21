# vLLM Ascend Adaptation Board（看板）

仿照 [SLAI Ascend Model Adaptation Board](https://chongweiliu.github.io/slai-ascend-auto-adapt/dashboard/) 的交互与布局，展示 [vllm-ascend-adapt](../vllm-ascend-adapt) 项目中的 **SQLite 任务板**（`vllm_board.db`）数据。

## 功能

- 团队 Agent 状态、当前任务
- 模型适配 / Benchmark / 优化 三阶段流水线状态
- 统计汇总、排序、分页
- 中英文切换（界面文案）

## 本地预览

```bash
cd vllm-ascend-adapt-dashboard
python3 -m http.server 8080
# 浏览器打开 http://127.0.0.1:8080/
```

## 更新数据（从主项目数据库导出）

默认读取主项目数据库路径（与 `board_ops.py` 一致）：

```bash
cd vllm-ascend-adapt-dashboard
python3 scripts/export_board_json.py \
  --db ../vllm-ascend-adapt/vllm_board.db \
  --out data/board.json
```

导出后刷新页面即可。

## 远端打开（公网访问）

推荐 **GitHub Pages**（免费、HTTPS 固定域名）：

1. 在 GitHub 新建一个 **空仓库**（例如 `vllm-ascend-adapt-dashboard`），不要勾选 README。
2. 在本机把看板目录推上去（把 `YOUR_USER` 换成你的 GitHub 用户名）：

   ```bash
   cd vllm-ascend-adapt-dashboard
   git init
   git add -A
   git commit -m "Initial dashboard"
   git branch -M main
   git remote add origin git@github.com:YOUR_USER/vllm-ascend-adapt-dashboard.git
   git push -u origin main
   ```

3. 打开仓库 **Settings → Pages** → **Build and deployment** → Source 选 **Deploy from a branch**，Branch 选 **main**、文件夹 **/ (root)**，保存。
4. 等待 1～2 分钟后访问：

   **`https://YOUR_USER.github.io/vllm-ascend-adapt-dashboard/`**

   （若仓库名是 `USERNAME.github.io` 且内容为站点根目录，则域名为 `https://USERNAME.github.io/`。）

5. 之后每次更新数据：在本地执行 `export_board_json.py` 更新 `data/board.json`，`git commit` + `git push`，刷新网页即可。

> **说明**：本仓库是静态页 + `data/board.json`，不依赖后端；远端能打开的前提是**已把最新 `board.json` 推送到 GitHub**。

### 临时分享（仅本机调试）

若只想把当前机器上的页面临时给别人看，可用 [ngrok](https://ngrok.com/) 等内网穿透：`python3 -m http.server 8080` 后再 `ngrok http 8080`，会生成临时公网 URL（适合短期演示，不适合长期）。

## GitHub Pages 部署（摘要）

- 将本目录作为仓库根目录推送即可。
- 若必须用 **/docs** 子目录发布：把本目录内容移到仓库的 `docs/` 下，Pages 里选 **/docs**。
- 静态站点使用**相对路径**加载 `data/board.json`，`index.html` 已按相对路径编写。

## 可选：合并性能摘要

若存在 `data/metrics_overrides.json`（按 `model_id` 键入补充字段），会与导出数据合并，用于展示吞吐/延迟等（数据库中无这些列时）。可拷贝示例：

```bash
cp data/metrics_overrides.example.json data/metrics_overrides.json
```

```json
{
  "qwen3_5_0_8b": {
    "throughput_npu": "2417 tok/s",
    "latency_npu": "—",
    "memory_usage_npu": "—",
    "optimization": {
      "speedup": 1.12,
      "baseline_latency_s": 0.0414,
      "perf_latency_s": 0.0369,
      "latency_reduction_pct": 13.2,
      "cosine_similarity": 0.9999
    }
  }
}
```

## 许可证

与主项目保持一致。
