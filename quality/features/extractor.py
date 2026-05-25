"""
Unified feature extractor.

Orchestrates all feature extraction submodules (spectrogram, audio_stats,
channel_analysis) to produce a single AudioFeatures dataclass. This is the
only entry point that rules and the risk engine should use.
"""

from __future__ import annotations

import logging
from pathlib import Path

from quality.features.audio_stats import (
    compute_fake_hires_score,
    compute_mp3_signature_score,
    get_audio_metadata,
)
from quality.features.channel_analysis import compute_channel_similarity
from quality.features.spectrogram import (
    extract_spectrogram_features,
    get_audio_specs,
)
from quality.models import AudioFeatures

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """Unified audio feature extraction pipeline.

    Extracts all AudioFeatures from a single audio file or a directory
    of audio files. Delegates to specialized submodules and aggregates
    results into an AudioFeatures dataclass.

    Usage::

        extractor = FeatureExtractor()
        features = extractor.extract_file(Path("track.flac"))
        features = extractor.extract_album(Path("/album/"))
    """

    AUDIO_EXTENSIONS: frozenset[str] = frozenset({
        ".flac", ".wav", ".ape", ".alac", ".m4a", ".mp3", ".ogg", ".wv",
    })

    def extract_file(
        self,
        file_path: Path,
        work_dir: Path | None = None,
    ) -> AudioFeatures:
        """Extract all features from a single audio file with caching."""
        # 1. 尝试从缓存中极速读取
        from quality.cache.feature_cache import FeatureCache
        cache = FeatureCache()
        cached = cache.get_cached_features(file_path)
        if cached is not None:
            logger.info("Cache hit for: %s", file_path.name)
            return cached

        logger.info("Extracting features for: %s", file_path.name)
        features = AudioFeatures()

        # 1. Spectrogram-based features
        spec_result = extract_spectrogram_features(file_path, work_dir)
        features.cutoff_freq = spec_result.get("cutoff_freq")
        features.hf_energy_ratio = spec_result.get("hf_energy_ratio")
        features.spectrogram_gap_detected = spec_result.get(
            "spectrogram_gap_detected", False
        )
        features.hf_rolloff_smoothness = spec_result.get("hf_rolloff_smoothness")

        # 2. Audio metadata
        meta = get_audio_metadata(file_path)
        features.avg_bitrate_kbps = meta.get("avg_bitrate_kbps")

        bit_depth = meta.get("bit_depth")
        sample_rate = meta.get("sample_rate")

        # Fallback to soxi if ffprobe didn't provide specs
        if bit_depth is None or sample_rate is None:
            soxi_bd, soxi_sr = get_audio_specs(file_path)
            if bit_depth is None:
                bit_depth = soxi_bd
            if sample_rate is None:
                sample_rate = soxi_sr

        # 3. Composite scores
        features.fake_hires_score = compute_fake_hires_score(
            bit_depth, sample_rate, features.cutoff_freq
        )
        features.mp3_signature_score = compute_mp3_signature_score(
            features.cutoff_freq,
            features.hf_rolloff_smoothness,
            features.avg_bitrate_kbps,
        )

        # 4. Channel similarity
        features.channel_similarity = compute_channel_similarity(file_path)

        logger.info(
            "Features extracted for %s: cutoff=%.1f, hf_ratio=%s, gap=%s",
            file_path.name,
            features.cutoff_freq or 0,
            features.hf_energy_ratio,
            features.spectrogram_gap_detected,
        )
        
        # 5. 存储计算完毕的结果到缓存
        cache.save_cached_features(file_path, features)
        return features

    def extract_album(
        self,
        album_dir: Path,
        work_dir: Path | None = None,
    ) -> AudioFeatures:
        """Extract aggregated features for an album directory.

        Analyzes all audio files in the directory and returns a
        single AudioFeatures representing the worst-case (most risky)
        characteristics found across all tracks.

        Args:
            album_dir: Path to a directory containing audio files.
            work_dir: Optional working directory for temporary files.

        Returns:
            Aggregated AudioFeatures instance.
        """
        audio_files = self._find_audio_files(album_dir)
        if not audio_files:
            logger.warning("No audio files found in %s", album_dir)
            return AudioFeatures()

        logger.info("Extracting features for album: %s (%d tracks)", album_dir.name, len(audio_files))

        all_features: list[AudioFeatures] = []
        for f in audio_files:
            try:
                feat = self.extract_file(f, work_dir)
                all_features.append(feat)
            except Exception as exc:
                logger.warning("Failed to extract features for %s: %s", f.name, exc)

        if not all_features:
            return AudioFeatures()

        return self._aggregate_features(all_features)

    def _find_audio_files(self, album_dir: Path) -> list[Path]:
        """Find all audio files in a directory recursively.

        Args:
            album_dir: Root directory to search.

        Returns:
            Sorted list of audio file paths.
        """
        files = [
            f
            for f in album_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in self.AUDIO_EXTENSIONS
        ]
        files.sort(key=lambda p: p.name)
        return files

    def _aggregate_features(self, features_list: list[AudioFeatures]) -> AudioFeatures:
        """Aggregate features from multiple tracks into album-level features.

        Uses worst-case (most risky) values: lowest cutoff, lowest HF ratio,
        highest similarity, etc.

        Args:
            features_list: List of per-track features.

        Returns:
            Aggregated AudioFeatures.
        """
        agg = AudioFeatures()

        # Cutoff: use minimum (worst case)
        cutoffs = [f.cutoff_freq for f in features_list if f.cutoff_freq is not None]
        if cutoffs:
            agg.cutoff_freq = min(cutoffs)

        # HF energy: use minimum (worst case)
        hf_ratios = [f.hf_energy_ratio for f in features_list if f.hf_energy_ratio is not None]
        if hf_ratios:
            agg.hf_energy_ratio = min(hf_ratios)

        # Gap: True if any track has a gap
        agg.spectrogram_gap_detected = any(f.spectrogram_gap_detected for f in features_list)

        # Channel similarity: use maximum (worst case = most similar)
        similarities = [f.channel_similarity for f in features_list if f.channel_similarity is not None]
        if similarities:
            agg.channel_similarity = max(similarities)

        # Fake Hi-Res: use maximum (worst case)
        fhr_scores = [f.fake_hires_score for f in features_list if f.fake_hires_score is not None]
        if fhr_scores:
            agg.fake_hires_score = max(fhr_scores)

        # MP3 signature: use maximum (worst case)
        mp3_scores = [f.mp3_signature_score for f in features_list if f.mp3_signature_score is not None]
        if mp3_scores:
            agg.mp3_signature_score = max(mp3_scores)

        # Rolloff smoothness: use maximum (worst case = sharpest)
        rolloffs = [f.hf_rolloff_smoothness for f in features_list if f.hf_rolloff_smoothness is not None]
        if rolloffs:
            agg.hf_rolloff_smoothness = max(rolloffs)

        # Bitrate: use average
        bitrates = [f.avg_bitrate_kbps for f in features_list if f.avg_bitrate_kbps is not None]
        if bitrates:
            agg.avg_bitrate_kbps = round(sum(bitrates) / len(bitrates), 1)

        return agg
