#!/usr/bin/env python3
"""NanoJev MCP 服务器：把 NanoJev 推理服务的 /api/evaluate 接口暴露为 MCP 工具。

本进程是薄代理，不加载模型；模型由 NanoJev 仓库的 serve_decisions.py 进程持有。
使用前先安装 NanoJev 并启动推理服务：
    python scripts/serve_decisions.py --checkpoint-dir checkpoints/NanoJev-unified \
        --web-root web --port 8765 --disable-native-triton

注册到 agent（stdio 传输，mcp>=2 的 API）：
    claude mcp add nanojev --scope user -- <python> <本文件路径>

服务地址可用环境变量 NANOJEV_EVALUATE_URL 覆盖（默认 http://127.0.0.1:8765/api/evaluate）。
"""
import json
import os
import sys
import urllib.error
import urllib.request

from pydantic import Field

from mcp.server.mcpserver import MCPServer

EVALUATE_URL = os.environ.get("NANOJEV_EVALUATE_URL", "http://127.0.0.1:8765/api/evaluate")

EVALUATE_DOC = """向 NanoJev 世界模型（Qwen3-0.6B 决策模型）提问，获取概率化决策判断。

三种题型（questions 每项的 type 字段）：
- boolean：判断命题真伪。criteria 可省略，或 {"true": "判真标准", "false": "判假标准"}。返回 p_true（为真概率）。
- choice：从候选动作中选一个。criteria 必填：{"动作名": "候选描述", ...}（2-255 项）。返回选择和完整概率分布。
- score：给状态打等级分。criteria 必填：["等级0描述", "等级1描述", ...]（2-10 项，顺序即等级从低到高）。返回期望分和 argmax 等级。

questions 示例：
[{"id": "clear_north", "type": "boolean", "instructions": "If the agent attempts one cell north, will it be inside the maze and not a wall?"},
 {"id": "best_move", "type": "choice", "instructions": "Which single move should the agent take next?",
  "criteria": {"north": "Move north.", "south": "Move south.", "east": "Move east.", "west": "Move west."}}]

返回格式化文本：每题的概率分布、argmax 结论和推理耗时。"""

server = MCPServer(
    "nanojev",
    version="1.0.0",
    instructions=(
        "NanoJev：基于 Qwen3-0.6B 的游戏决策世界模型。把环境观察写成文本（或 JSON 字符串），"
        "用 boolean/choice/score 三种题型向它提问，返回概率化答案。"
        "适用于迷宫、贪吃蛇等网格类游戏的状态评估。"
    ),
)


def _http_evaluate(payload: dict) -> dict:
    request = urllib.request.Request(
        EVALUATE_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"推理服务返回 {error.code}：{detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"无法连接 {EVALUATE_URL}（推理服务未启动？请先在 NanoJev 仓库运行 serve_decisions.py）：{error.reason}"
        ) from error


def _format_result(result: dict) -> str:
    execution = result.get("execution", {})
    lines = [
        f"device={execution.get('device')} precision={execution.get('precision')} "
        f"forward_passes={execution.get('forward_passes')} "
        f"耗时 {execution.get('server_evaluation_seconds', 0):.2f}s"
    ]
    for state in result.get("states", []):
        lines.append(f"[state {state['id']}]")
        for question_id, answer in state["answers"].items():
            probabilities = " | ".join(
                f"{key}: {value:.4f}" for key, value in answer["probabilities"].items()
            )
            if answer["type"] == "boolean":
                verdict = "true" if answer["value"] else "false"
                lines.append(f"  {question_id} (boolean)：p_true={answer['p_true']:.4f} → {verdict}")
            elif answer["type"] == "choice":
                ranked = sorted(answer["probabilities"].items(), key=lambda item: -item[1])
                ranked_text = " | ".join(f"{key}: {value:.4f}" for key, value in ranked)
                lines.append(f"  {question_id} (choice)：选择 {answer['choice']}；排名：{ranked_text}")
            else:
                lines.append(
                    f"  {question_id} (score)：期望 {answer['score']:.4f}，argmax 等级 {answer['level']}"
                )
            lines.append(f"    概率：{probabilities}")
    return "\n".join(lines)


@server.tool(description=EVALUATE_DOC)
def nanojev_evaluate(
    state: str = Field(description="环境观察文本，建议与游戏训练数据同风格，例如：'Agent at (2,2) on a 5x5 maze. Local 5x5 window:\\n# # # # #\\n# . . . #\\n# . A . #\\n...'"),
    questions: list[dict] = Field(description="问题列表，每项含 id/type/instructions/criteria，详见工具说明。"),
) -> str:
    if not state.strip():
        raise ValueError("state 不能为空")
    if not questions:
        raise ValueError("questions 不能为空")
    questions_map = {}
    for question in questions:
        entry = dict(question)
        question_id = entry.pop("id", "")
        if not isinstance(question_id, str) or not question_id.strip():
            raise ValueError("每个问题都必须有非空的字符串 id 字段")
        entry.setdefault("type", "boolean")
        questions_map[question_id] = entry
    payload = {
        "states": [{"id": "mcp_state", "state": state, "questions": questions_map}]
    }
    return _format_result(_http_evaluate(payload))


@server.tool(description="检查 NanoJev 推理服务是否就绪。")
def nanojev_health() -> str:
    try:
        with urllib.request.urlopen(
            EVALUATE_URL.rsplit("/", 1)[0] + "/health", timeout=10
        ) as response:
            data = json.loads(response.read().decode("utf-8"))
        return f"就绪：{json.dumps(data, ensure_ascii=False)}"
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as error:
        return f"不可用：{error}（请先在 NanoJev 仓库启动 serve_decisions.py）"


if __name__ == "__main__":
    # Windows 上 stdio 默认可能是 GBK，强制 UTF-8 保证 JSON-RPC 中文不乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")
    server.run()
