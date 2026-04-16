(function (window, document) {


    const fetchWithTimeout = ({url, options, timeout}) => {
        const apiResponse = fetch(url, options);
        const timoutPromise = new Promise((res, rej) => {
            setTimeout(() => {
                rej(new Error('Request timeout'));
            }, timeout);
        })

        return Promise.race([apiResponse, timoutPromise])
    }

    if (window.AdServerSDK) {
        console.warn('Already initialized')
        return;
    }

    console.log('Initializing..')

    class AdSDK {

        constructor() {
            this.config = {
                baseUrl: 'http://localhost:8081/api',
                timeout: 30000,

                // https://www.iab.com/guidelines/mrc-viewable-impression-guidelines/
                viewabilityThreshold: 0.5,
                viewabilityDuration: 1000,
                viewabilityPolling: 100
            }

            this.tracker = {
                impressions: new Set(),
                clicks: new Set()
            }
            this.slots = new Map()
            this.adContext = new AdContext()

            this.processQueue();
            console.log('[Ad SDK] Initialization complete.')
        }

        processQueue() {
            if (!window.adServerQueue) {
                window.adServerQueue = [];
            }
            console.log('[Ad SDK] Processing queue.')
            while (window.adServerQueue.length > 0) {
                const command = window.adServerQueue.shift();
                this.execute(command);
            }
            //this will esnure that anything added in the publisher site is processed immediately
            window.adServerQueue.push = async (command) => {
                console.log('[Ad SDK] Processing pushed message.')
                await this.execute(command);
            }
        }

        async execute(command) {
            if (!command) {
                console.error('Command not present')
                return;
            }
            const {type} = command || {};
            if (!type || typeof type !== 'string') {
                console.error(`Command type ${type} is invalid`)
                return;
            }

            console.log(`Executing command:  ${type}`)

            switch (type) {
                case 'renderAd':
                    await this.renderAd(command);
                    break;
                default:
                    console.error(`Unknown command type: ${type}`)
            }
        }

        async renderAd(command) {
            const {slotId, publisherId} = command || {};

            if (!slotId) {
                console.error("Slot Id not provided")
                return;
            }

            if (!publisherId) {
                console.error("Publisher Id not provided")
                return;
            }

            const adSlotElement = this.findAdSlotElementById(slotId);

            if (!adSlotElement) {
                const error = new Error('Slot element not found for slitId: ' + slotId);
                console.error(error.message)
                return;
            }


            adSlotElement.innerHTML = ` <div> Loading </div> `;


            try {
                console.log('[Ad SDK] before request build...')

                const adRequest = this.buildAdRequest(publisherId)
                console.log('[Ad SDK] after request buid...')

                console.log('Built ad request:', adRequest)
                const adResponse = await this.requestAd({adRequest})

                console.log('Received ad response:', adResponse)

                this.renderCreative({
                    adSlotElement: adSlotElement,
                    slotId: slotId,
                    adData: adResponse,
                })

                console.log('[Ad SDK] after render creative...')

                const observer = this.trackViewability({
                    element: adSlotElement,
                    adData: adResponse,
                    publisherId: publisherId
                })

                this.slots.set(slotId, {
                    element: adSlotElement,
                    config: command,
                    adData: adResponse,
                    renderedDate: Date.now(),
                    observers: [observer],
                    eventListeners: []
                })

                console.log(`Successfully rendered Ad on slot ${slotId}`)
            } catch (e) {
                adSlotElement.innerHTML = '';
                console.error('Failed to render ad')
            }

        }

        trackViewability = ({element, adData}) => {

            let isCurrentlyVisible = false;
            let viewabilityTimeout = null;

            const observer = new IntersectionObserver(
                (entries) => {
                    entries.forEach(({intersectionRatio}) => {
                        const meetsThreshold = intersectionRatio >= this.config.viewabilityThreshold;

                        // Ad just became visible
                        if (meetsThreshold && !isCurrentlyVisible) {
                            isCurrentlyVisible = true;

                            viewabilityTimeout = setTimeout(() => {
                                if (isCurrentlyVisible) {
                                    this.trackImpression({adData});
                                    observer.disconnect();
                                }
                            }, this.config.viewabilityDuration);
                        }

                        // Ad became invisible before the duration was met
                        if (!meetsThreshold && isCurrentlyVisible) {
                            isCurrentlyVisible = false;

                            if (viewabilityTimeout) {
                                clearTimeout(viewabilityTimeout);
                                viewabilityTimeout = null;
                            }
                        }
                    });
                },
                {threshold: this.config.viewabilityThreshold}
            );

            observer.observe(element);
            return observer;
        };


        renderCreative = ({element, adData, slotId}) => {
            const {publisher_id, click_url, ad_id, media_url, headline, description} = adData;
            console.log('[Ad SDK] renderCreative ad')

            const htmlCreative = `
                <div class="ad-banner" style="font-family:Arial,serif;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                    <img src="${media_url}" alt="${headline}" style="width:100%;height:auto;display:block;">
                    <div style="padding:12px;">
                        <h3 style="margin:0 0 8px 0;font-size:18px;font-weight:bold;color:#333;">${headline}</h3>
                        <p style="margin:0;font-size:14px;color:#666;line-height:1.4;">${description}</p>
                    </div>
                </div>
            `;

            const iframe = document.createElement('iframe');
            iframe.style.cssText = 'width:100%;height:100%;border:none;';
            iframe.sandbox = 'allow-scripts allow-same-origin allow-popups';
            iframe.srcdoc = htmlCreative;

            element.innerHTML = '';
            element.appendChild(iframe);

            console.log('[Ad SDK] renderCreative html creative...', click_url)

            if (click_url) {
                this.addClickTracking(element, click_url, slotId, ad_id, publisher_id);
            }

            console.debug('Done Rendering HTML creative...')

        }

        addClickTracking(adSlotElement, clickUrl, slotId, adId, publisherId) {
            console.log('Adding click tracking...')

            const onClick = (event) => {
                console.log('Ad clicked:', adId);

                this.tracker.clicks.add(adId)

                window.open(clickUrl, '_blank');
            }

            console.log('Adding click event listener...')

            adSlotElement.addEventListener('click', onClick)

            if (this.slots.has(slotId)) {
                const slot = this.slots.get(slotId)
                slot.eventListeners.push({element: adSlotElement, event: 'click', handler: onClick})
            }

        }

        buildAdRequest = (publisherId) => {
            return {
                publisherId,
                context: {
                    url: window.location.href,
                    keywords: this.adContext.extractKeyword(),
                    title: document.title,
                    description: document.description,
                },
                device: {
                    type: this.adContext.getDeviceType(),
                    userAgent: navigator.userAgent,
                    language: navigator.language,
                },
                //todo do we need user timezone in the BE???
                meta: {
                    timestamp: Date.now()
                }
            }

        }

        requestAd = async ({adRequest}) => {
            const adUrl = `${this.config.baseUrl}/ads/serve`;

            const options = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-Forwarded-For': '143.58.162.73'
                },
                body: JSON.stringify(adRequest),
                credentials: 'include',
            }

            const response = await fetchWithTimeout({url: adUrl, options: options, timeout: this.config.timeout})

            if (!response.ok) {
                throw new Error(response.statusText)
            }

            return await response.json()

        }

        findAdSlotElementById(slotId) {
            if (typeof slotId !== 'string' || slotId.length === 0) {
                console.error('Invalid slotId type');
                return null;
            }
            try {
                return document.getElementById(slotId);
            } catch (e) {
                console.error('Error finding ad slot element with id ' + slotId);
            }
            return null;

        }

        trackImpression({adData}) {
            const {ad_id, impression_url} = adData;
            if (this.tracker.impressions.has(ad_id)) {
                console.log(`Impression already tracked for ad: ${ad_id}`);
                return;
            }

            this.tracker.impressions.add(ad_id);

            const pixel = new Image();
            pixel.src = impression_url;
        }
    }

    class AdContext {
        extractKeyword() {
            console.log("Extracting keywords from page context...")

            // Ensure the keywords Set exists
            const keywords = new Set();

            const metaKeywords = document.querySelectorAll('meta[name="keywords"]');
            metaKeywords.forEach(metaTag => {
                const content = metaTag.getAttribute("content");
                if (content) {
                    content.split(',').forEach(kw => {
                        const cleaned = kw.trim().toLowerCase();
                        if (cleaned) keywords.add(cleaned);
                    });
                }
            });

            const metaDescriptions = document.querySelectorAll('meta[name="description"]');
            metaDescriptions.forEach(tag => {
                const content = tag.getAttribute("content");
                if (content) {
                    content
                        .toLowerCase()
                        .split(/\s+/)
                        .filter(word => word.length > 4)
                        .slice(0, 10)
                        .forEach(word => keywords.add(word));
                }
            });


            const headings = document.querySelectorAll('h1, h2, h3');
            headings.forEach(h => {
                const text = h.textContent || "";
                text
                    .toLowerCase()
                    .split(/\s+/)
                    .filter(word => word.length > 4)
                    .slice(0, 3)
                    .forEach(word => keywords.add(word));
            });

            return Array.from(keywords).slice(0, 20);
        }

        getDeviceType() {
            const ua = navigator.userAgent.toLowerCase();
            if (/(ipad|tablet|(android(?!.*mobile))|(windows(?!.*phone)(.*touch))|kindle|playbook|silk|(puffin(?!.*(IP|AP|WP))))/.test(ua)) {
                return 'tablet';
            }
            if (/(mobi|ipod|phone|blackberry|opera mini|fennec|minimo|symbian|psp|nintendo ds|archos|skyfire|puffin|blazer|bolt|gobrowser|iris|maemo|semc|teashark|uzard)/.test(ua)) {
                return 'mobile';
            }

            return 'desktop';
        }
    }

    window.AdServerSDK = new AdSDK();
})(window, document);