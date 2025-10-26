import spacy

nlp = spacy.load("en_core_web_sm")


import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer  # <-- IMPORT THE CORRECT TOKENIZER



def sent_tokenize(text):
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents]



# --- STEP 1: DYNAMIC SEMANTIC CHUNKER ---
# (This function is unchanged, but we'll pass the model in)

def semantic_chunker(text: str, model: SentenceTransformer, std_dev_threshold: float = 1.0) -> list[str]:
    # 1. Split the text into sentences
    sentences = sent_tokenize(text)
    if len(sentences) <= 1:
        return sentences

    # 2. Generate embeddings for each sentence
    embeddings = model.encode(sentences)

    # 3. Calculate cosine similarity between adjacent sentences
    similarities = []
    for i in range(len(embeddings) - 1):
        emb1 = embeddings[i].reshape(1, -1)
        emb2 = embeddings[i + 1].reshape(1, -1)
        sim = cosine_similarity(emb1, emb2)[0][0]
        similarities.append(sim)

    if not similarities:
        return sentences

    # 4. Find the dynamic "breakpoint" threshold
    mean_sim = np.mean(similarities)
    std_dev_sim = np.std(similarities)
    threshold = mean_sim - std_dev_threshold * std_dev_sim

    # 5. Group sentences into chunks
    chunks = []
    current_chunk_sentences = [sentences[0]]

    for i in range(len(similarities)):
        if similarities[i] < threshold:
            chunks.append(" ".join(current_chunk_sentences))
            current_chunk_sentences = [sentences[i + 1]]
        else:
            current_chunk_sentences.append(sentences[i + 1])

    if current_chunk_sentences:
        chunks.append(" ".join(current_chunk_sentences))
    return chunks


# --- STEP 2: MERGE SHORT CHUNKS ---
# (This function is unchanged)

def merge_short_chunks(chunks: list[str], min_chunk_words: int = 20) -> list[str]:
    if len(chunks) <= 1:
        return chunks

    merged_chunks = []
    i = 0
    while i < len(chunks):
        current_chunk = chunks[i]
        if len(current_chunk.split()) < min_chunk_words and (i < len(chunks) - 1):
            merged_chunks.append(current_chunk + " " + chunks[i + 1])
            i += 2
        else:
            merged_chunks.append(current_chunk)
            i += 1

    if len(merged_chunks) > 1 and len(merged_chunks[-1].split()) < min_chunk_words:
        merged_chunks[-2] = merged_chunks[-2] + " " + merged_chunks[-1]
        merged_chunks.pop()

    return merged_chunks


def split_large_chunks(chunks: list[str], tokenizer: AutoTokenizer, max_tokens: int = 256) -> list[str]:
    """
    Splits chunks that exceed the 'max_tokens' limit using the model's
    own tokenizer.
    """
    final_chunks = []

    for chunk in chunks:
        # Tokenize the chunk and get input IDs
        token_ids = tokenizer.encode(chunk, add_special_tokens=False)  # We don't need special tokens for counting

        if len(token_ids) <= max_tokens:
            final_chunks.append(chunk)
        else:
            sub_sentences = sent_tokenize(chunk)
            current_sub_chunk_sentences = []
            current_sub_chunk_tokens = 0

            for sentence in sub_sentences:
                sentence_token_ids = tokenizer.encode(sentence, add_special_tokens=False)
                sentence_tokens = len(sentence_token_ids)

                if sentence_tokens > max_tokens:
                    # Edge case: A single sentence is too long
                    if current_sub_chunk_sentences:
                        final_chunks.append(" ".join(current_sub_chunk_sentences))
                    final_chunks.append(sentence)  # Add the long sentence
                    current_sub_chunk_sentences = []
                    current_sub_chunk_tokens = 0
                    continue

                if current_sub_chunk_tokens + sentence_tokens <= max_tokens:
                    current_sub_chunk_sentences.append(sentence)
                    current_sub_chunk_tokens += sentence_tokens
                else:
                    final_chunks.append(" ".join(current_sub_chunk_sentences))
                    current_sub_chunk_sentences = [sentence]
                    current_sub_chunk_tokens = sentence_tokens

            if current_sub_chunk_sentences:
                final_chunks.append(" ".join(current_sub_chunk_sentences))

    return final_chunks

if __name__ == '__main__':
    # Example Usage
    text = """
    Artificial intelligence is transforming industries around the world.
    Machine learning and deep learning are key components of AI.
    They are used in healthcare, finance, and transportation.
    On the other hand, there are concerns about bias and fairness.
    Regulators are trying to ensure responsible AI development.
    """

    text1 = """
    The first topic is about Python. Python is a versatile programming language known for its readability. It's widely used in web development, data science, and artificial intelligence. Its standard library is extensive. Now, let's talk about something different. The Eiffel Tower is a famous landmark in Paris, France. It was designed and built by Gustave Eiffel's company. Millions of tourists visit it every year. Finally, a third subject. Coffee is a popular beverage made from roasted coffee beans. It is cherished for its stimulating effect, which is primarily due to caffeine. Many people start their day with a cup of coffee.
    """

    # --- 1. Define Model Name ---
    model_name = 'all-MiniLM-L6-v2'

    # --- 2. Load Model and Tokenizer ONCE ---
    print(f"Loading {model_name}...")
    embedding_model = SentenceTransformer(model_name)
    tokenizer = AutoTokenizer.from_pretrained(f'sentence-transformers/{model_name}')

    # --- 3. Define the text ---
    text_to_chunk = "All products featured on Vogue are independently selected by our editors. However, we may earn affiliate revenue on this article and commission when you buy something. While strong notions of femininity prevailed in the spring/summer collections, the spring/summer 2025 fashion trends we’re predicting to take over the fashion landscape are less ethereal and dreamy as they are practical and empowering. Rooted in a sense of “soft power,” which Vogue’s Laird Borelli-Persson connected to designers encouraging “an openness to a sense of wonder” in her analysis of the shows, these trends can be embraced in more ways than one. And key themes can already be incorporated into your wardrobe. Vogue’s Top Spring 2025 Fashion Trends: The Summertime Dress: Proenza Schouler Yves stripe fringed knit dress, $2,490 The Bohemian Blouse: Banana Republic chiffon twist-neck top, $100 The Preppy Pleated Skirt: Prada rush stitch skirt, $2,950 The Vintage-Inspired Print: Dries Van Noten printed midi skirt, $620 The Checked Top: Simkhai Calliope tailored vest, $495 The New Business Blazer: The Frankie Shop Bea oversized cady blazer, $345 The Crafty Minimalism Skirt: Diotima Darliston skirt, $1,095 The New Proportions Mini: Alaïa cotton poplin mini dress, $3,900 The Romantic Floral Dress: Lafayette 148 New York Gesture handkerchief dress, $1,798 The Coastal Stripe: Aligne Omari striped shorts, $90 The New-Season Suede: Tory Burch suede bomber jacket, $2,898 Consider spring’s outerwear stories, which reimagine lightweight jackets of all types, particularly sporty styles for the season ahead. For inspiration on how to wear these jackets from now, look no further than Bottega, where an elasticated windbreaker was styled with fluid trousers. A zip-up à la Gucci works equally well here—just throw an overcoat on top. Suede will continue to trend as well, so if you invested last fall, keep wearing it! Dark chocolate brown styles pair particularly nicely with spring’s softer color palette of wispy pinks and pale yellows. As for the print that reigned supreme on the spring/summer runways? It wasn’t a floral or an animal but plaid, and its first cousin, gingham. The autumnal pattern was already a favorite last fall, and it seems like fashion wasn’t done with it for spring, rendering it in softer colors and shapes. If your wardrobe already has a spirited amount of checks, look to the runways for ideas on how to print clash—another major theme this spring that was put forward at Dries Van Noten, Gucci, and Miu Miu, where high-impact, retro-inspired prints were piled on in an artfully chaotic manner. (If it looks wrong, it’s probably right.) These and more key spring/summer 2025 fashion trends to know and shop now as spring deliveries land in stores. Femininity Unraveled Soft pastels brought romance and airiness to the runways, but the color palette didn’t feel overly feminine. Even minimalists will be drawn to this season’s wispy pinks and pale yellows, which look great against wardrobe neutrals like grey, navy, and even chocolate brown suede. Summertime Prep Inspired by sunny weekends on the coast, but really for any kind of weather or locale, the abundance of seaside-inspired pieces offer imaginative dressing solutions that are both practical and seasonally appropriate. Key pieces include anything with a sailor stripe, buoyant cotton skirts and dresses, and wind-resistant jackets—it does get blustery out there! Spring Outerwear Stories A sporty sensibility carried over from fashion’s Olympics fervor pervaded the spring/summer 2025 runways. Sabato de Sarno showed various fitted zip-up jackets at Gucci, while Bottega and Miu Miu reimagined the wind breaker—Matthieu Blazy notably lined his in plaid, a carryover from fall we’ll get into next. But other kinds of lightweight outerwear were also introduced. At Prada, Miuccia and Raf Simons showed a suede style, proof that fashion’s ongoing obsession with the texture isn’t going anywhere. A cropped leather cape made an appearance at Loewe, upleveling the boho staple we were reacquainted with last spring. Investing in next-season outerwear now doesn’t mean you have to wait until March to wear your pieces—layer similar styles from Gucci and Loewe under heavier coats to maximize their cost per wear. Checks and Balances Plaid may be synonymous with fall—where it indeed saw a resurgence this season—but its presence in the spring collections takes on a softer tune. Borelli-Persson described these checks best as “Nirvana meets Country Living… for any season or type of weather” in her trend report. The Row’s ‘Tavishina’ coat in look 29 exemplifies the fashion mood, with an energizing combination of beige, black, and baby blue squares that was styled with pinstripe pants and a plain white button-up for a harmonious, minimalist-approved take on print mixing. Blazy meanwhile played with a classic color scheme of browns, greys, and white, but showed it as an oversized shacket meets coat hybrid. At Tod’s checks were playfully introduced once more, worn inside out as a full ensemble. In New York, Daniella Kallmeyer furthered the artful drape with a fluid blouse, while Acne Studios dabbled in the art of the clash (nails included!) and incorporated another theme seen in the resort 2025 trends: the bubble hem. This ’90s-inspired look can be achieved now with printed pieces from the likes of Massimo Dutti, Ralph Lauren, or Zara—and styled with pattern opposites for a true runway-coded look. Let’s Go Thrifting Maximalists will always have print, and this season encourages us to revisit the art of the clash with retro-inspired patterns. A devil-may-care approach will be rewarded here, but if your less-is-more tendencies are too strong to rebel against, a graphic top or skirt (ideally one that looks, or is, vintage) will do the trick. Denim with trims, per Valentino, can achieve the same mix-and-match effect. Crafty Minimalism Texture, fringe, and crochet can do much for a minimalist wardrobe with very little. The idea here isn’t to do away with the clean line entirely, but rather play up those refrained sensibilities with novelty and craft. Even purists will enjoy styling these pieces. Exaggerated Proportions Sculptural shapes alluding to a Japanese-style minimalism will inspire you to look differently at your everyday staples. These boisterous, asymmetric, and fanned-out silhouettes offer a true fashion POV to pieces you might wear everyday, from white T-shirts to nipped-in jackets. New Business Codes We’re leaving the office siren behind for spring, and embracing new tailoring codes for 2025. Simone Bellotti suggested a nipped-in peplum shape with drop shoulders at Bally, Stella McCartney went ’80s oversize, Tory Burch introduced a collarless, belted, and wrapped silhouette, and Blazy showed an almost cartoonishly oversize take at Bottega. A happy medium can be found at Saint Laurent, where the many full suiting looks in the collection were inspired by the house founder, and meant to convey “control and power,” as designer Anthony Vaccarello told Vogue’s Mark Holgate post-show backstage. Until these spring deliveries land, find inspiration for your own uniform refresh with current season styles from Saint Laurent, Tory Burch, Bally, and more."

    # --- 4. Define the "Knobs" for RAG Embedding ---
    std_dev_break = 0.3  # How sensitive to topic change (lower = more chunks)
    min_words = 20  # To merge transition sentences
    max_tok_for_embedding = 256  # The model's true training limit


    # Step 1: Dynamic Semantic Chunking
    chunks_step1 = semantic_chunker(
        text_to_chunk,
        embedding_model,
        std_dev_threshold=std_dev_break
    )

    # Step 2: Merge Short Transition Chunks
    chunks_step2 = merge_short_chunks(
        chunks_step1,
        min_chunk_words=min_words
    )

    # Step 3: Split Oversized Chunks (using the correct tokenizer)
    final_text_chunks = split_large_chunks(
        chunks_step2,
        tokenizer,
        max_tokens=max_tok_for_embedding
    )

    # --- 6. FINALLY, CREATE YOUR EMBEDDINGS ---
    print(f"\n--- Creating {len(final_text_chunks)} Embeddings ---")

    final_embeddings = embedding_model.encode(final_text_chunks, show_progress_bar=True)

    print("\n--- Ready to store in Vector DB ---")
    for i, chunk in enumerate(final_text_chunks):
        token_count = len(tokenizer.encode(chunk, add_special_tokens=False))
        print(f"\n[CHUNK {i + 1} (Tokens: {token_count})]")
        print(f"Text: {chunk}...")
