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
                "https://www.reuters.com/business/finance/feds-williams-says-central-banks-must-prepare-unexpected-2025-10-03/",
                "https://www.reuters.com/business/finance/global-markets-view-usa-2025-10-02/",
                "https://www.reuters.com/business/never-mind-wall-street-records-investors-rethink-us-market-supremacy-2025-08-01/",
                "https://www.reuters.com/business/wall-street-indexes-notch-record-high-closes-investors-bet-rate-cut-2025-09-09/",
                "https://www.reuters.com/sustainability/boards-policy-regulation/how-us-government-shutdown-could-affect-financial-markets-2025-09-25/"
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
            "tennis": [
                "https://www.atptour.com/en/news/djokovic-shanghai-2025-friday-reaction",
                "https://www.atptour.com/en/news/sinner-altmaier-shanghai-sunday-2025",
                "https://www.atptour.com/en/news/shang-khachanov-shanghai-2025-saturday",
                "https://www.atptour.com/en/news/alcaraz-wins-2025-atp-500-bonus-pool",
                "https://www.atptour.com/en/news/sinner-griekspoor-shanghai-2025-sunday"
            ],
            "politics": [
                "https://www.reuters.com/world/us/government-shutdown-nears-with-no-deal-washington-2025-09-30/",
                "https://www.reuters.com/world/us/us-government-begins-shut-down-most-operations-after-congress-fails-advance-2025-10-01/",
                "https://www.reuters.com/world/us/us-senate-vote-dueling-plans-end-shutdown-though-neither-likely-pass-2025-10-03/",
                "https://www.reuters.com/world/us/trump-discuss-agency-cuts-with-ombs-vought-thursday-2025-10-02/",
                "https://www.reuters.com/world/france-names-new-government-amid-political-turmoil-2025-10-05/",
                "https://www.bbc.co.uk/news/articles/c24rmdngrrjo",
                "https://www.bbc.co.uk/news/articles/cy0v7zwp0dlo"
            ],
            "tech": [
                "https://www.reuters.com/technology/opera-launches-neon-ai-browser-join-agentic-web-browsing-race-2025-09-30/",
                "https://www.reuters.com/world/asia-pacific/inspired-by-thatcher-japans-pm-in-waiting-takaichi-smashes-glass-ceiling-2025-10-04/",
                "https://www.reuters.com/world/china/japans-next-leader-may-be-its-first-wife-or-youngest-modern-era-2025-10-02/",
                "https://www.reuters.com/world/china/japans-ruling-party-pick-new-leader-hoping-revive-fortunes-2025-10-03/",
                "https://www.reuters.com/business/retail-consumer/amazons-aws-strikes-ai-cloud-partnership-with-nba-2025-10-01/"
            ],
            "ai": [
                "https://www.reuters.com/technology/artificial-intelligence/",
                "https://www.reuters.com/technology/china-says-it-will-increase-support-ai-science-tech-innovation-2025-03-05/",
                "https://www.reuters.com/technology/artificial-intelligence/synopsys-lays-out-strategy-ai-agents-design-computer-chips-2025-03-19/",
                "https://www.reuters.com/technology/meta-invest-up-65-bln-capital-expenditure-this-year-2025-01-24/",
                "https://www.reuters.com/world/uk/uk-pm-starmer-outline-plan-make-britain-world-leader-ai-2025-01-12/"
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
                return None

            result = extract(downloaded, output_format="json", include_comments=False, include_images=False,
                             include_links=False, with_metadata=True)
            if not result:
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
