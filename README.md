# contextual-ads-server

/ad-server-project/
├── .git/
├── services/
│   ├── ad-handler/          # Go, Rust, or Java (Fast API)
│   │   ├── main.go
│   │   └── Dockerfile
│   ├── auction-service/     # Go or Java (Ranking logic)
│   │   ├── main.go
│   │   └── Dockerfile
│   ├── tracking-service/    # Go (Simple ingestion)
│   │   ├── main.go
│   │   └── Dockerfile
│   └── nlp-processor/       # Python (Offline analysis)
│       ├── main.py
│       └── Dockerfile
├── pkg/ or /libs/
│   └── ad-models/           # Shared code (e.g., Ad struct)
│       └── models.go
├── scripts/
│   ├── deploy.sh
│   └── reset_budgets.py
├── docker-compose.yml       # To run everything locally
└── README.md

how keybert works
// imporvemtns chunk based add placements

https://maartengr.github.io/KeyBERT/api/keybert.html