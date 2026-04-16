"""
Content processors for extracting context from different content types

These processors use the core NLP services to extract keywords, entities,
topics, and embeddings from ads, pages, and other content.
"""

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.crawler_service import WebCrawler
from services.nlp_service import (
    KeywordExtractor,
    EntityExtractor,
    TopicClassifier,
    EmbeddingGenerator
)

logger = logging.getLogger(__name__)


class BaseProcessor:
    """Base processor with shared NLP services"""

    def __init__(self, enable_crawler: bool = False, crawler_config: Optional[Dict[str, Any]] = None):
        """
        Initialize processor with NLP services

        Args:
            enable_crawler: Whether to initialize web crawler
            crawler_config: Configuration for web crawler (user_agent, headless, timeout)
        """
        logger.info("Initializing NLP services...")
        self.keyword_extractor = KeywordExtractor()
        self.entity_extractor = EntityExtractor()
        self.topic_classifier = TopicClassifier()
        self.embedding_generator = EmbeddingGenerator()

        # Optional crawler
        self.crawler = None
        if enable_crawler:
            config = crawler_config or {}
            self.crawler = WebCrawler(
                user_agent=config.get('user_agent'),
                headless=config.get('headless', True),
                timeout=config.get('timeout', 30)
            )
            logger.info("Web crawler initialized")

        logger.info("NLP services initialized")


class AdProcessor(BaseProcessor):
    """Process ads to extract contextual information"""

    def process(
            self,
            ad_data: Dict[str, Any],
            crawl_landing_page: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Process an ad to extract keywords, entities, topics, and embeddings

        Args:
            ad_data: Dictionary with ad_id, headline, description, destination_url, etc.
            crawl_landing_page: Whether to crawl and analyze landing page content

        Returns:
            Dictionary with extracted context or None if processing fails
        """
        try:
            ad_id = ad_data.get('ad_id')
            headline = ad_data.get('headline', '')
            description = ad_data.get('description', '')
            destination_url = ad_data.get('destination_url', '')

            logger.info(f"Processing ad {ad_id}: {headline[:50]}...")

            # Start with ad text
            text_parts = []
            if headline:
                text_parts.append(headline)
            if description:
                text_parts.append(description)

            # todo, this should be optional I think, what's more important is the ad creatives.
            if crawl_landing_page and destination_url and self.crawler:
                logger.info(f"Crawling landing page for ad {ad_id}: {destination_url}")
                crawled_content = self.crawler.crawl(destination_url)

                if crawled_content and crawled_content.get('content'):
                    text_parts.append(crawled_content['content'])
                    logger.info(f"Added landing page content for ad {ad_id}")
                else:
                    logger.warning(f"Failed to crawl landing page for ad {ad_id}")

            combined_text = ". ".join(text_parts).strip()

            if not combined_text:
                logger.warning(f"No text content for ad {ad_id}")
                return None

            # Extract features in parallel (all operations are independent)
            with ThreadPoolExecutor(max_workers=4) as executor:
                kw_future = executor.submit(self.keyword_extractor.extract, combined_text, 20)
                ent_future = executor.submit(self.entity_extractor.extract, combined_text)
                topic_future = executor.submit(
                    self.topic_classifier.classify_fast,
                    text=combined_text, taxonomy="product",
                    threshold=0.1, top_k=2, return_top_paths=5
                )
                emb_future = executor.submit(self.embedding_generator.generate, combined_text, False)

                keywords = kw_future.result()
                entities = ent_future.result()
                topic_paths = topic_future.result()
                embedding = emb_future.result()

            topics = self._flatten_topics(topic_paths)

            result = {
                'ad_id': ad_id,
                'keywords': keywords,
                'entities': entities,
                'topics': topics,
                'embedding': embedding.tolist(),
                'crawled_landing_page': crawl_landing_page and destination_url and self.crawler is not None,
                'processed_at': datetime.now(timezone.utc).isoformat()
            }

            logger.info(
                f"Successfully processed ad {ad_id}: {len(keywords)} keywords, {len(entities)} entities, {len(topics)} topics")
            return result

        except Exception as e:
            logger.error(f"Error processing ad {ad_data.get('ad_id')}: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _flatten_topics(topic_paths: List[List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
        """Flatten topic paths into a dictionary keyed by iab_id"""
        topics = {}
        for path in topic_paths:
            for topic in path:
                if topic and "iab_id" in topic:
                    iab_id = topic["iab_id"]
                    if iab_id not in topics:
                        topics[iab_id] = topic
        return topics


class PageProcessor(BaseProcessor):
    """Process web pages to extract contextual information"""

    def process(self, page_data: Dict[str, Any], auto_crawl: bool = True ) -> Optional[Dict[str, Any]]:
        """
        Process a web page to extract keywords, entities, topics, and embeddings

        Args:
            page_data: Dictionary with page_id, url, content (optional), title, description, etc.
            auto_crawl: If True and content is missing, automatically crawl the URL

        Returns:
            Dictionary with extracted context or None if processing fails
        """
        try:
            page_id = page_data.get('page_url_hash')
            url = page_data.get('page_url', '')
            if not url:
                return None

            logger.info(f"Processing page {page_id}: {url[:50]}...")

            # Initialize content variables
            content = ''
            title = ''
            description = ''

            # Crawl the URL to get content
            if auto_crawl and url and self.crawler:
                logger.info(f"Crawling URL: {url}")
                crawled = self.crawler.crawl(url)

                if crawled:
                    content = crawled.get('content', '')
                    title = crawled.get('title', '')
                    description = crawled.get('description', '')
                    logger.info(f"Successfully crawled content for page {page_id}")
                else:
                    logger.warning(f"Failed to crawl URL for page {page_id}")

            if not content:
                logger.warning(f"No content available for page {page_id}")
                return None

            # Extract features in parallel (all operations are independent)
            with ThreadPoolExecutor(max_workers=4) as executor:
                kw_future = executor.submit(self.keyword_extractor.extract, content, 30)
                ent_future = executor.submit(self.entity_extractor.extract, content)
                topic_future = executor.submit(
                    self.topic_classifier.classify_fast,
                    text=content, taxonomy="content",
                    threshold=0.3, top_k=2, return_top_paths=5
                )
                emb_future = executor.submit(self.embedding_generator.generate, content, True)

                keywords = kw_future.result()
                entities = ent_future.result()
                topic_paths = topic_future.result()
                chunks, page_embedding = emb_future.result()

            topics = self._flatten_topics(topic_paths)

            # Build metadata
            meta_data = {
                "url": url,
                "title": title,
                "description": description,
            }

            result = {
                'page_url_hash': page_id,
                'meta_data': meta_data,
                'keywords': keywords,
                'entities': entities,
                'topics': topics,
                'page_embedding': page_embedding.tolist(),
                'chunk_context': chunks,
                'crawled': auto_crawl and self.crawler is not None,
                'processed_at': datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Successfully processed page {page_id}: "
                        f"{len(keywords)} keywords, {len(entities)} entities, "
                        f"{len(topics)} topics, {len(chunks)} chunks")
            return result

        except Exception as e:
            logger.error(f"Error processing page {page_data.get('page_url_hash')}: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _flatten_topics(topic_paths: List[List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
        """Flatten topic paths into a dictionary keyed by iab_id"""
        topics = {}
        for path in topic_paths:
            for topic in path:
                if topic and "iab_id" in topic:
                    iab_id = topic["iab_id"]
                    if iab_id not in topics:
                        topics[iab_id] = topic
        return topics
