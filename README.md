# Redacted Audio Toolbox / Redacted 音乐工具箱
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
[English Version](#english) | [中文版本](#chinese)
---
<a name="english"></a>
## 🇬🇧 English
**Redacted Audio Toolbox** is a unified, 3-in-1 desktop application built with Python and Tkinter, designed specifically for music enthusiasts and Private Tracker (PT) users (like Redacted/OPS). It streamlines the process of discovering, validating, and preparing high-quality FLAC audio files.
### 🌟 Features
1. **Redacted 24bit FLAC Finder**: 
   - Automates the searching and filtering of 24-bit FLAC torrents via the Redacted API.
   - Supports advanced filters (ignore lossy approved, ignore trumpable, NYP Bandcamp only, etc.).
   - Auto-downloads `.torrent` files for matched releases.
2. **FLAC Downsampler & Torrent Creator**: 
   - Batch processes directories of 24-bit FLAC albums, concurrently downsampling them to 16-bit/44.1kHz using FFmpeg.
   - Preserves all metadata and cover art.
   - Automatically generates PT-compliant `.torrent` files for the converted albums using `torf`.
3. **Lossless Audio / Hi-Res Checker**: 
   - Generates and analyzes audio spectrograms using SoX to determine if a track is true lossless, fake lossless, or fake Hi-Res based on frequency cutoffs.
   - Automatically stitches individual track spectrograms into a single, long album image for easy reporting.
### ⚙️ Installation & Usage
**Method 1: Use the Standalone Executable (Windows Only)**
- Simply download the compiled `RedactedAudioToolbox.exe` from the Releases page.
- Double-click to run. No Python installation required!
- **Note**: The app features an intelligent Dependency Manager. On its first run, if `ffmpeg` and `sox` are missing, it will automatically download and configure them for you.
**Method 2: Run from Source**
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/redacted-audio-toolbox.git
   cd redacted-audio-toolbox
   ```
2. Install the required Python packages:
   ```bash
   pip install requests pillow torf
   ```
3. Run the application:
   ```bash
   python main.py
   ```
---
<a name="chinese"></a>
## 🇨🇳 中文
**Redacted 音乐工具箱** 是一个基于 Python 和 Tkinter 构建的三合一桌面级应用程序。专为无损音乐爱好者和 PT（Private Tracker，如 Redacted/OPS）用户设计，旨在简化高质量 FLAC 音频的发现、验证和制种流程。
### 🌟 核心功能
1. **Redacted 24bit FLAC 搜索器**: 
   - 通过 Redacted API 自动化搜索、过滤和抓取 24-bit 高清无损种子。
   - 支持高级过滤选项（例如：忽略 Lossy 批准、忽略可被顶替(Trumpable)的种子、仅限 Bandcamp 免费专辑等）。
   - 支持命中目标后自动下载 `.torrent` 种子文件。
2. **FLAC 批量降频与自动制种**: 
   - 批量扫描包含多张 24-bit 专辑的文件夹。
   - 利用并发线程和 FFmpeg 将 24-bit 无损音频降采样至标准的 16-bit/44.1kHz，同时完美保留所有元数据标签和封面图。
   - 使用 `torf` 为降频后的文件夹自动生成符合 PT 站点规范的 `.torrent` 文件。
3. **真假无损及 Hi-Res 频谱检测**: 
   - 调用 SoX 提取音频频谱图，并通过分析高频信号的截止频率，智能判断音频是“真无损”、“假无损”还是“假 Hi-Res（升频）”。
   - 检测完毕后，自动将专辑内所有单曲的频谱图拼接成一张完整的长图，方便您上传至论坛或保存为检测报告。
### ⚙️ 安装与使用
**方法一：使用独立运行程序 (仅限 Windows)**
- 直接从 Releases 页面下载打包好的 `RedactedAudioToolbox.exe`。
- 双击即可运行，无需安装 Python 环境！
- **特色**：软件内置了智能环境依赖管理器。首次运行时，如果您的电脑没有配置 `ffmpeg` 或 `sox` 环境，它会自动联网下载、解压并配置好一切。
**方法二：通过源码运行**
1. 克隆代码仓库：
   ```bash
   git clone https://github.com/yourusername/redacted-audio-toolbox.git
   cd redacted-audio-toolbox
   ```
2. 安装必要的 Python 依赖库：
   ```bash
   pip install requests pillow torf
   ```
3. 运行主程序：
   ```bash
   python main.py
   ```
---
*Built with ❤️ for the audiophile community.*
