"""
报告生成模块
支持生成 Markdown、HTML、JSON 格式的汇总报告
"""

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import json
from .config import get_reports_path


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


class ReportGenerator:
    """报告生成器"""

    def __init__(self, format: str = "markdown", config: Optional[Dict[str, Any]] = None):
        """
        初始化

        Args:
            format: 报告格式 (markdown/html/json)
            config: 配置选项
        """
        self.format = format.lower()
        self.config = config or {}

    def generate(self, videos: List[Dict[str, Any]], title: str = "抖音内容汇总报告", report_type: str = "汇总") -> Path:
        """
        生成报告

        Args:
            videos: 视频数据列表
            title: 报告标题
            report_type: 报告类型

        Returns:
            报告文件路径
        """
        if self.format == "markdown":
            content = self._generate_markdown(videos, title, report_type)
            ext = ".md"
        elif self.format == "html":
            content = self._generate_html(videos, title, report_type)
            ext = ".html"
        elif self.format == "json":
            content = self._generate_json(videos, title, report_type)
            ext = ".json"
        else:
            raise ValueError(f"不支持的格式: {self.format}")

        # 保存文件
        output_dir = get_reports_path()
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_{timestamp}{ext}"
        file_path = output_dir / filename

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return file_path

    def _generate_markdown(self, videos: List[Dict[str, Any]], title: str, report_type: str) -> str:
        """生成 Markdown 格式报告"""
        lines = []

        # 标题
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"视频数量: {len(videos)}")
        lines.append("")

        # 摘要统计
        if self.config.get("include_summary"):
            stats = self._calculate_stats(videos)
            lines.append("## 统计摘要")
            lines.append("")
            lines.append(f"- 总视频数: {stats['total_videos']}")
            lines.append(f"- 已转录: {stats['with_transcript']}")
            lines.append(f"- 未转录: {stats['without_transcript']}")
            lines.append(f"- 主播数: {stats['unique_streamers']}")
            lines.append(f"- 总点赞: {stats['total_likes']:,}")
            lines.append(f"- 总评论: {stats['total_comments']:,}")
            if stats['total_size_mb']:
                lines.append(f"- 总大小: {stats['total_size_mb']} MB")
            lines.append("")

        # 关键词
        keywords = self._extract_keywords(videos)
        if keywords:
            lines.append("## 热门关键词")
            lines.append("")
            lines.append(", ".join(f"**{kw}**" for kw in keywords[:10]))
            lines.append("")

        # 视频列表
        lines.append("## 视频列表")
        lines.append("")

        if self.config.get("group_by_date"):
            # 按日期分组
            videos_by_date = {}
            for video in videos:
                create_time = video.get('create_time', 0)
                date_str = format_create_time(create_time, '%Y-%m-%d')
                if date_str not in videos_by_date:
                    videos_by_date[date_str] = []
                videos_by_date[date_str].append(video)

            for date in sorted(videos_by_date.keys(), reverse=True):
                lines.append(f"### {date}")
                lines.append("")
                for video in videos_by_date[date]:
                    lines.append(self._format_video_markdown(video))
                    lines.append("")
        else:
            # 不分组，直接列出
            for video in videos:
                lines.append(self._format_video_markdown(video))
                lines.append("")

        return "\n".join(lines)

    def _format_video_markdown(self, video: Dict[str, Any]) -> str:
        """格式化单个视频为 Markdown"""
        lines = []

        # 标题
        desc = video.get('desc', '')[:80] or '无标题'
        create_time = video.get('create_time', 0)
        time_str = format_create_time(create_time, '%Y-%m-%d')

        lines.append(f"### {time_str} {desc}")
        lines.append("")

        # 元数据
        if self.config.get("include_metadata"):
            lines.append("| 属性 | 值 |")
            lines.append("|------|-----|")
            lines.append(f"| 视频ID | `{video.get('aweme_id', '')}` |")
            
            if create_time:
                time_str_full = format_create_time(create_time, '%Y-%m-%d %H:%M:%S')
                lines.append(f"| 发布时间 | {time_str_full} |")
            
            duration = video.get('duration', 0)
            if duration:
                lines.append(f"| 时长 | {duration // 1000}秒 |")

            lines.append(f"| 点赞 | {video.get('digg_count', 0):,} |")
            lines.append(f"| 评论 | {video.get('comment_count', 0):,} |")
            lines.append(f"| 收藏 | {video.get('collect_count', 0):,} |")
            lines.append(f"| 分享 | {video.get('share_count', 0):,} |")

            streamer_name = video.get('streamer_name', '')
            if streamer_name:
                lines.append(f"| 主播 | {streamer_name} |")

            local_path = video.get('local_path', '')
            if local_path:
                lines.append(f"| 本地路径 | `{local_path}` |")

            lines.append("")

        # 描述
        full_desc = video.get('desc', '')
        if full_desc:
            lines.append("#### 描述")
            lines.append("")
            lines.append(full_desc)
            lines.append("")

        # 转录文本
        transcript_text = video.get('transcript_text', '')
        if transcript_text:
            lines.append("#### 转录内容")
            lines.append("")
            lines.append(transcript_text)
            lines.append("")

        return "\n".join(lines)

    def _generate_html(self, videos: List[Dict[str, Any]], title: str, report_type: str) -> str:
        """生成 HTML 格式报告"""
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', sans-serif; line-height: 1.6; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        .stats {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .video {{ border: 1px solid #ddd; padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .metadata {{ background: #f9f9f9; padding: 10px; margin: 10px 0; }}
        .transcript {{ background: #fffde7; padding: 15px; margin: 10px 0; border-left: 4px solid #ffc107; }}
        .keywords {{ margin: 20px 0; }}
        .keyword {{ display: inline-block; background: #e3f2fd; padding: 5px 10px; margin: 5px; border-radius: 15px; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>视频数量: {len(videos)}</p>
"""

        # 统计摘要
        if self.config.get("include_summary"):
            stats = self._calculate_stats(videos)
            html += f"""
    <div class="stats">
        <h2>统计摘要</h2>
        <ul>
            <li>总视频数: {stats['total_videos']}</li>
            <li>已转录: {stats['with_transcript']}</li>
            <li>未转录: {stats['without_transcript']}</li>
            <li>主播数: {stats['unique_streamers']}</li>
            <li>总点赞: {stats['total_likes']:,}</li>
            <li>总评论: {stats['total_comments']:,}</li>
        </ul>
    </div>
"""

        # 关键词
        keywords = self._extract_keywords(videos)
        if keywords:
            html += """
    <div class="keywords">
        <h2>热门关键词</h2>
"""
            for kw in keywords[:10]:
                html += f'        <span class="keyword">{kw}</span>\n'
            html += "    </div>\n"

        # 视频列表
        html += "    <h2>视频列表</h2>\n"
        for video in videos:
            html += self._format_video_html(video)

        html += """
</body>
</html>
"""
        return html

    def _format_video_html(self, video: Dict[str, Any]) -> str:
        """格式化单个视频为 HTML"""
        desc = video.get('desc', '')[:80] or '无标题'
        create_time = video.get('create_time', 0)
        time_str = format_create_time(create_time, '%Y-%m-%d')

        html = f"""
    <div class="video">
        <h3>{time_str} {desc}</h3>
"""

        if self.config.get("include_metadata"):
            html += f"""
        <div class="metadata">
            <p><strong>视频ID:</strong> {video.get('aweme_id', '')}</p>
"""
            if create_time:
                time_str_full = format_create_time(create_time, '%Y-%m-%d %H:%M:%S')
                html += f"            <p><strong>发布时间:</strong> {time_str_full}</p>\n"

            html += f"""
            <p><strong>点赞:</strong> {video.get('digg_count', 0):,}</p>
            <p><strong>评论:</strong> {video.get('comment_count', 0):,}</p>
        </div>
"""

        transcript_text = video.get('transcript_text', '')
        if transcript_text:
            html += f"""
        <div class="transcript">
            <h4>转录内容</h4>
            <p>{transcript_text}</p>
        </div>
"""

        html += "    </div>\n"
        return html

    def _generate_json(self, videos: List[Dict[str, Any]], title: str, report_type: str) -> str:
        """生成 JSON 格式报告"""
        data = {
            "title": title,
            "generated_at": datetime.now().isoformat(),
            "report_type": report_type,
            "video_count": len(videos),
            "stats": self._calculate_stats(videos),
            "keywords": self._extract_keywords(videos),
            "videos": []
        }

        for video in videos:
            video_data = {
                "aweme_id": video.get('aweme_id', ''),
                "streamer_name": video.get('streamer_name', ''),
                "desc": video.get('desc', ''),
                "create_time": video.get('create_time', ''),
                "create_time_formatted": format_create_time(video.get('create_time', ''), '%Y-%m-%d %H:%M:%S'),
                "duration": video.get('duration', 0),
                "digg_count": video.get('digg_count', 0),
                "comment_count": video.get('comment_count', 0),
                "collect_count": video.get('collect_count', 0),
                "share_count": video.get('share_count', 0),
                "play_count": video.get('play_count', 0),
                "local_path": video.get('local_path', ''),
                "transcript_text": video.get('transcript_text', '')
            }
            data["videos"].append(video_data)

        return json.dumps(data, ensure_ascii=False, indent=2)

    def _calculate_stats(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算统计信息"""
        total_videos = len(videos)
        with_transcript = sum(1 for v in videos if v.get('transcript_text'))
        without_transcript = total_videos - with_transcript
        unique_streamers = len(set(v.get('streamer_name') for v in videos if v.get('streamer_name')))
        
        total_likes = sum(v.get('digg_count', 0) or 0 for v in videos)
        total_comments = sum(v.get('comment_count', 0) or 0 for v in videos)
        total_size = sum(v.get('file_size', 0) or 0 for v in videos)

        return {
            "total_videos": total_videos,
            "with_transcript": with_transcript,
            "without_transcript": without_transcript,
            "unique_streamers": unique_streamers,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2) if total_size else None,
        }

    def _group_by_streamer(self, videos: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按主播分组"""
        result = {}
        for video in videos:
            streamer_name = video.get('streamer_name', '未知')
            if streamer_name not in result:
                result[streamer_name] = []
            result[streamer_name].append(video)
        return result

    def _extract_keywords(self, videos: List[Dict[str, Any]]) -> List[str]:
        """提取关键词（简单实现）"""
        import re
        from collections import Counter

        # 收集所有转录文本和描述
        texts = []
        for video in videos:
            desc = video.get('desc') or ''
            transcript = video.get('transcript_text') or ''
            texts.append(str(desc) + " " + str(transcript))

        # 提取中文关键词
        all_text = " ".join(texts)
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', all_text)

        # 统计词频
        word_counts = Counter(words)

        # 过滤常见词
        common_words = {'因为', '所以', '但是', '然后', '这个', '那个', '视频', '大家', '我们', '可以', '就是', '今天', '现在', '一下', '一个', '什么', '没有', '这个', '那个'}
        keywords = [w for w, c in word_counts.most_common(20) if w not in common_words and c >= 2]

        return keywords


def generate_summary_report(videos: List[Dict[str, Any]], report_type: str = "汇总") -> Path:
    """生成汇总报告（快捷函数）

    Args:
        videos: 视频数据列表
        report_type: 报告类型

    Returns:
        报告文件路径
    """
    title = f"抖音内容汇总报告 - {datetime.now().strftime('%Y-%m-%d')}"

    generator = ReportGenerator(format="markdown")
    return generator.generate(videos, title, report_type)
