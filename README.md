<p align="center">
  <h1 align="center">🎵 Redacted Audio Toolbox</h1>
  <p align="center">
    <b>All-in-one desktop toolkit for audiophiles & Private Tracker power users</b>
  </p>
  <p align="center">
    <a href="#-english">English</a> · <a href="#-中文">中文</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white" alt="Platform">
    <img src="https://img.shields.io/badge/GUI-CustomTkinter-2B2D42?style=flat-square" alt="GUI">
    <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
    <img src="https://img.shields.io/github/stars/whn2000/RedactedAudioToolbox?style=flat-square" alt="Stars">
  </p>
</p>

---

<a name="-english"></a>

## 🇬🇧 English

**Redacted Audio Toolbox** is a feature-rich, multi-tab desktop application built with Python and [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter). Designed for music enthusiasts and Private Tracker (PT) users on sites like **Redacted (RED)** and **Orpheus (OPS)**, it provides a complete workflow — from discovering 24-bit FLAC torrents to downsampling, spectrogram verification, quality auditing, and automated seeding.

### ✨ Key Features

| Tab | Feature | Description |
|-----|---------|-------------|
| 🔍 **Search** | 24-bit FLAC Finder | Discover and filter 24-bit FLAC torrents via Redacted / OPS API |
| 🔽 **Downsample** | FLAC Batch Converter | Convert 24-bit FLAC → 16-bit/44.1kHz with automatic `.torrent` creation |
| 📊 **Check** | Lossless / Hi-Res Checker | Verify audio authenticity using SoX spectrograms |
| 🏅 **Audit** | Quality Audit | AI-powered audio quality scoring system |

---

### 🔍 Tab 1: 24-bit FLAC Finder

Automates the discovery and downloading of 24-bit FLAC torrents from Redacted (RED) and Orpheus (OPS).

- **Multi-site support**: Switch between RED and OPS with independent API keys and per-site configuration
- **Advanced filtering**:
  - Ignore lossy-approved / trumpable torrents
  - Bandcamp "Name Your Price" only mode
  - Filter by media type (CD, WEB, Vinyl, SACD, etc.)
  - Filter by release type (Album, EP, Single, Soundtrack, Compilation, etc.)
  - Year range, max file size, minimum seeders, exclude zero-snatch torrents
- **Smart search**: Automatic pagination with intelligent page-splitting by release type / media / sort order when results exceed limits
- **Buffer protection**: Configurable buffer formula and safety limit — stops downloading when buffer drops below threshold
- **Freeleech token support**: Automatically uses FL tokens for torrents exceeding a configurable size threshold
- **Auto-download**: Directly download matched `.torrent` files to a specified directory
- **Result caching**: Avoids re-processing previously seen torrents across sessions

### 🔽 Tab 2: FLAC Downsampler & Torrent Creator

Batch-processes directories of 24-bit FLAC albums for PT seeding.

- **Concurrent processing**: Multi-threaded FFmpeg conversion (configurable thread count)
- **Intelligent downsampling**: 24-bit → 16-bit with sample rate conversion to 44.1kHz/48kHz as needed
- **Metadata preservation**: All FLAC tags and embedded cover art are retained
- **Automatic torrent creation**: Generates PT-compliant `.torrent` files using `torf` with correct tracker announce URL and source tag
- **Folder scanning**: Recursively discovers albums from a root directory
- **Skip logic**: Automatically skips albums that are already 16-bit

### 📊 Tab 3: Lossless / Hi-Res Checker

Generates and analyzes audio spectrograms to determine audio authenticity.

- **SoX-powered spectrogram generation**: Creates detailed frequency analysis images for each track
- **Automatic stitching**: Combines individual track spectrograms into a single panoramic album image for easy reporting
- **Intelligent analysis**: Detects frequency cutoff points to classify audio as:
  - ✅ True Lossless
  - ⚠️ Fake Lossless (lossy source transcoded to FLAC)
  - ⚠️ Fake Hi-Res (upsampled from 16-bit/44.1kHz)
- **Batch processing**: Analyze entire albums at once
- **Visual output**: Generated spectrograms can be saved for upload to PT forums

### 🏅 Tab 4: Quality Audit

Modular, plugin-based audio quality risk assessment framework with a 0–100 scoring system.

- **10 built-in risk rules** (plugin architecture — zero-registration auto-discovery):
  - Frequency cutoff analysis (22kHz threshold)
  - Fake Hi-Res detection (upsampled content)
  - MP3 transcode artifact detection (128k/192k/256k/320k signature frequencies)
  - Spectrogram gap detection
  - Suspicious channel similarity (identical L/R channels)
  - Sharp high-frequency rolloff detection
  - Bitrate anomaly detection
  - AccurateRip verification failure
  - Missing rip log penalty (CD sources)
  - WEB source trust bonus
- **EAC / XLD log analysis**: Parses ripping logs, deducts points for insecure read mode, offset errors, CRC mismatches, read errors, etc.
- **Duplicate & trump detection**: Compares against existing releases by format, bitrate, source, log quality, and bit depth
- **BBCode description generator**: Auto-generates formatted upload descriptions with risk notices and spectrogram embeds
- **Feature caching**: MD5-based cache for extracted audio features (configurable TTL)
- **Risk levels**: SAFE → LOW_RISK → SUSPICIOUS → HIGH_RISK → LIKELY_TRANSCODE
- **Per-rule breakdown**: Color-coded display of each triggered rule with score delta and explanation

### 🔄 Automation Pipeline

The integrated **Pipeline Manager** connects all tabs into a fully automated workflow:

```
Search → Download → qBittorrent → Convert (24bit→16bit) → Check (Spectrogram) → Create Torrent → Seed
```

- **qBittorrent integration**: Monitors download completion via qBittorrent Web API
- **Automatic chaining**: When a download completes, automatically triggers conversion and spectrogram checking
- **Manual confirmation**: Optionally prompts for manual review before proceeding to upload
- **Background operation**: Pipeline runs in a separate thread, allowing you to continue using the app

---

### ⚙️ Installation

#### Method 1: Standalone Executable (Recommended for Windows)

1. Download `RedactedAudioToolbox.exe` from the [Releases](https://github.com/whn2000/RedactedAudioToolbox/releases) page
2. Double-click to run — no Python installation required!
3. On first launch, the built-in **Dependency Manager** will automatically download and configure `ffmpeg` and `sox` for you

#### Method 2: Run from Source

**Prerequisites:**
- Python 3.8+
- Windows OS (DPI awareness and some path handling are Windows-specific)

```bash
# 1. Clone the repository
git clone https://github.com/whn2000/RedactedAudioToolbox.git
cd RedactedAudioToolbox

# 2. Install Python dependencies
pip install requests pillow torf customtkinter

# 3. Run the application
python main.py
```

**External dependencies** (auto-managed on first run):
- [FFmpeg](https://ffmpeg.org/) — audio conversion
- [SoX](https://sox.sourceforge.net/) — spectrogram generation

---

### 🛠️ Configuration

All settings are persisted in `config.json` in the application directory.

#### Configuration Structure

```jsonc
{
  "site": "RED",                    // Active site: "RED" or "OPS"
  "global": {
    "qb_host": "http://127.0.0.1", // qBittorrent Web UI host
    "qb_port": "8080",             // qBittorrent Web UI port
    "qb_user": "admin",            // qBittorrent username
    "qb_pass": "adminadmin",       // qBittorrent password
    "enable_pipeline": false        // Enable automation pipeline
  },
  "sites": {
    "RED": {
      "api_key": "",               // RED API key (Settings → API Keys → New Key)
      "save_path": "",             // Torrent file save directory
      "buffer_formula": "(U / 0.65) - D", // Buffer calculation formula
      "media": "CD",               // Media filter
      "year_latest": "2025",       // End year for search
      "year_earliest": "1970",     // Start year for search
      "number": "50",              // Target number of torrents to find
      "max_size": "2048",          // Max torrent size (MB)
      "order_by": "time",          // Sort order: time/size/snatched/seeders/random
      "ignore_lossy": false,       // Skip lossy-approved torrents
      "ignore_16bit": false,       // Skip torrents that already have a 16-bit version
      "ignore_trumpable": false,   // Skip trumpable torrents
      "auto_download": false,      // Auto-download matched .torrent files
      "use_fl_token": false,       // Auto-use freeleech tokens
      "fl_token_threshold": "500", // FL token size threshold (MB)
      "request_interval": "3.0"    // API request interval (seconds)
      // ... release type filters, etc.
    },
    "OPS": {
      // Same structure as RED, with independent settings
    }
  }
}
```

#### Buffer Formula

The buffer formula uses three variables:
- `U` — Total uploaded bytes
- `D` — Total downloaded bytes
- `R` — Required ratio

Default formulas:
- RED: `(U / 0.65) - D`
- OPS: `(U / 1.2) - D`

---

### 🌐 Internationalization (i18n)

The application fully supports **Chinese (zh_CN)** and **English (en_US)** interfaces. Switch languages anytime from the menu bar: **Language → 中文 / English**.

---

### 📁 Project Structure

```
RedactedAudioToolbox/
├── main.py                 # Application entry point & tab manager
├── elitetmhelper2.py       # 24-bit FLAC Finder (search tab core logic + GUI)
├── flac_downsampler.py     # FLAC downsampler & torrent creator (GUI + logic)
├── lossless_checker.py     # Lossless/Hi-Res spectrogram checker (GUI + logic)
├── pipeline_manager.py     # Automation pipeline (download → convert → check → seed)
├── qbittorrent_client.py   # qBittorrent Web API client
├── push_to_qb.py           # Torrent push utility
├── dependency_manager.py   # Auto-download ffmpeg & sox on first run
├── i18n.py                 # Internationalization (zh_CN / en_US)
├── config.json             # User configuration (auto-generated)
├── gui/
│   └── audit_tab.py        # Quality Audit tab GUI
├── quality/                # Modular audio quality audit framework
│   ├── models.py           # Data models (RiskLevel, AudioFeatures, RiskReport, etc.)
│   ├── config.py           # Scoring thresholds & rule configuration
│   ├── cli.py              # CLI interface (risk / log / dedup / describe / audit)
│   ├── features/           # Feature extraction layer
│   │   ├── extractor.py    # Unified feature pipeline with caching
│   │   ├── spectrogram.py  # SoX spectrogram analysis (cutoff, gaps, HF energy)
│   │   ├── audio_stats.py  # ffprobe metadata & fake Hi-Res / MP3 scoring
│   │   └── channel_analysis.py  # L/R channel similarity detection
│   ├── risk/               # Risk scoring engine
│   │   ├── engine.py       # Score normalization & level classification
│   │   ├── base.py         # Abstract base rule class
│   │   ├── registry.py     # Auto-discovery plugin registry
│   │   └── rules/          # 10 pluggable risk rule modules
│   ├── log_parser/         # EAC / XLD rip log analysis
│   ├── dedup/              # Duplicate & trump detection
│   ├── description/        # BBCode upload description generator
│   └── cache/              # MD5-based feature caching
├── dataset/                # Test data for quality models
├── bin/                    # Auto-downloaded ffmpeg & sox binaries
└── RedactedAudioToolbox.spec  # PyInstaller build spec
```

---

### ⚠️ Disclaimer

> [!WARNING]
> **The detection and scoring features provided by this tool (including but not limited to lossless/Hi-Res verification, quality audit scoring, risk level assessment, and EAC/XLD log analysis) are for reference purposes only and DO NOT constitute a definitive or authoritative judgment of audio quality.**

- **No universal applicability**: The spectrogram analysis and rule-based scoring algorithms rely on heuristic methods and predefined thresholds. They may produce **false positives** (flagging genuine lossless as fake) or **false negatives** (failing to detect actual transcodes) depending on the source material, mastering characteristics, and audio content.
- **Not a substitute for manual review**: Automated results should never be treated as the sole basis for determining whether a file is genuine lossless, fake lossless, or fake Hi-Res. **You must always perform your own manual verification** (e.g., visually inspecting spectrograms, cross-referencing with trusted sources) before uploading to any tracker.
- **User responsibility**: By using this tool, you acknowledge that **you are solely responsible** for the quality and authenticity of any content you upload. Uploading improperly verified content may violate tracker rules and result in warnings or account penalties.
- **No warranty**: This software is provided "as is" without any warranty of any kind. The authors are not liable for any consequences arising from reliance on the tool's automated analysis results.

---

### 🔒 Security Notes

- **API keys** are stored locally in `config.json`. Never commit this file to a public repository
- The `.gitignore` is pre-configured to exclude `config.json`, cache files, and binary dependencies
- API requests are rate-limited (configurable interval, default 3 seconds) to comply with tracker rules

---

### 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

### 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

### 🙏 Acknowledgments

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — Modern UI framework
- [FFmpeg](https://ffmpeg.org/) — Audio processing
- [SoX](https://sox.sourceforge.net/) — Sound eXchange & spectrogram generation
- [torf](https://github.com/rndusr/torf) — Torrent file creation
- [Redacted](https://redacted.sh/) & [Orpheus](https://orpheus.network/) — Music tracker APIs

---
---

<a name="-中文"></a>

## 🇨🇳 中文

**Redacted Audio Toolbox（Redacted 音乐工具箱）** 是一款功能丰富的多标签页桌面应用程序，基于 Python 和 [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) 构建。专为无损音乐爱好者和 PT（Private Tracker）用户设计，支持 **Redacted (RED)** 和 **Orpheus (OPS)** 站点，提供从发现 24-bit FLAC 种子到降采样、频谱验证、质量审计和自动做种的完整工作流。

### ✨ 核心功能

| 标签页 | 功能 | 说明 |
|--------|------|------|
| 🔍 **搜索** | 24-bit FLAC 搜索器 | 通过 Redacted / OPS API 发现和过滤 24-bit FLAC 种子 |
| 🔽 **降频** | FLAC 批量转换器 | 将 24-bit FLAC 转换为 16-bit/44.1kHz 并自动制种 |
| 📊 **检测** | 真假无损检测器 | 使用 SoX 频谱图验证音频真实性 |
| 🏅 **审计** | 质量审计 | AI 驱动的音频质量评分系统 |

---

### 🔍 标签页 1：24-bit FLAC 搜索器

自动化搜索和下载来自 Redacted (RED) 和 Orpheus (OPS) 的 24-bit FLAC 种子。

- **多站点支持**：在 RED 和 OPS 之间自由切换，各站点独立保存 API Key 和配置
- **高级过滤**：
  - 忽略 Lossy 批准 / 可被顶替（Trumpable）的种子
  - 仅限 Bandcamp "随意定价"（Name Your Price）专辑
  - 按媒体类型过滤（CD、WEB、Vinyl、SACD 等）
  - 按发行类型过滤（专辑、EP、单曲、原声带、合集等）
  - 年份范围、最大文件大小、最低做种人数、排除零下载量种子
- **智能搜索**：自动分页，当搜索结果超过限制时智能按发行类型 / 媒体类型 / 排序方式拆分搜索
- **Buffer 保护**：可自定义 Buffer 计算公式和安全阈值 — 当 Buffer 低于设定值时自动停止下载
- **免费令牌支持**：对超过指定大小阈值的种子自动使用 Freeleech Token
- **自动下载**：将匹配的 `.torrent` 文件直接下载到指定目录
- **结果缓存**：跨会话避免重复处理已查看过的种子

### 🔽 标签页 2：FLAC 批量降频与自动制种

批量处理 24-bit FLAC 专辑目录，为 PT 做种做准备。

- **并发处理**：多线程 FFmpeg 转换（可配置线程数）
- **智能降采样**：24-bit → 16-bit，根据需要进行 44.1kHz/48kHz 采样率转换
- **元数据保留**：所有 FLAC 标签和内嵌封面图完整保留
- **自动制种**：使用 `torf` 生成符合 PT 站点规范的 `.torrent` 文件，自动填写正确的 Tracker Announce URL 和 Source 标签
- **文件夹扫描**：从根目录递归发现所有专辑
- **跳过逻辑**：自动跳过已经是 16-bit 的专辑

### 📊 标签页 3：真假无损 / Hi-Res 频谱检测

生成并分析音频频谱图以判断音频真实性。

- **SoX 频谱图生成**：为每个音轨生成详细的频率分析图像
- **自动拼接**：将专辑内所有单曲的频谱图合成一张全景长图，方便上传论坛或保存为检测报告
- **智能分析**：检测高频截止点，将音频分类为：
  - ✅ 真无损（True Lossless）
  - ⚠️ 假无损（有损源转码为 FLAC）
  - ⚠️ 假 Hi-Res（从 16-bit/44.1kHz 升频）
- **批量处理**：一次分析整张专辑
- **可视化输出**：生成的频谱图可保存用于上传至 PT 论坛

### 🏅 标签页 4：质量审计

模块化、插件式的音频质量风险评估框架，采用 0–100 分评分体系。

- **10 条内置风险规则**（插件架构 — 零注册自动发现）：
  - 频率截止分析（22kHz 阈值）
  - 假 Hi-Res 检测（升频内容）
  - MP3 转码特征检测（128k/192k/256k/320k 特征频率）
  - 频谱图间隙检测
  - 可疑声道相似性检测（左右声道完全相同）
  - 高频急剧衰减检测
  - 码率异常检测
  - AccurateRip 校验失败
  - CD 源缺失抓取日志扣分
  - WEB 源信任加分
- **EAC / XLD 日志分析**：解析抓取日志，对不安全读取模式、偏移错误、CRC 不匹配、读取错误等进行扣分
- **重复 & 顶替检测**：按格式、码率、来源、日志质量和位深度与已有版本进行比较
- **BBCode 描述生成器**：自动生成格式化的上传描述，包含风险提示和频谱图嵌入
- **特征缓存**：基于 MD5 的音频特征缓存（可配置 TTL）
- **风险等级**：安全 → 低风险 → 可疑 → 高风险 → 疑似转码
- **逐条规则展示**：彩色显示每条触发规则的分值变化和详细说明

### 🔄 自动化流水线

内置的 **Pipeline Manager（流水线管理器）** 将所有标签页串联为全自动工作流：

```
搜索 → 下载 → qBittorrent → 转换 (24bit→16bit) → 频谱检测 → 自动制种 → 做种
```

- **qBittorrent 集成**：通过 qBittorrent Web API 监控下载完成状态
- **自动衔接**：下载完成后自动触发格式转换和频谱检测
- **手动确认**：可选在上传前弹出对话框供人工审核
- **后台运行**：流水线在独立线程中运行，不影响应用正常使用

---

### ⚙️ 安装指南

#### 方法一：独立运行程序（推荐 Windows 用户使用）

1. 从 [Releases](https://github.com/whn2000/RedactedAudioToolbox/releases) 页面下载 `RedactedAudioToolbox.exe`
2. 双击即可运行 — 无需安装 Python 环境！
3. 首次启动时，内置的**智能环境依赖管理器**会自动下载并配置 `ffmpeg` 和 `sox`

#### 方法二：通过源码运行

**前置要求：**
- Python 3.8+
- Windows 操作系统（DPI 感知和部分路径处理为 Windows 特定）

```bash
# 1. 克隆代码仓库
git clone https://github.com/whn2000/RedactedAudioToolbox.git
cd RedactedAudioToolbox

# 2. 安装 Python 依赖库
pip install requests pillow torf customtkinter

# 3. 运行主程序
python main.py
```

**外部依赖**（首次运行时自动管理）：
- [FFmpeg](https://ffmpeg.org/) — 音频转换
- [SoX](https://sox.sourceforge.net/) — 频谱图生成

---

### 🛠️ 配置说明

所有设置保存在应用目录下的 `config.json` 中。

#### 配置结构

```jsonc
{
  "site": "RED",                    // 当前活跃站点："RED" 或 "OPS"
  "global": {
    "qb_host": "http://127.0.0.1", // qBittorrent Web UI 主机地址
    "qb_port": "8080",             // qBittorrent Web UI 端口
    "qb_user": "admin",            // qBittorrent 用户名
    "qb_pass": "adminadmin",       // qBittorrent 密码
    "enable_pipeline": false        // 启用自动化流水线
  },
  "sites": {
    "RED": {
      "api_key": "",               // RED API 密钥（设置 → API Keys → 新建密钥）
      "save_path": "",             // 种子文件保存目录
      "buffer_formula": "(U / 0.65) - D", // Buffer 计算公式
      "media": "CD",               // 媒体类型过滤
      "year_latest": "2025",       // 搜索结束年份
      "year_earliest": "1970",     // 搜索起始年份
      "number": "50",              // 目标搜索数量
      "max_size": "2048",          // 最大种子大小（MB）
      "order_by": "time",          // 排序方式：time/size/snatched/seeders/random
      "ignore_lossy": false,       // 跳过 Lossy 批准的种子
      "ignore_16bit": false,       // 跳过已有 16-bit 版本的种子
      "ignore_trumpable": false,   // 跳过可被顶替的种子
      "auto_download": false,      // 自动下载匹配的 .torrent 文件
      "use_fl_token": false,       // 自动使用免费令牌
      "fl_token_threshold": "500", // 免费令牌触发大小阈值（MB）
      "request_interval": "3.0"    // API 请求间隔（秒）
      // ... 发行类型过滤器等
    },
    "OPS": {
      // 与 RED 结构相同，独立配置
    }
  }
}
```

#### Buffer 计算公式

公式中可使用以下变量：
- `U` — 总上传字节数
- `D` — 总下载字节数
- `R` — 需求比率（Required Ratio）

默认公式：
- RED：`(U / 0.65) - D`
- OPS：`(U / 1.2) - D`

---

### 🌐 国际化 (i18n)

应用完整支持**中文 (zh_CN)** 和**英文 (en_US)** 界面。随时通过菜单栏切换语言：**语言 → 中文 / English**。

---

### 📁 项目结构

```
RedactedAudioToolbox/
├── main.py                 # 应用入口 & 标签页管理器
├── elitetmhelper2.py       # 24-bit FLAC 搜索器（搜索标签页核心逻辑 + GUI）
├── flac_downsampler.py     # FLAC 降频器 & 制种工具（GUI + 逻辑）
├── lossless_checker.py     # 真假无损频谱检测器（GUI + 逻辑）
├── pipeline_manager.py     # 自动化流水线（下载 → 转换 → 检测 → 做种）
├── qbittorrent_client.py   # qBittorrent Web API 客户端
├── push_to_qb.py           # 种子推送工具
├── dependency_manager.py   # 首次运行自动下载 ffmpeg & sox
├── i18n.py                 # 国际化（zh_CN / en_US）
├── config.json             # 用户配置（自动生成）
├── gui/
│   └── audit_tab.py        # 质量审计标签页 GUI
├── quality/                # 模块化音频质量审计框架
│   ├── models.py           # 数据模型（RiskLevel、AudioFeatures、RiskReport 等）
│   ├── config.py           # 评分阈值 & 规则配置
│   ├── cli.py              # CLI 命令行接口（risk / log / dedup / describe / audit）
│   ├── features/           # 特征提取层
│   │   ├── extractor.py    # 统一特征管线（带缓存）
│   │   ├── spectrogram.py  # SoX 频谱分析（截止频率、间隙、高频能量）
│   │   ├── audio_stats.py  # ffprobe 元数据 & 假 Hi-Res / MP3 评分
│   │   └── channel_analysis.py  # 左右声道相似度检测
│   ├── risk/               # 风险评分引擎
│   │   ├── engine.py       # 分数归一化 & 等级分类
│   │   ├── base.py         # 抽象基础规则类
│   │   ├── registry.py     # 自动发现插件注册表
│   │   └── rules/          # 10 个可插拔风险规则模块
│   ├── log_parser/         # EAC / XLD 抓取日志分析
│   ├── dedup/              # 重复 & 顶替检测
│   ├── description/        # BBCode 上传描述生成器
│   └── cache/              # 基于 MD5 的特征缓存
├── dataset/                # 模型训练数据
├── bin/                    # 自动下载的 ffmpeg & sox 二进制文件
└── RedactedAudioToolbox.spec  # PyInstaller 打包配置
```

---

### ⚠️ 免责声明

> [!WARNING]
> **本工具提供的检测与评分功能（包括但不限于真假无损/Hi-Res 检测、质量审计评分、风险等级评估、EAC/XLD 日志分析）仅供参考，不构成对音频质量的权威或最终判定。**

- **不具有普适性**：频谱分析和基于规则的评分算法依赖于启发式方法和预设阈值。由于音源素材、母带处理方式和音频内容的差异，可能产生**误报**（将真正的无损标记为假无损）或**漏报**（未能检出实际的转码文件）。
- **不能替代人工审核**：自动化检测结果绝不应作为判断文件是否为真无损、假无损或假 Hi-Res 的唯一依据。**在上传到任何 Tracker 之前，您必须自行进行人工核验**（例如：目视检查频谱图、与可信来源交叉比对等）。
- **用户责任**：使用本工具即表示您确认并同意，**您对上传内容的质量和真实性承担全部责任**。上传未经充分验证的内容可能违反 Tracker 规则，导致警告或账号处罚。
- **无担保声明**：本软件按「现状」提供，不附带任何形式的担保。作者不对因依赖本工具自动化分析结果而产生的任何后果承担责任。

---

### 🔒 安全须知

- **API 密钥** 存储在本地 `config.json` 文件中，切勿将此文件提交到公开仓库
- `.gitignore` 已预配置排除 `config.json`、缓存文件和二进制依赖
- API 请求速率受限（可配置间隔，默认 3 秒），以遵守 Tracker 规则

---

### 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 发起 Pull Request

---

### 📄 许可证

本项目使用 MIT 许可证 — 详见 [LICENSE](LICENSE) 文件。

---

### 🙏 致谢

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — 现代 UI 框架
- [FFmpeg](https://ffmpeg.org/) — 音频处理
- [SoX](https://sox.sourceforge.net/) — 声音处理 & 频谱图生成
- [torf](https://github.com/rndusr/torf) — 种子文件创建
- [Redacted](https://redacted.sh/) & [Orpheus](https://orpheus.network/) — 音乐 Tracker API

---

<p align="center">
  Built with ❤️ for the audiophile community / 为无损音乐爱好者社区倾心打造
</p>
