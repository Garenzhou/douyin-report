# Douyin Report Skill

抖音主播内容批量下载与汇总分析工具

## 功能特性

- ✨ **增量下载**：自动检测已下载视频，避免重复下载
- ✨ **主播管理**：配置要跟踪的主播列表
- ✨ **语音转文字**：使用硅基流动 API 自动识别视频中的语音内容
- ✨ **汇总报告**：生成 Markdown/HTML/JSON 三种格式的详细报告
- ✨ **关键词提取**：自动分析视频内容，提取热门话题

## 安装

```bash
# 进入技能目录
cd ~/.agents/skills/douyin-report

# 安装依赖
python scripts/install.py

# 或手动安装
pip install f2 pyyaml requests openai ffmpeg-python
```

## 快速开始

### 1. 配置 Cookie

编辑 `config/config.yaml`，填入抖音 Cookie：

```yaml
cookie: "你的抖音Cookie"
```

**获取 Cookie 方法**：
1. 打开浏览器开发者工具（F12）
2. 访问抖音主页 https://www.douyin.com/
3. 在 Network 标签中找到请求，复制 Request Headers 中的 Cookie

### 2. 配置要跟踪的主播

```bash
# 添加主播
python scripts/streamers.py add "https://www.douyin.com/user/MS4wLjABAAAA..."

# 添加主播（指定昵称）
python scripts/streamers.py add "https://www.douyin.com/user/xxx" "丹木大叔"

# 查看主播列表
python scripts/streamers.py list
```

### 3. 下载视频并生成报告

```bash
# 下载所有主播的视频并生成报告
python scripts/run_full.py

# 限制每个主播下载数量
python scripts/run_full.py --max-counts=10

# 只下载单个主播
python scripts/run_full.py --streamer "https://www.douyin.com/user/xxx"
```

### 4. 查看报告

报告保存在 `~/Downloads/douyin-report/reports/` 目录：
- Markdown: `*.markdown`
- HTML: `*.html`
- JSON: `*.json`

## 使用方法

### 命令行选项

```bash
# 完整工作流程（下载 + 转录 + 报告）
python scripts/run_full.py

# 选项：
#   --max-counts=N      每个主播最多下载 N 个视频
#   --streamer URL      只下载指定主播
#   --no-download       跳过下载，只生成报告
#   --no-transcript     跳过转录

# 仅生成报告
python scripts/run.py
python scripts/run.py --streamer "主播UID或昵称"

# 主播管理
python scripts/streamers.py list              # 列出所有主播
python scripts/streamers.py add "URL"         # 添加主播
python scripts/streamers.py add "URL" "昵称"  # 添加主播（指定昵称）
python scripts/streamers.py remove "URL"      # 移除主播
python scripts/streamers.py clear             # 清除所有主播
```

### 配置文件

编辑 `config/config.yaml`：

```yaml
# Cookie（必需）
cookie: "你的抖音Cookie"

# 下载路径（可选）
download_path: ""

# 增量下载
incremental:
  enabled: true

# 要跟踪的主播（可选，也可用命令行添加）
streamers:
  - url: "https://www.douyin.com/user/xxx"
    name: "丹木大叔"

# 语音转录
transcript:
  enabled: true
  api_key: "硅基流动API Key"  # 或设置环境变量 API_KEY
  api_base_url: "https://api.siliconflow.cn/v1"
  model: "FunAudioLLM/SenseVoiceSmall"

# 报告配置
report:
  format: "markdown"  # markdown, html, json
  include_metadata: true
  include_summary: true
```

## 目录结构

```
douyin-report/
├── config/
│   ├── config.yaml
│   └── config.yaml.example
├── scripts/
│   ├── install.py      # 安装依赖
│   ├── run_full.py     # 完整流程（下载+转录+报告）
│   ├── run.py          # 仅生成报告
│   └── streamers.py    # 主播管理
└── utils/
    ├── config.py       # 配置加载
    ├── database.py     # 数据库管理
    ├── downloader.py   # 视频下载
    ├── report.py       # 报告生成
    └── transcript.py   # 语音转录
```

## 输出目录

```
~/Downloads/douyin-report/
├── download/           # 下载的视频
│   ├── 丹木大叔/
│   │   └── *.mp4
│   └── 速趴作手/
│       └── *.mp4
└── reports/           # 报告
    ├── *.markdown
    ├── *.html
    └── *.json
```

## 数据库

数据库文件：`~/.agents/skills/douyin-report/data.db`

### 表结构

**streamers**：主播信息
- uid, sec_user_id, nickname, folder, url, last_fetch_time

**videos**：视频元数据
- aweme_id, streamer_uid, streamer_name, desc, create_time, duration, digg_count, comment_count, collect_count, share_count, play_count, local_path, has_transcript

**transcripts**：转录文本
- aweme_id, text, model, status

## 常见问题

### Q: Cookie 过期怎么办？
A: 重新获取 Cookie 并更新配置文件，然后重新运行脚本。

### Q: 如何只下载特定主播的视频？
A: 使用 `--streamer` 参数：
```bash
python scripts/run_full.py --streamer "https://www.douyin.com/user/xxx"
```

### Q: 如何增量更新？
A: 默认启用增量模式，脚本会自动跳过已下载的视频。

### Q: 转录失败怎么办？
A: 检查 API Key 是否正确，账户余额是否充足。

## 技术栈

- **下载**：F2 框架
- **语音识别**：硅基流动 API（FunAudioLLM/SenseVoiceSmall）
- **数据存储**：SQLite
- **报告生成**：Markdown/HTML/JSON

## 许可证

MIT License