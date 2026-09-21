# nanojev_mcp 集成指南

本包把 NanoJev 的 `/api/evaluate` 决策接口暴露为 MCP 工具。安装与快速开始见 [README](../README.md)，本页记录工具细节、agent 决策环节与故障排查。

## 架构

```
agent ──stdio(MCP)──> mcp_nanojev.py（本包，薄代理）──HTTP──> serve_decisions.py :8765（模型只加载一次）
```

- MCP 进程不加载模型，启动即用；模型常驻在 NanoJev 仓库的推理服务里。
- 多个 agent / 多个 MCP 客户端可同时连同一个服务。
- 服务地址默认 `http://127.0.0.1:8765/api/evaluate`，可用环境变量 `NANOJEV_EVALUATE_URL` 覆盖。

## 工具契约

### `nanojev_evaluate`

| 参数 | 类型 | 说明 |
|---|---|---|
| `state` | string | 环境观察文本，建议与游戏训练数据同风格（自然语言或 JSON 字符串） |
| `questions` | list[dict] | 每项含 `id`（非空字符串）、`type`、`instructions`（非空）、`criteria` |

三种题型的 `criteria`：

- **boolean** — 可省略，或 `{"true": "判真标准", "false": "判假标准"}`。返回 `p_true` 与真伪结论。
- **choice** — 必填 `{"动作名": "候选描述", ...}`，2–255 项。返回 argmax 选择与完整概率排名。
- **score** — 必填 `["等级0描述", "等级1描述", ...]`，2–10 项、顺序即等级从低到高。返回期望分与 argmax 等级。

返回文本示例：

```
device=cuda:0 precision=bf16 forward_passes=1 耗时 0.13s
[state mcp_state]
  clear_north (boolean)：p_true=0.5950 → true
    概率：false: 0.4050 | true: 0.5950
  best_move (choice)：选择 north；排名：north: 0.3122 | west: 0.2489 | ...
```

### `nanojev_health`

无参数，返回推理服务就绪状态。

## Agent 决策回路的四个环节

这四个环节对应 NanoJev 四个游戏任务（Maze / Snake / ViZDoom Basic / Predict Position）的控制循环，接入任意 LLM agent 时同样适用：

1. **可行性闸门（Boolean）** — 移动前逐方向询问"向北一格是否在迷宫内且非墙"（`results/composed_games_api.json` 里的 `clear_north` 模板）。agent 用它把非法动作从候选集剪掉。
2. **动作选择（Choice）** — 候选集确定后询问"下一步走哪个"。一次前向返回全部候选的分布，agent 取 argmax 或按概率采样。
3. **风险/紧急度（Score）** — 询问"必须改变方向的紧急程度"（Snake 用 0–3 分级），对期望分设阈值即可规则化：`> 2 → 立即转向`。
4. **前瞻规划（Boolean + Choice）** — 把候选动作序列推演出的未来状态批量编码，一次 `nanojev_evaluate` 问完所有分支，比较得分后再执行。模型的并行批处理正是为此设计。

一个典型 agent 提示：

> 蛇身 [[3,3],[3,4],[3,5]]，方向 east，食物 [3,0]。用 nanojev 查哪些方向可走，选出下一步，并告诉我转向紧急度。

## 手动调用（不开 agent）

```bash
python ask_nanojev.py [服务地址]
```

按提示录入 state 与问题，自动发送并格式化打印结果。

## 故障排查

- **工具调用报连接错误** — 推理服务没启动；先在 NanoJev 仓库运行 `serve_decisions.py`（`nanojev_health` 也会提示）。
- **`claude mcp list` 显示未连接** — 检查注册的 command 是否指向装有 `mcp` 包的解释器（重跑 `setup_mcp.py` 可覆盖旧注册）。
- **请求被拒（400）** — 服务端校验严格：≤ 32 states、≤ 96 questions、字段非空、choice 需 2–255 项 criteria、score 需 2–10 项；错误信息会指明具体规则，MCP 工具会原样透出。
- **浏览器页面跨域被拒** — 这是服务端有意限制；只有同源页面和服务器端客户端（包括本 MCP 服务器）可以调用。
- **中文乱码** — 本包在 Windows 上已强制 stdio 使用 UTF-8；若自定义客户端出现乱码，检查其读写编码。
