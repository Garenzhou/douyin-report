#!/usr/bin/env python3
"""
依赖安装脚本
"""

import subprocess
import sys
from pathlib import Path


def main():
    """安装依赖"""
    skill_dir = Path(__file__).parent.parent.resolve()
    requirements = skill_dir / "requirements.txt"

    print("=" * 60)
    print("Douyin Report - 依赖安装")
    print("=" * 60)
    print()

    if requirements.exists():
        print(f"从 {requirements.name} 安装...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
            capture_output,
            text=True
        )
        if result.returncode == 0:
            print("  ✓ 安装成功")
        else:
            print(f"  ✗ 安装失败: {result.stderr}")
    else:
        print("安装 Python 依赖...")
        deps = ["f2", "pyyaml", "requests", "openai", "ffmpeg-python"]
        for dep in deps:
            print(f"  安装 {dep}...", end=" ")
            if subprocess.run([sys.executable, "-m", "pip", "install", dep]).returncode == 0:
                print("✓")
            else:
                print("✗")

    print()
    print("=" * 60)
    print("下一步:")
    print("1. 编辑 config/config.yaml，填入 Cookie（必需）")
    print("2. 运行: python scripts/streamers.py add \"主播URL\"")
    print("3. 运行: python scripts/run_full.py")
    print("=" * 60)


if __name__ == "__main__":
    main()