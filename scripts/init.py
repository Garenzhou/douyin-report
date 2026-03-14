#!/usr/bin/env python3
"""
初始化脚本
"""

import os
import shutil
from pathlib import Path

# 切换到技能根目录
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent.resolve()
os.chdir(SKILL_DIR)


def main():
    """初始化配置"""
    config_dir = SKILL_DIR / "config"

    # 复制配置模板
    config_example = config_dir / "config.yaml.example"
    config_file = config_dir / "config.yaml"

    if not config_file.exists() and config_example.exists():
        shutil.copy(config_example, config_file)
        print(f"[完成] 已创建配置文件: {config_file}")
    else:
        print(f"[跳过] 配置文件已存在: {config_file}")

    # 复制主播列表模板
    streamers_example = config_dir / "streamers.json.example"
    streamers_file = config_dir / "streamers.json"

    if not streamers_file.exists() and streamers_example.exists():
        shutil.copy(streamers_example, streamers_file)
        print(f"[完成] 已创建主播列表: {streamers_file}")
    else:
        print(f"[跳过] 主播列表已存在: {streamers_file}")

    print()
    print("下一步:")
    print(f"1. 编辑配置文件: {config_file}")
    print("   - 填入 Cookie（必需）")
    print("   - 可选: 配置 transcript.api_key（语音转文字需要）")
    print()
    print(f"2. 编辑主播列表: {streamers_file}")
    print("   - 添加要跟踪的主播链接")
    print()
    print("3. 初始化数据库:")
    print("   python scripts/main.py --help")


if __name__ == "__main__":
    main()
