#!/usr/bin/env python3
"""NanoJev 交互式问答客户端：在终端录入 state 和问题，发送到本地 /api/evaluate。

用法：
    .venv\\Scripts\\python.exe scripts\\ask_nanojev.py [服务地址]
    # 服务地址默认 http://127.0.0.1:8765/api/evaluate

录入规则：
    - state 编号回车用默认值；状态文本可多行，空行结束
    - boolean：true/false 标准可选，直接回车跳过
    - choice / score：逐项录入，直接回车结束
"""
import json
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8765/api/evaluate"


def ask(prompt, default=""):
    value = input(prompt).strip()
    return value or default


def ask_required(prompt):
    while True:
        value = ask(prompt)
        if value:
            return value
        print("  不能为空，请重新输入")


def input_boolean():
    question = {"type": "boolean", "instructions": ask_required("  问题指令（完整描述要判断的命题）：")}
    print("  可选：输入判真/判假标准，直接回车跳过")
    criteria = {}
    for key in ("true", "false"):
        text = ask(f"    {key} 标准：")
        if text:
            criteria[key] = text
    if criteria:
        question["criteria"] = criteria
    return question


def input_choice():
    question = {"type": "choice", "instructions": ask_required("  问题指令：")}
    criteria = {}
    print("  输入候选，格式：名称=描述；直接回车结束（至少 2 项，最多 255 项）")
    while True:
        line = input(f"    候选{len(criteria) + 1}：").strip()
        if not line:
            if len(criteria) < 2:
                print("    至少需要 2 个候选")
                continue
            break
        if "=" not in line:
            print("    格式错误，需要 名称=描述")
            continue
        name, description = (part.strip() for part in line.split("=", 1))
        if not name or not description:
            print("    名称和描述都不能为空")
            continue
        criteria[name] = description
    question["criteria"] = criteria
    return question


def input_score():
    question = {"type": "score", "instructions": ask_required("  问题指令：")}
    levels = []
    print("  从低到高逐项输入等级描述，直接回车结束（2-10 项）")
    while True:
        line = input(f"    等级{len(levels)}：").strip()
        if not line:
            if len(levels) < 2:
                print("    至少需要 2 个等级")
                continue
            break
        levels.append(line)
    question["criteria"] = levels
    return question


def input_state(index):
    state_id = ask(f"state #{index + 1} 的编号 [state_{index + 1}]：", f"state_{index + 1}")
    print("输入状态观察文本（可多行，单独一行空行结束）：")
    lines = []
    while True:
        line = input("  > ")
        if not line.strip():
            if lines:
                break
            print("  状态不能为空")
            continue
        lines.append(line)
    questions = {}
    while True:
        question_id = ask_required("问题 ID（如 best_move）：")
        if question_id in questions:
            print("  该 ID 已存在，请换一个")
            continue
        print("题型：1) boolean 布尔判断  2) choice 候选选择  3) score 等级评分")
        picker = {"1": input_boolean, "2": input_choice, "3": input_score}
        questions[question_id] = picker.get(ask("选择 [1-3，默认 1]：", "1"), input_boolean)()
        if ask("继续为该 state 添加问题？(y/N)：", "n").lower() != "y":
            break
    return {"id": state_id, "state": "\n".join(lines), "questions": questions}


def print_results(result):
    execution = result.get("execution", {})
    print(f"\n=== 结果（device={execution.get('device')} precision={execution.get('precision')} "
          f"forward_passes={execution.get('forward_passes')} "
          f"耗时 {execution.get('server_evaluation_seconds', 0):.2f}s）===")
    for state in result.get("states", []):
        print(f"\n[state {state['id']}]")
        for question_id, answer in state["answers"].items():
            probabilities = " | ".join(f"{key}: {value:.4f}"
                                       for key, value in answer["probabilities"].items())
            if answer["type"] == "boolean":
                verdict = "true" if answer["value"] else "false"
                print(f"  {question_id} (boolean)：p_true={answer['p_true']:.4f} → {verdict}")
            elif answer["type"] == "choice":
                ranked = sorted(answer["probabilities"].items(), key=lambda item: -item[1])
                ranked_text = " | ".join(f"{key}: {value:.4f}" for key, value in ranked)
                print(f"  {question_id} (choice)：选择 {answer['choice']}")
                print(f"      排名：{ranked_text}")
            else:
                print(f"  {question_id} (score)：期望 {answer['score']:.4f}，argmax 等级 {answer['level']}")
            print(f"      概率：{probabilities}")


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    print("NanoJev 交互式问答客户端")
    print(f"服务地址：{url}")
    print("请确保推理服务已启动（scripts/serve_decisions.py）\n")
    states = []
    while True:
        states.append(input_state(len(states)))
        if ask("\n添加下一个 state？(y/N)：", "n").lower() != "y":
            break
    payload = {"states": states}
    print("\n请求 JSON：")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    request = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        print(f"服务返回 {error.code}：{error.read().decode('utf-8', 'replace')}")
        raise SystemExit(1)
    except urllib.error.URLError as error:
        print(f"无法连接 {url}：{error.reason}")
        raise SystemExit(1)
    print_results(result)


if __name__ == "__main__":
    main()
