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

**Redacted Audio Toolbox** is a feature-rich, multi-tab desktop application built with Python and [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter). Designed for music enthusiasts and Private Tracker (PT) users on sites like **Redacted (RED)** and **Orpheus (OPS)**, it provides a complete workflow — from discovering 24-bit FLAC torrents to multi-format downsampling, spectrogram verification, EAC/XLD log auditing with PCM CRC matching, advanced MQA / wasted bits detection, and automated local or remote seeding.

### ✨ Key Features

| Tab | Feature | Description |
|-----|---------|-------------|
| 🔍 **Search** | 24-bit FLAC Finder | Discover and filter 24-bit FLAC torrents via Redacted / OPS API |
| 🔽 **Downsample** | Multi-Format Transcoder | Batch convert 24-bit FLAC → 16-bit FLAC / MP3 320k / MP3 V0 in one click |
| 📊 **Check** | Lossless & Log Auditor | Verify audio via SoX spectrograms, parse EAC/XLD logs, and match PCM CRC32 |
| 🏅 **Audit** | Quality Audit | AI-powered audio quality risk assessment scoring system |
| 🚀 **AAFS** | Advanced Feature Suite | Detect MQA syncwords and wasted bits upconvert anomalies |
| 🌐 **Seeding** | Client & Remote Support | Seed to qBittorrent / Transmission locally or to remote Seedbox via rclone |

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

---

### 🔽 Tab 2: FLAC Downsampler & Multi-Format Creator

Batch-processes directories of 24-bit FLAC albums for PT seeding with one-click multi-format support.

- **Multi-Format Selection**: Support choosing any combination of:
  - `16-bit FLAC` (standard downsampling with dither/resampling)
  - `MP3 320k` (high quality CBR MP3)
  - `MP3 V0` (high quality VBR MP3)
- **Concurrent processing**: Multi-threaded conversion (configurable thread count)
- **Metadata preservation**: All FLAC tags, embedded cover art, and comments are fully preserved
- **Automatic torrent creation**: Generates PT-compliant `.torrent` files using `torf` with correct tracker announce URL and source tag for each chosen format
- **Smart skip logic**: Automatically skips folders that are already 16-bit FLAC or already transcoded

---

### 📊 Tab 3: Lossless / Hi-Res Checker & Log Auditor

Generates audio spectrograms and parses ripping logs to determine authenticity.

- **SoX-powered spectrogram generation**: Creates detailed frequency analysis images for each track
- **Automatic stitching**: Combines individual track spectrograms into a single panoramic album image
- **Intelligent analysis**: Detects frequency cutoff points to classify audio as True Lossless, Fake Lossless (transcoded), or Fake Hi-Res (upsampled)
- **EAC / XLD Log parsing**:
  - Automatically scans for `.log` files in the album directory
  - Extracts and verifies rip log Checksum to check if the log has been modified/tampered with
  - Extracts individual track Test and Copy CRCs
- **PCM CRC32 Verification**:
  - Decodes FLAC audio tracks to raw 16-bit / 44.1kHz stereo PCM streams in the background
  - Calculates the raw PCM CRC32 hash and matches it track-by-track against the log
  - Confirms the audio data exactly matches the rip log

---

### 🏅 Tab 4: Quality Audit

Modular, plugin-based audio quality risk assessment framework with a 0–100 scoring system.

- **10 built-in risk rules** (plugin architecture — zero-registration auto-discovery):
  - Frequency cutoff analysis (22kHz threshold)
  - Fake Hi-Res detection (upsampled content)
  - MP3 transcode signature detection (128k/192k/256k/320k signature frequencies)
  - Spectrogram gap detection
  - Suspicious channel similarity (identical L/R channels)
  - Sharp high-frequency rolloff detection
  - Bitrate anomaly detection
  - AccurateRip verification failure
  - Missing rip log penalty (CD sources)
  - WEB source trust bonus
- **Duplicate & trump detection**: Compares against existing releases by format, bitrate, source, log quality, and bit depth
- **BBCode description generator**: Auto-generates formatted upload descriptions with risk notices and spectrogram embeds
- **Feature caching**: MD5-based cache for extracted audio features (configurable TTL)
- **Per-rule breakdown**: Color-coded display of each triggered rule with score delta and explanation

---

### 🚀 Tab 5 / AAFS: Advanced Audio Feature Suite

A specialized analytical layer to detect modern hidden anomalies in high-resolution audio.

- **MQA Syncword Detection**:
  - Decodes audio files and performs correlation analysis to scan for the MQA syncword marker (`0xbe1788`).
  - Identifies if a high-resolution FLAC file is actually MQA-encoded or contains MQA remnants.
- **Wasted Bits Upconvert Detection**:
  - Analyzes whether a 24-bit audio file contains "wasted bits" (i.e. the lower bits are padded with zeros).
  - Utilizes `flac -ac` (or native bitwise check) to detect files that were artificially upconverted from 16-bit to 24-bit without extra detail.

---

### 🌐 Cross-Seed & Remote Seeding Client Support

- **Seeding Client Integration**: Supports local injection into **qBittorrent** and **Transmission** client.
- **Remote Seeding (rclone)**:
  - Automates uploading the newly transcoded folder/torrent to a remote Seedbox via `rclone` subprocess calls.
  - Automatically adds the uploaded torrent to your remote client (qBittorrent/Transmission) for immediate seeding.

---

### ⚙️ Installation

#### Method 1: Standalone Executable (Recommended for Windows)

1. Download `RedactedAudioToolbox.exe` from the `release` folder (or Releases page)
2. Double-click to run — no Python installation required!
3. On first launch, the built-in **Dependency Manager** will automatically configure `ffmpeg` and `sox` for you

#### Method 2: Run from Source

**Prerequisites:**
- Python 3.8+
- Windows OS (DPI awareness and path handling are Windows-specific)

```bash
# 1. Clone the repository
git clone https://github.com/whn2000/RedactedAudioToolbox.git
cd RedactedAudioToolbox

# 2. Install dependencies
pip install requests pillow torf customtkinter soundfile numpy scipy transmission-rpc

# 3. Run the application
python main.py
```

---

### ⚠️ Disclaimer

> [!WARNING]
> **The detection and scoring features provided by this tool (including but not limited to lossless/Hi-Res verification, quality audit scoring, risk level assessment, and EAC/XLD log analysis) are for reference purposes only and DO NOT constitute a definitive or authoritative judgment of audio quality.**
> Always perform manual inspection before uploading.

---

### 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

### 🙏 Acknowledgments

This project is built upon and inspired by the following amazing open-source projects:

- **[smoked-salmon](https://github.com/smokin-salmon/smoked-salmon)**: An audio verification and seeding utility for PT users, from which we migrated the AAFS core, rip log parser, multi-format transcoding logic, and remote seeding client features.
- **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)**: Modern, customizable GUI library for Python Tkinter.
- **[numpy](https://github.com/numpy/numpy)**: Fundamental package for scientific computing, used for MQA syncword correlation.
- **[scipy](https://github.com/scipy/scipy)**: Python library for scientific and technical computing.
- **[librosa](https://github.com/librosa/librosa)**: Python package for music and audio analysis.
- **[soundfile](https://github.com/bastibe/python-soundfile)**: Audio library based on libsndfile, used for decoding audio to PCM streams.
- **[torf](https://github.com/rndusr/torf)**: High-level Python library for creating torrents.
- **[transmission-rpc](https://github.com/progressbar/transmission-rpc)**: Python client library for Transmission RPC.
- **[pillow](https://github.com/python-pillow/Pillow)**: Python Imaging Library, used for stitching track spectrograms.
- **[RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)**: Rapid fuzzy string matching.
- **[requests](https://github.com/psf/requests)**: Simple yet elegant HTTP library for Python.
- **[mutagen](https://github.com/quodlibet/mutagen)**: Python module to handle audio metadata.
- **[FFmpeg](https://ffmpeg.org/)**: A complete, cross-platform solution to convert audio.
- **[SoX (Sound eXchange)](https://sox.sourceforge.net/)**: The Swiss Army knife of sound processing, used for spectrogram generation.
- **[PyInstaller](https://github.com/pyinstaller/pyinstaller)**: Packages Python applications into standalone executables.

---
---

<a name="-中文"></a>

## 🇨🇳 中文

**Redacted Audio Toolbox（Redacted 音乐工具箱）** 是一款功能丰富的多标签页桌面应用程序，基于 Python 和 [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) 构建。专为无损音乐爱好者和 PT（Private Tracker）用户设计，支持 **Redacted (RED)** 和 **Orpheus (OPS)** 站点，提供从发现 24-bit FLAC 种子到多格式降采样、频谱验证、EAC/XLD 抓取日志校验与 PCM CRC32 还原比对、高级音频特征分析、以及自动化本地或远程做种的完整工作流。

### ✨ 核心功能

| 标签页 | 功能 | 说明 |
|--------|------|------|
| 🔍 **搜索** | 24-bit FLAC 搜索器 | 通过 Redacted / OPS API 发现和过滤 24-bit FLAC 种子 |
| 🔽 **降频** | 多格式一键转码 | 一键批量将 24-bit FLAC 转换为 16-bit FLAC / MP3 320k / MP3 V0 并制种 |
| 📊 **检测** | 日志校验与频谱检测 | 使用 SoX 频谱图验证音频，解析 EAC/XLD 日志并匹配真实 PCM CRC32 |
| 🏅 **审计** | 质量审计 | 模块化、可插拔的音频质量风险评估评分系统 |
| 🚀 **AAFS** | 高级特征套件 | 深度检测 MQA 编码标志和 Wasted Bits 虚假升频异常 |
| 🌐 **做种** | 客户端与远程支持 | 支持本地导入 qB / Transmission 做种，或通过 rclone 自动远程上传做种 |

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

---

### 🔽 标签页 2：FLAC 批量降频与多格式制种

批量处理 24-bit FLAC 专辑目录，为 PT 转码制种提供一键多格式解决方案。

- **多格式并行选择**：支持同时勾选任意组合：
  - `16-bit FLAC`（标准的降位深和抖动重采样）
  - `MP3 320k`（高品质 CBR MP3）
  - `MP3 V0`（高品质 VBR MP3）
- **并发处理**：多线程并发转换（可自定义线程数）
- **元数据保留**：完整保留所有 FLAC 标签、内嵌封面图和注释
- **自动制种**：使用 `torf` 生成符合 PT 规范的 `.torrent` 文件，为每个选中的格式生成独立文件夹及种子，自动填写 Tracker Announce URL 和 Source 标签
- **智能跳过**：自动跳过已经是 16-bit 或者是已经处理过的专辑文件夹

---

### 📊 标签页 3：真假无损检测 & 日志校验审计

生成并分析音频频谱图，并深度校验抓取日志以判断音频真实性。

- **SoX 频谱图生成**：为每个音轨生成详细的频率分析图像，并自动拼接为专辑全景长图
- **智能频谱分析**：检测高频截止点，将音频分类为真无损、假无损（有损转码）或假 Hi-Res（升频）
- **EAC / XLD 日志分析器**：
  - 自动查找专辑文件夹下的 `.log` 抓取日志
  - 解析并验证日志 Checksum 校验和，检测日志是否被非法篡改/修图
  - 提取每首音轨的 Test 和 Copy CRC
- **PCM CRC32 还原比对**：
  - 在后台自动将 FLAC 音轨解码为标准 16-bit / 44.1kHz 双声道无损 PCM 数据流
  - 实时计算各音轨的 PCM CRC32 值，并与日志中记录的 CRC 逐轨比对
  - 确保音频数据与原始 CD 抓取日志完全一致，排除“假抓取日志”

---

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
- **重复 & 顶替检测**：按格式、码率、来源、日志质量和位深度与已有版本进行比较
- **BBCode 描述生成器**：自动生成格式化的上传描述，包含风险提示和频谱图嵌入
- **特征缓存**：基于 MD5 的音频特征缓存（可配置 TTL）
- **逐条规则展示**：彩色显示每条触发规则的分值变化和详细说明

---

### 🚀 标签页 5 / AAFS：高级音频特征套件 (Advanced Audio Feature Suite)

用于识别高规格无损音乐中隐蔽技术特征和封装异常的专项分析模块。

- **MQA 标志同步字检测**：
  - 读取音轨数据并执行互相关计算，检测是否存在 MQA 同步字标志（`0xbe1788`）。
  - 识别出实际为 MQA 编码或带有 MQA 残留的 FLAC 文件，方便用户识别其真实的母带来源。
- **Wasted Bits 虚假高位深检测**：
  - 分析 24-bit 音频的底部位深是否为空白（全零）。
  - 借由 `flac -ac` (或原生位逻辑校验) 检测虚假高位深升频（Wasted Bits Upconvert），验证音轨是否只是由 16-bit 简单填充而成。

---

### 🌐 跨站做种与远程做种支持

- **多客户端支持**：支持本地 qBittorrent 和 **Transmission** 做种客户端接入。
- **rclone 远程做种**：
  - 在本地完成转码和制种后，自动调用系统 `rclone` 命令将转码数据包和种子文件同步到远程 Seedbox 服务器。
  - 自动将种子推送到远程种子客户端（qB/Transmission）并自动开始做种。

---

### ⚙️ 安装指南

#### 方法一：独立运行程序（推荐 Windows 用户使用）

1. 从项目 `release` 文件夹中下载 `RedactedAudioToolbox.exe`
2. 双击即可运行 — 无需安装 Python 环境！
3. 首次启动时，内置的环境依赖管理器会自动配置好 `ffmpeg` 和 `sox`

#### 方法二：通过源码运行

**前置要求：**
- Python 3.8+
- Windows 操作系统（DPI 感知和路径处理为 Windows 特定）

```bash
# 1. 克隆代码仓库
git clone https://github.com/whn2000/RedactedAudioToolbox.git
cd RedactedAudioToolbox

# 2. 安装 Python 依赖库
pip install requests pillow torf customtkinter soundfile numpy scipy transmission-rpc

# 3. 运行主程序
python main.py
```

---

### ⚠️ 免责声明

> [!WARNING]
> **本工具提供的检测与评分功能（包括但不限于真假无损/Hi-Res 检测、质量审计评分、风险等级评估、EAC/XLD 日志分析、PCM CRC32 还原比对）仅供参考，不构成对音频质量的权威或最终判定。**
> 请在上传前配合人工频谱审查。

---

### 📄 许可证

本项目使用 MIT 许可证 — 详见 [LICENSE](LICENSE) 文件。

---

### 🙏 Acknowledgments / 致谢

This project is built upon and inspired by the following amazing open-source projects / 本项目基于以下优秀的开源项目构建或受其启发：

- **[smoked-salmon](https://github.com/smokin-salmon/smoked-salmon)**: An audio verification and seeding utility for PT users, from which we migrated the AAFS core, rip log parser, multi-format transcoding logic, and remote seeding client features / 优秀的 PT 音乐审计与转制种工具，本项目的高级音频特征分析（AAFS）、EAC/XLD 抓取日志校验、多格式转码逻辑以及远程做种支持均移植或参考自该项目。
- **[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)**: Modern, customizable GUI library for Python Tkinter / 现代化的 Tkinter 界面组件库。
- **[numpy](https://github.com/numpy/numpy)**: Fundamental package for scientific computing, used for MQA syncword correlation / 基础科学计算库，用于 MQA 同步字相关性分析。
- **[scipy](https://github.com/scipy/scipy)**: Python library for scientific and technical computing / 科学与信号处理库。
- **[librosa](https://github.com/librosa/librosa)**: Python package for music and audio analysis / 音乐及音频特征分析库。
- **[soundfile](https://github.com/bastibe/python-soundfile)**: Audio library based on libsndfile, used for decoding audio to PCM streams / 基于 libsndfile 的音频读写库，用于音轨的 PCM 解码与校验。
- **[torf](https://github.com/rndusr/torf)**: High-level Python library for creating torrents / 高级 Python 制种库，用于生成 PT 规范的种子。
- **[transmission-rpc](https://github.com/progressbar/transmission-rpc)**: Python client library for Transmission RPC / Transmission 远程客户端通信库。
- **[pillow](https://github.com/python-pillow/Pillow)**: Python Imaging Library, used for stitching track spectrograms / 图像处理库，用于拼接专辑频谱长图。
- **[RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)**: Rapid fuzzy string matching / 快速模糊字符串匹配库。
- **[requests](https://github.com/psf/requests)**: Simple yet elegant HTTP library for Python / Python HTTP 请求库。
- **[mutagen](https://github.com/quodlibet/mutagen)**: Python module to handle audio metadata / 音频元数据（FLAC/MP3 标签）读写模块。
- **[FFmpeg](https://ffmpeg.org/)**: A complete, cross-platform solution to convert audio / 跨平台音频转换引擎，用于音频降频与转码。
- **[SoX (Sound eXchange)](https://sox.sourceforge.net/)**: The Swiss Army knife of sound processing, used for spectrogram generation / 音频处理工具，用于生成高精度频谱图。
- **[PyInstaller](https://github.com/pyinstaller/pyinstaller)**: Packages Python applications into standalone executables / 将 Python 项目打包成独立可执行程序的工具。

---

<p align="center">
  Built with ❤️ for the audiophile community / 为无损音乐爱好者社区倾心打造
</p>
