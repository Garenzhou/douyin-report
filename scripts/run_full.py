#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整工作流程：下载视频 + 语音转录 + 生成报告

功能：
1. 下载所有配置中主播的最新视频（增量模式）
2. 对没有转录的视频进行语音转录
3. 生成汇总报告

用法：
    python scripts/run_full.py                 # 下载所有主播视频并生成报告
    python scripts/run_full.py --max-counts=5  # 限制每个主播最多下载5个视频
    python scripts/run_full.py --streamer "主播URL"  # 只下载单个主播
"""

import sys
import os
import asyncio
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent.resolve()
sys.path.insert(0, str(SKILL_DIR))
os.chdir(SKILL_DIR)

from utils.config import get_report_config, get_transcript_config, load_config
from utils import database
from utils import downloader
from utils.transcript import TranscriptExtractor
from utils.report import ReportGenerator


def parse_args():
    """解析命令行参数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='抖音内容汇总报告生成器')
    parser.add_argument('--max-counts', type=int, default=5, help='每个主播最多下载的视频数')
    parser.add_argument('--streamer', type=str, default=None, help='单个主播的URL')
    parser.add_argument('--no-download', action='store_true', help='跳过下载，只生成报告')
    parser.add_argument('--no-transcript', action='store_true', help='跳过转录')
    
    return parser.parse_args()


async def download_phase(args):
    """下载阶段"""
    print("=" * 70)
    print("阶段 1: 下载视频")
    print("=" * 70)
    print()
    
    # 检查 Cookie
    try:
        from utils.config import get_cookie
        cookie = get_cookie()
        if not cookie:
            print("[错误] Cookie 未配置，请编辑 config/config.yaml")
            return None
    except ValueError as e:
        print(f"[错误] {e}")
        return None

    # 初始化数据库
    print("[初始化] 数据库...")
    database.init_database()
    print()
    
    if args.streamer:
        # 下载单个主播
        print(f"[主播] 下载: {args.streamer}")
        result = await downloader.download_single_streamer(args.streamer, args.max_counts)
    else:
        # 下载所有配置的主播
        result = await downloader.download_all_streamers(args.max_counts)
    
    print()
    print(f"[下载完成] 新增: {result.get('downloaded', 0)}, 跳过: {result.get('skipped', 0)}")
    
    return result


def transcript_phase(enable_transcript: bool):
    """转录阶段"""
    if not enable_transcript:
        print()
        print("=" * 70)
        print("阶段 2: 语音转录 (已跳过)")
        print("=" * 70)
        return
    
    print()
    print("=" * 70)
    print("阶段 2: 语音转录")
    print("=" * 70)
    print()
    
    # 获取转录配置
    transcript_config = get_transcript_config()
    api_key = transcript_config.get("api_key")
    
    if not api_key:
        print("[警告] 未配置 API Key，跳过转录")
        return
    
    # 初始化转录器
    try:
        extractor = TranscriptExtractor(
            api_key=api_key,
            api_base_url=transcript_config.get("api_base_url"),
            model=transcript_config.get("model")
        )
        print("[转录器] 已初始化")
    except ValueError as e:
        print(f"[错误] 转录器初始化失败: {e}")
        return
    
    # 获取没有转录的视频
    videos = database.get_videos_without_transcript()
    
    if not videos:
        print("[信息] 所有视频都已完成转录")
        return
    
    print(f"[信息] 找到 {len(videos)} 个需要转录的视频")
    print()
    
    success_count = 0
    failed_count = 0
    
    for video in videos:
        aweme_id = video['aweme_id']
        local_path = video.get('local_path', '')
        
        if not local_path or not Path(local_path).exists():
            print(f"[跳过] {aweme_id[:15]}... (文件不存在)")
            continue
        
        print(f"[转录] {aweme_id[:15]}...", end=" ", flush=True)
        
        try:
            text = extractor.transcribe(Path(local_path))
            database.save_transcript(aweme_id, text, transcript_config.get("model"))
            print(f"OK ({len(text)}字)")
            success_count += 1
        except Exception as e:
            print(f"失败: {e}")
            failed_count += 1
    
    print()
    print(f"[转录完成] 成功: {success_count}, 失败: {failed_count}")


def report_phase():
    """报告生成阶段"""
    print()
    print("=" * 70)
    print("阶段 3: 生成报告")
    print("=" * 70)
    print()
    
    # 获取所有视频
    all_videos = database.get_all_videos()
    
    if not all_videos:
        print("[警告] 没有视频数据")
        return
    
    print(f"[信息] 共 {len(all_videos)} 个视频")
    
    # 为每个视频附加转录文本
    for video in all_videos:
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
    for fmt in formats:
        try:
            print(f"[生成] {fmt.upper()} 报告...", end=" ", flush=True)
            generator = ReportGenerator(format=fmt, config=report_config)
            report_path = generator.generate(all_videos, "抖音内容汇总报告", "完整")
            print(f"OK: {report_path.name}")
        except Exception as e:
            # 打印出错日志
            import traceback
            traceback.print_exc()
            print(f"失败: {e}")
    
    print()
    
    # 显示统计信息
    print("=" * 70)
    print("统计摘要")
    print("=" * 70)
    
    stats = database.get_stats()
    print(f"  主播数: {stats['streamer_count']}")
    print(f"  视频总数: {stats['total_videos']}")
    print(f"  有本地文件: {stats['with_local_file']}")
    print(f"  有转录: {stats['with_transcript']}")
    print(f"  总大小: {stats['total_size_mb']} MB")
    
    # 按主播统计
    streamers = database.get_all_streamers()
    if streamers:
        print()
        print("主播统计:")
        for streamer in streamers:
            nickname = streamer.get('nickname', '未知')
            s_stats = database.get_streamer_stats(streamer.get('uid'))
            print(f"  - {nickname}: {s_stats['video_count']} 个视频, {s_stats['total_likes']:,} 点赞")


async def main():
    args = parse_args()
    
    print("=" * 70)
    print("抖音内容汇总报告生成器")
    print("=" * 70)
    print()
    
    # 阶段 1: 下载视频
    if not args.no_download:
        result = await download_phase(args)
        if result is None:
            print("\n[终止] 下载阶段失败")
            return
    
    # 阶段 2: 语音转录
    transcript_config = get_transcript_config()
    enable_transcript = transcript_config.get("enabled", False) and not args.no_transcript
    
    # 检查是否有本地文件需要转录
    videos_without_transcript = database.get_videos_without_transcript()
    has_local_files = any(v.get('local_path') for v in videos_without_transcript)
    
    if enable_transcript and has_local_files:
        transcript_phase(enable_transcript)
    else:
        print()
        print("=" * 70)
        print("阶段 2: 语音转录 (跳过)")
        print("=" * 70)
        if not enable_transcript:
            print("  原因: 转录功能未启用")
        elif not has_local_files:
            print("  原因: 没有需要转录的本地文件")
    
    # 阶段 3: 生成报告
    report_phase()
    
    print()
    print("=" * 70)
    print("完成!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())