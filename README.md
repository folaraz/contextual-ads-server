# Contextual Ads Server

A contextual advertising system that serves ads based on page content rather than user tracking. It uses NLP to analyze page and ad content, matches them via IAB taxonomy-based targeting, runs a real-time auction, and enforces budget pacing -- all without third-party cookies.

For a detailed write-up on the design, architecture, and decisions behind this project, see the blog post: [Contextual Ads](https://folaraz.com/blog/contextual-ad-server/#exploring-contextual-ad-serving-by-building-one-from-scratch)

## Architecture

- **Ad Server (Go)** -- Handles ad requests, runs the auction (second-price), and tracks events. Maintains an in-memory ad index that refreshes every 30s.
- **Context Processors (Python)** -- Kafka consumers that run NLP (embeddings + classification) on pages and ads, writing results to Redis and PostgreSQL.
- **Analytics Pipeline (Apache Flink)** -- Aggregates impression, click, and pacing events from Kafka and sinks to PostgreSQL.
- **Pacing Worker (Python)** -- Enforces daily budget pacing so campaigns spend evenly over their flight.
- **Dashboard (Streamlit)** -- Business metrics dashboard for spend, CTR, and pacing health.

## Infrastructure

PostgreSQL (pgvector), Redis, Kafka, Apache Flink, and an OpenTelemetry observability stack (Prometheus, Grafana, Loki, Tempo). Everything runs via Docker Compose.

## Quick Start

```bash
make up              
make bootstrap       
make simulate        
```

## Key Make Targets

| Command                            | Description |
|------------------------------------|---|
| `make restart clean` / `make down` | Start / stop all services |
| `make bootstrap`                   | Generate campaigns, seed DB, preprocess pages and ads |
| `make simulate`                    | Traffic simulation (1k reqs, 10 workers) |
| `make simulate-heavy`              | Heavy simulation (10k reqs, 50 workers) |
| `make eval`                        | Run all evaluation tests (relevance + pacing) |
| `make dashboard`                   | Launch the Streamlit metrics dashboard |
| `make help`                        | List all available targets |

