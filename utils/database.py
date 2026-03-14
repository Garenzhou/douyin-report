"""
数据库管理模块
独立存储视频元数据、主播信息和转录文本
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from .config import get_db_path, get_config_path


def init_database():
    """初始化数据库"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 主播信息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS streamers (
            uid TEXT PRIMARY KEY,
            sec_user_id TEXT UNIQUE,
            nickname TEXT,
            folder TEXT,
            url TEXT,
            avatar_url TEXT,
            signature TEXT,
            follower_count INTEGER DEFAULT 0,
            video_count INTEGER DEFAULT 0,
            last_fetch_time INTEGER,
            created_time INTEGER,
            updated_time INTEGER
        )
    """)

    # 视频元数据表（从 F2 下载时保存）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            aweme_id TEXT PRIMARY KEY,
            streamer_uid TEXT NOT NULL,
            streamer_name TEXT,
            desc TEXT,
            create_time INTEGER,
            duration INTEGER,
            digg_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            collect_count INTEGER DEFAULT 0,
            share_count INTEGER DEFAULT 0,
            play_count INTEGER DEFAULT 0,
            local_path TEXT,
            file_size INTEGER,
            has_transcript INTEGER DEFAULT 0,
            created_time INTEGER,
            updated_time INTEGER
        )
    """)

    # 转录文本表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            aweme_id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            created_time INTEGER,
            model TEXT,
            status TEXT DEFAULT 'pending',
            error_message TEXT
        )
    """)

    # 索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_streamer ON videos(streamer_uid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_has_transcript ON videos(has_transcript)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_create_time ON videos(create_time)")

    conn.commit()
    conn.close()


# ==================== 主播管理 ====================

def save_streamer(streamer: Dict[str, Any]) -> bool:
    """保存或更新主播信息"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        now = int(datetime.now().timestamp())
        
        cursor.execute("""
            INSERT OR REPLACE INTO streamers (
                uid, sec_user_id, nickname, folder, url,
                avatar_url, signature, follower_count, video_count,
                last_fetch_time, created_time, updated_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            streamer.get('uid'),
            streamer.get('sec_user_id', ''),
            streamer.get('nickname', ''),
            streamer.get('folder', ''),
            streamer.get('url', ''),
            streamer.get('avatar_url', ''),
            streamer.get('signature', ''),
            streamer.get('follower_count', 0),
            streamer.get('video_count', 0),
            streamer.get('last_fetch_time'),
            now,
            now
        ))

        conn.commit()
        return True
    except Exception as e:
        print(f"保存主播信息失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_streamer(uid: str) -> Optional[Dict[str, Any]]:
    """获取单个主播信息"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM streamers WHERE uid = ?", (uid,))
    row = cursor.fetchone()
    conn.close()

    if row:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    return None


def get_streamer_by_sec_user_id(sec_user_id: str) -> Optional[Dict[str, Any]]:
    """通过 sec_user_id 获取主播信息"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM streamers WHERE sec_user_id = ?", (sec_user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    return None


def get_all_streamers() -> List[Dict[str, Any]]:
    """获取所有主播"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM streamers ORDER BY updated_time DESC")
    rows = cursor.fetchall()

    columns = [desc[0] for desc in cursor.description]
    result = [dict(zip(columns, row)) for row in rows]

    conn.close()
    return result


def update_streamer_fetch_time(uid: str):
    """更新主播的最后抓取时间"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    now = int(datetime.now().timestamp())
    cursor.execute("""
        UPDATE streamers
        SET last_fetch_time = ?, updated_time = ?
        WHERE uid = ?
    """, (now, now, uid))

    conn.commit()
    conn.close()


def delete_streamer(uid: str) -> bool:
    """删除主播"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM streamers WHERE uid = ?", (uid,))
        conn.commit()
        return True
    except Exception as e:
        print(f"删除主播失败: {e}")
        return False
    finally:
        conn.close()


# ==================== 视频管理 ====================

def save_video(video: Dict[str, Any]) -> bool:
    """保存或更新视频元数据"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        now = int(datetime.now().timestamp())

        cursor.execute("""
            INSERT OR REPLACE INTO videos (
                aweme_id, streamer_uid, streamer_name, desc, create_time,
                duration, digg_count, comment_count, collect_count, share_count,
                play_count, local_path, file_size, created_time, updated_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            video.get('aweme_id'),
            video.get('streamer_uid'),
            video.get('streamer_name', ''),
            video.get('desc', ''),
            video.get('create_time', 0),
            video.get('duration', 0),
            video.get('digg_count', 0),
            video.get('comment_count', 0),
            video.get('collect_count', 0),
            video.get('share_count', 0),
            video.get('play_count', 0),
            video.get('local_path', ''),
            video.get('file_size', 0),
            now,
            now
        ))

        conn.commit()
        return True
    except Exception as e:
        print(f"保存视频元数据失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def save_videos(videos: List[Dict[str, Any]]) -> int:
    """批量保存视频元数据，返回保存数量"""
    count = 0
    for video in videos:
        if save_video(video):
            count += 1
    return count


def get_video(aweme_id: str) -> Optional[Dict[str, Any]]:
    """获取单个视频信息"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM videos WHERE aweme_id = ?", (aweme_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    return None


def get_all_videos() -> List[Dict[str, Any]]:
    """获取所有视频"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM videos ORDER BY create_time DESC")
    rows = cursor.fetchall()

    columns = [desc[0] for desc in cursor.description]
    result = [dict(zip(columns, row)) for row in rows]

    conn.close()
    return result


def get_videos_by_streamer(streamer_uid: str) -> List[Dict[str, Any]]:
    """获取指定主播的视频"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM videos
        WHERE streamer_uid = ?
        ORDER BY create_time DESC
    """, (streamer_uid,))

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    result = [dict(zip(columns, row)) for row in rows]

    conn.close()
    return result


def get_videos_without_transcript() -> List[Dict[str, Any]]:
    """获取没有转录文本的视频"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM videos
        WHERE has_transcript = 0
        ORDER BY create_time DESC
    """)

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    result = [dict(zip(columns, row)) for row in rows]

    conn.close()
    return result


def get_existing_aweme_ids() -> set:
    """获取已存在的视频 ID 集合（用于增量下载判断）"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT aweme_id FROM videos")
    result = {row[0] for row in cursor.fetchall()}

    conn.close()
    return result


def update_video_local_path(aweme_id: str, local_path: str, file_size: int = 0) -> bool:
    """更新视频的本地路径"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        now = int(datetime.now().timestamp())
        cursor.execute("""
            UPDATE videos
            SET local_path = ?, file_size = ?, updated_time = ?
            WHERE aweme_id = ?
        """, (local_path, file_size, now, aweme_id))

        conn.commit()
        return True
    except Exception as e:
        print(f"更新视频路径失败: {e}")
        return False
    finally:
        conn.close()


def update_video_transcript_status(aweme_id: str, has_transcript: bool) -> bool:
    """更新视频的转录状态"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE videos
            SET has_transcript = ?
            WHERE aweme_id = ?
        """, (1 if has_transcript else 0, aweme_id))

        conn.commit()
        return True
    except Exception as e:
        print(f"更新转录状态失败: {e}")
        return False
    finally:
        conn.close()


# ==================== 转录管理 ====================

def save_transcript(aweme_id: str, text: str, model: str = "unknown") -> bool:
    """保存转录文本"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        now = int(datetime.now().timestamp())
        
        cursor.execute("""
            INSERT OR REPLACE INTO transcripts (
                aweme_id, text, created_time, model, status
            ) VALUES (?, ?, ?, ?, 'completed')
        """, (aweme_id, text, now, model))

        # 更新视频表的转录标记
        cursor.execute("""
            UPDATE videos SET has_transcript = 1 WHERE aweme_id = ?
        """, (aweme_id,))

        conn.commit()
        return True
    except Exception as e:
        print(f"保存转录文本失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_transcript(aweme_id: str) -> Optional[Dict[str, Any]]:
    """获取转录文本"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM transcripts WHERE aweme_id = ?", (aweme_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    return None


# ==================== 统计 ====================

def get_stats() -> Dict[str, Any]:
    """获取统计信息"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 主播数
    cursor.execute("SELECT COUNT(*) FROM streamers")
    streamer_count = cursor.fetchone()[0]

    # 总视频数
    cursor.execute("SELECT COUNT(*) FROM videos")
    total_videos = cursor.fetchone()[0]

    # 有转录的视频数
    cursor.execute("SELECT COUNT(*) FROM videos WHERE has_transcript = 1")
    with_transcript = cursor.fetchone()[0]

    # 有本地文件的视频数
    cursor.execute("SELECT COUNT(*) FROM videos WHERE local_path IS NOT NULL AND local_path != ''")
    with_local_file = cursor.fetchone()[0]

    # 总文件大小
    cursor.execute("SELECT SUM(file_size) FROM videos WHERE file_size > 0")
    total_size = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "streamer_count": streamer_count,
        "total_videos": total_videos,
        "with_transcript": with_transcript,
        "without_transcript": total_videos - with_transcript,
        "with_local_file": with_local_file,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
    }


def get_streamer_stats(streamer_uid: str) -> Dict[str, Any]:
    """获取指定主播的统计信息"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM videos WHERE streamer_uid = ?", (streamer_uid,))
    video_count = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(digg_count) FROM videos WHERE streamer_uid = ?", (streamer_uid,))
    total_likes = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(comment_count) FROM videos WHERE streamer_uid = ?", (streamer_uid,))
    total_comments = cursor.fetchone()[0] or 0

    conn.close()

    return {
        "video_count": video_count,
        "total_likes": total_likes,
        "total_comments": total_comments,
    }