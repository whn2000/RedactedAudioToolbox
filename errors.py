"""
Unified error hierarchy for RedactedAudioToolbox.
All business modules MUST use exceptions defined here.
"""


class RedactedToolboxError(Exception):
    """Base class for all custom exceptions."""
    pass


# ── Network & API ──────────────────────────────────────────────

class APIError(RedactedToolboxError):
    """API request errors."""
    def __init__(self, message, status_code=None, response_body=None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class RateLimitError(APIError):
    """API rate limit exceeded."""
    pass


class AuthError(APIError):
    """Authentication failure (invalid API key, expired cookie, etc)."""
    pass


class NetworkError(RedactedToolboxError):
    """Network level errors (timeout, DNS failure, etc)."""
    pass


# ── Search ─────────────────────────────────────────────────────

class SearchError(RedactedToolboxError):
    """Search process errors."""
    pass


class SearchAbortedError(SearchError):
    """Search manually aborted by user."""
    pass


class NoResultsError(SearchError):
    """No results found."""
    pass


# ── Download ───────────────────────────────────────────────────

class DownloadError(RedactedToolboxError):
    """Download torrent/file errors."""
    pass


class DownloadFailedError(DownloadError):
    """Download request failed (HTTP non-200)."""
    def __init__(self, message, status_code=None):
        self.status_code = status_code
        super().__init__(message)


class DownloadAuthError(DownloadError):
    """Download authentication failure."""
    pass


# ── Pipeline ───────────────────────────────────────────────────

class PipelineError(RedactedToolboxError):
    """Pipeline processing errors."""
    pass


class PipelineStepError(PipelineError):
    """Specific step failure in pipeline."""
    def __init__(self, step_name: str, message: str, cause: Exception = None):
        self.step_name = step_name
        self.cause = cause
        detail = f" [{cause}]" if cause else ""
        super().__init__(f"[{step_name}] {message}{detail}")


class DownsampleError(PipelineError):
    """Downsample processing failed."""
    pass


class LosslessCheckError(PipelineError):
    """Lossless check failed."""
    pass


class No16BitFolderError(PipelineError):
    """Downsample did not generate 16bit folder."""
    pass


class MetadataNotFoundError(PipelineError):
    """Metadata JSON not found for auto upload."""
    pass


class TorrentGenerationError(PipelineError):
    """Torrent file generation failed."""
    pass


# ── Upload ─────────────────────────────────────────────────────

class UploadError(RedactedToolboxError):
    """Torrent upload errors."""
    pass


class UploadAPIError(UploadError):
    """API returned failure status."""
    def __init__(self, message, response=None):
        self.response = response
        super().__init__(message)


class UploadHTTPError(UploadError):
    """HTTP request failed."""
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body[:200] if body else 'Unknown'}")


class RiskBlockedError(UploadError):
    """Upload blocked by risk audit system."""
    def __init__(self, risk_level: str, score: float):
        self.risk_level = risk_level
        self.score = score
        super().__init__(f"Upload blocked by risk system: level={risk_level}, score={score}")


# ── Config ─────────────────────────────────────────────────────

class ConfigError(RedactedToolboxError):
    """Configuration errors."""
    pass


class ConfigValidationError(ConfigError):
    """Configuration validation failed."""
    pass


class ConfigMigrationError(ConfigError):
    """Config migration failed."""
    pass


# ── Cache ──────────────────────────────────────────────────────

class CacheError(RedactedToolboxError):
    """Cache related errors."""
    pass


class CacheCorruptedError(CacheError):
    """Cache data corrupted."""
    pass


# ── Quality Check ─────────────────────────────────────────────

class QualityCheckError(RedactedToolboxError):
    """Quality check process errors."""
    pass


class AudioAnalysisError(QualityCheckError):
    """Audio analysis failed."""
    def __init__(self, file_path: str, message: str, cause: Exception = None):
        self.file_path = file_path
        self.cause = cause
        detail = f" [{cause}]" if cause else ""
        super().__init__(f"Audio analysis failed for '{file_path}': {message}{detail}")

