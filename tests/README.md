# Test Suite

This directory contains the test suite for the Contextual Ads Server, covering data seeding, traffic simulation, end-to-end scenarios, offline evaluation, observability, and a business metrics dashboard.

## Directory Structure

```
tests/
  README.md
  config/
    config.go                # Config types and loading
    config.yaml              # Test environment settings
  client/                    # API client for test interactions
    client.go                # Main HTTP client
    advertisers.go           # Advertiser API methods
    publishers.go            # Publisher API methods
    campaigns.go             # Campaign API methods
    ads.go                   # Ad serving API methods
    events.go                # Event tracking API methods
  fixtures/                  # Test data fixtures
    advertisers.go           # Advertiser seed data templates
    publishers.go            # Publisher seed data templates
    campaigns.go             # Campaign building utilities
    targeting.go             # Targeting data (keywords, topics, entities)
    page_urls.go             # Real page URLs for traffic simulation
  helpers/                   # Shared test helpers
    assertions.go            # Custom test assertions
    generators.go            # Random data generators
  e2e/                       # End-to-end test scenarios
    setup/
      seeder.go              # Main seeder orchestration
      seeder_test.go         # Seeder tests
    traffic/
      simulator.go           # Traffic simulator core
      simulator_test.go      # Traffic simulation tests
    scenarios/
      ad_serving.go          # Ad serving scenarios
      event_tracking.go      # Event tracking scenarios
      scenarios_test.go      # Scenario tests
  evaluation/                # Offline evaluation (ranking + pacing)
    report.go                # JSON + console report generation
    reports/                 # Generated reports and charts
    fixtures/                # Evaluation fixture generators
    relevance/               # Ranking and auction evaluation tests
    pacing/                  # Pacing simulation and visualization tests
  reports/                   # E2E test execution reports
  cmd/                       # CLI entry points
    seed/
      main.go                # Seeding CLI (supports --from-file for bulk seeding)
    traffic_simulator/
      main.go                # Traffic simulator CLI entry point

python/scripts/                         # Python utilities (outside tests/)
  bulk_ads_generator.py                 # Bulk campaign generator (10k-100k+)
  generate_creative_bank.py             # Optional LLM creative enrichment
  generate_eval_fixtures.py             # NLP evaluation fixture generation
  preprocess_all.py                     # NLP preprocessing (pages + ads)
  flatten_iab_taxonomy.py               # IAB taxonomy flattening
  iab_taxonomy_converter.py             # IAB taxonomy format conversion
  generate_annotations.py               # Annotation generation

python/dashboard/                       # Business metrics dashboard
  app.py                                # Streamlit application
  db.py                                 # Database connection
  queries.py                            # SQL queries
```

## Prerequisites

1. All services running (Postgres, Redis, Kafka, Go API server)
2. Database migrations applied
3. Go 1.21+
4. Python 3 with dependencies from `python/requirements.txt`

The fastest way to bring everything up:

```bash
make up           # Start all infrastructure, observability, consumers, and the ad server
make bootstrap    # Generate data, seed the database, and run NLP preprocessing
```

## Configuration

Edit `tests/config/config.yaml` to customise:

- API base URL and timeouts
- Advertiser count and industry list
- Publisher count and category list
- Campaign count, budget range, pricing models, bid ranges
- Geographic targeting countries
- Device types
- Kafka broker addresses and topic names
- Database connection details

## Data Seeding

There are two approaches to seeding: file-based (10k-100k+ campaigns from pre-generated JSON) and fixture-based (small counts from Go templates).

### File-Based Seeding (Recommended for Scale)

This is a three-step process: optionally generate enriched creatives, generate campaign request JSON, then seed the server through the API.

#### Step 1 (Optional): LLM-Enriched Creatives

For richer creative diversity, generate a creative bank using the Claude API before running the bulk generator. This is a one-time step:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install anthropic
python3 python/scripts/generate_creative_bank.py
```

This produces `data/creative_bank.json`. The bulk generator detects and uses it automatically if present; otherwise it falls back to 600+ built-in templates.

#### Step 2: Generate Campaign Requests

```bash
# Generate 10,000 campaigns (default)
python3 python/scripts/bulk_ads_generator.py

# Generate 50,000 campaigns
python3 python/scripts/bulk_ads_generator.py --count 50000

# Generate 100,000 campaigns
python3 python/scripts/bulk_ads_generator.py --count 100000

# Custom seed for different data variations
python3 python/scripts/bulk_ads_generator.py --count 10000 --seed 99
```

Output is written to `data/campaign_requests_{count}.json`.

#### Step 3: Seed Into the Server

```bash
# Seed 10k campaigns with 10 concurrent workers
go run ./tests/cmd/seed --from-file=data/campaign_requests_10k.json --workers=10

# Seed with a fresh database
go run ./tests/cmd/seed --from-file=data/campaign_requests_10k.json --workers=10 --reset-db

# Dry run (validate file, show count, no API calls)
go run ./tests/cmd/seed --from-file=data/campaign_requests_10k.json --dry-run

# Increase concurrency for faster seeding
go run ./tests/cmd/seed --from-file=data/campaign_requests_50k.json --workers=20

# Use custom API URL
go run ./tests/cmd/seed --from-file=data/campaign_requests_10k.json --api-url=https://your-server.com
```

The `--from-file` path seeds campaigns through the full API pipeline (validation, Kafka publishing, Redis caching). Each campaign requires a valid `advertiser_id`, so ensure advertisers are seeded first.

#### Shortcut via Make

```bash
make generate-data          # Step 2: generate campaign + inventory JSONs (default 10k)
make generate-data COUNT=50000   # Custom count
make seed-from-file         # Step 3: seed from the most recent generated file
make bootstrap              # Steps 2 + 3 + NLP preprocessing in one command
make bootstrap-clean        # Same as above but resets the database first
```

### Fixture-Based Seeding (Small Counts)

For smaller-scale seeding using Go templates:

```bash
# Seed all data with default counts (241 advertisers, 50 publishers, 100 campaigns)
go run ./tests/cmd/seed --all --verbose

# Seed with a fresh database
go run ./tests/cmd/seed --all --reset-db --verbose

# Or use make
make seed-clean

# Seed specific entities with custom counts
go run ./tests/cmd/seed --advertisers --adv-count=30 --verbose
go run ./tests/cmd/seed --publishers --pub-count=50 --verbose
go run ./tests/cmd/seed --campaigns --camp-count=200 --verbose

# Dry run
go run ./tests/cmd/seed --all --dry-run --verbose

# Custom API URL
go run ./tests/cmd/seed --all --api-url=https://your-server.com --verbose

# Custom config file
go run ./tests/cmd/seed --all --config=tests/config/config.yaml
```

### Seed Data Details

The bulk generator (`python/scripts/bulk_ads_generator.py`) produces:

- 241 advertisers across 42 industries
- 20 headline and 10 description templates per industry (600+ built-in)
- Full IAB product taxonomy integration (583 categories)
- Typed entities: BRAND, PRODUCT, ORGANIZATION, PERSON
- Weighted distributions for countries (US/CA/GB/DE/FR/AU), devices (industry-specific), and pricing (CPM 60% / CPC 40%)
- Linear scaling via the `--count` flag

The fixture-based seeder covers 12 industries (e-commerce, SaaS, entertainment, education, finance, healthcare, travel, automotive, food and beverage, technology, fashion, sports) and 12 publisher categories (news, blog, e-commerce, entertainment, sports, technology, lifestyle, finance, health, travel, food, automotive). Campaigns include varied budgets ($100 to $50,000), pricing models (CPM, CPC), targeting (keywords, topics, entities, geo, devices), date ranges, and statuses (ACTIVE, PAUSED).

## NLP Preprocessing

After seeding, run NLP preprocessing to extract page and ad context signals and cache them in Redis:

```bash
make preprocess                  # Run NLP preprocessing (pages + ads)
make preprocess-verify           # Verify preprocessing results
make warm-cache                  # Re-populate Redis cache from PostgreSQL without re-running NLP
```

Preprocessed URLs are written to `data/preprocessed_urls.txt`, which the traffic simulator uses for realistic page contexts.

## Traffic Simulation

The traffic simulator sends ad requests through the full serving pipeline and tracks impressions and clicks.

### Running the Simulator

```bash
# Basic simulation (1000 requests, 10 concurrent)
go run ./tests/cmd/traffic_simulator -requests 1000 -concurrency 10 -page-urls-file data/preprocessed_urls.txt

# High volume with rate limiting
go run ./tests/cmd/traffic_simulator -requests 10000 -concurrency 50 -rate 500 -page-urls-file data/preprocessed_urls.txt

# Duration-based soak test
go run ./tests/cmd/traffic_simulator -duration 6h -concurrency 50 -impression-rate 0.95 -click-rate 0.06 -page-urls-file data/preprocessed_urls.txt

# Custom impression and click rates
go run ./tests/cmd/traffic_simulator -requests 200 -impression-rate 0.9 -click-rate 0.05 -concurrency 10 -page-urls-file data/preprocessed_urls.txt

# Geo-distributed traffic
go run ./tests/cmd/traffic_simulator -requests 2000 -countries "US:0.5,GB:0.3,DE:0.2"

# Disable geo simulation (use your real IP)
go run ./tests/cmd/traffic_simulator -requests 1000 -countries ""

# Dry run (show config without running)
go run ./tests/cmd/traffic_simulator -dry-run
```

Or use Make targets:

```bash
make simulate            # 1k requests, 10 workers
make simulate-heavy      # 10k requests, 50 workers, rate-limited to 500/s
make simulate-soak       # 6-hour duration, 50 workers
```

### Geo-Distributed Traffic

Most ads in the inventory have country-level targeting (US, GB, DE, FR, CA, AU). When running the simulator locally, your real IP resolves to a single country, which causes most geo-targeted ads to be filtered out and produces a low fill rate. The `--countries` flag solves this by distributing requests across multiple simulated countries.

The default distribution is `US:0.35,GB:0.20,DE:0.15,FR:0.10,CA:0.10,AU:0.10`. The simulator sends an `X-Geo-Country` header with each request, and the server uses it directly instead of performing a GeoIP lookup. Pass `--countries ""` to disable this behaviour and use your real IP.

The summary output includes a per-country breakdown:

```
Per-Country Breakdown:
  Country  Requests    Fills  NoFills  Fill Rate
  US            700      210       490     30.0%
  GB            400      120       280     30.0%
  DE            300       75       225     25.0%
  ...
```

### Simulator Capabilities

**Ad request generation:**
- Random publisher selection from seeded data
- Realistic page contexts (URLs, titles, descriptions, keywords)
- Device type distribution (desktop, mobile, tablet)
- User agent simulation
- Country-weighted geo distribution

**Event tracking:**
- Impression tracking with configurable rate (default 80%)
- Click tracking with configurable CTR (default 3%)
- Full ad lifecycle testing (request, impression, click)

**Metrics and reporting:**
- Request success/failure rates
- Fill rate calculation
- Latency statistics (average, minimum, maximum)
- CTR calculation
- Per-publisher statistics
- Per-country statistics
- Error aggregation

## End-to-End Tests

```bash
# Run all e2e tests
go test ./tests/e2e/... -v

# Run setup tests only
go test ./tests/e2e/setup/... -v

# Run traffic simulation tests
go test ./tests/e2e/traffic/... -v

# Run scenario tests (ad serving + event tracking)
go test ./tests/e2e/scenarios/... -v

# Run with race detection
go test ./tests/e2e/... -race -v

# Run with custom API URL
TEST_API_URL=http://localhost:8090 go test ./tests/e2e/... -v
```

### Scenario Coverage

**Ad serving scenarios:**
- Basic flow testing
- Keyword-based targeting validation
- Device variation testing
- Latency benchmarking (p50, p95, p99)

**Event tracking scenarios:**
- Full lifecycle tests (ad serve, impression, click)
- Batch event testing
- Impression-only testing
- Click tracking validation

## Evaluation Framework

The `evaluation/` directory contains an offline evaluation suite for the ad ranking pipeline and pacing system. It runs entirely in-process with no external service dependencies (no Kafka, Postgres, or live Redis required), calling exported scoring functions directly (`ads.ScoreAdsWithParams`, `ads.RunSecondPriceAuction`, `ads.CalculateKeywordScore`, etc.) rather than going through HTTP endpoints. This isolates ranking logic from infrastructure concerns.

Pacing tests use [miniredis](https://github.com/alicebob/miniredis) for an in-memory Redis server. The Python pacing CLI connects to miniredis over TCP, so the PI controller code runs identically to production.

### Running Evaluations

```bash
make eval              # Run all evaluations
make eval-relevance    # Relevance only (5s)
make eval-pacing       # Pacing only (30s, requires python3 + redis)
make eval-short        # Short mode (skip closed-loop simulation and visualization)

# NLP-based evaluation (uses real NLP pipeline signals)
make eval-fixtures     # Pre-compute NLP fixtures (3-5 min, requires python3 + NLP deps)
make eval-nlp          # Generate fixtures + run NLP eval tests
```

### Evaluation Dependencies

- Go: `github.com/alicebob/miniredis/v2`, `github.com/stretchr/testify`, `gonum.org/v1/plot`
- Python (pacing only): `python3` with `redis` package (`pip install redis`)
- Python (NLP fixtures only): `python3` with `spacy`, `sentence-transformers`, `keybert`, `transformers`, `torch` (see `python/requirements.txt`)
- No running services needed

### Evaluation Directory Structure

```
tests/evaluation/
  fixtures/
    ad_generator.go         # 50 real + ~1,450 synthetic ads across 12 industries
    page_generator.go       # ~100 pages from crawled data + synthetic fill
    ground_truth.go         # Relevance labels: category+keyword and hybrid embedding
    industry_templates.go   # Per-industry keyword pools, entities, topics, headlines
    taxonomy_fixtures.go    # IAB taxonomy mappings loaded from JSON files
    nlp_fixtures.go         # Loader for pre-computed NLP fixture JSON files
    vector_util.go          # Cosine similarity for real embedding comparison
  relevance/
    scorer_test.go          # Unit tests for each scoring signal
    ranking_eval_test.go    # Full ranking evaluation with IR metrics (synthetic)
    ranking_eval_nlp_test.go # NLP-based eval with real embeddings (build tag: nlp_eval)
    auction_eval_test.go    # Second-price auction correctness
    metrics.go              # Precision@K, NDCG@K, aggregation helpers
  pacing/
    pacing_eval_test.go     # Closed-loop simulation with miniredis + Python
    charts_test.go          # PNG chart generation (gonum/plot)
  report.go                 # JSON + console report generation

python/scripts/
  generate_eval_fixtures.py # Pre-compute NLP signals into data/eval/*.json

python/pacing/
  pacing_cli.py             # CLI wrapper for pacing subprocess calls

data/eval/
  nlp_page_contexts.json   # NLP-extracted page signals (committed to repo)
  nlp_ad_contexts.json     # NLP-extracted ad signals (committed to repo)
```

### Ranking Pipeline Signals

The ranking pipeline scores each ad against a page using four independent signals, then combines them into a composite quality score. Each signal captures a different dimension of contextual relevance.

#### Keyword Score

Measures direct keyword overlap between the ad's targeting keywords and the keywords extracted from the page content.

Calculated as a weighted Jaccard-style overlap. For each ad keyword that appears in the page keywords, the product of their weights is accumulated. The sum is divided by the total ad keyword weight, then a normalization penalty is applied if the page has more keywords than the ad (meaning the ad is too narrow for the page context).

```
keywordScore = min(sum(adWeight[k] * pageWeight[k] for shared k) / totalAdWeight, 1.0)
keywordScore *= normalize(pageKeywordCount, adKeywordCount)
```

Keywords are the most explicit signal of intent. A travel ad targeting "flights" and "hotels" appearing on a page about "best hotel deals in Paris" has direct keyword overlap that strongly indicates relevance. However, keywords alone are brittle: they miss semantic relationships and can produce false positives on ambiguous terms.

Weight in composite: 10% (CPM), 20% (CPC).

#### Topic Score

Measures whether the ad's IAB product taxonomy categories map to the page's IAB content taxonomy categories, using the official IAB cross-taxonomy mapping tables.

Each topic has a tier (depth in the taxonomy tree) and a relevance score. The tier-weighted score is `relevanceScore * (1.0 + tier * 0.5)`, so deeper and more specific taxonomy matches are rewarded. The ad's product taxonomy IDs are translated to content taxonomy IDs via the mapping table. Matched weight is divided by the union of page and ad topic weights.

```
topicWeight(t) = t.relevanceScore * (1.0 + t.tier * 0.5)
topicScore = matchedWeight / (pageWeight + adWeight - matchedWeight)
```

Topics capture category-level relevance that keywords miss. A page about "machine learning frameworks" and an ad for "cloud GPU instances" may share zero keywords but both sit under the same IAB taxonomy branch (Technology > Computing). Topic scoring carries the highest weight for CPM campaigns because brand advertisers care most about contextual alignment at the category level.

Weight in composite: 60% (CPM), 30% (CPC).

#### Entity Score

Measures whether named entities in the ad targeting (brands, products, people, organizations) appear in the page content.

Calculated using two-pass matching. First, exact string match (case-insensitive) with entity type validation. If no exact match, token-level matching checks individual words from the entity against page entity tokens. Coverage is `matched / totalAdEntities`, then normalized for page-vs-ad entity count disparity.

```
entityScore = normalize(pageEntityCount, adEntityCount, matched / totalAdEntities)
```

Entity matching captures specificity that categories and keywords cannot. An ad targeting "Tesla" and "Elon Musk" on a page mentioning both entities is highly specific relevance. For CPC campaigns, entity matching gets the highest weight because performance advertisers want to appear alongside specific brands, products, or people that their audience cares about.

When a page has no extractable entities, the entity weight is redistributed to the vector similarity signal. This prevents pages with thin entity extraction from penalizing all ads equally.

Weight in composite: 10% (CPM), 40% (CPC).

#### Vector Similarity

Measures cosine similarity between the ad's embedding vector and the page's embedding vector in a shared semantic space.

In production, this comes from Redis vector search (HNSW index). In evaluation, mock scores are assigned: relevant ads get 0.6-0.8 (seeded random), irrelevant ads get 0.2-0.4. This simulates a well-calibrated embedding model without requiring one.

Vector similarity is the soft semantic signal. It captures relationships that discrete keyword/topic/entity matching misses, for example an ad about "sustainable packaging" being relevant to a page about "eco-friendly product design." It acts as a safety net that prevents the ranking from being too brittle when structured signals are sparse.

Weight in composite: 20% (CPM), 10% (CPC).

#### Normalization Penalty

If the page has more targeting attributes (keywords, entities) than the ad, a logarithmic penalty is applied:

```
if pageLen > adLen:
    penalty = 1.0 / (1.0 + log10(pageLen / adLen))
    score *= penalty
```

Without normalization, an ad targeting a single keyword "tech" would score 1.0 on keyword match against a rich tech page with 20 keywords, the same score as an ad targeting all 20. The penalty ensures that narrowly-targeted ads do not get inflated scores just because their one keyword happens to match.

#### Composite Quality Score

All four signals are combined into a single quality score using pricing-model-dependent weights:

| Signal | CPM Weight | CPC Weight |
|--------|-----------|-----------|
| Keyword | 0.10 | 0.20 |
| Topic | 0.60 | 0.30 |
| Entity | 0.10 | 0.40 |
| Vector Similarity | 0.20 | 0.10 |

CPM (cost-per-thousand-impressions) advertisers pay for eyeballs regardless of clicks, so they care most about broad contextual alignment (topic). CPC (cost-per-click) advertisers pay per click, so they care most about specific, high-intent placements (entity + keyword).

#### Final Rank Score

The auction ranking combines quality with economics and pacing:

```
finalRankScore = eCPM * qualityScore * pacingMultiplier
```

- **eCPM** normalizes different pricing models to a comparable basis. CPM ads use bid directly; CPC ads convert via `bid * predictedCTR * 1000`.
- **pacingMultiplier** (0.5-2.0) adjusts the effective rank to control delivery speed. Underspending campaigns get boosted; overspending ones get suppressed.

### Information Retrieval Metrics

These metrics measure how well the ranking pipeline places relevant ads at the top of the results, using ground-truth relevance labels.

#### Precision@K

Of the top K ranked ads, what fraction are actually relevant?

```
Precision@K = (number of relevant ads in top K) / K
```

K values tracked: 1, 3, 5, 10.

In ad serving, typically only 1-3 ads are shown per page. Precision@1 directly measures whether the winning ad is relevant. Precision@5 and Precision@10 measure depth: if the top choice is filtered (budget, frequency cap), are the fallbacks also relevant?

Pass thresholds:
- Mean Precision@1 > 0.50, meaning the top-ranked ad is relevant at least half the time
- These are intentionally conservative. Real-world ad serving has additional context (user signals, frequency caps) that improve precision beyond what offline evaluation can measure.

#### NDCG@K (Normalized Discounted Cumulative Gain)

Measures how well relevant ads are concentrated at the very top of the ranking, accounting for position.

```
DCG@K  = sum(relevance[i] / log2(i + 1)) for i in 1..K
IDCG@K = DCG of the ideal ranking (all relevant items first)
NDCG@K = DCG@K / IDCG@K
```

K values tracked: 5, 10.

Precision@K treats all positions equally: an ad at position 1 and position 5 contribute the same. NDCG weights earlier positions more heavily (via the `1/log2(i+1)` discount). This matters because position 1 gets shown, position 5 probably does not. A system that always ranks relevant ads at positions 4-5 would have decent Precision@5 but poor NDCG@5.

Pass thresholds:
- Mean NDCG@5 > 0.40

#### Quality Gap

Measures the separation in composite quality score between relevant and irrelevant ads.

```
qualityGap = mean(qualityScore of relevant ads) - mean(qualityScore of irrelevant ads)
```

A positive quality gap means the scoring signals are working: relevant ads consistently receive higher quality scores than irrelevant ones. If the gap is near zero, the scoring function cannot distinguish relevant from irrelevant ads, and the ranking is essentially random (driven only by bid). A large gap means the scoring function is a strong ranker independent of bid amount.

Pass threshold:
- Quality gap > 0.0

#### Per-Category Breakdown

All metrics above are also computed per industry category (e-commerce, finance, healthcare, etc.). This reveals whether the ranking works uniformly or has blind spots. For example, if entertainment pages have P@1=0.30 while finance pages have P@1=1.00, it suggests the taxonomy mapping or keyword templates are weaker for entertainment.

### Auction Metrics

These are correctness properties, not quality metrics. They verify the second-price auction behaves according to its specification.

| Property | What it verifies |
|----------|-----------------|
| Highest rank score wins | `sort(candidates, by=finalRankScore, desc)[0]` is the winner |
| Second-price payment | Winner pays based on second place's score, not their own bid |
| Floor price | Single bidder pays the floor ($0.50), not $0 |
| Quality overrides bid | Lower bid + higher quality can beat higher bid + lower quality |
| Pacing filtering | `pacingMultiplier <= 0` removes the ad from the auction entirely |
| Tie-breaking | Equal `finalRankScore` then higher `eCPM` then higher `qualityScore` |
| Price cap | `pricePaid <= winnerBid` always (winner never pays more than they offered) |

### Pacing Metrics

The pacing system uses a PI (Proportional-Integral) controller to adjust each campaign's delivery rate. The simulation runs a closed loop: Go auctions generate spend, a Python subprocess computes new multipliers, which feed back into the next round of auctions.

#### Budget Utilization Error

Measures how close the campaign's actual spend is to its target budget.

```
utilizationError = |1.0 - (actualSpend / totalBudget)|
```

The entire purpose of pacing is to spend the budget, not more, not less. A utilization error of 0 means the campaign spent exactly its budget. Underspending means missed opportunity (the advertiser paid for impressions they did not get). Overspending means the platform absorbs the loss or the advertiser is overcharged.

#### Over-Spend Ratio

Measures how much a campaign exceeded its budget, as a multiple.

```
overSpendRatio = actualSpend / totalBudget  (only when actualSpend > totalBudget, else 0)
```

This is the pacing system's most critical failure mode. Moderate underspend is tolerable (the campaign just runs a bit slowly). Overspend is a financial liability: the platform either eats the cost or bills the advertiser more than agreed.

Note: the PI controller does not hard-stop campaigns at budget exhaustion. When `remaining_budget <= 0`, it returns `status=budget_exhausted` with `error_normalized=-1.0`, but the multiplier floor (0.5) still allows the campaign to win auctions. Small-budget campaigns under heavy traffic can overspend significantly.

#### Multiplier CV (Coefficient of Variation)

Measures how stable the pacing multiplier is over time.

```
multiplierCV = stddev(multiplierHistory) / mean(multiplierHistory)
```

A pacing system that oscillates wildly (1.8 to 0.5 to 1.9 to 0.5) delivers in unpredictable bursts. This creates uneven impression distribution and can cause quality issues (all impressions concentrated in a few minutes). Low CV means the controller converged to a steady delivery rate. High CV might indicate the PI gains (Kp=0.3, Ki=0.08) are too aggressive, or the acceleration limit (10% per cycle) is too loose.

#### Multiplier History

Tracks the sequence of pacing multiplier values at each pacing checkpoint. A healthy campaign shows warmup (multiplier rises from 1.0 toward target), steady state (small oscillations around a stable value), and optionally wind-down (multiplier decreases as budget runs low). Pathological patterns include being stuck at bounds (0.5 or 2.0 for extended periods), monotonic decrease without recovery, or high-frequency oscillation.

#### Spend Curve

Tracks cumulative spend at each pacing checkpoint. The ideal spend curve is linear, with equal spend per interval. A steep early curve followed by a flat tail means the campaign front-loaded spend and then ran dry. A flat early curve followed by a steep tail means the controller was too conservative initially and had to rush at the end.

#### Chart Visualizations

`TestPacingVisualization` runs a large-scale simulation (500 intervals x 50 requests, 100 pacing cycles) and generates three PNG charts in `tests/reports/`:

1. **Multiplier Trajectory** (`{timestamp}_multiplier_trajectory.png`): line chart showing each campaign's multiplier over time, with dashed lines at the 0.5/2.0 bounds. Reveals warmup, correction, steady state, and how urgency affects late-day behavior.

2. **Cumulative Spend vs Ideal** (`{timestamp}_cumulative_spend.png`): solid lines for actual cumulative spend, dashed lines for ideal linear spend (daily budget distributed evenly across cycles). Shows whether campaigns are front-loading, starving, or tracking their target.

3. **Spend Rate** (`{timestamp}_spend_rate.png`): spend delta per pacing cycle. Shows velocity spikes and how quickly the controller reacts to over/underspend.

The PI controller uses `daily_time_factor` (fraction of day elapsed). A 24-second test would map to 0.03% of a day, making all spend look like massive overshoot. The visualization test passes simulated timestamps via `--sim-time` that advance proportionally across a full day (100 cycles = 864 simulated seconds each), producing realistic pacing dynamics without modifying production code paths.

### PI Controller Parameters

The production PI controller parameters exercised by the simulation:

| Parameter | Value | Description |
|-----------|-------|-------------|
| Kp | 0.3 | Proportional gain: how strongly the controller reacts to current error |
| Ki | 0.08 | Integral gain: how strongly the controller reacts to accumulated error |
| Min multiplier | 0.5 | Lower bound, campaign delivery can be halved but not stopped |
| Max multiplier | 2.0 | Upper bound, campaign delivery can be doubled |
| Max integral | 5.0 | Anti-windup cap on cumulative error |
| Acceleration limit | 10% | Maximum per-cycle change as fraction of current multiplier |

The urgency factor increases both P and I terms as deadlines approach:

```
urgency = 0.3 * (1 + campaignTimeFactor^2) + 0.7 * (1 + dailyTimeFactor^2)
```

This makes the controller more aggressive late in the day and late in the campaign, which is desirable since there is less time to recover from under/overspend.

### Ground Truth Methodology

An ad is labeled "relevant" to a page if both conditions hold:

1. **Same industry category**: the ad was generated from the same industry template as the page (e.g., both "finance")
2. **At least 2 keyword overlaps**: the ad's targeting keywords share at least 2 terms with the page's extracted keywords

This is intentionally a proxy, not a gold-standard label. The threshold of 2 keyword overlaps avoids labeling ads as relevant based on a single coincidental keyword match (e.g., "best" appearing in both a travel ad and a food page). The same-category constraint ensures the label reflects topical alignment, not just lexical overlap.

Limitations:
- Cross-category relevance is missed (a "cloud computing" ad is relevant to both "technology" and "saas" pages, but only labeled relevant for one)
- Semantic relevance without keyword overlap is missed (an ad about "luxury watches" is relevant to a page about "high-end fashion accessories" even with zero keyword overlap)
- The labels are only as good as the fixture templates; if an industry's keyword pool is too generic, the overlap threshold may be too easy or too hard to hit

These limitations are acceptable for a ranking evaluation because the metrics measure relative ordering (does the pipeline rank labeled-relevant ads above labeled-irrelevant ones?), not absolute recall. A biased but consistent label set still reveals whether scoring changes improve or degrade ranking quality.

### Evaluation Fixture Data

All fixtures are deterministically generated with seeded randomness (`seed=42` for ads, `seed=99` for pages), so results are reproducible across runs.

- **Ads**: approximately 1,500 ads (50 real from `data/ads_inventory.json` plus approximately 1,450 synthetic, targeting 125 per industry across 12 industries). 70% CPM ($1-$15 bid) / 30% CPC ($0.50-$5 bid). Industries: e-commerce, SaaS, entertainment, education, finance, healthcare, travel, automotive, food-beverage, technology, fashion, sports. Real ads from the inventory are mapped from their original content categories (lifestyle, soccer, football, etc.) to the 12-industry taxonomy via `ContentCategoryToIndustry`.
- **Pages**: approximately 100 pages, consisting of all 41 pages from `data/crawled_pages.json` (real crawled content, mapped to industries) plus synthetic pages for underrepresented categories (target: 9 per industry). Synthetic pages draw keywords from per-industry templates to ensure ground-truth overlap with the ad inventory.
- **Taxonomy**: IAB content-to-product and product-to-content mappings loaded from `data/` JSON files.

#### NLP Pre-Computed Fixtures

The `data/eval/` directory contains pre-computed NLP signals generated by running the real NLP pipeline (`KeywordExtractor`, `EntityExtractor`, `TopicClassifier`, `EmbeddingGenerator` from `python/services/nlp_service.py`) on crawled pages and ad creatives:

- `nlp_page_contexts.json`: real keywords (KeyBERT), entities (spaCy NER), IAB topics (embedding-based classification), page embeddings (384-dim, `all-MiniLM-L6-v2`), and chunk embeddings for all 41 crawled pages.
- `nlp_ad_contexts.json`: same NLP signals extracted from the 50 real ads' headline and description text.

These files are committed to the repo so Go tests never need Python or NLP models at test time. Regenerate with `make eval-fixtures`.

#### NLP Evaluation Tests

Gated behind `//go:build nlp_eval` to avoid running during normal `go test`. The NLP tests differ from synthetic tests in three ways:

1. **Real vector scores**: cosine similarity between NLP-extracted page and ad embeddings replaces mock random scores (0.6+rand / 0.2+rand).
2. **Hybrid ground truth**: an ad is "relevant" if structurally relevant (same category + keyword overlap) or semantically relevant (cosine similarity >= 0.5 between page and ad embeddings).
3. **Embedding clustering test**: verifies that intra-industry embedding similarity exceeds inter-industry similarity, confirming the NLP pipeline produces topically coherent embeddings.

### Evaluation Reports

Each evaluation run writes to `tests/evaluation/reports/`:

- `eval_{timestamp}.json`: structured JSON report with full per-category and per-campaign breakdowns
- `{timestamp}_multiplier_trajectory.png`: pacing multiplier chart (from visualization test)
- `{timestamp}_cumulative_spend.png`: spend vs ideal chart (from visualization test)
- `{timestamp}_spend_rate.png`: spend velocity chart (from visualization test)

Console output includes a formatted summary table with PASS/FAIL indicators against the configured thresholds.

## Observability

The observability stack (Prometheus, Grafana, Loki, Tempo, OpenTelemetry Collector) runs alongside the main infrastructure and provides monitoring for both system performance and business metrics.

### Instrumented Metrics

**Go API server metrics (exposed to Prometheus):**

| Metric | Description |
|--------|-------------|
| `http_requests_total` | API request rate by method, path, and status |
| `http_request_duration_seconds` | Response latencies (p50, p95, p99) |
| `events_total` | Impression and click counts by event type |
| `event_processing_duration_seconds` | Event processing latency |
| `kafka_messages_published_total` | Kafka publish rate by topic |
| `kafka_publish_duration_seconds` | Kafka publish latency |
| `db_query_duration_seconds` | Database query latency by query type |
| `db_errors_total` | Database errors by operation |
| `cache_operations_total` | Cache hit/miss by cache name (page_context, page_embedding, page_chunks, pacing_state) |
| `cache_operation_duration_seconds` | Cache operation latency |
| `ad_serve_requests_total` | Ad serve rate by status and publisher |
| `ad_fill_total` | Fill rate tracking |
| `auction_winning_bid_cents` | Bid distribution by pricing model |
| `ad_index_size` | Index statistics |

**Python consumer metrics:**

| Metric | Description |
|--------|-------------|
| `kafka_messages_processed` | Consumer throughput |
| `kafka_message_processing_duration` | Consumer processing latency |
| `kafka_consumer_lag` | Consumer lag by topic and partition |
| `pacing_calculations_total` | Pacing calculation rate by status |
| `pacing_multiplier` | Pacing multiplier distribution |

### Structured Logging

All runtime logs use structured logging via the OpenTelemetry slog handler and are shipped to Loki. The structured logger (`observability.Info`, `observability.Warn`, `observability.Error`, `observability.Debug`) is used across the service layer.

### Grafana Dashboards

The `observability/grafana/dashboards/` directory contains pre-configured dashboards:

- **API Server** with rows for Overview, Ad Serving Performance, Ad Index, Cache, Events, Database, Kafka, and Business Metrics
- **Kafka Consumers** for consumer lag and throughput

### Business and Pacing Metrics

Business metrics (campaign spend by advertiser, publisher revenue, average CPM/CPC, CTR by campaign) and pacing metrics (budget remaining, daily utilisation, spend rate vs target) are stored in the `ads_analytics` PostgreSQL schema rather than duplicated into Prometheus:

- `ads_analytics.ad_metrics_hourly` for spend, eCPM, and CTR per ad/campaign
- `ads_analytics.campaign_metrics_hourly` for spend, eCPM, and CTR per campaign
- `ads_analytics.auction_metrics_hourly` for fill rate and average winning bid
- `ads_analytics.pacing_history` for budget remaining, daily utilisation, multiplier history, and error signals

These can be queried directly via SQL or through a PostgreSQL Grafana datasource.

### Monitoring Checklist

When running traffic simulation, the following dashboards and tools are useful:

| Area | Where to look |
|------|---------------|
| Request rate, latency, error rate, fill rate | Grafana: API Server dashboard, Overview row |
| Ad serve performance, auction stats | Grafana: API Server dashboard, Ad Serving Performance row |
| Index health and refresh | Grafana: API Server dashboard, Ad Index row |
| Cache hit rates | Grafana: API Server dashboard, Cache row |
| Event processing | Grafana: API Server dashboard, Events row |
| Database query performance | Grafana: API Server dashboard, Database row |
| Kafka publish throughput | Grafana: API Server dashboard, Kafka row |
| Business KPIs (impressions, clicks, CTR) | Grafana: API Server dashboard, Business Metrics row |
| Kafka consumer lag and throughput | Grafana: Kafka Consumers dashboard |
| Kafka topics and consumer groups | Kafka UI at http://localhost:8080 |
| Application logs | Grafana: Explore with Loki datasource |
| Distributed traces | Grafana: Explore with Tempo datasource |
| Campaign spend and pacing | PostgreSQL: `ads_analytics` schema |

### Service URLs

| Service | URL |
|---------|-----|
| Ad Server API | http://localhost:8090 |
| Grafana | http://localhost:3000 (admin/admin) |
| Prometheus | http://localhost:9090 |
| Kafka UI | http://localhost:8080 |
| Flink UI | http://localhost:8081 |

## Business Metrics Dashboard

A Streamlit-based dashboard in `python/dashboard/` visualises business, pacing, and ad-level metrics by querying the `ads_analytics` PostgreSQL schema. All charts use seconds-granularity timestamps from raw event tables rather than hourly materialised views, so they remain accurate during short simulation runs.

### Launch

```bash
make dashboard

# Or directly
cd python && streamlit run dashboard/app.py
```

The dashboard opens at http://localhost:8501 and auto-refreshes every 15 seconds by default (configurable in the sidebar).

### Prerequisites

- PostgreSQL running with the `ads_analytics` schema migrated (`make setup-db`)
- Traffic simulation or live data generating events in the analytics tables
- Python dependencies installed: `pip install -r python/requirements.txt`

### Tabs

#### Overview

- Total Spend, Impressions, Clicks, CTR, Fill Rate, Active Campaigns
- Cumulative Spend Over Time
- Impression and Click Rate (rolling 10-second window)
- Spend by Advertiser
- Spend by Pricing Model (CPC/CPM)
- Fill Rate Over Time (rolling 50-auction window average)

#### Pacing Deep Dive

- Top-N Campaigns Table ranked by impression count, showing campaign name, advertiser, spend, budget, and status
- Pacing Summary Table with average, minimum, maximum, and standard deviation of multiplier, budget utilisation percentage, and latest status per campaign
- Multiplier Overlay Chart: a Plotly line chart overlaying `new_multiplier` for up to 10 selected campaigns, showing how pacing diverges across campaigns over time
- Error Signal Chart: `error_normalized` over time with a zero-line reference
- Per-Campaign Expandable Detail: current multiplier, status, budget utilisation progress bar, remaining budget, P-term vs I-term chart, urgency factor chart
- Budget Exhausted Campaigns table

#### Ad and Campaign Performance

- Campaign Performance Table sortable by spend, impressions, clicks, CTR, and eCPM, enriched with campaign and advertiser names
- Per-Campaign Ad Breakdown with expandable rows showing individual ads, including headline, pricing model, bid, spend, CTR, and destination URL
- Spend Burn-Down Chart showing remaining budget over time from `pacing_history` for top 10 campaigns
- Top Winning Ads ranked by auction wins, with average winning bid and final score

### Enrichment Joins

All analytics tables store only numeric IDs. The dashboard enriches display values using LEFT JOINs against the main `public` schema:

| Analytics Column | Joined To | Display |
|-----------------|-----------|---------|
| `campaign_id` | `public.campaigns.name` | Campaign name (fallback: "Campaign #ID") |
| `campaign_id` via `advertiser_id` | `public.advertisers.name` | Advertiser name (fallback: "Advertiser #ID") |
| `ad_id` | `public.ads.headline` | Ad headline (fallback: "Ad #ID") |
| `ad_id` via `ad_set_id` | `public.ad_sets.pricing_model` | CPC / CPM |

LEFT JOINs ensure the dashboard never breaks if main-schema data is missing; it gracefully falls back to displaying raw IDs.

### Sidebar Controls

- **Time Range**: Last 5 min, 15 min, 1 hour (default), 6 hours, 24 hours, or All time
- **Auto-Refresh**: Toggle on/off (default on), configurable interval from 5 to 120 seconds (default 15s)
- **Manual Refresh**: Button to clear cached data and re-query immediately

## Extending the Test Suite

To add new test scenarios:

1. Create new files in the appropriate directory
2. Follow existing patterns for API client usage
3. Use helpers for common operations
4. Update fixtures as needed

## Reports

E2E test reports are generated in the `tests/reports/` directory with timestamps. Evaluation reports and charts are written to `tests/evaluation/reports/`.
