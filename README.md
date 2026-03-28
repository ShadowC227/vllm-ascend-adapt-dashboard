# vLLM Ascend Adaptation Board（看板）

仿照 [SLAI Ascend Model Adaptation Board](https://chongweiliu.github.io/slai-ascend-auto-adapt/dashboard/) 的交互与布局，展示 [vllm-ascend-adapt](../vllm-ascend-adapt) 项目中的 **SQLite 任务板**（`vllm_board.db`）数据。

## 功能

- 团队 Agent 状态、当前任务
- 模型三阶段流水线：适配、精度对齐、性能优化；卡片内展示性能指标（baseline / optimized）
- 统计汇总、排序、分页
- 中英文切换（界面文案）
- **本地实时模式**：专用服务每次请求从 `vllm_board.db` 生成 JSON，页面可自动轮询，无需反复 `export` + 刷新

## 本地实时看板（推荐：随数据库更新）

不经过 GitHub，在本机启动 **实时服务**：浏览器访问时，每次拉取 `/data/board.json` 都会**现读 SQLite**，与 `board_ops.py` / Agent 写入的数据一致。

```bash
cd vllm-ascend-adapt-dashboard

# 默认：127.0.0.1:8765，数据库 ../vllm-ascend-adapt/vllm_board.db
python3 scripts/serve_live.py
```

浏览器打开终端里打印的地址（例如 `http://127.0.0.1:8765/`）。

若**改了前端**（`index.html` / `js` / `css`）却看不到变化：**强刷**（Ctrl+F5 / 清空缓存）或把 `index.html` 里资源链接的 `?v=` 数字改大；`serve_live.py` 已对静态资源返回 `Cache-Control: no-cache`。

- 页面上会显示 **LIVE** 标记，并默认 **每 5 秒自动刷新**（可在「自动刷新」里改为关闭 / 3s / 10s / 30s）。
- 同一局域网其他机器访问时，可加监听地址：

  ```bash
  python3 scripts/serve_live.py --host 0.0.0.0 --port 8765
  ```

  其他设备用 `http://<你的机器IP>:8765/` 打开。

常用参数与环境变量：

| 说明 | 参数 / 环境变量 |
|------|-----------------|
| 数据库路径 | `--db` 或 `VLLM_BOARD_DB` |
| 端口 | `--port` 或 `VAA_PORT`（默认 `8765`） |
| 监听地址 | `--host` 或 `VAA_HOST`（默认 `127.0.0.1`） |

> **说明**：`python3 -m http.server` 只能提供**静态文件**，读的是已导出的 `data/board.json`，**不会**随数据库变化；要「实时」请用 `serve_live.py`。

### 后续持续实时更新（推荐日常用法）

只要 **`board_ops` / Agent / 脚本持续写入 `vllm_board.db`**，看板侧无需再跑 `export_board_json.py`：

1. **长期运行**实时服务（任选一种启动方式）：

   ```bash
   cd vllm-ascend-adapt-dashboard
   chmod +x run_dashboard_live.sh
   ./run_dashboard_live.sh
   # 等价于: python3 scripts/serve_live.py --db ../vllm-ascend-adapt/vllm_board.db
   ```

2. 浏览器打开页面后保持 **「自动刷新」** 开启（默认约 5 秒）。每次轮询会重新请求 `/data/board.json`，服务端**每次现读数据库**，包含 **`agents`、`models`、`benchmark_results`**。

3. 局域网/远端访问时：

   ```bash
   VAA_HOST=0.0.0.0 ./run_dashboard_live.sh
   ```

### 持久化运行（推荐：systemd）

在 Linux 上把看板做成 **系统服务**，**开机自启**、进程退出后 **自动重启**，适合长期开机/服务器：

```bash
cd vllm-ascend-adapt-dashboard
sudo ./deploy/install-systemd.sh
# 可选：sudo ./deploy/install-systemd.sh --host 0.0.0.0 --port 8765
```

默认监听 `0.0.0.0:8765`，数据库为 `../vllm-ascend-adapt/vllm_board.db`。常用命令：

| 命令 | 说明 |
|------|------|
| `sudo systemctl status vaa-dashboard` | 查看服务状态 |
| `journalctl -u vaa-dashboard -f` | 看实时日志 |
| `sudo systemctl restart vaa-dashboard` | 重启 |
| `sudo systemctl disable --now vaa-dashboard` | 停止并取消开机自启 |

若无 root / 无 systemd，可用后台进程（**不保证**崩溃自启、**不保证**开机自启）：

```bash
cd vllm-ascend-adapt-dashboard
nohup env VAA_HOST=0.0.0.0 VAA_PORT=8765 ./run_dashboard_live.sh >> /tmp/vaa-dashboard.log 2>&1 &
echo $!   # 记下 PID，需要时用 kill <PID> 结束
```

> **与静态导出的区别**：`export_board_json.py` 仅用于生成仓库里的 `data/board.json`（如 GitHub Pages）；**日常盯盘请用 `serve_live.py` / `run_dashboard_live.sh`**，才能与 `vllm_board.db` 保持同步。

## 本地预览（仅静态文件）

若暂时不用实时服务，可用任意静态服务器（需先 `export_board_json.py` 生成 `data/board.json`）：

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

`data/board.json` 与实时接口一致，包含：

- **`models`**：每张模型卡展示 **适配耗时**、**精度结果**（`accuracy_results`，按 `benchmark_stage` 分组）、**性能指标**（`benchmark_results`）等。
- **`benchmark_results`**：**benchmark_results 表全列**（含 `bench_params`、`config`、`log_file`、`created_at`、`total_tok_per_s` 等）。
- **`accuracy_results`**：有数据时展示 **accuracy_results 表全列**；无数据则不显示该表。

前端 **`js/dashboard.js`** 中常量 **`MODEL_FIELD_ORDER` / `BENCH_COLS` / `ACC_COLS`** 与表结构对应；若你改了库表结构，请同步更新这些数组。

## 关于 metrics_overrides.json（已弃用）

当前看板**不再读取** `data/metrics_overrides.json`，所有展示以数据库导出字段为准。旧文件可保留作备忘或删除。

## 许可证

与主项目保持一致。
