const express = require('express')
const axios = require('axios');
const cheerio = require('cheerio');
const cors = require('cors');
const app = express()
const PORT = 3000


app.get('/sdk.js', (req, res) => {
    res.sendFile(__dirname + '/sdk.js');
})

app.get('/preview', async (req, res) => {
    const url = req.query.url;
    if (!url) {
        return res.status(400).send('Url parameter is required');
    }

    try {
        const response = await axios.get(url, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            },
            timeout: 10000,
            maxRedirects: 5
        });

        const $ = cheerio.load(response.data);

        $('meta[http-equiv="Content-Security-Policy"]').remove();
        $('meta[http-equiv="X-Frame-Options"]').remove();

        const baseUrl = new URL(url).origin;

        $('img, script, link, a').each((i, elem) => {
            ['src', 'href'].forEach(attr => {
                const val = $(elem).attr(attr);
                if (val && val.startsWith('/') && !val.startsWith('//')) {
                    $(elem).attr(attr, baseUrl + val);
                }
            });
        });

        const slotId = '123455';
        const width = 1000;
        const height = 300;
        const adContainer = `<div id="${slotId}" style="margin: 20px auto; width: ${width}px; height: ${height}px; background: transparent; position: relative;"></div>`;

        let injected = false;

        const mainContent = $('article, .content, .post, main').first();
        if (mainContent.length) {
            mainContent.prepend(adContainer);
            injected = true;
        }

        if (!injected) {
            $('p').first().after(adContainer);
        }

        const AD_SDK_SRC = '/sdk.js'

        const adScript = ` <script>
        (function(w, d) {
          w.adServerQueue = w.adServerQueue || [];
          
          let script = d.createElement('script');
          script.async = true;
          script.src = '${AD_SDK_SRC}';
          d.head.appendChild(script);
          
        adServerQueue.push({
            type: 'renderAd',
            slotId: '123455',
            siteId: 'pub-123456',
        });

        })(window, document);
      </script>
    `;

        $('head').append(adScript);

        res.setHeader('Content-Type', 'text/html');
        res.send($.html());

    } catch (error) {
        console.error('Error fetching page:', error.message);
        res.status(500).json({
            error: 'Failed to fetch page',
            details: error.message
        });
    }
});

app.listen(PORT, () => {
    console.log(`app listening on port ${PORT}`)
})
