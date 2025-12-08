(function (window, document) {


    function log(...args) {
        console.log('[Ad SDK] ', ...args);

    }

    function logError(...args) {
        console.error('[Ad SDK] ', ...args);
    }

    function logWarning(...args) {
        console.warn('[Ad SDK] ', ...args)
    }

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
        logWarning('Already initialized')
        return;
    }

    log('Initializing..')

    class AdSDK {

        constructor() {
            this.config = {
                apiEndpoint: 'http://localhost:8080',
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
            log('[Ad SDK] Initialization complete.')
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
                logError('Command not present')
                return;
            }
            const {slotId, type} = command || {};
            if (!type || typeof type !== 'string') {
                logError(`Command type ${type} is invalid`)
                return;
            }

            log(`Executing command:  ${type}`)

            switch (type) {
                case 'renderAd':
                    await this.renderAd(command);
                    break;
                case 'destroySlot':
                    this.destroySlot(slotId);
                    break;
                default:
                    logError(`Unknown command type: ${type}`)
            }
        }

        async renderAd(command) {
            const {slotId, siteId, sizes} = command || {};

            if (!slotId) {
                logError('Slot Id not provided')
                return;
            }

            if (!siteId) {
                logError('Site Id not provided')
                return;
            }

            const adSlotElement = this.findAdSlotElementById(slotId);

            if (!adSlotElement) {
                const error = new Error('Slot element not found for slitId: ' + slotId);
                logError(error.message)
                return;
            }


            adSlotElement.innerHTML = ` <div> Loading </div> `;


            try {
                console.log('[Ad SDK] before request build...')

                const adRequest = this.buildAdRequest(siteId, slotId, sizes)
                console.log('[Ad SDK] after request buid...')

                console.log('Built ad request:', adRequest)
                const adResponse = await this.requestAd({adRequest})

                console.log('Received ad response:', adResponse)

                this.renderCreative({
                    adSlotElement: adSlotElement,
                    slotId: slotId,
                    adData: adResponse,
                    siteId: siteId
                })

                console.log('[Ad SDK] after render creative...')

                const observer = this.trackViewability({
                    element: adSlotElement,
                    adData: adResponse.ad,
                    publisherId: siteId
                })

                this.slots.set(slotId, {
                    element: adSlotElement,
                    config: command,
                    adData: adResponse.ad,
                    renderedDate: Date.now(),
                    observers: [observer],
                    eventListeners: []
                })

                log(`Successfully rendered Ad on slot ${slotId}`)
            } catch (e) {
                adSlotElement.innerHTML = '';
                logError('Failed to render ad')
            }

        }


        trackViewability = ({element, adData, publisherId}) => {
            const adId = adData?.adId;
            let hasBeenVisible = false;
            let visibilityTimer = null;

            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    const isVisible = entry.intersectionRatio >= this.config.viewabilityThreshold;

                    if (isVisible && !hasBeenVisible) {
                        hasBeenVisible = true;

                        visibilityTimer = setTimeout(() => {
                            if (hasBeenVisible) {
                                this.trackImpression({adId: adId, adData: adData, publisherId: publisherId});
                                observer.disconnect();
                            }
                        }, this.config.viewabilityDuration)

                    } else if (!isVisible && hasBeenVisible) {
                        hasBeenVisible = false;
                        //this means that the user must have scrlled away after viewing the ad but before the time threshold could be met
                        if (visibilityTimer) {
                            clearTimeout(visibilityTimer);
                            visibilityTimer = null;
                        }
                    }
                })

            }, {threshold: this.config.viewabilityThreshold})

            observer.observe(element)
            return observer;
        }


        renderCreative = ({adSlotElement, adData, slotId, siteId}) => {
            const {type, creative, clickUrl, adId} = adData;
            console.log('[Ad SDK] renderCreative ad')


            if (!creative) {
                const error = new Error(`Ad not available for slot id ${slotId}`)
                logError(error.message)
                return;
            }

            switch (type) {
                case 'iframe':
                    this.renderIframeCreative(creative, adSlotElement);
                    break
                case 'image':
                    this.renderImageCreative(adSlotElement, creative, clickUrl, slotId, adId, siteId);
                    break
                case 'html':
                    this.renderHtmlCreative(creative, clickUrl, adSlotElement, slotId, adId, siteId)
                    break
                default:
                    logError(`Unknown creative type: ${type}`)
            }
        }

        renderHtmlCreative(creative, clickUrl, element, slotId, adId, publisherId) {
            console.log('Rendering HTML creative...')

            const container = document.createElement('div');
            container.style.cssText = 'position:relative;width:100%;height:100%;';

            const iframe = document.createElement('iframe');
            iframe.style.cssText = 'width:100%;height:100%;border:none;';
            iframe.sandbox = 'allow-scripts allow-same-origin allow-popups';
            iframe.srcdoc = creative;

            const overlay = document.createElement('div');
            overlay.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;cursor:pointer;';

            container.appendChild(iframe);
            container.appendChild(overlay);
            element.innerHTML = '';
            element.appendChild(container);

            console.log('[Ad SDK] renderCreative html creative...', clickUrl)

            if (clickUrl) {
                this.addClickTracking(overlay, clickUrl, slotId, adId, publisherId);
            }

            console.debug('Done Rendering HTML creative...')
        }

        renderIframeCreative(creative, adSlotElement) {
            const iframe = document.createElement('iframe');
            iframe.style.cssText = 'width:100%;height:100%;border:none;cursor:pointer;';
            iframe.sandbox = 'allow-scripts allow-popups allow-forms';

            if (creative.startsWith('http')) {
                iframe.src = creative
            } else {
                iframe.srcdoc = creative
            }

            adSlotElement.innerHTML = ''

            adSlotElement.appendChild(iframe)

        }

        renderImageCreative(adSlotElement, creative, clickUrl, slotId, adId, publisherId) {
            const link = document.createElement('a')
            link.href = clickUrl
            link.target = '_blank'
            link.rel = 'noopener noreferrer'
            link.style.cssText = 'display:block;width:100%;height:100%;cursor:pointer;';

            const img = document.createElement('img');
            img.src = creative
            img.style.cssText = 'width:100%;height:100%;object-fit:contain;cursor:pointer;';

            img.onerror = () => {
                logError(`Failed to load ad image:`, creative)
                adSlotElement.innerHTML = '<div>Failed to render ad</div>'
            }

            link.appendChild(img)
            adSlotElement.innerHTML = ''
            adSlotElement.appendChild(link)

            this.addClickTracking(adSlotElement, clickUrl, slotId, adId, publisherId)
        }

        addClickTracking(adSlotElement, clickUrl, slotId, adId, publisherId) {
            console.log('Adding click tracking...')

            const onClick = (event) => {
                if (this.tracker.clicks.has(adId)) {
                    log(`Click already tracked for adId: ${adId}`)
                    return;
                }
                log('Ad clicked:', adId);

                const payload = {
                    adId: adId,
                    eventType: 'click',
                    timestamp: Date.now(),
                    url: window.location.href,
                    clickUrl: clickUrl,
                    siteId: publisherId

                    //anything we need to track for fraud detecation??
                }
                this.tracker.clicks.add(adId)

                this.sendTrackingEvent({eventType: 'click', payload})
            }

            console.log('Adding click event listener...')

            adSlotElement.addEventListener('click', onClick)

            if (this.slots.has(slotId)) {
                const slot = this.slots.get(slotId)
                slot.eventListeners.push({element: adSlotElement, event: 'click', handler: onClick})
            }

        }

        buildAdRequest = (publisherId, slotId, sizes) => {
            return {
                slotId,
                publisherId,
                sizes: sizes || [[270, 270]],
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
            const adUrl = `${this.config.apiEndpoint}/v1/ads`;

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
                logError('Invalid slotId type');
                return null;
            }
            try {
                return document.getElementById(slotId);
            } catch (e) {
                logError('Error finding ad slot element with id ' + slotId);
            }
            return null;

        }

        destroySlot(command) {
            const {slotId} = command || {};
            if (!slotId) {
                logError('Slot Id not provided');
                return;
            }

            if (!this.slots.has(slotId)) {
                log('Slot not found, nothing to destroy for slotId: ' + slotId);
                return;
            }
            const adSlotElement = document.getElementById(slotId);
            if (!adSlotElement) {
                logError('Slot element not found for slotId: ' + slotId);
                return;
            }
            adSlotElement.innerHTML = '';

            const slot = this.slots.get(slotId);

            while (slot.eventListeners.length > 0) {
                const eventListener = slot.eventListeners.shift()
                eventListener.element.removeEventListener(eventListener.event, eventListener.handler)
            }


            while (slot.observers.length > 0) {
                const observer = slot.observers.shift();
                observer.disconnect();
            }

            if (slot.element) {
                slot.element.innerHTML = '';
            }

            this.slots.delete(slotId);

            log('Removed slotId', slotId);
        }

        trackImpression({adId, publisherId}) {
            if (this.tracker.impressions.has(adId)) {
                log(`Impression already tracked for ad: ${adId}`)
                return;
            }

            this.tracker.impressions.add(adId);

            const payload = {
                publisherId: publisherId,
                adId: adId,
                eventType: 'impression',
                url: window.location.href,
            }

            this.sendTrackingEvent({eventType: 'impression', payload})

        }

        sendTrackingEvent({eventType, payload}) {
            const url = `${this.config.apiEndpoint}/v1/events/${eventType}`;

            if (navigator.sendBeacon) {
                navigator.sendBeacon(url, JSON.stringify(payload));
            } else {
                const pixel = new Image();
                pixel.src = `${url}?data=${encodeURIComponent(JSON.stringify(payload))}`;
            }
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