"""
Shared optimization utilities: model classification, historical pattern extraction,
strategy-aware prompt generation.

Used by pipeline_runner.py (prompt generation) and config_recommend.py (method parsing).
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

# ── Known environment-variable keys ──────────────────────────────────────────

ENV_VAR_KEYS = frozenset({
    "TASK_QUEUE_ENABLE",
    "CPU_AFFINITY_CONF",
    "OMP_NUM_THREADS",
    "PYTORCH_NPU_ALLOC_CONF",
    "HCCL_OP_EXPANSION_MODE",
    "VLLM_WORKER_MULTIPROC_METHOD",
    "LD_PRELOAD",
    "ASCEND_RT_VISIBLE_DEVICES",
})

# Timeout (minutes) per experiment, keyed by size_category
# - serve_timeout: model loading + graph capture; scales with model size
# - bench_timeout: 64 prompts × 128 tokens; 5 min sufficient for all sizes
SERVE_TIMEOUT: dict[str, int] = {
    "tiny": 3,
    "small": 5,
    "medium": 5,
    "large": 10,
    "xlarge": 15,
    "unknown": 8,
}
BENCH_TIMEOUT = 5  # minutes, fixed for all model sizes

# Shorthand keys in optimization_methods → engine param keys
METHODS_ENGINE_MAP: dict[str, str] = {
    "max-batched-tokens": "max_num_batched_tokens",
    "max-num-batched-tokens": "max_num_batched_tokens",
    "max-num-seqs": "max_num_seqs",
    "max-model-len": "max_model_len",
    "gpu-mem": "gpu_memory_utilization",
}

# ── AclGraph compatibility rules (from optimizer MEMORY.md) ──────────────────

# Architectures confirmed WORKING with AclGraph (positive evidence only, never used to block)
_ACLGRAPH_COMPATIBLE_ARCHS = frozenset({
    "Qwen3ForCausalLM",
    "Qwen2ForCausalLM",
    "Qwen2VLForConditionalGeneration",
})

# ── Optimization parameter registry ──────────────────────────────────────────
#
# Each entry is a tunable parameter with applicability rules and priority.
# The protocol generator filters and sorts these dynamically per model.
#
# Fields:
#   id            — canonical ID (matches _normalize_strategy_name where possible)
#   name          — human-readable name for the protocol
#   phase         — logical group: graph_test | env | engine | additional | comm | stability | moe
#   priority      — base priority 0-100 (historical data + theoretical impact + low risk)
#   risk          — low | medium | high
#   expected_gain — generic expected improvement string
#   config_desc   — how to apply (CLI flag / env var / additional-config key)
#   notes         — caveats, compatibility warnings
#   families      — whitelist model families (empty = all)
#   exclude_if    — skip when profile field matches (e.g. {"is_moe": True})
#   require_if    — require profile field to equal value (e.g. {"min_chips": 2})
#   prefer_if     — boost priority when profile field matches
#   strategy_id   — maps to strategy_effectiveness key for historical data injection

_PARAMETER_REGISTRY: list[dict[str, Any]] = [
    # ── graph_test: compatibility gate ──
    {
        "id": "aclgraph",
        "name": "AclGraph FULL_DECODE_ONLY",
        "layer": "parameter",
        "layer": "parameter",
        "phase": "graph_test",
        "priority": 90,
        "risk": "medium",
        "expected_gain": "+200~1000%",
        "config_desc": "--compilation-config '{\"mode\":\"none\",\"cudagraph_mode\":\"FULL_DECODE_ONLY\"}'",
        "notes": "不兼容时崩溃 → 标记跳过，后续用 eager; gpu-mem 必须 ≤ 0.5",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {"aclgraph_compatible": "yes"},
        "strategy_id": "aclgraph",
    },
    # ── env: environment variables ──
    {
        "id": "task_queue",
        "name": "TASK_QUEUE_ENABLE",
        "layer": "parameter",
        "phase": "env",
        "priority": 80,
        "risk": "low",
        "expected_gain": "+10~13%",
        "config_desc": "TASK_QUEUE_ENABLE={1(AclGraph) 或 2(eager)}",
        "notes": "AclGraph 必须=1; eager 推荐=2",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "task_queue",
    },
    {
        "id": "flashcomm1",
        "name": "VLLM_ASCEND_ENABLE_FLASHCOMM1=1",
        "layer": "parameter",
        "phase": "env",
        "priority": 65,
        "risk": "low",
        "expected_gain": "+0~10%",
        "config_desc": "VLLM_ASCEND_ENABLE_FLASHCOMM1=1",
        "notes": "Ascend 910B 高速通信后端，TP>=2 时有效",
        "families": [],
        "exclude_if": {},
        "require_if": {"min_chips": 2},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "matmul_allreduce",
        "name": "VLLM_ASCEND_ENABLE_MATMUL_ALLREDUCE=1",
        "layer": "parameter",
        "phase": "env",
        "priority": 60,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "VLLM_ASCEND_ENABLE_MATMUL_ALLREDUCE=1",
        "notes": "融合 matmul 与 allreduce，TP>=2 有效; eager 模式表现更好",
        "families": [],
        "exclude_if": {},
        "require_if": {"min_chips": 2},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "hccl_aiv",
        "name": "HCCL_OP_EXPANSION_MODE=AIV",
        "layer": "parameter",
        "phase": "env",
        "priority": 55,
        "risk": "medium",
        "expected_gain": "+5~8%",
        "config_desc": "HCCL_OP_EXPANSION_MODE=AIV",
        "notes": "禁止设 full（导致 HcclGetRootInfo error）",
        "families": [],
        "exclude_if": {},
        "require_if": {"min_chips": 2},
        "prefer_if": {},
        "strategy_id": "hccl_aiv",
    },
    {
        "id": "jemalloc",
        "name": "jemalloc",
        "layer": "parameter",
        "phase": "env",
        "priority": 50,
        "risk": "low",
        "expected_gain": "+3~5%",
        "config_desc": "LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libjemalloc.so.2",
        "notes": "AclGraph 模式下效果可能微负",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "jemalloc",
    },
    {
        "id": "enable_nz",
        "name": "VLLM_ASCEND_ENABLE_NZ=1",
        "layer": "parameter",
        "phase": "env",
        "priority": 45,
        "risk": "low",
        "expected_gain": "+0~3%",
        "config_desc": "VLLM_ASCEND_ENABLE_NZ=1",
        "notes": "权重转 FRACTAL_NZ 格式加速; 默认已=1，确认即可",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "cpu_affinity",
        "name": "CPU_AFFINITY_CONF=1",
        "layer": "parameter",
        "phase": "env",
        "priority": 40,
        "risk": "low",
        "expected_gain": "+1~3%",
        "config_desc": "CPU_AFFINITY_CONF=1",
        "notes": "CPU 核绑定 NPU",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "cpu_affinity",
    },
    {
        "id": "balance_scheduling",
        "name": "VLLM_ASCEND_BALANCE_SCHEDULING=1",
        "layer": "parameter",
        "phase": "env",
        "priority": 35,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "VLLM_ASCEND_BALANCE_SCHEDULING=1",
        "notes": "负载均衡调度，多请求场景可能有效",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "omp_threads",
        "name": "OMP_NUM_THREADS=8",
        "layer": "parameter",
        "phase": "env",
        "priority": 30,
        "risk": "low",
        "expected_gain": "+0~2%",
        "config_desc": "OMP_NUM_THREADS=8",
        "notes": "TP>=2 时建议=1 避免争抢",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    # ── engine: vLLM CLI engine parameters ──
    {
        "id": "max_model_len",
        "name": "--max-model-len=4096",
        "layer": "parameter",
        "phase": "engine",
        "priority": 70,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--max-model-len 4096",
        "notes": "限制 KV 预分配，释放显存给并发; 不设可能默认 262144 导致 OOM",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "engine_params",
    },
    {
        "id": "gpu_mem_util",
        "name": "--gpu-memory-utilization=0.85",
        "layer": "parameter",
        "phase": "engine",
        "priority": 70,
        "risk": "medium",
        "expected_gain": "+0~10%",
        "config_desc": "--gpu-memory-utilization 0.85",
        "notes": "AclGraph+TP1 必须 ≤0.5; MoE 可能需 0.7",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "engine_params",
    },
    {
        "id": "max_batched_tokens",
        "name": "--max-num-batched-tokens=16384",
        "layer": "parameter",
        "phase": "engine",
        "priority": 65,
        "risk": "medium",
        "expected_gain": "+5~15%",
        "config_desc": "--max-num-batched-tokens 16384",
        "notes": "单次调度 token 上限; 过大可能 OOM",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "engine_params",
    },
    {
        "id": "prefix_caching",
        "name": "--enable-prefix-caching",
        "layer": "parameter",
        "phase": "engine",
        "priority": 50,
        "risk": "low",
        "expected_gain": "+5~15%",
        "config_desc": "--enable-prefix-caching",
        "notes": "KV cache 复用; bench serve 前缀不重复时效果有限",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {"is_vlm": True},
        "strategy_id": "",
    },
    {
        "id": "max_num_seqs",
        "name": "--max-num-seqs=256",
        "layer": "parameter",
        "phase": "engine",
        "priority": 55,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--max-num-seqs 256",
        "notes": "最大并发请求数",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "engine_params",
    },
    {
        "id": "chunked_prefill",
        "name": "--enable-chunked-prefill",
        "layer": "parameter",
        "phase": "engine",
        "priority": 45,
        "risk": "medium",
        "expected_gain": "+0~10%",
        "config_desc": "--enable-chunked-prefill",
        "notes": "分块 prefill 降低峰值显存; 大模型(14B+)更有效; **可能与 AclGraph 冲突**",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {"size_category": "large"},
        "strategy_id": "",
    },
    {
        "id": "kv_cache_fp8",
        "name": "--kv-cache-dtype fp8",
        "layer": "parameter",
        "phase": "engine",
        "priority": 40,
        "risk": "medium",
        "expected_gain": "间接(省显存)",
        "config_desc": "--kv-cache-dtype fp8",
        "notes": "KV cache 用 FP8，省 ~50% 显存; 需要硬件支持",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "performance_mode",
        "name": "--performance-mode throughput",
        "layer": "parameter",
        "phase": "engine",
        "priority": 35,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--performance-mode throughput",
        "notes": "vLLM 内置吞吐优先模式; 不确定 Ascend 后端是否完全支持",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    # ── additional: --additional-config keys ──
    {
        "id": "async_exponential",
        "name": "enable_async_exponential",
        "layer": "parameter",
        "phase": "additional",
        "priority": 60,
        "risk": "low",
        "expected_gain": "稳定性",
        "config_desc": "--additional-config '{\"enable_async_exponential\":true}'",
        "notes": "异步指数退避采样; Qwen3.5 系列实测 ~10x 提升",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {"family": "qwen3_5"},
        "strategy_id": "async_exponential",
    },
    {
        "id": "cpu_binding",
        "name": "enable_cpu_binding",
        "layer": "parameter",
        "phase": "additional",
        "priority": 30,
        "risk": "low",
        "expected_gain": "+0~2%",
        "config_desc": "--additional-config '{\"enable_cpu_binding\":true}'",
        "notes": "默认已开启; 确认即可",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "weight_prefetch",
        "name": "weight_prefetch_config",
        "layer": "parameter",
        "phase": "additional",
        "priority": 45,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--additional-config '{\"weight_prefetch_config\":{\"enabled\":true}}'",
        "notes": "权重预取隐藏延迟; 大模型可能更有效",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {"size_category": "large"},
        "strategy_id": "weight_prefetch",
    },
    {
        "id": "fuse_allreduce_rms",
        "name": "fuse_allreduce_rms",
        "layer": "parameter",
        "phase": "additional",
        "priority": 55,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--additional-config '{\"ascend_compilation_config\":{\"fuse_allreduce_rms\":true}}'",
        "notes": "融合 allreduce 与 RMSNorm; TP>=2 有效",
        "families": [],
        "exclude_if": {},
        "require_if": {"min_chips": 2},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "enable_npugraph_ex",
        "name": "enable_npugraph_ex",
        "layer": "parameter",
        "phase": "additional",
        "priority": 40,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--additional-config '{\"ascend_compilation_config\":{\"enable_npugraph_ex\":true}}'",
        "notes": "Fx graph 优化后端; 默认已开启",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "enable_kv_nz",
        "name": "enable_kv_nz",
        "layer": "parameter",
        "phase": "additional",
        "priority": 70,
        "risk": "medium",
        "expected_gain": "+5~15%",
        "config_desc": "--additional-config '{\"enable_kv_nz\":true}'",
        "notes": "KV cache 用 NZ 格式; **仅 MLA 架构 (DeepSeek)**; PD D 节点",
        "families": [],
        "exclude_if": {},
        "require_if": {"architecture_mla": True},
        "prefer_if": {},
        "strategy_id": "",
    },
    # ── comm: communication optimization (TP>=2) ──
    {
        "id": "flashcomm2_parallel",
        "name": "VLLM_ASCEND_FLASHCOMM2_PARALLEL_SIZE",
        "layer": "parameter",
        "phase": "comm",
        "priority": 55,
        "risk": "medium",
        "expected_gain": "+0~5%",
        "config_desc": "VLLM_ASCEND_FLASHCOMM2_PARALLEL_SIZE=<TP/2>",
        "notes": "O-matrix TP 分组; 必须 < 全局 TP; 与 oproj_tensor_parallel_size 互斥",
        "families": [],
        "exclude_if": {},
        "require_if": {"min_chips": 2},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "layer_sharding",
        "name": "layer_sharding=[\"o_proj\"]",
        "layer": "parameter",
        "phase": "comm",
        "priority": 50,
        "risk": "medium",
        "expected_gain": "+0~5%",
        "config_desc": "--additional-config '{\"layer_sharding\":[\"o_proj\"]}'",
        "notes": "与 FlashComm2 配合最佳; graph mode only",
        "families": [],
        "exclude_if": {},
        "require_if": {"min_chips": 2},
        "prefer_if": {},
        "strategy_id": "",
    },
    # ── moe: MoE-specific parameters ──
    {
        "id": "fused_mc2",
        "name": "VLLM_ASCEND_ENABLE_FUSED_MC2=1",
        "layer": "parameter",
        "phase": "moe",
        "priority": 80,
        "risk": "medium",
        "expected_gain": "+10~30%",
        "config_desc": "VLLM_ASCEND_ENABLE_FUSED_MC2=1",
        "notes": "融合 dispatch+FFN+combine; 仅 W8A8 量化 MoE; mode=1 非 MTP 非 dynamic-eplb",
        "families": [],
        "exclude_if": {},
        "require_if": {"is_moe": True},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "shared_expert_dp",
        "name": "enable_shared_expert_dp",
        "layer": "parameter",
        "phase": "moe",
        "priority": 60,
        "risk": "low",
        "expected_gain": "+0~10%",
        "config_desc": "--additional-config '{\"enable_shared_expert_dp\":true}' --enable-expert-parallel",
        "notes": "共享专家数据并行; 需要 TP>=2 + expert parallel",
        "families": [],
        "exclude_if": {},
        "require_if": {"is_moe": True, "min_chips": 2},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "multistream_overlap",
        "name": "multistream_overlap",
        "layer": "parameter",
        "phase": "moe",
        "priority": 50,
        "risk": "low",
        "expected_gain": "+0~10%",
        "config_desc": "--additional-config '{\"multistream_overlap_shared_expert\":true,\"multistream_overlap_gate\":true}'",
        "notes": "多流重叠计算; 仅含共享专家的 MoE 模型",
        "families": [],
        "exclude_if": {},
        "require_if": {"is_moe": True},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "eplb",
        "name": "dynamic EPLB",
        "layer": "parameter",
        "phase": "moe",
        "priority": 45,
        "risk": "medium",
        "expected_gain": "+0~10%",
        "config_desc": "DYNAMIC_EPLB=true --additional-config '{\"eplb_config\":{\"dynamic_eplb\":true}}'",
        "notes": "动态专家并行负载均衡; 需要 warmup 阶段收集热度",
        "families": [],
        "exclude_if": {},
        "require_if": {"is_moe": True},
        "prefer_if": {},
        "strategy_id": "",
    },
    # ── Layer 2: framework-level optimizations ──
    {
        "id": "block_size",
        "name": "--block-size 128",
        "layer": "framework",
        "phase": "framework",
        "priority": 50,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--block-size 128",
        "notes": "KV cache block 大小; 128 减少碎片",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "dtype_bf16",
        "name": "--dtype bfloat16",
        "layer": "framework",
        "phase": "framework",
        "priority": 45,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--dtype bfloat16",
        "notes": "BF16 计算通常比 FP16 更快; 确认模型权重支持",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "scheduling_policy",
        "name": "--scheduling-policy priority",
        "layer": "framework",
        "phase": "framework",
        "priority": 35,
        "risk": "low",
        "expected_gain": "多租户场景",
        "config_desc": "--scheduling-policy priority",
        "notes": "优先级调度 vs 默认 FCFS; 多请求混合场景可能有效",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "attention_backend",
        "name": "--attention-backend 选择",
        "layer": "framework",
        "phase": "framework",
        "priority": 40,
        "risk": "medium",
        "expected_gain": "+0~5%",
        "config_desc": "--attention-backend <backend_name>",
        "notes": "选择注意力后端; 架构相关，需要逐个测试可用后端",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "moe_backend",
        "name": "--moe-backend",
        "layer": "framework",
        "phase": "framework",
        "priority": 55,
        "risk": "medium",
        "expected_gain": "+5~15%",
        "config_desc": "--moe-backend aiter (or triton)",
        "notes": "MoE 后端选择; aiter 通常更快; 需要对应后端已安装",
        "families": [],
        "exclude_if": {},
        "require_if": {"is_moe": True},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "disable_cascade_attn",
        "name": "--disable-cascade-attn",
        "layer": "framework",
        "phase": "framework",
        "priority": 30,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--disable-cascade-attn",
        "notes": "禁用级联注意力; 某些模型架构可能受益",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "kv_sharing_fast_prefill",
        "name": "--kv-sharing-fast-prefill",
        "layer": "framework",
        "phase": "framework",
        "priority": 35,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--kv-sharing-fast-prefill",
        "notes": "KV 共享加速 prefill; 长上下文场景可能有效",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {"size_category": "large"},
        "strategy_id": "",
    },
    {
        "id": "ubatch_size",
        "name": "--ubatch-size",
        "layer": "framework",
        "phase": "framework",
        "priority": 40,
        "risk": "medium",
        "expected_gain": "+0~10%",
        "config_desc": "--ubatch-size <size>",
        "notes": "微批次大小; 调优需要多次尝试不同值",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    # ── Layer 3: model-level optimizations (no quantization) ──
    {
        "id": "override_attention_dtype",
        "name": "--override-attention-dtype float32",
        "layer": "model",
        "phase": "model",
        "priority": 30,
        "risk": "low",
        "expected_gain": "精度保障",
        "config_desc": "--override-attention-dtype float32",
        "notes": "注意力用 FP32 计算; 精度换速度（通常更慢）",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "disable_sliding_window",
        "name": "--disable-sliding-window",
        "layer": "model",
        "phase": "model",
        "priority": 30,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--disable-sliding-window",
        "notes": "禁用滑动窗口; 某些模型默认启用，禁用可能改善吞吐",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "prefix_caching_hash",
        "name": "--prefix-caching-hash-algo xxhash",
        "layer": "model",
        "phase": "model",
        "priority": 35,
        "risk": "low",
        "expected_gain": "+0~5%",
        "config_desc": "--prefix-caching-hash-algo xxhash",
        "notes": "prefix caching hash 算法; xxhash 比 sha256 更快",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "load_format",
        "name": "--load-format",
        "layer": "model",
        "phase": "model",
        "priority": 25,
        "risk": "low",
        "expected_gain": "启动速度",
        "config_desc": "--load-format safetensors (or npu / tensorizer)",
        "notes": "权重加载格式; safetensors 最通用; npu 格式可能更快加载",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    # ── Layer 4: operator-level optimizations ──
    {
        "id": "ascend_custom_ops",
        "name": "vllm_ascend_C 编译",
        "layer": "operator",
        "phase": "operator",
        "priority": 60,
        "risk": "high",
        "expected_gain": "+5~15%",
        "config_desc": "编译 vllm_ascend_C 自定义算子库",
        "notes": "需要 cmake 编译; 编译耗时长; -j1 必须; 编译后 cp .so 到 vllm_ascend/ 目录",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "hccl_bufsize",
        "name": "HCCL_BUFFSIZE 调优",
        "layer": "operator",
        "phase": "operator",
        "priority": 45,
        "risk": "medium",
        "expected_gain": "+0~5%",
        "config_desc": "HCCL_BUFFSIZE=<size>",
        "notes": "HCCL 通信缓冲区大小; 过大浪费显存，过小影响性能",
        "families": [],
        "exclude_if": {},
        "require_if": {"min_chips": 2},
        "prefer_if": {},
        "strategy_id": "",
    },
    {
        "id": "finegrained_tp",
        "name": "finegrained_tp_config",
        "layer": "operator",
        "phase": "operator",
        "priority": 50,
        "risk": "high",
        "expected_gain": "+0~10%",
        "config_desc": "--additional-config '{\"finegrained_tp_config\":{\"oproj_tensor_parallel_size\":<N>}}'",
        "notes": "细粒度 TP 分区; graph mode only; 与 FLASHCOMM2_PARALLEL_SIZE 互斥",
        "families": [],
        "exclude_if": {},
        "require_if": {"min_chips": 2},
        "prefer_if": {"is_moe": True},
        "strategy_id": "",
    },
    {
        "id": "static_kernel",
        "name": "enable_static_kernel",
        "layer": "operator",
        "phase": "operator",
        "priority": 45,
        "risk": "medium",
        "expected_gain": "+0~5%",
        "config_desc": "--additional-config '{\"ascend_compilation_config\":{\"enable_static_kernel\":true}}'",
        "notes": "静态 kernel 编译; 增加 startup 时间但运行时更快; 需要 npugraph_ex=True",
        "families": [],
        "exclude_if": {},
        "require_if": {},
        "prefer_if": {},
        "strategy_id": "",
    },
]

# Phase display order — grouped by layer, then by phase within layer
_PHASE_ORDER = [
    # Layer 1: parameter (existing phases)
    ("graph_test", "AclGraph 兼容性测试"),
    ("env", "环境变量"),
    ("engine", "引擎参数"),
    ("additional", "additional_config"),
    ("comm", "通信优化 (TP>=2)"),
    ("moe", "MoE 专用"),
    ("stability", "稳定性优化"),
    # Layer 2: framework
    ("framework", "框架层优化"),
    # Layer 3: model
    ("model", "模型层优化"),
    # Layer 4: operator
    ("operator", "算子层优化"),
]

# ── Method parsing (migrated from config_recommend.py) ──────────────────────


def _parse_methods_string(
    methods_str: str | None,
) -> tuple[dict[str, str], dict[str, Any], list[str]]:
    """
    Parse optimization_methods string (semicolon- or comma-separated).

    Returns:
        (env_vars_dict, engine_params_dict, feature_flags_list)
    """
    env_vars: dict[str, str] = {}
    engine_params: dict[str, Any] = {}
    features: list[str] = []

    if not methods_str:
        return env_vars, engine_params, features

    tokens = [t.strip() for t in methods_str.split(";") if t.strip()]
    if len(tokens) <= 1:
        tokens = [t.strip() for t in methods_str.split(",") if t.strip()]

    for token in tokens:
        token = token.strip()
        if not token:
            continue

        if token.lower() == "jemalloc":
            env_vars["LD_PRELOAD"] = "/usr/lib/aarch64-linux-gnu/libjemalloc.so"
            features.append(token)
            continue

        if token.lower().startswith("aclgraph") or token.lower().startswith("cudagraph"):
            if "full_decode" in token.lower():
                engine_params.setdefault("compilation_config", {})
                engine_params["compilation_config"]["mode"] = "none"
                engine_params["compilation_config"]["cudagraph_mode"] = "FULL_DECODE_ONLY"
            features.append(token)
            continue

        if token.lower().startswith("enable_async_exponential"):
            engine_params["enable_async_exponential_backoff"] = True
            features.append(token)
            continue

        if token.lower().startswith("weight_prefetch"):
            engine_params["weight_prefetch"] = True
            features.append(token)
            continue

        if "=" in token:
            key, _, val = token.partition("=")
            key = key.strip()
            val = val.strip()
            if key.isupper() and key in ENV_VAR_KEYS:
                env_vars[key] = val
                features.append(token)
                continue
            mapped_key = METHODS_ENGINE_MAP.get(key.lower())
            if mapped_key:
                try:
                    engine_params[mapped_key] = type(engine_params.get(mapped_key, 0))(val)
                except (ValueError, TypeError):
                    engine_params[mapped_key] = val
                features.append(token)
                continue
            features.append(token)
            continue

        features.append(token)

    return env_vars, engine_params, features


# ── Model classification ─────────────────────────────────────────────────────


def _classify_model(db_path: Path, model_id: str) -> dict[str, Any]:
    """
    Classify a model by family, size, type, and AclGraph compatibility.

    Uses DB metadata when available, falls back to model_id string parsing.
    """
    profile: dict[str, Any] = {
        "family": "unknown",
        "size_b": 0.0,
        "size_category": "unknown",
        "is_moe": False,
        "is_vlm": False,
        "architecture": None,
        "aclgraph_compatible": "try",  # "yes" | "no" | "try"
    }

    # ── Query DB for metadata ──
    db_arch = None
    db_param_count = None
    db_is_moe = None
    db_is_vlm = None

    if db_path.is_file():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT architecture, parameter_count, is_moe, is_vlm, model_type "
                "FROM models WHERE LOWER(model_id) = LOWER(?)",
                (model_id,),
            )
            row = cur.fetchone()
            conn.close()
            if row:
                db_arch = row["architecture"]
                db_param_count = row["parameter_count"]
                db_is_moe = row["is_moe"]
                db_is_vlm = row["is_vlm"]
        except Exception:
            pass

    # ── Parse model_id string ──
    mid_lower = model_id.lower().replace("/", "_").replace("-", "_")

    # Family detection
    if "qwen3_5" in mid_lower or "qwen3.5" in mid_lower:
        profile["family"] = "qwen3_5"
    elif "qwen3" in mid_lower:
        profile["family"] = "qwen3"
    elif "qwen2_5" in mid_lower or "qwen2.5" in mid_lower:
        profile["family"] = "qwen2_5"
    elif "qwen2" in mid_lower:
        profile["family"] = "qwen2"
    elif "llama" in mid_lower:
        profile["family"] = "llama"
    elif "mistral" in mid_lower:
        profile["family"] = "mistral"
    elif "gpt2" in mid_lower:
        profile["family"] = "gpt2"
    elif "internvl" in mid_lower or "intervl" in mid_lower:
        profile["family"] = "internvl"
    elif "smolvlm" in mid_lower:
        profile["family"] = "smolvlm"
    elif "phi" in mid_lower:
        profile["family"] = "phi"
    elif "gemma" in mid_lower:
        profile["family"] = "gemma"
    elif "deepseek" in mid_lower:
        profile["family"] = "deepseek"
    elif "opt" in mid_lower and "125m" in mid_lower:
        profile["family"] = "opt"

    # Size parsing from model_id
    size_b = _parse_size_from_id(mid_lower)
    # DB parameter_count can be misleading (sometimes token count, not param count).
    # Heuristic: if db value / id-derived value differs by > 10x, trust ID instead.
    if db_param_count and db_param_count > 1_000_000_000:
        # Looks like total parameters (e.g. 7B = 7_000_000_000)
        db_size_b = db_param_count / 1e9
        if size_b > 0 and (db_size_b / size_b > 10 or db_size_b / size_b < 0.1):
            # DB value wildly disagrees with ID — trust ID
            profile["size_b"] = size_b
        else:
            profile["size_b"] = db_size_b
    elif size_b > 0:
        profile["size_b"] = size_b

    # Size category
    sb = profile["size_b"]
    if sb <= 0:
        profile["size_category"] = "unknown"
    elif sb < 1:
        profile["size_category"] = "tiny"
    elif sb <= 3:
        profile["size_category"] = "small"
    elif sb <= 14:
        profile["size_category"] = "medium"
    elif sb <= 70:
        profile["size_category"] = "large"
    else:
        profile["size_category"] = "xlarge"

    # MoE detection
    is_moe_from_id = _detect_moe(mid_lower)
    # DB is_moe=0 often means "not filled in", not "confirmed non-MoE".
    # Only trust DB is_moe when it's explicitly 1.
    if db_is_moe == 1:
        profile["is_moe"] = True
    elif is_moe_from_id:
        profile["is_moe"] = True

    # VLM detection
    vlm_keywords = {"vl", "vision", "vlm", "internvl", "smolvlm", "blip", "moondream", "tarsier"}
    if db_is_vlm == 1:
        profile["is_vlm"] = True
    elif any(kw in mid_lower for kw in vlm_keywords):
        profile["is_vlm"] = True

    # Architecture
    profile["architecture"] = db_arch

    # AclGraph compatibility (must come after MoE/VLM detection)
    # NOTE: Only mark "yes" when we have positive evidence (DB or known-compatible arch).
    # Never hardcode "no" — insufficient data, and incompatibility is often version-dependent.
    # Let the exploration protocol's Phase 1 compatibility test handle unknown cases.
    if db_arch and db_arch in _ACLGRAPH_COMPATIBLE_ARCHS:
        profile["aclgraph_compatible"] = "yes"
    elif profile["family"] in ("qwen3_5", "qwen3", "qwen2_5", "qwen2"):
        # Qwen series has strong evidence of AclGraph working (dense models).
        # MoE is unproven but not theoretically blocked — let Phase 1 decide.
        profile["aclgraph_compatible"] = "yes"
    # else: "try" (default) — Phase 1 will test and mark result

    return profile


def _parse_size_from_id(mid_lower: str) -> float:
    """Extract model size in billions from model_id string."""
    # Special case: "0_8b" pattern (e.g., qwen3_5_0_8b → 0.8B).
    # Only match when first group is 0 to avoid false positives like "5_2b".
    match = re.search(r"(?<![a-z\d])0_(\d+)b(?![a-z0-9])", mid_lower)
    if match:
        return float(f"0.{match.group(1)}")
    # Standard match: "N.Nb" or "Nb" (e.g., "0.8b", "27b") — but not "a10b"
    match = re.search(r"(?<![a-z\d])(\d+(?:\.\d+)?)\s*b(?![a-z0-9])", mid_lower)
    if match:
        return float(match.group(1))
    return 0.0


def _detect_moe(mid_lower: str) -> bool:
    """Detect MoE from _A{N}B suffix pattern or explicit keywords."""
    if re.search(r"_a\d+b", mid_lower):
        return True
    moe_keywords = {"moe", "expert"}
    return any(kw in mid_lower for kw in moe_keywords)


# ── Historical pattern extraction ────────────────────────────────────────────


def _query_optimization_patterns(
    db_path: Path,
    model_id: str,
    model_profile: dict[str, Any],
    chips: int,
) -> dict[str, Any]:
    """
    Query historical optimization results to build strategy guidance.

    Returns a dict with:
        - already_optimized: bool
        - best_existing: dict | None
        - similar_models: list[dict]
        - strategy_effectiveness: dict
        - known_failures: list[dict]
        - tp_recommendations: dict
        - confidence: str
    """
    result: dict[str, Any] = {
        "already_optimized": False,
        "best_existing": None,
        "similar_models": [],
        "strategy_effectiveness": {},
        "known_failures": [],
        "tp_recommendations": {},
        "confidence": "low",
    }

    if not db_path.is_file():
        return result

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # ── Q1: Same model existing results ──
        cur.execute(
            """SELECT benchmark_stage, tensor_parallel_size, output_tok_per_s,
                      optimization_methods, chips, notes, config
               FROM benchmark_results
               WHERE LOWER(model_id) = LOWER(?)
               ORDER BY output_tok_per_s DESC""",
            (model_id,),
        )
        own_rows = [dict(r) for r in cur.fetchall()]

        optimized_own = [r for r in own_rows if r.get("benchmark_stage", "").lower() not in ("baseline",)]

        if optimized_own:
            result["already_optimized"] = True
            # Filter by chip constraint
            fitting = [r for r in optimized_own if (r.get("tensor_parallel_size") or 0) <= chips]
            if fitting:
                best = max(fitting, key=lambda r: r.get("output_tok_per_s") or 0)
            else:
                best = optimized_own[0]
            result["best_existing"] = {
                "tp": best.get("tensor_parallel_size"),
                "tok_per_s": best.get("output_tok_per_s"),
                "methods": best.get("optimization_methods", ""),
                "config": best.get("config", ""),
                "chips": best.get("chips"),
            }

        # ── Q2: Similar family results ──
        family = model_profile.get("family", "unknown")
        is_moe = model_profile.get("is_moe", False)
        size_cat = model_profile.get("size_category", "unknown")

        # Build LIKE patterns for family matching
        like_patterns = []
        if family != "unknown":
            like_patterns.append(f"%{family}%")
        # Also match normalized forms (e.g., "qwen3_5" matches "qwen/qwen3.5")
        family_dots = family.replace("_", ".")
        if family_dots != family:
            like_patterns.append(f"%{family_dots}%")

        similar = []
        if like_patterns:
            placeholders = " OR ".join(["LOWER(m.model_id) LIKE ?"] * len(like_patterns))
            cur.execute(
                f"""SELECT br.model_id, m.parameter_count, m.is_moe, m.is_vlm,
                          br.tensor_parallel_size as tp,
                          br.output_tok_per_s as opt_tps,
                          br.optimization_methods,
                          br.benchmark_stage,
                          br.notes
                   FROM benchmark_results br
                   JOIN models m ON LOWER(br.model_id) = LOWER(m.model_id)
                   WHERE br.benchmark_stage NOT LIKE '%baseline%'
                     AND LOWER(br.model_id) != LOWER(?)
                     AND ({placeholders})
                   ORDER BY br.output_tok_per_s DESC""",
                [model_id] + like_patterns,
            )
            similar = [dict(r) for r in cur.fetchall()]

        # Also add baseline data for improvement calculation
        if similar:
            similar_ids = [s["model_id"] for s in similar]
            id_placeholders = ",".join(["?"] * len(similar_ids))
            cur.execute(
                f"""SELECT model_id, tensor_parallel_size as tp, output_tok_per_s as base_tps
                   FROM benchmark_results
                   WHERE benchmark_stage LIKE '%baseline%'
                     AND model_id IN ({id_placeholders})""",
                similar_ids,
            )
            baselines = {}
            for r in cur.fetchall():
                baselines.setdefault(r["model_id"], {})[r["tp"]] = r["base_tps"]

            for s in similar:
                base_tps = baselines.get(s["model_id"], {}).get(s["tp"], 0)
                s["baseline_tps"] = base_tps
                if base_tps and base_tps > 0 and s.get("opt_tps"):
                    s["improvement_pct"] = round((s["opt_tps"] / base_tps - 1) * 100, 1)
                else:
                    s["improvement_pct"] = None

        result["similar_models"] = similar

        # ── Q3: Strategy effectiveness aggregation ──
        strat_stats: dict[str, dict[str, Any]] = {}
        for s in similar:
            methods_str = s.get("optimization_methods", "")
            _, _, features = _parse_methods_string(methods_str)
            # Also check config for AclGraph
            config_str = s.get("config", "")
            if config_str and ("aclgraph" in config_str.lower() or "cudagraph" in config_str.lower()):
                features.append("aclgraph_from_config")

            for f in features:
                norm = _normalize_strategy_name(f)
                if not norm:
                    continue
                if norm not in strat_stats:
                    strat_stats[norm] = {"improvements": [], "tok_per_sec": [], "source_sizes": []}
                if s.get("improvement_pct") is not None:
                    strat_stats[norm]["improvements"].append(s["improvement_pct"])
                if s.get("opt_tps"):
                    strat_stats[norm]["tok_per_sec"].append(s["opt_tps"])
                # Track source model size for relevance filtering
                # Try parameter_count first, then parse from model_id
                pc = s.get("parameter_count")
                if not pc:
                    mid = s.get("model_id", "")
                    # Extract size from model_id like "qwen3_5_0_8b" → 0.8
                    import re as _re
                    m = _re.search(r"(\d+(?:\.\d+)?)b", mid.lower())
                    if m:
                        pc = float(m.group(1))
                if pc:
                    strat_stats[norm]["source_sizes"].append(pc)

        for strat_id, stats in strat_stats.items():
            imps = [x for x in stats["improvements"] if x is not None]
            src_sizes = stats.get("source_sizes", [])
            result["strategy_effectiveness"][strat_id] = {
                "avg_improvement": round(sum(imps) / len(imps), 1) if imps else None,
                "max_improvement": max(imps) if imps else None,
                "min_improvement": min(imps) if imps else None,
                "success_count": len(imps),
                "avg_tok_per_s": round(sum(stats["tok_per_sec"]) / len(stats["tok_per_sec"]), 1) if stats["tok_per_sec"] else None,
                "avg_source_size_b": round(sum(src_sizes) / len(src_sizes), 1) if src_sizes else None,
            }

        # ── Q4: Models with explicit AclGraph failure notes ──
        # Only flag when notes explicitly mention AclGraph failure — don't infer from absence.
        if like_patterns:
            cur.execute(
                f"""SELECT DISTINCT br.model_id, br.notes
                   FROM benchmark_results br
                   WHERE LOWER(br.model_id) LIKE ?
                     AND LOWER(br.notes) LIKE '%aclgraph%'
                     AND (LOWER(br.notes) LIKE '%fail%' OR LOWER(br.notes) LIKE '%crash%'
                          OR LOWER(br.notes) LIKE '%不兼容%' OR LOWER(br.notes) LIKE '%skip%')
                   LIMIT 10""",
                (f"%{family}%",) if family != "unknown" else ("%",),
            )
            for r in cur.fetchall():
                result["known_failures"].append({
                    "strategy": "aclgraph",
                    "model_id": dict(r)["model_id"],
                    "reason": dict(r).get("notes", "AclGraph 失败")[:80],
                })

        # ── Q5: TP recommendations based on size ──
        size_cat = model_profile.get("size_category", "unknown")
        tp_map = {
            "tiny": {"primary": 1, "secondary": [2], "reason": "小模型 TP1/TP2 最优"},
            "small": {"primary": 2, "secondary": [1, 4], "reason": "小模型 TP2 通常最优"},
            "medium": {"primary": 4, "secondary": [2], "reason": "中模型 TP4 通常最优"},
            "large": {"primary": 4, "secondary": [2, 8], "reason": "大模型需要多卡"},
            "xlarge": {"primary": 8, "secondary": [4], "reason": "超大模型需要 8+ 卡"},
            "unknown": {"primary": 1, "secondary": [2, 4], "reason": "未知大小，从 TP1 开始尝试"},
        }
        if is_moe:
            tp_map.setdefault(size_cat, tp_map.get("medium", tp_map["medium"]))
            tp_map[size_cat]["primary"] = max(tp_map[size_cat].get("primary", 4), 4)
        result["tp_recommendations"] = tp_map.get(size_cat, tp_map["unknown"])

        # ── Confidence ──
        n_similar = len(set(s["model_id"] for s in similar))
        if n_similar >= 3:
            result["confidence"] = "high"
        elif n_similar >= 1:
            result["confidence"] = "medium"

        conn.close()

    except Exception:
        pass

    return result


def _normalize_strategy_name(name: str) -> str:
    """Normalize a strategy/feature name to a canonical ID."""
    n = name.lower().strip()
    # AclGraph / cudagraph variants
    if "aclgraph" in n or "cudagraph" in n:
        return "aclgraph"
    if n == "jemalloc":
        return "jemalloc"
    if "task_queue" in n:
        return "task_queue"
    if "cpu_affinity" in n:
        return "cpu_affinity"
    if "hccl" in n:
        return "hccl_aiv"
    if "async_exponential" in n:
        return "async_exponential"
    if "weight_prefetch" in n:
        return "weight_prefetch"
    # Engine param shorthands → group as "engine_params"
    if any(k in n for k in ("max-num-batched", "max-batched", "max-num-seqs", "max-model-len", "gpu-mem")):
        return "engine_params"
    return ""


# ── Dynamic exploration step generation ──────────────────────────────────────


def _is_applicable(param: dict[str, Any], profile: dict[str, Any], chips: int) -> bool:
    """Check if a parameter entry applies to the given model profile and chip count."""
    # Family whitelist
    families = param.get("families", [])
    if families and profile.get("family", "unknown") not in families:
        return False

    # Exclude conditions
    for field, value in param.get("exclude_if", {}).items():
        if profile.get(field) == value:
            return False

    # Require conditions
    for field, value in param.get("require_if", {}).items():
        if field == "min_chips":
            if chips < value:
                return False
        elif field == "architecture_mla":
            arch = profile.get("architecture", "") or ""
            if not ("mla" in arch.lower() or "deepseek" in profile.get("family", "").lower()):
                return False
        elif profile.get(field) != value:
            return False

    return True


def _compute_priority(param: dict[str, Any], profile: dict[str, Any], patterns: dict[str, Any]) -> int:
    """Compute dynamic priority score for a parameter."""
    score = param["priority"]

    # Historical data boost
    strategy_id = param.get("strategy_id", "")
    if strategy_id:
        eff = patterns.get("strategy_effectiveness", {}).get(strategy_id, {})
        if eff.get("avg_improvement") and eff["avg_improvement"] > 50:
            score += 20
        elif eff.get("success_count", 0) >= 3:
            score += 10
        elif eff.get("avg_improvement") and eff["avg_improvement"] > 10:
            score += 10

    # Model feature boost
    for field, value in param.get("prefer_if", {}).items():
        if profile.get(field) == value:
            score += 15

    return score


def _build_exploration_steps(
    profile: dict[str, Any],
    patterns: dict[str, Any],
    chips: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Build ordered exploration steps and list of skipped parameters.

    Returns:
        (steps, skipped) where each step is a dict with:
            - param: the registry entry
            - score: computed priority
            - expected: expected gain string (from history or default)
        and each skipped entry has:
            - id, name, reason
    """
    effectiveness = patterns.get("strategy_effectiveness", {})
    steps: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for param in _PARAMETER_REGISTRY:
        if not _is_applicable(param, profile, chips):
            # Record why it was skipped
            reason = _skip_reason(param, profile, chips)
            skipped.append({"id": param["id"], "name": param["name"], "reason": reason})
            continue

        score = _compute_priority(param, profile, patterns)

        # Determine expected gain from history
        strategy_id = param.get("strategy_id", "")
        if strategy_id and strategy_id in effectiveness:
            eff = effectiveness[strategy_id]
            if eff.get("avg_improvement"):
                avg_src_size = eff.get("avg_source_size_b", 0)
                current_size = profile.get("size_b", 0)
                # Check if historical data is from significantly smaller models
                if avg_src_size and current_size and avg_src_size < current_size * 0.5:
                    # Data from much smaller models — show as reference, not prediction
                    expected = f"参考(小模型)+{eff['avg_improvement']}%"
                else:
                    expected = f"+{eff['avg_improvement']}%"
            else:
                expected = param.get("expected_gain", "未知")
        else:
            expected = param.get("expected_gain", "未知")

        steps.append({
            "param": param,
            "score": score,
            "expected": expected,
        })

    # Sort: by phase order, then by score descending within each phase
    phase_index = {p: i for i, (p, _) in enumerate(_PHASE_ORDER)}
    steps.sort(key=lambda s: (phase_index.get(s["param"]["phase"], 99), -s["score"]))

    return steps, skipped


def _skip_reason(param: dict[str, Any], profile: dict[str, Any], chips: int) -> str:
    """Generate a human-readable reason for why a parameter was skipped."""
    # Check require_if first
    for field, value in param.get("require_if", {}).items():
        if field == "min_chips" and chips < value:
            return f"需要 TP>={value}，当前仅 {chips} 芯"
        if field == "architecture_mla":
            return "仅 MLA 架构 (DeepSeek)"
        if profile.get(field) != value:
            return f"不满足 {field}={value}"

    # Check exclude_if
    for field, value in param.get("exclude_if", {}).items():
        if profile.get(field) == value:
            return f"模型为 {field}"

    # Check families
    families = param.get("families", [])
    if families and profile.get("family", "unknown") not in families:
        return f"家族 {profile.get('family')} 不在适用列表"

    return "不适用"


# ── Prompt generation ────────────────────────────────────────────────────────


def build_optimization_prompt(
    db_path: Path | str,
    model_id: str,
    chips: int,
) -> str:
    """
    Build a data-driven optimization prompt for the team-lead.

    Queries historical results, classifies the model, and generates
    a targeted prompt that tells the optimizer exactly which strategies
    to try, skip, and in what order.
    """
    db_path = Path(db_path).resolve()
    profile = _classify_model(db_path, model_id)
    patterns = _query_optimization_patterns(db_path, model_id, profile, chips)

    return _generate_strategy_prompt(model_id, profile, patterns, chips)


def _generate_strategy_prompt(
    model_id: str,
    profile: dict[str, Any],
    patterns: dict[str, Any],
    chips: int,
) -> str:
    """Generate the full prompt: model header + exploration protocol."""
    lines: list[str] = []
    lines.append("仅执行优化阶段。")
    lines.append("")

    # ── Model header ──
    family = profile.get("family", "unknown")
    size_b = profile.get("size_b", 0)
    size_cat = profile.get("size_category", "unknown")
    is_moe = profile.get("is_moe", False)
    is_vlm = profile.get("is_vlm", False)

    model_type = "MoE" if is_moe else ("VLM" if is_vlm else "Dense")
    lines.append("## 目标模型")
    lines.append(f"- model_id: {model_id}")
    lines.append(f"- 分类: {family} {model_type} ~{size_b}B ({size_cat})")
    lines.append(f"- 可用芯片数: {chips}")
    lines.append("")

    # ── Exploration protocol (includes strategy guidance, TP recs, historical data) ──
    lines.append(_build_exploration_protocol(model_id, profile, patterns, chips))

    return "\n".join(lines)


# ── Systematic Ablation Exploration Protocol ──────────────────────────────────


def _build_exploration_protocol(
    model_id: str,
    profile: dict[str, Any],
    patterns: dict[str, Any],
    chips: int,
) -> str:
    """
    Build a dynamic exploration protocol based on model type and historical data.

    Instead of fixed phases, generates prioritized steps from the parameter
    registry, filtered by model applicability and sorted by expected impact.
    """
    is_moe = profile.get("is_moe", False)
    size_b = profile.get("size_b", 0)
    size_cat = profile.get("size_category", "unknown")
    already_opt = patterns.get("already_optimized", False)
    effectiveness = patterns.get("strategy_effectiveness", {})
    similar = patterns.get("similar_models", [])
    failures = patterns.get("known_failures", [])
    n_similar = len(set(s["model_id"] for s in similar))
    confidence = patterns.get("confidence", "low")

    tp_rec = patterns.get("tp_recommendations", {})
    primary_tp = tp_rec.get("primary", 1)
    secondary_tp = tp_rec.get("secondary", [])
    tp_configs = [primary_tp]
    for t in secondary_tp:
        if t <= chips and t not in tp_configs:
            tp_configs.append(t)
        if len(tp_configs) >= 3:
            break

    # Build dynamic steps
    steps, skipped = _build_exploration_steps(profile, patterns, chips)

    # Group steps by phase
    phase_steps: dict[str, list[dict[str, Any]]] = {}
    for s in steps:
        phase = s["param"]["phase"]
        phase_steps.setdefault(phase, []).append(s)

    lines: list[str] = []

    # ── Header ──
    if n_similar > 0:
        lines.append(f"## 探索协议（基于 {n_similar} 个相似模型数据，置信度: {confidence}）")
    else:
        lines.append("## 探索协议（无历史数据，使用通用策略）")
    lines.append("")

    n_total = sum(len(v) for v in phase_steps.values())

    # Count per-layer
    _LAYER_LABELS = {"parameter": "Layer 1 参数层", "framework": "Layer 2 框架层", "model": "Layer 3 模型层", "operator": "Layer 4 算子层"}
    layer_counts: dict[str, int] = {}
    for s in steps:
        layer = s["param"].get("layer", "parameter")
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    layer_summary = " | ".join(f"{_LAYER_LABELS.get(l, l)}: {c}" for l, c in layer_counts.items() if c > 0)
    lines.append(f"**适用参数**: {n_total} 个 | **跳过**: {len(skipped)} 个 | **模型**: {profile.get('family')} {'MoE' if is_moe else ''}{'VLM' if profile.get('is_vlm') else ''} ~{size_b}B")
    lines.append(f"**深度分布**: {layer_summary}")
    lines.append("")
    lines.append("**核心原则**：逐层叠加优化，每层测量边际增益，存储中间结果到 DB。")
    lines.append("禁止一次性应用所有策略——必须按阶段执行并记录每阶段数据。")
    lines.append("")
    lines.append("### 每阶段必须做的事")
    lines.append("1. 在 `benchmark_stage` 字段记录阶段名称（如 `explore_2a_tq`）")
    lines.append("2. 在 `notes` 字段记录本阶段相比上一阶段的边际增益（如 `+12.3% vs phase1`）")
    lines.append("3. 使用标准 bench 参数: seed=42, burstiness=1.0, 64 prompts, input=512, output=128")
    lines.append("4. bench 前发送 3 个预热请求排除冷启动")
    lines.append("")

    # ── Serve 命令模板（严格遵守） ──
    lines.append("### ⚠️ Serve/Bench 命令模板（严格遵守）")
    lines.append("")
    lines.append("**`vllm serve` 的模型路径是位置参数，不能用 `--model`！**")
    lines.append("")

    _SERVE_TEMPLATE = r"""```bash
# === 启动 serve ===
cd adaptations/{model_id}/benchmarks/explore_{phase}/

ASCEND_RT_VISIBLE_DEVICES={chips} \
MASTER_PORT=29500 \
HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 \
setsid vllm serve MODEL_PATH \
    --host 0.0.0.0 --port 9999 \
    --tensor-parallel-size {tp} \
    --enforce-eager \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.85 \
    --trust-remote-code \
    --served-model-name "MODEL_NAME" \
    > serve.log 2>&1 &
SERVE_PID=$!

# === 等待就绪（含进程存活检测） ===
for i in $(seq 1 120); do
    if ! kill -0 $SERVE_PID 2>/dev/null; then
        echo "SERVE_DIED: process exited"
        tail -20 serve.log
        break
    fi
    if curl -sf http://127.0.0.1:9999/v1/models > /dev/null 2>&1; then
        echo "SERVE_READY after $((i*5))s"
        break
    fi
    sleep 5
done

# === 预热 ===
for w in $(seq 1 3); do
  curl -sf http://127.0.0.1:9999/v1/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "MODEL_NAME", "prompt": "Warmup", "max_tokens": 128}' > /dev/null 2>&1
done

# === 标准 bench（A100 对标参数） ===
vllm bench serve \
    --seed 42 \
    --burstiness 1.0 \
    --backend vllm \
    --host 127.0.0.1 \
    --port 9999 \
    --endpoint /v1/completions \
    --model MODEL_NAME \
    --tokenizer MODEL_PATH \
    --dataset-name random \
    --num-prompts 64 \
    --random-input-len 512 \
    --random-output-len 128 \
    --ignore-eos

# === 停止 serve ===
PGID=$(ps -o pgid= -p $SERVE_PID | tr -d ' ')
[ -n "$PGID" ] && kill -9 -$PGID 2>/dev/null
sleep 3
npu-smi info | grep "HBM-Usage"
```"""
    lines.append(_SERVE_TEMPLATE)
    lines.append("")

    # ── Early exit: already optimized ──
    if already_opt and patterns.get("best_existing"):
        best = patterns["best_existing"]
        lines.append("### ⚠️ 该模型已有优化结果")
        lines.append(f"- 最优: TP{best.get('tp')} {best.get('tok_per_s', 0):.1f} tok/s")
        lines.append(f"- 方法: {best.get('methods', 'N/A')}")
        lines.append("")
        lines.append("**如果要重新探索**，执行下方完整协议。")
        lines.append("**如果接受现有结果**，直接跳到最终验证，然后报告完成。")
        lines.append("")

    # ── TP recommendations ──
    lines.append(f"### 推荐 TP 配置（{tp_rec.get('reason', '')}）")
    lines.append(f"- 首选: TP{primary_tp}")
    if secondary_tp:
        lines.append(f"- 备选: {', '.join(f'TP{t}' for t in secondary_tp)}")
    lines.append("")

    # ── Historical notes (informational) ──
    if failures:
        lines.append("### ⚠️ 历史参考")
        for f in failures[:3]:
            lines.append(f"- {f.get('model_id', '?')}: {f.get('reason', '')}")
        lines.append("以上仅供参考，仍需兼容性测试验证当前模型/版本。")
        lines.append("")

    # ── Skipped parameters (informational) ──
    if skipped:
        lines.append("### 跳过的参数")
        for s in skipped:
            lines.append(f"- ~~{s['name']}~~ — {s['reason']}")
        lines.append("")

    # ── Phase 0: Baseline (always) ──
    phase_num = 0
    lines.append("---")
    lines.append(f"### Phase {phase_num}: Baseline（必须，~5 分钟）")
    lines.append(f"- 配置: enforce-eager, TP{primary_tp}, 默认引擎参数")
    lines.append("- benchmark_stage: `baseline`")
    lines.append("- 退出条件: bench 成功完成")
    lines.append("")

    # ── Dynamic phases (grouped by layer) ──
    phase_num += 1
    current_layer = None
    for phase_key, phase_label in _PHASE_ORDER:
        phase_items = phase_steps.get(phase_key, [])
        if not phase_items:
            continue

        # Layer separator
        step_layer = phase_items[0]["param"].get("layer", "parameter")
        if step_layer != current_layer:
            layer_label = _LAYER_LABELS.get(step_layer, step_layer)
            if current_layer is not None:
                lines.append("")  # blank line between layers
            lines.append(f"**{layer_label}**")
            lines.append("")
            current_layer = step_layer

        lines.append("---")

        # Special handling for graph_test phase
        if phase_key == "graph_test":
            acl_step = phase_items[0]
            acl_exp = acl_step["expected"]
            lines.append(f"### Phase {phase_num}: {phase_label}（~5 分钟）")
            lines.append(f"- 配置: `{acl_step['param']['config_desc']}` + TP{primary_tp}")
            lines.append("- gpu-mem-util: 0.5（graph capture 需要）")
            lines.append("- benchmark_stage: `explore_{phase_num}_aclgraph`")
            lines.append("- 退出条件: bench 成功 或 serve 崩溃（标记为不兼容，后续用 eager）")
            eff = effectiveness.get("aclgraph", {})
            if eff:
                lines.append(f"- **历史参考**: 同类模型平均提升 {acl_exp}（{eff.get('success_count', 0)} 个验证）")
            lines.append("- **决策点**: 如果提升 > +50%，AclGraph 是主力 → env 阶段用 TASK_QUEUE_ENABLE=1")
            lines.append("- **决策点**: 如果崩溃或提升 < +10%，标记不兼容 → env 阶段用 TASK_QUEUE_ENABLE=2")
            lines.append("")
            phase_num += 1
            continue

        # Standard phases: render as table
        est_time = len(phase_items) * 3
        lines.append(f"### Phase {phase_num}: {phase_label}（~{est_time} 分钟）")

        if phase_key == "env":
            lines.append("")
            lines.append("**根据兼容性测试结果选择 TASK_QUEUE 值**:")
            lines.append("- AclGraph 成功 → TASK_QUEUE_ENABLE=1（图模式）")
            lines.append("- AclGraph 失败/未使用 → TASK_QUEUE_ENABLE=2（eager 模式）")

        lines.append("")
        lines.append("| 步骤 | 配置 | benchmark_stage | 预期边际增益 | 备注 |")
        lines.append("|------|------|----------------|-------------|------|")

        sub_label = "abcdefghijklmnopqrstuvwxyz"
        for i, item in enumerate(phase_items):
            p = item["param"]
            step_id = f"{phase_num}{sub_label[i]}"
            stage = f"explore_{step_id}_{p['id']}"
            notes = p.get("notes", "")[:50]
            lines.append(f"| {step_id} | {p['name']} | `{stage}` | {item['expected']} | {notes} |")

        # Phase-specific footers
        if phase_key == "env":
            lines.append("")
            lines.append("**早停规则**: 如果某步边际增益 < +2%，可以跳过后续 env var 步骤。")
        elif phase_key == "engine":
            lines.append("")
            lines.append("**OOM 处理**: 如果某步 OOM，回退到上一步的参数值并记录。")
            lines.append("**gpu-mem 规则**:")
            lines.append("- AclGraph 模式 + TP1: 必须 ≤ 0.5（graph capture 内存）")
            lines.append("- AclGraph 模式 + TP2: 可用 0.85")
            lines.append("- MoE 模型: 可能需要更保守（如 0.7）")
            lines.append("- Eager 模式: 通常 0.85 安全")
        elif phase_key == "additional":
            lines.append("")
            lines.append("**注意**: additional-config 以 JSON 传入，可与其他参数共存。")
        elif phase_key == "comm":
            lines.append("")
            lines.append("**注意**: 这些参数影响跨卡通信，仅 TP>=2 时有意义。")
        elif phase_key == "moe":
            lines.append("")
            lines.append("**注意**: MoE 专用参数，仅在 MoE 模型上测试。")
        elif phase_key == "stability":
            lines.append("")
            lines.append("**稳定性标准**: 3 次 bench 的 output_tok_per_s 波动 < ±5%。")

        lines.append("")
        phase_num += 1

    # ── TP Sweep ──
    if len(tp_configs) > 1:
        lines.append("---")
        lines.append(f"### Phase {phase_num}: TP 扩展扫描（~{len(tp_configs) * 5} 分钟）")
        lines.append("")
        lines.append("使用上方确定的最优策略组合，在不同 TP 下测试:")
        lines.append("")
        lines.append("| 步骤 | 配置 | benchmark_stage |")
        lines.append("|------|------|----------------|")
        for tp in tp_configs:
            lines.append(f"| {phase_num} TP{tp} | 最优策略 + TP{tp} | `explore_{phase_num}_tp{tp}` |")
        lines.append("")
        lines.append("**注意**: 如果 TP 扩展后吞吐反而下降（通信开销 > 计算收益），记录为「TP 无益」。")
        lines.append("")
        phase_num += 1

    # ── Final Validation ──
    lines.append("---")
    lines.append(f"### Phase {phase_num}: 最终验证（~10 分钟）")
    lines.append("")
    lines.append("1. 选出全局最优配置（TP + 策略组合）")
    lines.append("2. 用标准 bench 参数跑 3 次验证稳定性")
    lines.append("3. 计算最终提升: (最优 / baseline - 1) × 100%")
    lines.append("4. 与 A100 基准对比（查 `/mnt/model/ehein/a100-vllm-bench-data.txt`）")
    lines.append("5. 更新 DB: benchmark_stage=`optimized_final`，记录完整 config JSON + 各阶段边际增益摘要")
    lines.append("6. 生成优化报告到 `adaptations/{model_id}/benchmarks/optimization_report.md`")
    lines.append("")

    # ── Summary table template ──
    lines.append("---")
    lines.append("### 结果汇总模板")
    lines.append("")
    lines.append("| Phase | 配置 | Output tok/s | 边际增益 | 累计增益 | 备注 |")
    lines.append("|-------|------|-------------|---------|---------|------|")
    lines.append("| 0 Baseline | enforce-eager | | — | — | |")
    # Add dynamic phase rows
    dyn_phase_num = 1
    for phase_key, phase_label in _PHASE_ORDER:
        phase_items = phase_steps.get(phase_key, [])
        if not phase_items:
            continue
        first = phase_items[0]["param"]
        label_short = first["name"][:30]
        lines.append(f"| {dyn_phase_num} {phase_label} | {label_short} | | | |")
        dyn_phase_num += 1
    lines.append(f"| {phase_num} | **最优组合** | | | | |")
    lines.append("")

    # ── Global rules ──
    total_steps = n_total + 1  # +1 for baseline
    est_total = max(total_steps * 3, 60)
    lines.append("---")
    lines.append("### 全局规则")
    lines.append("")
    lines.append(f"1. **总时间预算**: ~{est_total} 分钟（{total_steps} 个实验步骤）。如果超出，优先完成前半部分高优先级步骤。")
    lines.append("2. **每次只改一个变量**: 这是消融实验的核心，禁止一次改多个。")
    lines.append("3. **中间结果必须入库**: 每个阶段 bench 完成后立即通过 board_ops.py 写入 DB。")
    lines.append("4. **OOM 不算失败**: 记录 OOM，回退参数，继续下一阶段。")
    lines.append("5. **bench 工作目录**: 必须先 `cd` 到 `adaptations/{model_id}/benchmarks/` 再执行 bench。")
    lines.append("6. **NPU 清理**: 每次 serve 停止后必须验证 HBM 已释放（`npu-smi info`）。")
    lines.append("7. **不执行适配**: 仅优化，不启动 adapter agent。")
    lines.append("")

    # ── Timeout rules ──
    serve_timeout = SERVE_TIMEOUT.get(size_cat, SERVE_TIMEOUT["unknown"])
    bench_timeout = BENCH_TIMEOUT
    lines.append("---")
    lines.append("### 超时规则")
    lines.append("")
    lines.append(f"每次实验分两个阶段计时，用 `timeout` 命令控制:")
    lines.append(f"- **serve 启动超时**: {serve_timeout} 分钟（模型加载 + graph capture）")
    lines.append(f"- **bench 执行超时**: {bench_timeout} 分钟（固定，所有模型通用）")
    lines.append("")
    lines.append("超时后处理:")
    lines.append("1. 读 serve 的最后 20 行日志，判断是启动失败 / 运行中崩溃 / 卡死")
    lines.append("2. **启动失败**（有 OOM/error 关键字）→ 记录原因到 notes，跳过此配置，继续下一阶段")
    lines.append("3. **卡死**（无输出）→ kill 进程、清 NPU、重试一次；再超时则跳过")
    lines.append("4. **连续 2 个阶段超时** → 中止流水线，报告环境异常")
    lines.append("")

    return "\n".join(lines)


# ── Strategy suggestion API payload ─────────────────────────────────────────


def build_strategy_suggestion(
    db_path: Path | str,
    model_id: str,
    chip_count: int,
) -> dict[str, Any]:
    """
    Build a strategy suggestion payload for the dashboard UI.

    Returns a dict with dynamically prioritized exploration steps, skip list,
    TP recommendations, and confidence level.
    """
    db_path = Path(db_path).resolve()
    profile = _classify_model(db_path, model_id)
    patterns = _query_optimization_patterns(db_path, model_id, profile, chip_count)

    # Build dynamic steps
    steps, skipped = _build_exploration_steps(profile, patterns, chip_count)

    # Convert steps to API-friendly format
    exploration_steps = []
    for s in steps:
        exploration_steps.append({
            "id": s["param"]["id"],
            "name": s["param"]["name"],
            "layer": s["param"].get("layer", "parameter"),
            "phase": s["param"]["phase"],
            "phase_label": dict(_PHASE_ORDER).get(s["param"]["phase"], s["param"]["phase"]),
            "priority_score": s["score"],
            "expected": s["expected"],
            "risk": s["param"].get("risk", "low"),
            "config_desc": s["param"].get("config_desc", ""),
        })

    skipped_params = []
    for s in skipped:
        skipped_params.append({
            "id": s["id"],
            "name": s["name"],
            "reason": s["reason"],
        })

    # Informational notes
    notes_list: list[str] = []
    has_aclgraph_failure = any(f["strategy"] == "aclgraph" for f in patterns.get("known_failures", []))
    if has_aclgraph_failure:
        for f in patterns.get("known_failures", [])[:2]:
            notes_list.append(f"同类模型 {f.get('model_id', '?')} AclGraph 未生效")

    # TP recommendations
    tp_rec = patterns.get("tp_recommendations", {})
    recommended_tp = [tp_rec.get("primary", 1)] + tp_rec.get("secondary", [])

    # Similar models
    similar_ids = list(dict.fromkeys(s["model_id"] for s in patterns.get("similar_models", [])))[:5]

    return {
        "model_id": model_id,
        "profile": {
            "family": profile.get("family"),
            "size_b": profile.get("size_b"),
            "size_category": profile.get("size_category"),
            "is_moe": profile.get("is_moe"),
            "is_vlm": profile.get("is_vlm"),
            "aclgraph_compatible": profile.get("aclgraph_compatible"),
        },
        "already_optimized": patterns.get("already_optimized", False),
        "best_existing": patterns.get("best_existing"),
        "exploration_steps": exploration_steps,
        "skipped_params": skipped_params,
        "total_steps": len(exploration_steps),
        "caution_notes": notes_list,
        "recommended_tp": recommended_tp,
        "confidence": patterns.get("confidence", "low"),
        "similar_models": similar_ids,
    }
