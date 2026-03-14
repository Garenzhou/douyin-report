"""
统一配置加载模块
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List


# 技能根目录
SKILL_DIR = Path(__file__).parent.parent.resolve()


def get_config_path() -> Path:
    """获取配置文件路径"""
    return SKILL_DIR / "config" / "config.yaml"


def get_db_path() -> Path:
    """获取数据库路径"""
    return SKILL_DIR / "data.db"


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    config_path = get_config_path()
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def save_config(config: Dict[str, Any]):
    """保存配置文件"""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def get_download_path() -> Path:
    """获取下载根目录"""
    config = load_config()
    custom_path = config.get("download_path", "").strip()

    if custom_path:
        return Path(custom_path)

    # 默认路径：系统 Downloads/douyin-report
    downloads = Path.home() / "Downloads" / "douyin-report"
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads


def get_videos_path() -> Path:
    """获取视频存储路径"""
    videos_path = get_download_path() / "download"
    videos_path.mkdir(parents=True, exist_ok=True)
    return videos_path


def get_transcripts_path() -> Path:
    """获取转录文本存储路径"""
    transcripts_path = get_download_path() / "transcripts"
    transcripts_path.mkdir(parents=True, exist_ok=True)
    return transcripts_path


def get_reports_path() -> Path:
    """获取报告存储路径"""
    reports_path = get_download_path() / "reports"
    reports_path.mkdir(parents=True, exist_ok=True)
    return reports_path


def get_cookie() -> str:
    """获取 Cookie 字符串"""
    config = load_config()
    cookie = config.get("cookie", "").strip()
    
    if not cookie:
        raise ValueError("未配置 Cookie，请在 config/config.yaml 中设置")
    
    return cookie


def get_incremental_config() -> Dict[str, Any]:
    """获取增量下载配置"""
    config = load_config()
    return config.get("incremental", {"enabled": True})


def get_streamers_config() -> List[Dict[str, Any]]:
    """获取要跟踪的主播列表配置"""
    config = load_config()
    return config.get("streamers", [])


def update_streamers_config(streamers: List[Dict[str, Any]]):
    """更新主播列表配置"""
    config = load_config()
    config["streamers"] = streamers
    save_config(config)


def add_streamer_config(streamer: Dict[str, Any]):
    """添加一个主播到配置"""
    config = load_config()
    streamers = config.get("streamers", [])
    
    # 检查是否已存在（通过 URL 判断）
    exists = False
    for s in streamers:
        if s.get("url") == streamer.get("url"):
            exists = True
            break
    
    if not exists:
        streamers.append(streamer)
        config["streamers"] = streamers
        save_config(config)


def remove_streamer_config(url: str):
    """从配置中移除一个主播"""
    config = load_config()
    streamers = config.get("streamers", [])
    
    config["streamers"] = [s for s in streamers if s.get("url") != url]
    save_config(config)


def get_transcript_config() -> Dict[str, Any]:
    """获取转录配置"""
    config = load_config()
    transcript_config = config.get("transcript", {})

    # 从环境变量读取 API_KEY
    api_key = os.environ.get("API_KEY", transcript_config.get("api_key", ""))

    return {
        "enabled": transcript_config.get("enabled", True),
        "api_key": api_key,
        "api_base_url": transcript_config.get("api_base_url", "https://api.siliconflow.cn/v1"),
        "model": transcript_config.get("model", "FunAudioLLM/SenseVoiceSmall"),
    }


def get_report_config() -> Dict[str, Any]:
    """获取报告配置"""
    config = load_config()
    return config.get("report", {
        "format": "markdown",
        "include_metadata": True,
        "group_by_date": True,
        "include_summary": True,
    })


def sanitize_folder_name(name: str) -> str:
    """清理文件夹名称，移除非法字符"""
    import re
    if not name:
        return "unknown"
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\s_]+', '_', name)
    name = name.strip('_')
    return name[:100] if name else "unknown"


def get_user_folder_name(nickname: str, uid: str) -> str:
    """获取用户文件夹名称"""
    if nickname:
        return sanitize_folder_name(nickname)
    return str(uid)[:20]