#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成报告（不含下载和转录）

功能：
1. 扫描本地视频文件
2. 生成汇总报告

用法：
    python scripts/run.py                 # 生成所有视频的报告
    python scripts/run.py --streamer uid  # 只生成指定主播的报告
"""

import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent.resolve()
sys.path.insert(0, str(SKILL_DIR))
os.chdir(SKILL_DIR)

from utils.config import get_report_config
from utils import database
from utils.report import ReportGenerator


def parse_args():
    """解析命令行参数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='生成抖音内容汇总报告')
    parser.add_argument('--streamer', type=str, default=None, help='只处理指定主播（UID 或昵称）')
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    print("=" * 70)
    print("抖音内容汇总报告生成器")
    print("=" * 70)
    print()
    
    # 初始化数据库
    print("[初始化] 数据库...")
    database.init_database()
    
    # 获取视频列表
    if args.streamer:
        # 按主播筛选
        videos = database.get_videos_by_streamer(args.streamer)
        if not videos:
            # 尝试按昵称查找
            all_streamers = database.get_all_streamers()
            for s in all_streamers:
                if args.streamer in (s.get('nickname', ''), s.get('uid', '')):
                    videos = database.get_videos_by_streamer(s.get('uid'))
                    break
        
        print(f"[主播] {args.streamer}: {len(videos)} 个视频")
    else:
        videos = database.get_all_videos()
        print(f"[视频] 共 {len(videos)} 个视频")
    
    if not videos:
        print("[警告] 没有视频数据")
        return
    
    print()
    
    # 为每个视频附加转录文本
    for video in videos:
        aweme_id = video['aweme_id']
        transcript = database.get_transcript(aweme_id)
        if transcript:
            video['transcript_text'] = transcript['text']
        else:
            video['transcript_text'] = ''
    
    # 获取报告配置
    report_config = get_report_config()
    formats = [report_config.get("format", "markdown")]
    
    # 生成报告
    print("[生成] 报告...")
    print()
    
    for fmt in formats:
        try:
            print(f"  [{fmt.upper()}]", end=" ")
            generator = ReportGenerator(format=fmt, config=report_config)
            
            if args.streamer:
                title = f"抖音内容汇总报告 - {args.streamer}"
                report_type = args.streamer
            else:
                title = f"抖音内容汇总报告 - {Path.home().name}"
                report_type = "汇总"
            
            report_path = generator.generate(videos, title, report_type)
            print(f"OK: {report_path.name}")
        except Exception as e:
            print(f"失败: {e}")
    
    # 显示统计信息
    print()
    print("=" * 70)
    print("统计摘要")
    print("=" * 70)
    
    if args.streamer:
        stats = database.get_streamer_stats(args.streamer)
        print(f"  视频数: {stats['video_count']}")
        print(f"  总点赞: {stats['total_likes']:,}")
        print(f"  总评论: {stats['total_comments']:,}")
    else:
        stats = database.get_stats()
        print(f"  主播数: {stats['streamer_count']}")
        print(f"  视频总数: {stats['total_videos']}")
        print(f"  有本地文件: {stats['with_local_file']}")
        print(f"  有转录: {stats['with_transcript']}")
        print(f"  总大小: {stats['total_size_mb']} MB")
    
    print()
    print("=" * 70)
    print("完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()