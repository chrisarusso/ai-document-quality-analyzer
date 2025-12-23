"""Document text extractors."""

from .google_slides import GoogleSlidesExtractor
from .google_docs import GoogleDocsExtractor

__all__ = ["GoogleSlidesExtractor", "GoogleDocsExtractor"]
