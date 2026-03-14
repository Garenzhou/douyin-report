#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主播管理脚本

功能：
1. 列出当前跟踪的主播
2. 添加主播
3. 移除主播

用法：
    python scripts/streamers.py list               # 列出所有主播
    python scripts/streamers.py add "URL"          # 添加主播
    python scripts/streamers.py add "URL" "昵称"   # 添加主播（指定昵称）
    python scripts/streamers.py remove "URL"       # 移除主播
    python scripts/streamers.py clear              # 清除所有主播
"""

import sys
import os
import asyncio
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent.resolve()
sys.path.insert(0, str(SKILL_DIR))
os.chdir(SKILL_DIR)

import os
from utils.config import (
    load_config,
    save_config,
    get_streamers_config,
    update_streamers_config,
    add_streamer_config,
    remove_streamer_config,
)
from utils import database


def list_streamers():
    """列出所有主播"""
    print("=" * 60)
    print("当前跟踪的主播")
    print("=" * 60)
    print()
    
    # 从配置文件读取
    config_streamers = get_streamers_config()
    
    # 从数据库读取
    db_streamers = database.get_all_streamers()
    
    if not config_streamers and not db_streamers:
        print("没有配置的主播")
        print()
        print("添加主播:")
        print("  python scripts/streamers.py add \"https://www.douyin.com/user/xxx\"")
        return
    
    # 合并显示
    print(f"{'昵称':<20} {'URL':<40} {'视频数':<8} {'最后抓取':<20}")
    print("-" * 90)
    
    # 创建 URL 到数据库信息的映射
    db_map = {s.get('url', ''): s for s in db_streamers}
    
    for s in config_streamers:
        url = s.get('url', '')
        name = s.get('name', '')
        
        # 从数据库获取更多信息
        db_info = db_map.get(url, {})
        video_count = 0
        last_fetch = ""
        
        if db_info:
            uid = db_info.get('uid')
            if uid:
                stats = database.get_streamer_stats(uid)
                video_count = stats.get('video_count', 0)
            
            fetch_time = db_info.get('last_fetch_time')
            if fetch_time:
                from datetime import datetime
                last_fetch = datetime.fromtimestamp(fetch_time).strftime('%Y-%m-%d %H:%M')
        
        name = name or db_info.get('nickname', '未知')
        url_display = url[:38] + '..' if len(url) > 40 else url
        
        print(f"{name:<20} {url_display:<40} {video_count:<8} {last_fetch:<20}")
    
    print()
    print(f"共 {len(config_streamers)} 个主播")


def add_streamer(url: str, name: str = None):
    """添加主播"""
    if not url:
        print("[错误] 请提供主播的主页 URL")
        return
    
    # 验证 URL 格式
    if 'douyin.com' not in url:
        print("[错误] 请提供正确的抖音主页 URL")
        return
    
    # 检查是否已存在
    streamers = get_streamers_config()
    for s in streamers:
        if s.get('url') == url:
            print(f"[信息] 主播已存在: {s.get('name') or url}")
            return
    
    # 添加主播
    streamer = {"url": url}
    if name:
        streamer["name"] = name
    
    add_streamer_config(streamer)
    print(f"[添加] {name or url}")
    print()
    print("下一步:")
    print(f"  python scripts/run_full.py --streamer \"{url}\"")


def remove_streamer(url: str):
    """移除主播"""
    if not url:
        print("[错误] 请提供主播的 URL")
        return
    
    # 查找主播
    streamers = get_streamers_config()
    found = None
    
    for s in streamers:
        if s.get('url') == url:
            found = s
            break
    
    if not found:
        print(f"[信息] 未找到主播: {url}")
        return
    
    # 移除
    remove_streamer_config(url)
    print(f"[移除] {found.get('name') or url}")
    
    # 询问是否删除本地文件
    print()
    print("注意: 不会删除已下载的视频文件和数据库记录")
    print("如需清理，请手动删除:")
    print(f"  - 下载目录: ~/Downloads/douyin-report/download/")
    print(f"  - 数据库: {SKILL_DIR / 'data.db'}")


def clear_streamers():
    """清除所有主播"""
    print("[确认] 将移除所有主播配置")
    print()
    response = input("继续? (y/N): ")
    
    if response.lower() != 'y':
        print("[取消]")
        return
    
    update_streamers_config([])
    print("[完成] 已清除所有主播配置")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_streamers()
    elif command == "add":
        url = sys.argv[2] if len(sys.argv) > 2 else None
        name = sys.argv[3] if len(sys.argv) > 3 else None
        add_streamer(url, name)
    elif command == "remove":
        url = sys.argv[2] if len(sys.argv) > 2 else None
        remove_streamer(url)
    elif command == "clear":
        clear_streamers()
    else:
        print(f"未知命令: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()