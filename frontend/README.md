Publishers put a small piece of JavaScript code, often called an **ad tag**, on their website to make API calls to a third-party ad server.

This ad tag is a lightweight script provided by the ad server company. The publisher simply copies and pastes it into the HTML of their webpage, exactly where they want the ad to appear.

-----

### How It Works: Step-by-Step

Think of the ad tag as a smart messenger that automatically calls for an ad when someone visits the page. 📞

Here's the sequence of events that happens in a fraction of a second:

1.  **Placement:** The publisher places the ad tag inside a `<div>` element on their page. The code looks something like this:

    ```html
    <div id="ad-slot-123"></div>

    <script async src="https://adserver.com/ad.js"></script>
    <script>
      requestAd({
        slotId: 'ad-slot-123',
        publisherId: 'pub-abc'
      });
    </script>
    ```

2.  **Page Load & Script Execution:** When a user visits the publisher's site, their web browser loads the HTML. When it gets to the `<script>` tag, it downloads and executes the `ad.js` file from the ad server. The `async` attribute is crucial because it tells the browser to load the ad script **asynchronously**, meaning it won't slow down the loading of the main page content.

3.  **Information Gathering:** Once the script runs, it gathers important contextual information needed to request a relevant ad. This includes:

      * The **page URL** (`window.location.href`) to know the page's content.
      * The specific **ad slot ID** (`ad-slot-123`) to know which ad on the page this is.
      * The **publisher ID** (`pub-abc`).

4.  **The API Call:** The script then constructs an HTTP request to the ad server's API endpoint. It attaches all the gathered information as query parameters in the URL. The call looks something like this:

    `GET https://api.adserver.com/request?publisherId=pub-abc&slotId=ad-slot-123&url=https://publisher.com/news/sports`

5.  **Ad Server Response:** The ad server receives this request, performs its logic (contextual analysis, auction, etc.), and sends a response back to the browser. This response usually contains the ad creative itself, typically as a block of HTML and JavaScript.

6.  **Rendering the Ad:** The original ad tag script on the publisher's page is designed to listen for this response. When it receives the ad creative, its final job is to inject that HTML into the placeholder `<div>` (`<div id="ad-slot-123">`). At this point, the ad becomes visible to the user.
