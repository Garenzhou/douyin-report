"""
语音转录模块
使用硅基流动 API 进行语音识别
"""

import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
from openai import OpenAI
import ffmpeg


def parse_create_time(create_time: Union[str, int, None]) -> Union[int, None]:
    """
    解析create_time字段，支持多种格式
    
    Args:
        create_time: 可能是时间戳字符串、整数时间戳或None
        
    Returns:
        整数时间戳或None
    """
    if not create_time:
        return None
    
    # 如果已经是整数，直接返回
    if isinstance(create_time, int):
        return create_time
    
    # 如果是字符串，尝试解析
    if isinstance(create_time, str):
        # 尝试解析格式: "2026-01-13 20-58-55"
        try:
            # 替换空格和破折号为标准格式
            time_str = create_time.replace('-', ' ')
            dt = datetime.strptime(time_str, '%Y %m %d %H %M %S')
            return int(dt.timestamp())
        except ValueError:
            # 如果解析失败，尝试其他格式
            try:
                dt = datetime.strptime(create_time, '%Y-%m-%d %H:%M:%S')
                return int(dt.timestamp())
            except ValueError:
                pass
    
    return None


def format_create_time(create_time: Union[str, int, None], format_str: str = '%Y-%m-%d') -> str:
    """
    格式化create_time为指定格式的字符串
    
    Args:
        create_time: 可能是时间戳字符串、整数时间戳或None
        format_str: 目标格式字符串
        
    Returns:
        格式化后的时间字符串
    """
    timestamp = parse_create_time(create_time)
    if not timestamp:
        return '未知'
    
    return datetime.fromtimestamp(timestamp).strftime(format_str)


class TranscriptExtractor:
    """语音转录提取器"""

    def __init__(self, api_key: str = "", api_base_url: Optional[str] = None, model: Optional[str] = None):
        """初始化

        Args:
            api_key: 硅基流动 API 密钥
            api_base_url: API 基础 URL
            model: 使用的模型
        """
        self.api_key = api_key or os.environ.get("API_KEY", "")
        self.api_base_url = api_base_url or "https://api.siliconflow.cn/v1"
        self.model = model or "FunAudioLLM/SenseVoiceSmall"
        self.temp_dir = Path(tempfile.mkdtemp())

    def __del__(self):
        """清理临时目录"""
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def extract_audio(self, video_path: Path) -> Optional[Path]:
        """从视频中提取音频

        Args:
            video_path: 视频文件路径

        Returns:
            提取的音频文件路径
        """
        try:
            audio_path = self.temp_dir / f"{video_path.stem}.wav"

            (
                ffmpeg
                .input(str(video_path))
                .output(str(audio_path), acodec='pcm_s16le', ac=1, ar=16000)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            return audio_path
        except Exception as e:
            print(f"[错误] 提取音频失败: {e}")
            return None

    def transcribe(self, audio_path: Path) -> Optional[str]:
        """使用硅基流动 API 进行语音识别

        Args:
            audio_path: 音频文件路径

        Returns:
            识别的文本
        """
        try:
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_base_url
            )

            with open(audio_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="text"
                )

            return response
        except Exception as e:
            print(f"[错误] 语音识别失败: {e}")
            return None

    def extract_transcript(self, video_path: Path) -> Optional[str]:
        """从视频中提取转录文本

        Args:
            video_path: 视频文件路径

        Returns:
            转录文本
        """
        # 提取音频
        audio_path = self.extract_audio(video_path)
        if not audio_path:
            return None

        # 语音识别
        transcript = self.transcribe(audio_path)
        return transcript


def save_transcript_markdown(
    aweme_id: str,
    nickname: str,
    video_title: str,
    transcript_text: str,
    metadata: dict,
    output_dir: Path
) -> Path:
    """保存转录为 Markdown 文件

    Args:
        aweme_id: 视频 ID
        nickname: 主播昵称
        video_title: 视频标题
        transcript_text: 转写文本
        metadata: 视频元数据
        output_dir: 输出目录

    Returns:
        保存的文件路径
    """
    # 创建主播文件夹
    streamer_dir = output_dir / nickname
    streamer_dir.mkdir(parents=True, exist_ok=True)

    # 文件名：aweme_id.md
    file_path = streamer_dir / f"{aweme_id}.md"

    # 获取格式化后的时间
    create_time = metadata.get('create_time', 0)
    create_time_str = format_create_time(create_time, '%Y-%m-%d %H:%M:%S')

    # 格式化内容
    content = f"""# {video_title}

| 属性 | 值 |
|------|-----|
| 视频 ID | `{aweme_id}` |
| 主播 | {nickname} |
| 转写时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| 发布时间 | {create_time_str} |
| 时长 | {metadata.get('duration', 0) / 1000:.0f}秒 |
| 点赞 | {metadata.get('digg_count', 0)} |
| 评论 | {metadata.get('comment_count', 0)} |
| 收藏 | {metadata.get('collect_count', 0)} |
| 分享 | {metadata.get('share_count', 0)} |

---

## 视频描述

{metadata.get('desc', '无描述')}

---

## 转写内容

{transcript_text}
"""

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return file_path
