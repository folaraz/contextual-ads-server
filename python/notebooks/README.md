- Try reading an html page, figure oout how to extract keyworrds and maybe weight them
- Try to get vector representation for the website
- Try to figure out how to store the vecotor representation
- Think about chunking of the vector representation and how you'll store that in a vector db given you can have same url as key multiple times
- statement chaining ( not sure if this is necessary given we're not doing a search)
- future, think about brand safety e.g content of the site







PERSON:      People, including fictional.
NORP:        Nationalities or religious or political groups.
FAC:         Buildings, airports, highways, bridges, etc.
ORG:         Companies, agencies, institutions, etc.
GPE:         Countries, cities, states.
LOC:         Non-GPE locations, mountain ranges, bodies of water.
PRODUCT:     Objects, vehicles, foods, etc. (Not services.)
EVENT: Named hurricanes, battles, wars, sports events, etc.
WORK_OF_ART: Titles of books, songs, etc.
LAW:         Named documents made into laws.
LANGUAGE:    Any named language.
DATE:        Absolute or relative dates or periods.
TIME:        Times smaller than a day.
PERCENT:     Percentage, including ”%“.
MONEY:       Monetary values, including unit.
QUANTITY:    Measurements, as of weight or distance.
ORDINAL:     “first”, “second”, etc.
CARDINAL:    Numerals that do not fall under another type.

why topic modelling?


Topic modeling is critically important because it allows you to understand the **true context and theme** of a webpage, moving beyond ambiguous individual keywords to enable smarter, safer, and more scalable ad targeting.

---
### ## It Unlocks Scale and Efficiency

Advertisers don't want to manage millions of individual keywords. It's inefficient and impossible to cover every possibility.

* **Problem:** An advertiser selling running shoes would have to manually target keywords like "marathon," "5k race," "jogging," "sprinting," "track spikes," and thousands more.
* **Solution:** Topic modeling allows them to simply target the broad **topic** of "Sports > Running." Your system then automatically identifies all pages that fall into this theme, regardless of the specific keywords used. This makes setting up and managing ad campaigns vastly more efficient.

---
### ## It Solves Ambiguity and Improves Relevance

Keywords can be misleading. Topic modeling looks at the bigger picture to understand the actual subject matter.

* **Problem:** The keyword "Jaguar" could refer to the luxury car or the wild cat. Placing a car ad on a page about rainforest animals is a wasted impression and a poor user experience.
* **Solution:** By analyzing all the words on the page together (e.g., "engine," "speed," "horsepower" vs. "jungle," "prey," "habitat"), a topic model correctly classifies the page as "Automotive" or "Science > Animals." This ensures the ad is genuinely relevant, which increases click-through rates and advertiser satisfaction.



---
### ## It Provides Essential Brand Safety

Advertisers are extremely concerned about their brand appearing next to inappropriate or sensitive content.

* **Problem:** A family-friendly airline doesn't want its ad for holiday deals appearing on a news article about a plane crash.
* **Solution:** Topic modeling can identify and flag negative or sensitive categories like "Disasters," "Crime," or "Political Conflict." Advertisers can then use these topics in an "avoidance list" to prevent their ads from ever serving on such pages, protecting their brand's reputation. This is a non-negotiable feature for most major advertisers.

---
### ## It Enables Powerful Analytics

Once you can categorize content, you can generate valuable insights for both publishers and advertisers.

* **For Publishers:** They can see which topics are most popular on their website, helping guide their content strategy.
* **For Advertisers:** They can discover which themes their ads perform best on. For example, they might find that their ads have a 50% higher conversion rate on pages with the topic "Personal Finance" compared to "General Business News," allowing them to optimize their ad spend.

https://www.blend360.com/thought-leadership/fine-tuning-a-vision-transformer#:~:text=Since%20we%20wanted%20to%20tackle%20this%20problem,with%20a%20single%20Tier%201%20IAB%20category.

https://www.reddit.com/r/adtech/comments/1lx0470/api_to_categorize_content_with_iab_taxonomy/