#  NanoJev 的 MCP
简体中文|[English](README.md)

[NanoJev](https://github.com/TianyuCodings/NanoJev) 的决策服务包装成 MCP 服务器，让 Claude Code、ccwitch、Cline、Cursor 等任何支持 MCP 的 agent 用自然语言直接调NanoJev模型。

```
agent ──stdio(MCP)──> mcp_nanojev.py ──HTTP──> NanoJev 仓库的 serve_decisions.py :8765（模型只加载一次）
```

MCP 进程是薄代理，不加载模型；多个 agent 可同时共享同一个推理服务。

## 前提：安装 NanoJev

```bash
git clone https://github.com/TianyuCodings/NanoJev.git
cd NanoJev
python -m pip install -r requirements-toy.txt huggingface_hub
```

下载 checkpoint（约 2.3 GB，详见 NanoJev README）：

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="C-Tianyu/NanoJev",
    revision="unified-games-v1",
    local_dir="checkpoints/NanoJev-unified",
    allow_patterns=["best.safetensors", "config.json", "tokenizer/*", "backbone_config/*"],
)
```

## 接入

**1. 下载本包**（clone / 解压到任意目录，如 `D:\nanojev_mcp`）

**2. 一键配置**

```bash
python setup_mcp.py
```

脚本会：安装 `mcp` SDK → 探测推理服务 → 把 `nanojev` 注册进 Claude Code（user 级）→ 打印其他客户端 JSON。常用选项：

```bash
python setup_mcp.py --service-url http://127.0.0.1:9000/api/evaluate   # 服务不在默认端口
python setup_mcp.py --python D:\NanoJev\.venv\Scripts\python.exe       # 借用 NanoJev 的 venv
python setup_mcp.py --skip-claude                                      # 只打印 JSON，不改 claude 配置
```

**3. 启动 NanoJev 推理服务**（在 NanoJev 仓库目录）

```bash
python scripts/serve_decisions.py --checkpoint-dir checkpoints/NanoJev-unified --web-root web --port 8765 --disable-native-triton   
```

完成。在 agent 里用自然语言下达即可，例如：

> 用 nanojev 判断：agent 在 (2,2)，北边一格能不能走？四个方向里哪步最优？

### 启动NanoJev MCP

本MCP通过stdio接入本地NanoJev

```bash
python mcp_nanojev.py                    # 默认服务地址 http://127.0.0.1:8765/api/evaluate
```

自定义服务地址时用环境变量 `NANOJEV_EVALUATE_URL`：

```bash
# Linux / macOS
NANOJEV_EVALUATE_URL=http://127.0.0.1:9000/api/evaluate python mcp_nanojev.py
# Windows PowerShell
$env:NANOJEV_EVALUATE_URL = "http://127.0.0.1:9000/api/evaluate"; python mcp_nanojev.py
```

agent 会把它作为子进程拉起，通过 stdin/stdout 通信；手动单独运行时终端里只有 JSON-RPC 报文，Ctrl+C 退出。

## Agent 能看到的工具

| 工具 | 输入 | 输出 |
|---|---|---|
| `nanojev_evaluate` | `state`（观察文本）+ `questions`（boolean / choice / score 列表） | 每题概率分布、argmax 结论、推理耗时 |
| `nanojev_health` | — | 推理服务是否就绪 |

## Agent 在决策回路的四个环节使用模型

1. **可行性闸门（Boolean）** — 移动前逐方向询问"向北一格是否可通行"，先剪掉非法动作。
2. **动作选择（Choice）** — 在候选动作里选下一步，2–255 个候选项一次前向返回完整分布。
3. **风险/紧急度（Score）** — 询问"这一步必须转向的紧急程度"（0–3），对期望分设阈值即可变成规则。
4. **前瞻规划（Boolean + Choice）** — 把候选动作序列推演出的未来状态**批量**发进一次 `nanojev_evaluate`，比较各分支得分后再落子。

更多示例与故障排查见 [docs/MCP.md](docs/MCP.md)。不用 agent 时，也可以用终端交互客户端：

```bash
python ask_nanojev.py
```

## Quick start (English)

1. Install NanoJev from the [official repo](https://github.com/TianyuCodings/NanoJev) and download the checkpoint (see its README).
2. Download this folder, then run `python setup_mcp.py` — it installs the `mcp` SDK, registers `nanojev` into Claude Code (user scope) and prints stdio JSON for any other MCP client.
3. Start `serve_decisions.py` in the NanoJev repo, then ask your agent naturally.
