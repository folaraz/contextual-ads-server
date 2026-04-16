"""
Web crawler service for extracting content from URLs

Supports both sync and async crawling:
- crawl(): Synchronous crawling (trafilatura → selenium fallback)
- crawl_async(): Async crawling via aiohttp + trafilatura extraction
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from json import loads

import aiohttp
from trafilatura import fetch_url, extract
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


logger = logging.getLogger(__name__)


class WebCrawler:
    """Service for crawling and extracting content from web pages"""

    def __init__(self, user_agent: Optional[str] = None, headless: bool = True, timeout: int = 30):
        """
        Initialize web crawler

        Args:
            user_agent: User agent string for requests
            headless: Whether to run browser in headless mode
            timeout: Request timeout in seconds
        """
        self.user_agent = user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        self.headless = headless
        self.timeout = timeout

        # Setup Chrome options for fallback selenium scraping
        self.chrome_options = Options()
        if self.headless:
            self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument(f'--user-agent={self.user_agent}')

        logger.info("WebCrawler initialized")

    # as part of the crawl function, try to include images, videos and other media if possible for extraction as well.
    def crawl(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Crawl a URL and extract content

        Args:
            url: URL to crawl

        Returns:
            Dictionary with extracted content or None if failed
        """
        logger.info(f"Crawling URL: {url}")

        result = self._crawl_with_trafilatura(url)
        if result:
            return result

        logger.info(f"Trafilatura failed, trying Selenium for: {url}")
        result = self._crawl_with_selenium(url)
        return result

    def _crawl_with_trafilatura(self, url: str) -> Optional[Dict[str, Any]]:
        """Crawl using trafilatura (fast, lightweight)"""
        try:
            downloaded = fetch_url(url=url)
            if not downloaded:
                logger.warning(f"Failed to download content from {url}")
                return None

            # Extract content as JSON
            extracted = extract(
                downloaded,
                output_format="json",
                include_comments=False,
                include_images=False,
                include_links=False,
                with_metadata=True
            )

            if not extracted:
                logger.warning(f"Failed to extract content from {url}")
                return None

            data = loads(extracted)

            # Build content from available fields
            content_parts = []
            if data.get("title"):
                content_parts.append(data["title"])
            if data.get("description"):
                content_parts.append(data["description"])
            if data.get("raw_text"):
                content_parts.append(data["raw_text"])

            content = ". ".join(content_parts)

            result = {
                "url": data.get("source", url),
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "content": content,
                "image": data.get("image", ""),
                "date": data.get("date", ""),
                "tags": data.get("tags", "").split(", ") if data.get("tags") else [],
                "author": data.get("author", ""),
                "sitename": data.get("sitename", ""),
                "method": "trafilatura"
            }

            logger.info(f"Successfully crawled {url} with trafilatura")
            return result

        except Exception as e:
            logger.error(f"Error crawling {url} with trafilatura: {str(e)}")
            return None

    # todo need to comeback and improeve this function later
    def _crawl_with_selenium(self, url: str) -> Optional[Dict[str, Any]]:
        """Crawl using Selenium (slower, handles JS-heavy sites)"""
        driver = None
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.set_page_load_timeout(self.timeout)
            driver.get(url)

            # Try to extract title
            title = ""
            try:
                title = driver.title
            except:
                pass

            # Try to extract meta description
            description = ""
            try:
                meta_desc = driver.find_element("css selector", 'meta[name="description"]')
                description = meta_desc.get_attribute("content") or ""
            except:
                pass

            # Extract body text
            content = ""
            try:
                body = driver.find_element("tag name", "body")
                content = body.text
            except:
                pass

            # Try to extract image
            image = ""
            try:
                og_image = driver.find_element("css selector", 'meta[property="og:image"]')
                image = og_image.get_attribute("content") or ""
            except:
                pass

            result = {
                "url": url,
                "title": title,
                "description": description,
                "content": content,
                "image": image,
                "date": "",
                "tags": [],
                "author": "",
                "sitename": "",
                "method": "selenium"
            }

            logger.info(f"Successfully crawled {url} with Selenium")
            return result

        except Exception as e:
            logger.error(f"Error crawling {url} with Selenium: {str(e)}")
            return None

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    async def crawl_async(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Async crawl using aiohttp for fetch + trafilatura for extraction.
        Falls back to sync selenium in thread pool if aiohttp/trafilatura fails.
        """
        logger.info(f"Async crawling URL: {url}")

        try:
            async with aiohttp.ClientSession(
                headers={'User-Agent': self.user_agent},
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"HTTP {response.status} for {url}")
                        return None
                    html = await response.text()
        except Exception as e:
            logger.warning(f"Async fetch failed for {url}: {e}")
            # Fall back to sync crawl in thread pool
            return await asyncio.get_running_loop().run_in_executor(None, self.crawl, url)

        # Use trafilatura to extract content from downloaded HTML
        try:
            extracted = extract(
                html,
                output_format="json",
                include_comments=False,
                include_images=False,
                include_links=False,
                with_metadata=True
            )

            if not extracted:
                logger.warning(f"Trafilatura extraction failed for {url}, falling back to sync")
                return await asyncio.get_running_loop().run_in_executor(None, self.crawl, url)

            data = loads(extracted)

            content_parts = []
            if data.get("title"):
                content_parts.append(data["title"])
            if data.get("description"):
                content_parts.append(data["description"])
            if data.get("raw_text"):
                content_parts.append(data["raw_text"])

            result = {
                "url": data.get("source", url),
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "content": ". ".join(content_parts),
                "image": data.get("image", ""),
                "date": data.get("date", ""),
                "tags": data.get("tags", "").split(", ") if data.get("tags") else [],
                "author": data.get("author", ""),
                "sitename": data.get("sitename", ""),
                "method": "aiohttp+trafilatura"
            }

            logger.info(f"Successfully async crawled {url}")
            return result

        except Exception as e:
            logger.error(f"Error in async extraction for {url}: {e}")
            return None

    def crawl_multiple(self, urls: list[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Crawl multiple URLs

        Args:
            urls: List of URLs to crawl

        Returns:
            Dictionary mapping URLs to their crawled content
        """
        results = {}
        for url in urls:
            results[url] = self.crawl(url)
        return results

