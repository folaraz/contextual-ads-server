import random
import time
from json import loads, dumps

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
        self.article_path = "../data/crawled_articles.json"
        self.ads_inventory_path = "../data/ads_inventory.json"

    def get_ads_inventory(self):
        with open(self.ads_inventory_path, "r") as f:
            return loads(f.read())

    def crawl(self):
        print("Checking path for existing data...")
        try:
            with open(self.article_path, "r") as f:
                data = loads(f.read())
                if data:
                    print(f"Found {len(data)} articles in {self.article_path}. Skipping crawl.")
                    return data
        except Exception as e:
            print(f"Error reading data: {str(e)}")

        print("Starting crawling...")
        data = []
        for theme, values in self.urls.items():
            for url in values:
                result = self.scrape(url)
                if result:
                    result["theme"] = theme
                    data.append(result)
                time.sleep(random.uniform(1, 3))
        print(f"Crawled {len(data)} articles.")
        with open(self.article_path, "w") as f:
            f.write(dumps(data, indent=2))
            print(f"Saved crawled data to {self.article_path}.")
        return data

    @staticmethod
    def scrape(url):
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
            payload = {
                "image": result.get("image", ""),
                "url": result.get("source", url),
                "tags": result.get("tags", "").split(", ") if result.get("tags") else [],
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "content": result.get("raw_text", ""),
                "date": result.get("date", ""),
                "author": result.get("author", "")
            }
            return payload
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
            return None
