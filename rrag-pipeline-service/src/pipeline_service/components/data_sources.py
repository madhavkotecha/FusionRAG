from typing import Any

from .base import BaseComponent


class FileLoader(BaseComponent):
    """Stub: loads documents from a file path."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "documents": [
                {
                    "content": f"Mock content from {config.get('file_path', 'unknown')}",
                    "metadata": {"source": config.get("file_path", "unknown")},
                }
            ]
        }


class WebScraper(BaseComponent):
    """Stub: scrapes content from a web page."""

    async def execute(
        self, input_data: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "documents": [
                {
                    "content": f"Mock scraped content from {config.get('url', 'unknown')}",
                    "metadata": {"source": config.get("url", "unknown")},
                }
            ]
        }
