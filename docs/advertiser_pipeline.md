# Ad Preprocessing Pipeline

## Input from Advertiser

```json
{
  "ad_id": "ad_67890",
  "advertiser_id": "adv_zoom_inc",
  "campaign_id": "camp_q4_2025",
  "creative": {
    "title": "Zoom - #1 Video Conferencing",
    "description": "Connect your remote team with HD video, screen sharing, and breakout rooms.",
    "landing_url": "https://zoom.us/video-conferencing",
    "image_url": "https://zoom.us/assets/banner.jpg"
  },
  "advertiser_keywords": ["video conferencing", "remote meetings", "webinar"],
  "advertiser_topics": ["Business Software", "Communication Tools"],
  "targeting": {
    "countries": ["US", "CA", "GB"],
    "languages": ["en"]
  },
  "bid_cpm": 3.50,
  "daily_budget": 1000.00
}
```

---

## Processing Pipeline

### 1. Landing Page Crawl & Extract (5-10 seconds)

```python
# Fetch landing page
response = requests.get("https://zoom.us/video-conferencing", timeout=10)
html = response.text

# Extract using readability/beautifulsoup
from readability import Document
doc = Document(html)

extracted = {
    "title": "Video Conferencing Solutions | Zoom",
    "meta_description": "Zoom provides HD video meetings for teams...",
    "h1": "Professional Video Conferencing",
    "h2_headings": [
        "HD Video & Audio",
        "Screen Sharing & Collaboration", 
        "Breakout Rooms",
        "Recording & Transcription"
    ],
    "body_text": """
        Zoom is a leader in modern enterprise video communications...
        Features include HD video, screen sharing, breakout rooms...
        Trusted by 500,000+ organizations worldwide...
    """,
    "word_count": 847,
    "token_count": 1123
}

# Combine all text
full_text = f"{extracted['title']} {extracted['meta_description']} {' '.join(extracted['h2_headings'])} {extracted['body_text']}"
```

---

### 2. Keyword Extraction & Augmentation (1-2 seconds)

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from rake_nltk import Rake
import spacy

# Method A: TF-IDF extraction
tfidf = TfidfVectorizer(max_features=50, ngram_range=(1,3))
tfidf.fit_transform([full_text])
tfidf_keywords = tfidf.get_feature_names_out()

# Result
tfidf_keywords = [
    "video conferencing", "screen sharing", "breakout rooms",
    "hd video", "remote meetings", "collaboration tools",
    "zoom meetings", "video calls", "enterprise video"
]

# Method B: RAKE (Rapid Automatic Keyword Extraction)
rake = Rake()
rake.extract_keywords_from_text(full_text)
rake_keywords = rake.get_ranked_phrases()[:20]

# Result
rake_keywords = [
    "professional video conferencing solutions",
    "hd video audio quality",
    "screen sharing collaboration features",
    "breakout rooms functionality"
]

# Method C: spaCy noun phrases
nlp = spacy.load("en_core_web_lg")
doc = nlp(full_text)
noun_phrases = [chunk.text for chunk in doc.noun_chunks if len(chunk.text.split()) <= 3]

# Combine all sources
all_keywords = (
    list(advertiser_keywords) +  # ["video conferencing", "remote meetings", "webinar"]
    list(tfidf_keywords) +
    [kw for kw in rake_keywords if len(kw.split()) <= 3] +
    list(set(noun_phrases))
)

# Deduplicate and score
from collections import Counter
keyword_freq = Counter(all_keywords)

# Final keywords with weights
final_keywords = {
    "video conferencing": 1.0,    # Advertiser + found multiple times
    "remote meetings": 0.9,        # Advertiser keyword
    "webinar": 0.8,                # Advertiser keyword
    "screen sharing": 0.85,        # High TF-IDF
    "breakout rooms": 0.75,        # Found in headings
    "hd video": 0.7,
    "collaboration": 0.65,
    "zoom": 0.6,                   # Brand name
    "enterprise video": 0.55
}
```

**Output**:
```json
{
  "keywords": [
    {"term": "video conferencing", "weight": 1.0, "source": "advertiser+auto"},
    {"term": "remote meetings", "weight": 0.9, "source": "advertiser"},
    {"term": "webinar", "weight": 0.8, "source": "advertiser"},
    {"term": "screen sharing", "weight": 0.85, "source": "tfidf"},
    {"term": "breakout rooms", "weight": 0.75, "source": "rake+heading"}
  ]
}
```

---

### 3. Named Entity Recognition (2-3 seconds)

```python
import spacy

nlp = spacy.load("en_core_web_lg")
doc = nlp(full_text)

entities = []
for ent in doc.ents:
    if ent.label_ in ["PRODUCT", "ORG", "PERSON", "GPE"]:
        entities.append({
            "text": ent.text,
            "label": ent.label_,
            "confidence": 1.0 if ent.label_ in ["PRODUCT", "ORG"] else 0.8
        })

# Also use custom patterns for products
from spacy.matcher import Matcher
matcher = Matcher(nlp.vocab)

# Pattern: "Zoom", "Microsoft Teams", "Google Meet" etc
product_patterns = [
    [{"LOWER": {"IN": ["zoom", "teams", "meet", "webex", "slack"]}}],
    [{"TEXT": {"REGEX": "^[A-Z][a-z]+"}}, {"LOWER": {"IN": ["meet", "video", "conference"]}}]
]

for pattern in product_patterns:
    matcher.add("PRODUCT", [pattern])

matches = matcher(doc)
for match_id, start, end in matches:
    span = doc[start:end]
    entities.append({
        "text": span.text,
        "label": "PRODUCT",
        "confidence": 0.9
    })
```

**Output**:
```json
{
  "entities": [
    {"text": "Zoom", "type": "PRODUCT", "confidence": 1.0},
    {"text": "Microsoft Teams", "type": "PRODUCT", "confidence": 0.9},
    {"text": "Google Meet", "type": "PRODUCT", "confidence": 0.9},
    {"text": "United States", "type": "GPE", "confidence": 0.8},
    {"text": "enterprise", "type": "ORG", "confidence": 0.7}
  ]
}
```

---

### 4. Topic Classification (1-2 seconds)

```python
# Option A: Rule-based (fast)
def classify_by_keywords(keywords):
    topic_map = {
        "Business Software": ["software", "enterprise", "business", "saas"],
        "Communication Tools": ["communication", "chat", "messaging", "video"],
        "Video Conferencing": ["video conferencing", "video call", "meeting", "zoom"],
        "Productivity": ["productivity", "workflow", "task", "project"],
        "Remote Work": ["remote", "work from home", "distributed"]
    }
    
    scores = {}
    for topic, trigger_words in topic_map.items():
        score = sum(1 for kw in keywords if any(tw in kw.lower() for tw in trigger_words))
        if score > 0:
            scores[topic] = min(score / len(trigger_words), 1.0)
    
    return scores

topic_scores = classify_by_keywords(final_keywords.keys())

# Result
topic_scores = {
    "Video Conferencing": 0.95,
    "Communication Tools": 0.85,
    "Business Software": 0.75,
    "Remote Work": 0.70
}

# Option B: ML Classifier (more accurate)
from transformers import pipeline

classifier = pipeline("zero-shot-classification", 
                     model="facebook/bart-large-mnli")

candidate_labels = [
    "Business Software",
    "Communication Tools", 
    "Video Conferencing",
    "Productivity Tools",
    "Remote Work",
    "Project Management",
    "E-commerce",
    "Finance"
]

result = classifier(full_text[:512], candidate_labels)

# Result
ml_topics = {
    result['labels'][0]: result['scores'][0],  # "Video Conferencing": 0.92
    result['labels'][1]: result['scores'][1],  # "Communication Tools": 0.87
    result['labels'][2]: result['scores'][2],  # "Business Software": 0.81
}

# Merge with advertiser topics
advertiser_topics = ["Business Software", "Communication Tools"]
for topic in advertiser_topics:
    if topic in ml_topics:
        ml_topics[topic] = max(ml_topics[topic], 0.95)  # Boost advertiser-declared
    else:
        ml_topics[topic] = 0.90

# Map to taxonomy IDs
topic_taxonomy = {
    "Business Software": 101,
    "Communication Tools": 215,
    "Video Conferencing": 338,
    "Remote Work": 421
}

final_topics = [
    {"id": 338, "name": "Video Conferencing", "confidence": 0.92},
    {"id": 215, "name": "Communication Tools", "confidence": 0.87},
    {"id": 101, "name": "Business Software", "confidence": 0.81},
    {"id": 421, "name": "Remote Work", "confidence": 0.70}
]
```

---

### 5. Embedding Generation (0.5-1 second)

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-mpnet-base-v2')  # 768 dims

# Prepare text for embedding
embedding_text = f"""
{extracted['title']}. {extracted['meta_description']}. 
{' '.join(extracted['h2_headings'])}. 
{' '.join(list(final_keywords.keys())[:10])}.
"""

# Truncate to 512 tokens
tokens = embedding_text.split()[:512]
embedding_text = ' '.join(tokens)

# Generate embedding
ad_embedding = model.encode(embedding_text)

# Result: numpy array of 768 floats
ad_embedding = [0.234, -0.891, 0.456, 0.123, ..., 0.789]  # 768 dimensions
```

**Example values**:
```python
ad_embedding[:10] = [
    0.234,   # Dimension 0
    -0.891,  # Dimension 1
    0.456,   # Dimension 2
    0.123,
    -0.567,
    0.890,
    -0.234,
    0.678,
    0.345,
    -0.901
]
```

---

### 6. Quality Checks & Validation (0.5 seconds)

```python
def validate_ad_data(ad_data):
    issues = []
    
    # Check keyword count
    if len(ad_data['keywords']) < 3:
        issues.append("WARNING: Only 2 keywords, recommend 5-10")
    
    # Check topic confidence
    if all(t['confidence'] < 0.6 for t in ad_data['topics']):
        issues.append("WARNING: Low topic confidence, verify targeting")
    
    # Check landing page content
    if ad_data['word_count'] < 100:
        issues.append("ERROR: Landing page too short")
    
    # Check embedding quality
    if abs(ad_data['embedding'].mean()) > 0.5:
        issues.append("WARNING: Unusual embedding distribution")
    
    return {
        "valid": len([i for i in issues if i.startswith("ERROR")]) == 0,
        "issues": issues
    }

validation = validate_ad_data(ad_data)
# Result: {"valid": True, "issues": []}
```

---

## Final Processed Ad Record

```json
{
  "ad_id": "ad_67890",
  "advertiser_id": "adv_zoom_inc",
  "campaign_id": "camp_q4_2025",
  
  "creative": {
    "title": "Zoom - #1 Video Conferencing",
    "description": "Connect your remote team with HD video...",
    "landing_url": "https://zoom.us/video-conferencing",
    "image_url": "https://zoom.us/assets/banner.jpg"
  },
  
  "keywords": [
    {"term": "video conferencing", "weight": 1.0, "source": "advertiser+auto"},
    {"term": "remote meetings", "weight": 0.9, "source": "advertiser"},
    {"term": "webinar", "weight": 0.8, "source": "advertiser"},
    {"term": "screen sharing", "weight": 0.85, "source": "auto"},
    {"term": "breakout rooms", "weight": 0.75, "source": "auto"},
    {"term": "hd video", "weight": 0.7, "source": "auto"},
    {"term": "collaboration", "weight": 0.65, "source": "auto"}
  ],
  
  "entities": [
    {"text": "Zoom", "type": "PRODUCT", "confidence": 1.0},
    {"text": "Microsoft Teams", "type": "PRODUCT", "confidence": 0.9},
    {"text": "Google Meet", "type": "PRODUCT", "confidence": 0.9}
  ],
  
  "topics": [
    {"id": 338, "name": "Video Conferencing", "confidence": 0.92},
    {"id": 215, "name": "Communication Tools", "confidence": 0.87},
    {"id": 101, "name": "Business Software", "confidence": 0.81},
    {"id": 421, "name": "Remote Work", "confidence": 0.70}
  ],
  
  "embedding": [0.234, -0.891, 0.456, ..., 0.789],  // 768 dims
  
  "landing_page_metadata": {
    "title": "Video Conferencing Solutions | Zoom",
    "word_count": 847,
    "token_count": 1123,
    "main_topics": ["video", "conferencing", "meetings"],
    "crawled_at": "2025-11-05T10:30:00Z"
  },
  
  "targeting": {
    "countries": ["US", "CA", "GB"],
    "languages": ["en"]
  },
  
  "bid_cpm": 3.50,
  "daily_budget": 1000.00,
  "status": "active",
  
  "quality_metrics": {
    "keyword_count": 7,
    "topic_count": 4,
    "entity_count": 3,
    "landing_page_quality": 0.85,
    "overall_quality": 0.82
  },
  
  "processed_at": "2025-11-05T10:30:15Z",
  "processing_version": "v2.3"
}
```

---

## Storage Operations

### Elasticsearch Insert

```json
POST /contextual_ads/_doc/ad_67890
{
  "ad_id": "ad_67890",
  "keywords": ["video conferencing", "remote meetings", "webinar", "screen sharing", "breakout rooms"],
  "topics": ["Video Conferencing", "Communication Tools", "Business Software"],
  "topic_ids": [338, 215, 101],
  "bid_cpm": 3.50,
  "targeting": {
    "countries": ["US", "CA", "GB"]
  },
  "status": "active"
}
```

### PostgreSQL Inserts

```sql
-- Ad topics
INSERT INTO ad_topics VALUES
('ad_67890', 338, 0.92),
('ad_67890', 215, 0.87),
('ad_67890', 101, 0.81),
('ad_67890', 421, 0.70);

-- Ad entities
INSERT INTO ad_entities VALUES
('ad_67890', 'PRODUCT', 'Zoom', 1.0),
('ad_67890', 'PRODUCT', 'Microsoft Teams', 0.9),
('ad_67890', 'PRODUCT', 'Google Meet', 0.9);

-- Ad metadata
INSERT INTO ads VALUES
('ad_67890', 'adv_zoom_inc', 'Zoom - #1 Video Conferencing', 
 'Connect your remote team...', 'https://zoom.us/video-conferencing',
 3.50, 1000.00, 'active', '2025-11-05 10:30:15');
```

### Milvus Insert

```python
from pymilvus import Collection

collection = Collection("ad_embeddings")

data = [
    ["ad_67890"],  # IDs
    [[0.234, -0.891, 0.456, ..., 0.789]],  # Embeddings (768 dims)
    [3.50],  # Bid CPM
    [0.0]    # Initial CTR
]

collection.insert(data)
```

---

## Processing Time Breakdown

```
Operation                        Time
─────────────────────────────────────
1. Landing page fetch            3s
2. Content extraction            1s
3. Keyword extraction            2s
4. NER                           3s
5. Topic classification          2s
6. Embedding generation          1s
7. Validation                    0.5s
8. Database writes               1.5s
─────────────────────────────────────
Total                            14s
```

---

## Batch Processing

For bulk ad uploads (e.g., 10,000 ads):

```python
# Parallel processing with 20 workers
from concurrent.futures import ThreadPoolExecutor

ads_to_process = load_ads_from_csv("ads.csv")  # 10,000 ads

with ThreadPoolExecutor(max_workers=20) as executor:
    results = executor.map(process_single_ad, ads_to_process)

# Processing time: 10,000 ads / 20 workers = 500 batches
# Time per batch: ~14s
# Total: ~7,000s (2 hours)

# With GPU for embeddings: ~30 minutes
```

---

## Key Points

1. **Advertiser inputs are trusted but augmented** - Use their keywords/topics as high-confidence signals, then add auto-extracted ones
2. **Landing page is critical** - 80% of semantic understanding comes from crawling the landing page
3. **Multi-source keyword extraction** - Combine TF-IDF, RAKE, and spaCy for comprehensive coverage
4. **Topic classification** - Use both rule-based (fast) and ML (accurate), boost advertiser-declared topics
5. **Embeddings capture semantics** - Combine title, description, headings, and top keywords into one text for embedding
6. **Quality validation** - Check for minimum requirements before activating ad
7. **Processing is offline** - Done once per ad, results cached in multiple indexes for fast serving

This pipeline runs once when ad is uploaded, then serves millions of requests efficiently.