# Scaling and Weight Determination Strategies

Great questions! These are critical practical challenges in building a contextual ad system. Let me break down both.

---

## Part 1: Determining Hierarchical Category Weights

### **Initial Weight Assignment Methods**

#### **Method A: Data-Driven Learning (Most Common)**

**Historical Performance Analysis**:

```
Collect data over 2-3 months:
- Topic: Business Software > Productivity > Project Management
- Page Topic: Business Software > Productivity
- Result: Ad served, CTR: 2.3%, Conversion: 0.8%

Aggregate thousands of such data points:
- 3-level exact match: Average CTR 2.1%, CVR 0.9%
- 2-level match: Average CTR 1.5%, CVR 0.6%
- 1-level match: Average CTR 0.8%, CVR 0.3%
- Sibling category match: Average CTR 1.2%, CVR 0.5%
- No match: Average CTR 0.2%, CVR 0.1%
```

**Derive weights from performance**:
- 3-level exact match = baseline 1.0 (best performance)
- 2-level match = 0.85× (performance ratio: 1.5/2.1 ≈ 0.71, adjusted to 0.85)
- 1-level match = 0.60× (performance ratio: 0.8/2.1 ≈ 0.38, adjusted to 0.60)
- Sibling category = 0.70× (shares parent, better than unrelated)
- Parent-child relation = 0.75×

**These multipliers become your hierarchy weights**

---

#### **Method B: Expert-Based Rule System**

When you don't have historical data yet:

**Define business rules**:
```
Exact Match at Level 3 (most specific):
- Weight: 1.0
- Example: Ad is "Video Conferencing" → Page is "Video Conferencing"

Match at Level 2 (category):
- Weight: 0.85
- Example: Ad is "Video Conferencing" → Page is "Communication Tools"

Match at Level 1 (broad):
- Weight: 0.70
- Example: Ad is "Video Conferencing" → Page is "Business Software"

Related Categories (siblings):
- Weight: 0.65
- Example: Ad is "Video Conferencing" → Page is "Messaging Platforms"
  (both under Communication Tools)

Adjacent Categories (cousins):
- Weight: 0.45
- Example: Ad is "Video Conferencing" → Page is "Project Management"
  (both under Business Software but different Level 2)

No Relationship:
- Weight: 0.0
- Example: Ad is "Video Conferencing" → Page is "Athletic Footwear"
```

---

#### **Method C: Machine Learning Approach**

**Train a model to learn optimal weights**:

1. **Feature Engineering**:
    - Topic path similarity (how many levels match)
    - Category co-occurrence in training data
    - Semantic similarity between category names
    - User behavior patterns (do users who view X also click Y?)

2. **Training Dataset**:
   ```
   Features: [page_topic_L1, page_topic_L2, page_topic_L3, 
              ad_topic_L1, ad_topic_L2, ad_topic_L3,
              levels_matched, semantic_distance]
   Label: user_clicked (1/0)
   ```

3. **Model Output**:
    - Learned weights for each hierarchy level
    - Automatically discovers that some category pairs perform better
    - Example: "Video Conferencing" ads might perform unusually well on "Remote Work" content even without exact topic match

4. **Update Periodically**:
    - Retrain weekly/monthly with fresh performance data
    - Weights adapt to changing user behavior

---

### **Confidence Score Assignment**

**For page classification confidence (e.g., "Business Software: 0.92")**:

**Classifier Output Method**:
```
Use a multi-label classifier (like BERT-based model):

Input: Page content
Output: Probability distribution over topics

Example Output:
- Business Software: 0.92 (strong signals: "software", "tools", "platforms")
- Productivity: 0.88 (signals: "productivity", "efficiency", "tasks")
- Technology: 0.65 (generic, less specific)
- Finance: 0.12 (few relevant signals)
- Sports: 0.03 (almost no signals)
```

**The probability IS the confidence score**

**Rule-Based Confidence (simpler approach)**:
```
Count topic-relevant keywords:

Business Software signals found: 18 keywords
Productivity signals found: 15 keywords
Sports signals found: 1 keyword

Normalize:
- Business Software: 18/20 possible strong signals = 0.90
- Productivity: 15/18 possible signals = 0.83
- Sports: 1/15 possible signals = 0.07
```

---

## Part 2: Scaling for Many Ads

### **Challenge**: 10 million ads × keyword matching × topic matching × similarity calculation = **too slow!**

### **Solution: Multi-Stage Filtering Pipeline**

#### **Stage 1: Pre-Computation (Done Offline)**

**For Each Ad (done once, stored in database)**:
```
Ad Upload/Update Time:
1. Extract keywords → Store in inverted index
2. Classify topics → Store topic IDs
3. Generate content embedding → Store 768-dim vector
4. Compute keyword hash signatures → Store
5. Index in vector database (FAISS, Pinecone, etc.)

Example Ad Record:
{
  ad_id: 12345,
  keywords: ["project management", "productivity", "team"],
  keyword_hash: "a3f9c2b8d1e...",
  topics: [101, 215, 338],  // Topic IDs in hierarchy
  topic_path: "Software>Productivity>ProjectMgmt",
  embedding: [0.234, -0.891, 0.456, ...],  // 768 numbers
  bid: 4.20,
  ... other metadata
}
```

**Build Inverted Indexes**:
```
Keyword Index:
"project management" → [ad_12345, ad_23456, ad_78901, ...]
"productivity" → [ad_12345, ad_34567, ad_45678, ...]
"video conferencing" → [ad_67890, ad_89012, ...]

Topic Index:
Topic_ID_215 (Productivity) → [ad_12345, ad_34567, ad_56789, ...]
Topic_ID_338 (ProjectMgmt) → [ad_12345, ad_23456, ...]
```

This reduces 10 million ads to manageable candidate sets!

---

#### **Stage 2: Rapid Filtering (Real-Time)**

**Request comes in** → Need ad in <50ms

**Step 1: Extract Page Keywords** (5ms)
```
Quick keyword extraction from page:
→ ["remote work", "productivity", "team", "project management"]
```

**Step 2: Query Inverted Index** (2ms)
```
Look up each keyword in index:

"remote work" → 15,000 ads
"productivity" → 25,000 ads
"team" → 40,000 ads
"project management" → 8,000 ads

Take UNION: ~50,000 candidate ads (many ads match multiple keywords)
```

**Step 3: Topic Filter** (3ms)
```
Page classified as: Topic_215 (Productivity), Topic_101 (Business Software)

Query topic index:
Topic_215 → 30,000 ads
Topic_101 → 50,000 ads

Take INTERSECTION with keyword candidates:
50,000 keyword matches ∩ 80,000 topic matches = ~12,000 ads
```

**Already reduced from 10 million to 12,000!**

**Step 4: Quick Score Filter** (8ms)
```
For each of 12,000 ads:
- Count exact keyword matches (fast lookup)
- Check topic overlap (simple array intersection)
- Apply minimum threshold

Example:
Ad must have:
- At least 2 matching keywords OR
- At least 1 exact topic match

This eliminates ads with weak signals
Result: ~2,000 ads remain
```

---

#### **Stage 3: Detailed Scoring** (15ms)

Now we have manageable number (2,000 ads) for expensive operations:

**Step 1: Cosine Similarity on Subset**
```
NOT calculated for all 10M ads!
Only for the 2,000 candidates

Use approximate nearest neighbor search:
- FAISS library with IVF index
- Pre-clustered embeddings
- Only compute exact similarity for top candidates

Find top 200 by similarity in ~10ms
```

**Step 2: Detailed Keyword Scoring** (3ms)
```
For 200 ads:
- Calculate exact match vs partial match
- Apply importance weighting
- Compute final keyword score
```

**Step 3: Detailed Topic Scoring** (2ms)
```
For 200 ads:
- Calculate hierarchy depth match
- Apply confidence weights
- Compute final topic score
```

---

#### **Stage 4: Final Ranking** (5ms)

```
200 fully-scored ads:
- Apply combined scoring formula
- Sort by final score
- Apply business rules (budget, frequency caps)
- Select top 3-5 winners
```

**Total Time: 38ms** (well under 50ms target!)

---

### **Scaling Strategies in Detail**

#### **1. Inverted Index Sharding**

```
Shard keywords by hash:

Shard 1: Keywords starting with A-F → Server 1
Shard 2: Keywords starting with G-M → Server 2
Shard 3: Keywords starting with N-S → Server 3
Shard 4: Keywords starting with T-Z → Server 4

Parallel lookup across shards, merge results
```

#### **2. Topic Index Optimization**

```
Instead of storing full paths, use bit vectors:

Each ad has a 1024-bit vector:
- Bit 0: Has Topic_1 (yes/no)
- Bit 1: Has Topic_2 (yes/no)
- ...
- Bit 1023: Has Topic_1024 (yes/no)

Fast bitwise operations:
Page topics: 0100101000...
Ad topics:   0110100000...
AND result:  0100100000... (matches found!)

This is extremely fast (nanoseconds)
```

#### **3. Bloom Filters for Quick Rejection**

```
Create a bloom filter for each ad's keywords:

Before detailed matching:
Query: "Does ad contain keyword 'productivity'?"
Bloom filter: NO → Skip this ad immediately
Bloom filter: MAYBE → Do detailed check

Bloom filters are tiny (few KB) and super fast
Eliminates 70-80% of ads instantly
```

#### **4. Tiered Scoring**

```
Tier 1: Cheap filters (keyword count, topic match)
→ 10M ads → 50K ads (5ms)

Tier 2: Medium cost (detailed keyword scoring)
→ 50K ads → 2K ads (10ms)

Tier 3: Expensive (cosine similarity)
→ 2K ads → 200 ads (15ms)

Tier 4: Final ranking
→ 200 ads → 5 winners (5ms)
```

---

## Part 3: Implementing Keyword Matching

### **Exact Match Detection**

#### **String Normalization Pipeline**:

```
Step 1: Lowercase everything
"Project Management" → "project management"

Step 2: Remove punctuation
"project-management" → "project management"

Step 3: Handle variations
"project mgmt" → add "management" as synonym

Step 4: Stemming/Lemmatization
"managing projects" → "manage project"
"productivity" → "product" (stem)
```

#### **Exact Match Logic**:

```
Page keywords: {remote work, productivity, team collaboration, video conferencing}
Ad keywords: {remote work, productivity tools, team communication}

For each ad keyword:
  For each page keyword:
    If ad_keyword == page_keyword:
      → EXACT MATCH
    
Example:
Ad: "remote work" 
Page: "remote work"
→ Exact match! (after normalization)
```

#### **Multi-word Phrase Matching**:

```
Use n-gram tokenization:

Page text: "We help teams with project management software"

Extract n-grams:
- 1-grams: [we, help, teams, with, project, management, software]
- 2-grams: [we help, help teams, teams with, with project, 
            project management, management software]
- 3-grams: [we help teams, help teams with, ...]

Ad keyword: "project management"

Check if "project management" exists in 2-grams:
→ YES! Exact match found
```

---

### **Partial Match Detection**

#### **Method 1: Substring Matching**

```
Ad keyword: "task management"
Page keywords: ["tasks", "project management", "productivity"]

Check "task management":
- Contains "task" (substring of "tasks") → PARTIAL
- Contains "management" (exact in "project management") → PARTIAL

Partial match score: 0.5 (one word matched)
```

#### **Method 2: Edit Distance (Levenshtein)**

```
Measures how many character changes needed to transform one word to another:

Ad: "productivity"
Page: "productive"

Changes needed: 
- Remove "ity"
- 3 operations

If edit distance ≤ 2: Consider partial match
If edit distance ≤ 4: Consider weak match

"productivity" vs "productive": distance = 3 → PARTIAL MATCH
```

#### **Method 3: Shared Root/Stem**

```
Use stemming algorithm (Porter Stemmer, Snowball):

Ad: "managing"     → stem: "manag"
Page: "management" → stem: "manag"

Stems match → PARTIAL MATCH

Ad: "productivity" → stem: "product"
Page: "productive" → stem: "product"

Stems match → PARTIAL MATCH
```

#### **Method 4: Synonym Dictionary**

```
Build/use synonym database:

Synonyms of "project management":
- task tracking
- work management  
- project planning
- project coordination

Ad has "task tracking"
Page has "project management"

Look up in synonym database:
→ SYNONYM MATCH (treated as partial match with score 0.7)
```

#### **Method 5: Word Embeddings for Semantic Similarity**

```
Each word gets a vector representation:

"productivity" → [0.23, -0.45, 0.89, ...]
"efficiency" → [0.19, -0.41, 0.85, ...]

Calculate cosine similarity between word vectors:
similarity("productivity", "efficiency") = 0.82

If similarity > 0.7: SEMANTIC PARTIAL MATCH
If similarity > 0.5: WEAK MATCH
```

---

### **Combined Matching Strategy**

**Priority Order** (check in sequence):

```
1. Exact phrase match (score: 1.0)
   "project management" exactly in both
   
2. Exact word match (score: 0.9)
   All words present but different order
   Ad: "management project" vs Page: "project management"
   
3. Synonym match (score: 0.8)
   Dictionary lookup finds synonyms
   
4. Partial word overlap (score: 0.5-0.7)
   Some words match
   Ad: "project management software" 
   Page: "project tracking"
   → "project" matches (0.5)
   
5. Stem match (score: 0.6)
   Root forms match after stemming
   
6. Semantic similarity (score: 0.3-0.7)
   Word embeddings show relatedness
   
7. No match (score: 0.0)
```

---

### **Practical Example**

**Page keywords**: `remote work, productivity, team collaboration, video calls`

**Ad keyword**: `remote team communication`

**Matching process**:

```
Split ad keyword into components: [remote, team, communication]

Check "remote":
→ Exact match with "remote work" (first word matches)
→ Score: 0.9

Check "team":
→ Exact match in "team collaboration" (first word matches)
→ Score: 0.9

Check "communication":
→ No exact match
→ Check synonyms: "communication" ≈ "collaboration"
→ Synonym match found
→ Score: 0.7

Aggregate: (0.9 + 0.9 + 0.7) / 3 = 0.83
Classification: STRONG PARTIAL MATCH
```

---

## Summary

**Weight Determination**:
- Start with expert rules or industry standards
- Learn from historical performance data
- Use ML models to optimize over time
- Update periodically based on new data

**Scaling**:
- Pre-compute and index everything possible
- Use multi-stage filtering (10M → 50K → 2K → 200 → winners)
- Leverage inverted indexes, bloom filters, bit vectors
- Only do expensive operations (embeddings) on small candidate sets

**Keyword Matching**:
- Normalize everything first
- Use n-grams for phrase detection
- Apply stemming, synonyms, and edit distance for partial matches
- Prioritize exact matches, fall back to semantic similarity
- Assign scores based on match quality

The key insight: **Don't process everything!** Filter aggressively at each stage to keep only promising candidates.