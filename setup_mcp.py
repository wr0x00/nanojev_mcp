#!/usr/bin/env python3
"""nanojev_mcp 一键接入脚本（独立包，与 NanoJev 仓库分离）。

做什么：
  1. 确认本目录的 mcp_nanojev.py 存在
  2. 确认所选 Python 解释器装了 mcp SDK（缺则自动 pip install）
  3. 探测 NanoJev 推理服务是否在运行
  4. 把 nanojev MCP 服务器注册进 Claude Code（user 级）
  5. 打印其他 MCP 客户端（ccwitch / Cline / Cursor 等）可用的 stdio JSON 配置

用法：
  python setup_mcp.py                        # 默认用当前解释器、默认服务地址
  python setup_mcp.py --service-url http://127.0.0.1:9000/api/evaluate
  python setup_mcp.py --python D:\\NanoJev\\.venv\\Scripts\\python.exe   # 指定解释器
  python setup_mcp.py --skip-claude          # 不动 claude 配置，只打印 JSON

前提：先安装 NanoJev 官方仓库并启动推理服务（见 README）。
"""
import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
MCP_SCRIPT = PACKAGE_ROOT / "mcp_nanojev.py"
DEFAULT_SERVICE_URL = "http://127.0.0.1:8765/api/evaluate"


def run(command: list[str]) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(command)}")
    return subprocess.run(command, check=False)


def ensure_mcp_sdk(python_exe: str) -> bool:
    probe = subprocess.run(
        [python_exe, "-c", "import mcp"],
        capture_output=True, check=False,
    )
    if probe.returncode == 0:
        print("[1/4] mcp SDK 已安装")
        return True
    print("[1/4] 安装 mcp SDK ...")
    return run([python_exe, "-m", "pip", "install", "mcp"]).returncode == 0


def check_service(service_url: str) -> None:
    health = service_url.rsplit("/", 1)[0] + "/health"
    try:
        with urllib.request.urlopen(health, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("ready"):
            print(f"[3/4] 推理服务：运行中 ✔（{health}）")
            return
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        pass
    print(f"[3/4] 推理服务：未运行（{health}）。先在 NanoJev 仓库启动，agent 才能真正调到模型：")
    print("  python scripts/serve_decisions.py \\")
    print("    --checkpoint-dir checkpoints/NanoJev-unified \\")
    print("    --web-root web --port 8765 --disable-native-triton")


def register_claude(python_exe: str) -> None:
    claude_exe = shutil.which("claude")
    if claude_exe is None:
        print("[4/4] 未检测到 claude CLI，跳过自动注册（其他客户端用下面的 JSON 即可）")
        return
    print("[4/4] 注册到 Claude Code（user 级）...")
    if run([claude_exe, "mcp", "add", "nanojev", "--scope", "user",
            "--", python_exe, str(MCP_SCRIPT)]).returncode == 0:
        print("      完成：claude mcp list 应显示 nanojev ✔ Connected")


def print_client_config(python_exe: str, service_url: str) -> None:
    entry = {"command": python_exe, "args": [str(MCP_SCRIPT)]}
    if service_url != DEFAULT_SERVICE_URL:
        entry["env"] = {"NANOJEV_EVALUATE_URL": service_url}
    config = {"mcpServers": {"nanojev": entry}}
    print("\n其他 MCP 客户端（ccwitch / Cline / Cursor / Cherry Studio 等）配置：")
    print(json.dumps(config, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--service-url", default=DEFAULT_SERVICE_URL,
                        help=f"NanoJev 推理服务地址（默认 {DEFAULT_SERVICE_URL}）")
    parser.add_argument("--python", default=sys.executable,
                        help="运行 MCP 服务器用的解释器（默认当前解释器；可指向 NanoJev 的 venv）")
    parser.add_argument("--skip-claude", action="store_true", help="跳过 claude mcp add")
    args = parser.parse_args()

    python_exe = str(Path(args.python).resolve())
    if not MCP_SCRIPT.exists():
        raise SystemExit(f"找不到 {MCP_SCRIPT}，请在本目录运行")
    print(f"nanojev_mcp 接入\n  包目录：{PACKAGE_ROOT}\n  解释器：{python_exe}\n")
    if not ensure_mcp_sdk(python_exe):
        raise SystemExit("mcp SDK 安装失败，请手动：pip install mcp")
    check_service(args.service_url)
    if not args.skip_claude:
        register_claude(python_exe)
    print_client_config(python_exe, args.service_url)
    print("\n下一步：在 agent 里直接说『用 nanojev 判断...』即可。详见 README.md / docs/MCP.md")


if __name__ == "__main__":
    main()
