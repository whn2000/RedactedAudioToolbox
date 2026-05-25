"""
Audio feature extraction layer.

Provides a unified FeatureExtractor that computes AudioFeatures from
audio files. Individual extraction tasks are delegated to specialized
submodules (spectrogram, audio_stats, channel_analysis).
"""

from quality.features.extractor import FeatureExtractor

__all__ = ["FeatureExtractor"]
