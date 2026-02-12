"""LALInference Pipeline integration for Asimov."""

from .lalinference import LALInference

__all__ = ["LALInference"]

try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    from importlib_metadata import version, PackageNotFoundError

try:
    __version__ = version(__name__)
except PackageNotFoundError:
    __version__ = "unknown"
