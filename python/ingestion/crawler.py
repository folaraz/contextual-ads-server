import random
import time
from json import loads, dumps

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from trafilatura import fetch_url, extract


class Crawler:
    def __init__(self):
        self.urls = {
            "lifestyle": [
                "https://www.vogue.com/article/spring-2025-fashion-trends",
                "https://www.vogue.com/article/editor-picks-spring-summer-2025-trends",
                "https://www.vogue.com/article/the-essential-spring-2025-trends-fashion-celebrates-soft-power-the-sorcery-of-seduction-dandies-and-more",
                "https://www.vogue.com/article/9-outdated-fashion-pieces-vogue-editors-still-love",
                "https://www.vogue.com/article/5-easy-wellness-habits-2025",
                "https://variety.com/2025/tv/news/jimmy-kimmel-late-night-return-review-suspension-1236527655/"
            ],
            "music": [
                "https://variety.com/2025/music/spotlight/bad-bunny-grammys-super-bowl-redefining-pop-culture-1236537483/",
                "https://www.bbc.co.uk/news/articles/c9dx235qe04o"
            ],
            "movies": [
                "https://variety.com/lists/best-movies-of-2025-so-far/",
                "https://variety.com/2025/film/box-office/taylor-swift-release-party-showgirl-box-office-debut-smashing-machine-bombs-1236540485/",
                "https://variety.com/lists/most-anticipated-movies-2025/",
                "https://variety.com/2025/film/box-office/box-office-2025-hits-misses-lilo-stitch-mission-impossible-sinners-1236438377/",
                "https://variety.com/lists/best-movies-streaming-october-2025/",
                "https://variety.com/2025/music/news/diddy-jail-sentence-four-years-prison-1236537592/",
                "https://variety.com/2025/film/news/kill-bill-the-whole-bloody-affair-sets-theatrical-release-1236536800/"
            ],
            "finance": [
                "https://www.theguardian.com/business/2025/oct/12/the-imf-boss-is-right-to-say-buckle-up-the-global-economy-is-facing-multiple-menaces",
                "https://www.theguardian.com/business/2025/oct/12/urgent-call-debt-relief-imf-world-bank-debt-justice",
                "https://abcnews.go.com/Business/soaring-gold-prices-warning-sign-economy/story?id=126414464",
                "https://www.theguardian.com/business/2025/oct/09/the-debasement-trade-is-this-whats-driving-gold-bitcoin-and-shares-to-record-highs",
                "https://www.theguardian.com/business/2025/sep/25/us-stock-market-trump-wall-street-financial-crisis-federal-reserve"
            ],
            "basketball": [
                "https://www.espn.com/nba/story/_/id/46467409/nba-2025-2026-season-defining-names-paolo-banchero-mike-brown-trae-young",
                "https://www.espn.com/nba/story/_/id/45519132/nba-free-agency-2025-reaction-grades-biggest-signings",
                "https://www.espn.com/nba/story/_/id/46424210/2025-nba-training-camp-storylines-extensions-depth-charts-kuminga-durant",
                "https://www.espn.com/nba/transactions",
                "https://www.espn.com/nba/story/_/id/46357146/nba-2025-2026-season-biggest-questions-all-30-teams"
            ],
            "football": [
                "https://www.espn.com/nfl/story/_/id/46435996/nfl-week-5-2025-season-questions-takeaways-lessons-stats-recap-every-game",
                "https://www.espn.com/nfl/story/_/id/46443618/2025-nfl-quarter-season-awards-ranking-mvp-rookies-coaches-candidates",
                "https://www.espn.com/nfl/story/_/id/46447959/nfl-kickoff-rules-return-landing-zone",
                "https://www.espn.com/nfl/story/_/id/46423263/nfl-week-5-power-rankings-2025-biggest-issues-offense",
                "https://www.espn.com/nfl/story/_/id/46449711/2025-nfl-week-5-predictions-fantasy-sleepers-upsets-bets-stats-matchups"
            ],
            "politics": [
                "https://www.aljazeera.com/news/2025/10/12/us-congress-fails-pass-budget-deal",
                "https://abcnews.go.com/International/wireStory/us-government-shutdown-begins-2025-10-01",
                "https://www.theguardian.com/world/2025/oct/10/macron-reappoints-sebastien-lecornu-as-french-prime-minister",
                "https://www.aljazeera.com/news/2025/10/1/the-us-government-has-shut-down-what-happens-now",
                "https://www.bbc.co.uk/news/articles/c24rmdngrrjo",
                "https://www.bbc.co.uk/news/articles/cy0v7zwp0dlo"
            ],
            "tennis": [
                "https://www.tennis.com/news/articles/daniil-medvedev-records-50th-top-10-win-of-career-with-victory-over-de-minaur-in-shanghai"
            ],
            "soccer": [
                "https://www.espn.com/soccer/iraqs-iqbal-earns-1-0-win-over-indonesia-world-cup-qualifier-2025-10-11",
                "https://www.espn.com/soccer/story/_/id/39814568/south-korea-bounces-back-iraq-australia-progress-world-cup-qualifiers",
                "https://www.espn.com/football/story/_/id/39480574/asian-cup-transfer-targets-which-young-guns-europes-giants-eying"
            ],
            "technology": [
                "https://www.aljazeera.com/economy/2025/10/10/californias-landmark-frontier-ai-law-to-bring-transparency",
                "https://abcnews.go.com/Technology/wireStory/us-opens-tesla-probe-after-crashes-involving-called-126365399",
                "https://www.theguardian.com/technology/2025/oct/11/using-a-swearword-in-your-google-search-can-stop-the-ai-answer-but-should-you"
            ]
        }
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        self.chrome_options = chrome_options

        self.article_path = "../data/crawled_articles.json"
        self.ads_inventory_path = "../data/ads_inventory.json"
        self.crawled_pages_path = "../data/crawled_pages.json"
        self.crawled_pages_cache = self._load_crawled_pages()

    def get_ads_inventory(self):
        ad_inventories = []
        print(f"Loading ads inventory from {self.ads_inventory_path}...")
        with open(self.ads_inventory_path, "r") as f:
            ad_inventories = loads(f.read())
            print(f"Loaded {len(ad_inventories)} ads from inventory.")
        return ad_inventories

    def _load_crawled_pages(self):
        """Load existing crawled pages from file into cache"""
        try:
            with open(self.crawled_pages_path, "r") as f:
                data = loads(f.read())
                print(f"Loaded {len(data)} crawled pages into cache.")
                return data
        except FileNotFoundError:
            print("No existing crawled pages file found. Starting with empty cache.")
            return {}
        except Exception as e:
            print(f"Error loading crawled pages: {str(e)}")
            return {}

    def save_crawled_page(self, url, page_data):
        """Update cache and persist to file"""
        self.crawled_pages_cache[url] = page_data

        with open(self.crawled_pages_path, "w") as f:
            f.write(dumps(self.crawled_pages_cache, indent=2))
            print(f"Updated crawled pages cache with {url}.")

    def crawl_ads_landing_page(self, url):
        print(f"Scraping ads landing page: {url}")
        if url in self.crawled_pages_cache:
            print(f"Found cached data for {url}.")
            return self.crawled_pages_cache[url]
        print("No cached data found. Scraping anew...")
        result = self.scrape(url)
        if result:
            self.save_crawled_page(url, result)
            print(f"Successfully scraped ads landing page: {url}")
        else:
            print(f"Failed to scrape ads landing page: {url}")
        return result

    def crawl_web_pages(self):
        publication_data = self.crawl_publication_pages()
        ads_inventory_data = self.craw_ad_inventory_pages()
        data = {
            "publication_web_ages": publication_data,
            "ads_inventory_web_pages": ads_inventory_data
        }
        return data

    def craw_ad_inventory_pages(self):
        ads = self.get_ads_inventory()
        print("Starting crawling ads inventory pages...")
        data = dict()
        for ad in ads:
            creative = ad.get("creative", None)
            landing_page_url = creative.get("landing_page_url", "")
            result = self.crawl_ads_landing_page(landing_page_url)
            if result:
                data[landing_page_url] = result
        return data

    def crawl_publication_pages(self):
        print("Starting crawling publication pages...")
        data = {}
        for _, values in self.urls.items():
            for url in values:
                if url in self.crawled_pages_cache:
                    print(f"Using cached data for {url}.")
                    result = self.crawled_pages_cache[url]
                    data[url] = result
                    continue
                print("No cached data found. Scraping anew...")
                result = self.scrape(url)
                if result:
                    print(f"Successfully scraped: {url}")
                self.save_crawled_page(url, result)
                data[url] = result
                time.sleep(random.uniform(1, 3))
        return data

    def scrape(self, url):
        result = self.scrape_via_fetch(url)
        if result:
            return result
        result = self.scrape_via_driver(url)
        return result

    @staticmethod
    def scrape_via_fetch(url):
        try:
            downloaded = fetch_url(url=url)
            if not downloaded:
                print(f"Error downloading {url}")
                return None

            result = extract(downloaded, output_format="json", include_comments=False, include_images=False,
                             include_links=False, with_metadata=True)
            if not result:
                print(f"Error extracting {url}")
                return None
            result = loads(result)
            content = result.get("title", "") + "." + result.get("description", "") + "." + result.get("raw_text", "")
            payload = {
                "image": result.get("image", ""),
                "url": result.get("source", url),
                "tags": result.get("tags", "").split(", ") if result.get("tags") else [],
                "content": content,
                "date": result.get("date", ""),
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "author": result.get("author", "")
            }
            return payload
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
            return None

    def scrape_via_driver(self, url):
        driver = webdriver.Chrome(options=self.chrome_options)
        try:
            print(f"Scraping via driver: {url}")
            driver.get(url)

            time.sleep(10)

            title = driver.title
            description = self._get_meta_description(driver)
            body_text = self._get_body_text(driver)
            img_alts_text = self._get_image_alts(driver)

            content = f"""{title}. {description}. {body_text}. {img_alts_text}"""

            payload = {
                'url': url,
                'title': title,
                'content': content,
                'description': description,
            }
            return payload

        finally:
            driver.quit()

    def _get_meta_description(self, driver):
        """Extract meta description"""
        try:
            meta = driver.find_element(By.CSS_SELECTOR, 'meta[name="description"]')
            return meta.get_attribute('content')
        except:
            return ""

    def _get_body_text(self, driver):
        """Extract main body text"""
        try:
            body = driver.find_element(By.TAG_NAME, 'body')
            return body.text
        except:
            return ""

    def _get_image_alts(self, driver):
        """Extract image alt text"""
        alts = []
        images = driver.find_elements(By.TAG_NAME, 'img')
        for img in images[:30]:
            alt = img.get_attribute('alt')
            if alt:
                alts.append(alt)
        return alts
