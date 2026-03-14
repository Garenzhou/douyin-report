"""
抖音视频下载模块
使用 F2 框架实现增量下载
"""

import shutil
import sqlite3
import asyncio
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from f2.apps.douyin.handler import DouyinHandler
from f2.apps.douyin.db import AsyncUserDB, AsyncVideoDB
from f2.utils.conf_manager import ConfigManager
import f2

from .config import (
    get_download_path,
    get_db_path,
    get_user_folder_name,
    sanitize_folder_name,
    load_config,
    get_cookie,
)
from . import database


def merge_config(main_conf: dict, custom_conf: dict) -> dict:
    """合并配置"""
    result = (main_conf or {}).copy()
    for key, value in (custom_conf or {}).items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key].update(value)
        else:
            result[key] = value
    return result


def get_f2_kwargs() -> dict:
    """获取 F2 所需的配置参数"""
    # 加载 F2 默认配置
    try:
        main_conf_manager = ConfigManager(f2.F2_CONFIG_FILE_PATH)
        all_conf = main_conf_manager.config
        main_conf = all_conf.get("douyin", {}) if all_conf else {}
    except Exception:
        main_conf = {}

    # 加载自定义配置
    custom_conf = load_config()

    # 合并配置
    kwargs = merge_config(main_conf, custom_conf)

    # 添加必要参数
    kwargs["app_name"] = "douyin"
    kwargs["mode"] = "post"

    # 设置路径
    kwargs["path"] = str(get_download_path())

    # 处理 cookie 配置
    cookie = get_cookie()
    kwargs["cookie"] = cookie

    # 确保 headers 存在
    if not kwargs.get("headers"):
        kwargs["headers"] = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/",
        }

    return kwargs


def create_tables():
    """确保数据库表存在"""
    database.init_database()


async def fetch_user_info(url: str) -> Optional[Dict[str, Any]]:
    """获取用户信息（UID、昵称等）"""
    from f2.apps.douyin.utils import SecUserIdFetcher
    
    sec_user_id = await SecUserIdFetcher.get_sec_user_id(url)
    if not sec_user_id:
        return None

    kwargs = get_f2_kwargs()
    handler = DouyinHandler(kwargs)

    # 获取用户信息
    async with AsyncUserDB(str(get_db_path())) as db:
        user_path = await handler.get_or_add_user_data(kwargs, sec_user_id, db)

    # 从数据库获取用户信息
    conn = sqlite3.connect(str(get_db_path()))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT uid, sec_user_id, nickname, avatar_url, signature, 
               follower_count, following_count, aweme_count
        FROM user_info_web 
        ORDER BY ROWID DESC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "uid": row[0],
            "sec_user_id": row[1],
            "nickname": row[2] or "",
            "avatar_url": row[3] or "",
            "signature": row[4] or "",
            "follower_count": row[5] or 0,
            "video_count": row[7] or 0,
            "url": url,
        }
    return None


async def download_videos(url: str, max_counts: int = None) -> Dict[str, Any]:
    """
    下载视频（增量模式）
    
    Returns:
        {
            "downloaded": 0,  # 新下载的视频数
            "skipped": 0,     # 跳过的视频数（已存在）
            "total": 0,       # 总共处理的视频数
            "streamer": {}    # 主播信息
        }
    """
    kwargs = get_f2_kwargs()
    kwargs["url"] = url

    if max_counts:
        kwargs["max_counts"] = max_counts

    downloads_path = get_download_path()
    
    # 获取已有的视频 ID 集合
    existing_ids = database.get_existing_aweme_ids()


    # 清理临时目录
    f2_temp_path = downloads_path / "douyin"
    if f2_temp_path.exists():
        shutil.rmtree(f2_temp_path)

    # 创建数据库表
    create_tables()

    # 初始化 Handler
    handler = DouyinHandler(kwargs)

    # 解析 sec_user_id
    from f2.apps.douyin.utils import SecUserIdFetcher
    sec_user_id = await SecUserIdFetcher.get_sec_user_id(url)

    if not sec_user_id:
        raise ValueError("无法解析用户 ID，请检查 URL 是否正确")

    print(f"[下载] 开始下载视频...")
    print(f"[信息] sec_user_id: {sec_user_id[:30]}...")

    # 获取用户信息并保存
    async with AsyncUserDB(str(get_db_path())) as db:
        user_path = await handler.get_or_add_user_data(kwargs, sec_user_id, db)

    # 从数据库获取用户信息
    conn = sqlite3.connect(str(get_db_path()))
    cursor = conn.cursor()
    cursor.execute("SELECT uid, nickname FROM user_info_web ORDER BY ROWID DESC LIMIT 1")
    user_info = cursor.fetchone()
    conn.close()

    uid = user_info[0] if user_info else ""
    nickname = user_info[1] if user_info else ""

    if nickname:
        print(f"[博主] {nickname} (UID: {uid})")

        # 保存主播信息到数据库
        folder_name = get_user_folder_name(nickname, uid)
        streamer_info = {
            "uid": uid,
            "sec_user_id": sec_user_id,
            "nickname": nickname,
            "folder": folder_name,
            "url": url,
        }
        database.save_streamer(streamer_info)

    # 下载视频
    downloaded = 0
    skipped = 0
    total = 0
    videos_data = []  # 保存视频数据用于后续处理

    async for aweme_data_list in handler.fetch_user_post_videos(
        sec_user_id,
        max_counts=max_counts or float("inf")
    ):
        video_list = aweme_data_list._to_list()

        if not video_list:
            continue

        # 过滤已存在的视频（增量下载）
        new_videos = []
        for video in video_list:
            aweme_id = video.get("aweme_id", "")
            if aweme_id and aweme_id not in existing_ids:
                new_videos.append(video)
            else:
                skipped += 1

        # 如果有新视频，保存元数据并下载
        if new_videos:
            # 保存视频元数据
            raw_data = aweme_data_list._to_raw()
            aweme_list = raw_data.get("aweme_list", [])
            
            for video in new_videos:
                aweme_id = video.get("aweme_id", "")
                stats = video.get("statistics", {}) or {}
                author = video.get("author", {}) or {}
                
                video_meta = {
                    "aweme_id": aweme_id,
                    "streamer_uid": uid,
                    "streamer_name": nickname,
                    "desc": video.get("desc", ""),
                    "create_time": video.get("create_time", 0),
                    "duration": video.get("video", {}).get("duration", 0) if video.get("video") else 0,
                    "digg_count": stats.get("digg_count", 0),
                    "comment_count": stats.get("comment_count", 0),
                    "collect_count": stats.get("collect_count", 0),
                    "share_count": stats.get("share_count", 0),
                    "play_count": stats.get("play_count", 0),
                }
                database.save_video(video_meta)
                videos_data.append(video_meta)

            # 创建下载任务
            await handler.downloader.create_download_tasks(kwargs, new_videos, user_path)
            downloaded += len(new_videos)

        total += len(video_list)
        print(f"[进度] 已处理 {total} 个视频，新增 {downloaded}，跳过 {skipped}")

    # 整理文件（移动到以主播昵称命名的文件夹）
    print("[整理] 重新组织文件...")
    folder_name = get_user_folder_name(nickname, uid)
    post_path = downloads_path / "douyin" / "post" / folder_name
    
    moved_count = 0
    if post_path.exists() and nickname:

        new_folder = downloads_path / "download" / folder_name
        new_folder.mkdir(parents=True, exist_ok=True)
        
        print(f"  [整理] 从 {post_path} 移动到 {new_folder}")

        # 移动文件（先复制再删除，更安全）
        for pattern in ["*.mp4", "*.jpg", "*.webp"]:
            for f in list(post_path.glob(pattern)):  # 用 list 避免迭代中修改
                dest = new_folder / f.name
                if dest.exists():
                    print(f"  [跳过] {f.name} (已存在)")
                    continue
                try:
                    shutil.copy2(str(f), str(dest))
                    f.unlink()  # 删除源文件
                    moved_count += 1
                    print(f"  [移动] {f.name} -> {new_folder.name}")
                    
                    # 通过视频元数据匹配 aweme_id 更新数据库
                    # F2下载的文件名格式: 2026-03-14 14-33-38_描述_video.mp4
                    # 需要通过描述或时间戳来匹配数据库中的记录
                    file_name = f.stem
                    matched_aweme_id = None
                    
                    # 尝试通过描述和时间戳匹配
                    # 注意：优先使用时间戳匹配，因为时间戳更准确且唯一
                    for video_meta in videos_data:
                        desc = video_meta.get('desc', '')
                        create_time = video_meta.get('create_time', 0)
                        aweme_id = video_meta.get('aweme_id', '')
                        
                        # 方法1: 通过时间戳匹配（优先，因为更准确）
                        try:
                            # 如果create_time是字符串格式的时间
                            if isinstance(create_time, str) and create_time in file_name:
                                matched_aweme_id = aweme_id
                                break
                            # 如果create_time是时间戳
                            elif isinstance(create_time, (int, float)) and create_time > 1000000000:
                                file_time_str = file_name.split('_')[0] if '_' in file_name else ''
                                if file_time_str:
                                    from datetime import datetime
                                    try:
                                        file_time = datetime.strptime(file_time_str, '%Y-%m-%d %H-%M-%S')
                                        file_timestamp = int(file_time.timestamp())
                                        # 允许1小时的误差
                                        if abs(create_time - file_timestamp) < 3600:
                                            matched_aweme_id = aweme_id
                                            break
                                    except ValueError:
                                        pass
                        except (ValueError, TypeError):
                            pass
                    
                    # 如果时间戳匹配失败，尝试通过描述匹配（备用方案）
                    if not matched_aweme_id:
                        for video_meta in videos_data:
                            desc = video_meta.get('desc', '')
                            aweme_id = video_meta.get('aweme_id', '')
                            
                            if desc and desc in file_name:
                                matched_aweme_id = aweme_id
                                break
                    
                    if matched_aweme_id:
                        file_size = dest.stat().st_size
                        database.update_video_local_path(matched_aweme_id, str(dest), file_size)
                        print(f"  [更新] 已更新本地路径: {matched_aweme_id}")
                    else:
                        print(f"  [警告] 无法匹配数据库记录: {file_name}")
                except Exception as e:
                    print(f"  [错误] 移动 {f.name} 失败: {e}")

        # 清理旧目录（只有确认文件都处理完才删除）
        try:
            # 检查是否还有文件
            remaining = list(post_path.glob("*"))
            if not remaining:
                shutil.rmtree(post_path)
                print(f"  [清理] 已删除空目录 {post_path}")
            else:
                print(f"  [保留] {post_path} 还有 {len(remaining)} 个文件")
        except Exception as e:
            print(f"  [错误] 清理目录失败: {e}")
    
    if moved_count == 0:
        print("  [信息] 没有需要整理的文件")

    # 更新主播的最后抓取时间
    if uid:
        database.update_streamer_fetch_time(uid)

    print(f"\n[完成] 新增: {downloaded}，跳过: {skipped}")

    return {
        "downloaded": downloaded,
        "skipped": skipped,
        "total": total,
        "streamer": {
            "uid": uid,
            "nickname": nickname,
            "sec_user_id": sec_user_id,
        }
    }


async def download_single_streamer(url: str, max_counts: int = None) -> Dict[str, Any]:
    """下载单个主播的视频"""
    return await download_videos(url, max_counts)


async def download_all_streamers(max_counts: int = None) -> Dict[str, Any]:
    """下载配置中所有主播的视频"""
    from .config import get_streamers_config
    
    streamers = get_streamers_config()
    
    if not streamers:
        print("[警告] 没有配置要跟踪的主播，请在 config.yaml 中添加 streamers 配置")
        return {
            "downloaded": 0,
            "skipped": 0,
            "total": 0,
            "streamers": [],
        }

    total_downloaded = 0
    total_skipped = 0
    streamer_results = []

    for streamer in streamers:
        url = streamer.get("url")
        name = streamer.get("name", "")
        
        if not url:
            continue

        print(f"\n{'='*60}")
        print(f"[主播] {name or url}")
        print(f"{'='*60}")

        try:
            result = await download_videos(url, max_counts)
            total_downloaded += result["downloaded"]
            total_skipped += result["skipped"]
            streamer_results.append(result)
        except Exception as e:
            print(f"[错误] 下载失败: {e}")

    return {
        "downloaded": total_downloaded,
        "skipped": total_skipped,
        "total": len(streamer_results),
        "streamers": streamer_results,
    }


def sync_streamers_from_config():
    """从配置文件同步主播列表到数据库"""
    from .config import get_streamers_config
    
    streamers = get_streamers_config()
    
    for streamer in streamers:
        url = streamer.get("url")
        name = streamer.get("name", "")
        
        if url:
            # 保存主播信息（等下载时再获取完整信息）
            database.save_streamer({
                "url": url,
                "nickname": name,
                "folder": sanitize_folder_name(name) if name else "",
            })
            print(f"[同步] {name or url}")