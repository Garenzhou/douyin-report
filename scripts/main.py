#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音内容汇总 - 主脚本
功能：
1. 下载主播视频（增量下载）
2. 语音转文字
3. 生成汇总报告

用法：
    python main.py                      # 下载并生成所有配置主播的报告
    python main.py --streamer "主播名"   # 只处理指定主播
    python main.py --download-only       # 只下载，不生成报告
    python main.py --report-only         # 只生成报告，不下载
"""

import sys
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent.resolve()
sys.path.insert(0, str(SKILL_DIR))
os.chdir(SKILL_DIR)

import os

from utils.config import (
    load_config,
    get_cookie,
    get_videos_path,
)
from utils.database import (
    init_database,
    get_streamers,
    get_streamer_by_url,
    save_streamer,
    get_videos_by_streamer,
    get_all_videos,
    save_video_metadata,
    scan_and_sync_videos,
    get_stats,
    get_transcript,
    save_transcript,
)
from utils.downloader import download_streamer_videos
from utils.transcript import TranscriptExtractor
from utils.report import ReportGenerator


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="抖音内容汇总生成器")
    parser.add_argument(
        "--streamer", "-s",
        type=str,
        help="只处理指定主播（使用配置文件中的 name）"
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="只下载视频，不生成报告"
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="只生成报告，不下载视频"
    )
    parser.add_argument(
        "--max-counts", "-n",
        type=int,
        default=10,
        help="每个主播最多下载视频数（默认10）"
    )
    return parser.parse_args()


def check_config():
    """检查配置完整性"""
    config = load_config()
    
    # 检查 Cookie
    cookie = get_cookie()
    if not cookie:
        print("[警告] Cookie 未配置，将无法下载视频")
        print("       请在 config/config.yaml 中填写 cookie 字段")
    
    return config


def download_all_streamers(config, max_counts=10):
    """下载所有配置的主播视频"""
    streamers = config.get("streamers", [])
    
    if not streamers:
        print("[警告] 未配置任何主播，请在 config/config.yaml 中添加 streamers 列表")
        print("       格式：")
        print("       streamers:")
        print("         - url: 'https://www.douyin.com/user/...'")
        print("           name: '主播昵称'  # 可选")
        return []
    
    downloaded_streamers = []
    
    for streamer in streamers:
        url = streamer.get("url", "")
        name = streamer.get("name", "")  # 可选，不填则自动获取
        
        if not url:
            print(f"[跳过] 主播配置缺少 URL: {streamer}")
            continue
        
        print(f"\n{'='*60}")
        print(f"开始下载: {name or url}")
        print(f"{'='*60}")
        
        try:
            result = download_streamer_videos(url, name, max_counts)
            
            if result.get("success"):
                print(f"[成功] 下载完成: {result.get('downloaded', 0)} 个视频")
                downloaded_streamers.append(result.get("streamer_info", {}))
            else:
                print(f"[失败] 下载失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            print(f"[错误] 下载异常: {e}")
    
    return downloaded_streamers


def transcribe_videos(config):
    """转录未转录的视频"""
    transcript_config = config.get("transcript", {})
    enable_transcript = transcript_config.get("enabled", False)
    
    if not enable_transcript:
        print("[信息] 转录功能未启用")
        return
    
    # 检查 API Key
    api_key = transcript_config.get("api_key", "")
    if not api_key:
        api_key = os.environ.get("API_KEY", "")
    
    if not api_key:
        print("[警告] 未配置 API Key，无法进行转录")
        print("       请在 config/config.yaml 的 transcript.api_key 中填写")
        return
    
    try:
        extractor = TranscriptExtractor(
            api_key=api_key,
            api_base_url=transcript_config.get("api_base_url", "https://api.siliconflow.cn/v1"),
            model=transcript_config.get("model", "FunAudioLLM/SenseVoiceSmall")
        )
    except ValueError as e:
        print(f"[错误] 转录器初始化失败: {e}")
        return
    
    # 获取未转录的视频
    all_videos = get_all_videos()
    videos_without_transcript = [v for v in all_videos if not v.get("has_transcript")]
    
    if not videos_without_transcript:
        print("[信息] 所有视频已有转录文本")
        return
    
    print(f"\n[转录] 开始转录 {len(videos_without_transcript)} 个视频...")
    
    for video in videos_without_transcript:
        aweme_id = video.get("aweme_id")
        local_path = video.get("local_path")
        
        if not local_path or not Path(local_path).exists():
            print(f"  [跳过] 视频文件不存在: {local_path}")
            continue
        
        print(f"  [转录] {aweme_id}...")
        
        try:
            result = extractor.extract(local_path)
            
            if result.get("success"):
                text = result.get("text", "")
                save_transcript(aweme_id, text, extractor.model)
                print(f"         转录成功 ({len(text)} 字符)")
            else:
                print(f"         转录失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            print(f"         转录异常: {e}")


def generate_reports(config):
    """生成汇总报告"""
    report_config = config.get("report", {})
    formats = report_config.get("format", "markdown")
    
    # 获取所有视频
    all_videos = get_all_videos()
    
    if not all_videos:
        print("[警告] 没有视频数据可生成报告")
        return
    
    # 为每个视频附加转录文本
    for video in all_videos:
        aweme_id = video.get("aweme_id")
        transcript = get_transcript(aweme_id)
        if transcript:
            video["transcript_text"] = transcript.get("text", "")
        else:
            video["transcript_text"] = ""
    
    print(f"\n[报告] 生成 {len(all_videos)} 个视频的报告...")
    
    # 生成报告
    generator = ReportGenerator(format=formats, config=report_config)
    
    # 按主播分组
    videos_by_streamer = {}
    for video in all_videos:
        streamer_name = video.get("streamer_name", "未知主播")
        if streamer_name not in videos_by_streamer:
            videos_by_streamer[streamer_name] = []
        videos_by_streamer[streamer_name].append(video)
    
    # 生成汇总报告
    output_path = generator.generate(
        all_videos,
        title="抖音内容汇总报告",
        report_type="汇总"
    )
    
    # 按主播分别生成报告
    for streamer_name, videos in videos_by_streamer.items():
        output_path = generator.generate(
            videos,
            title=f"{streamer_name} 内容汇总",
            report_type=streamer_name
        )
    
    print(f"[完成] 报告已生成")


def main():
    """主函数"""
    print("=" * 70)
    print("抖音内容汇总生成器")
    print("=" * 70)
    print()
    
    # 解析参数
    args = parse_args()
    
    # 检查配置
    config = check_config()
    
    # 初始化数据库
    print("[1/3] 初始化数据库...")
    init_database()
    print("  ✓ 数据库初始化完成")
    print()
    
    # 下载视频
    if not args.report_only:
        print("[2/3] 下载视频...")
        
        if args.streamer:
            # 只下载指定主播
            streamers = config.get("streamers", [])
            target = next((s for s in streamers if s.get("name") == args.streamer), None)
            
            if not target:
                print(f"[错误] 未找到主播: {args.streamer}")
                return
            
            result = download_streamer_videos(
                target.get("url"),
                target.get("name", ""),
                args.max_counts
            )
            
            if result.get("success"):
                print(f"  ✓ 下载完成: {result.get('downloaded', 0)} 个视频")
            else:
                print(f"  ✗ 下载失败: {result.get('error', '未知错误')}")
        else:
            # 下载所有主播
            download_all_streamers(config, args.max_counts)
        
        print()
    
    # 转录
    if not args.download_only:
        print("[3/4] 语音转录...")
        transcribe_videos(config)
        print()
    
    # 生成报告
    if not args.download_only:
        print("[4/4] 生成报告...")
        generate_reports(config)
        print()
    
    # 统计信息
    stats = get_stats()
    print("=" * 70)
    print("统计信息")
    print("=" * 70)
    print(f"  总视频数: {stats.get('total_videos', 0)}")
    print(f"  已转录: {stats.get('with_transcript', 0)}")
    print(f"  未转录: {stats.get('without_transcript', 0)}")
    print(f"  主播数: {stats.get('streamer_count', 0)}")
    print()


if __name__ == "__main__":
    main()