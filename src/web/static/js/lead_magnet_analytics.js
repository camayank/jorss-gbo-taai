(function (global) {
    'use strict';

    const VARIANT_COOKIE = 'lm_variant_hero';
    const VARIANT_STORAGE = 'lm_variant_hero';
    const UTM_STORAGE = 'lm_utm_payload';
    const DEVICE_STORAGE = 'lm_device_type';
    const KNOWN_VARIANTS = ['A', 'B', 'C', 'D', 'E'];
    const EXPERIMENT_MATRIX = {
        A: {
            hero_emotion: 'fear',
            phone_capture_variant: 'optional',
            gate_aggressiveness: 'soft',
            score_visualization: 'donut',
            teaser_cta: 'unlock_report',
        },
        B: {
            hero_emotion: 'curiosity',
            phone_capture_variant: 'optional',
            gate_aggressiveness: 'hard',
            score_visualization: 'gauge',
            teaser_cta: 'free_analysis',
        },
        C: {
            hero_emotion: 'benchmark',
            phone_capture_variant: 'required',
            gate_aggressiveness: 'soft',
            score_visualization: 'donut',
            teaser_cta: 'unlock_report',
        },
        D: {
            hero_emotion: 'proof',
            phone_capture_variant: 'optional',
            gate_aggressiveness: 'soft',
            score_visualization: 'gauge',
            teaser_cta: 'free_analysis',
        },
        E: {
            hero_emotion: 'deadline',
            phone_capture_variant: 'optional',
            gate_aggressiveness: 'hard',
            score_visualization: 'donut',
            teaser_cta: 'unlock_report',
        },
    };

    function getUrlParams() {
        try {
            return new URLSearchParams(global.location.search || '');
        } catch (_) {
            return new URLSearchParams();
        }
    }

    function getCookie(name) {
        const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const match = document.cookie.match(new RegExp('(?:^|; )' + escaped + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : null;
    }

    function setCookie(name, value, days) {
        const ttlDays = Number.isFinite(days) ? days : 30;
        const expires = new Date(Date.now() + ttlDays * 86400000).toUTCString();
        document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
    }

    function normalizeVariant(value, fallback) {
        if (!value) return fallback || null;
        const candidate = String(value).trim().toUpperCase();
        if (KNOWN_VARIANTS.includes(candidate)) return candidate;
        return fallback || null;
    }

    function resolveVariant(defaultVariant) {
        const params = getUrlParams();
        const fromQuery = normalizeVariant(params.get('v'), null);
        const fromStorage = normalizeVariant(sessionStorage.getItem(VARIANT_STORAGE), null);
        const fromCookie = normalizeVariant(getCookie(VARIANT_COOKIE), null);
        const resolved = fromQuery || fromStorage || fromCookie || normalizeVariant(defaultVariant, 'A') || 'A';
        sessionStorage.setItem(VARIANT_STORAGE, resolved);
        setCookie(VARIANT_COOKIE, resolved, 30);
        return resolved;
    }

    function inferDeviceType() {
        const width = Math.max(global.innerWidth || 0, document.documentElement.clientWidth || 0);
        if (width > 0 && width <= 767) return 'mobile';
        if (width > 767 && width <= 1024) return 'tablet';
        return 'desktop';
    }

    function getDeviceType() {
        const stored = sessionStorage.getItem(DEVICE_STORAGE);
        if (stored) return stored;
        const detected = inferDeviceType();
        sessionStorage.setItem(DEVICE_STORAGE, detected);
        return detected;
    }

    function parseUtmFromUrl() {
        const params = getUrlParams();
        const payload = {
            utm_source: params.get('utm_source') || null,
            utm_medium: params.get('utm_medium') || null,
            utm_campaign: params.get('utm_campaign') || null,
        };
        if (payload.utm_source || payload.utm_medium || payload.utm_campaign) {
            sessionStorage.setItem(UTM_STORAGE, JSON.stringify(payload));
            return payload;
        }
        return null;
    }

    function getUtmPayload() {
        const fromUrl = parseUtmFromUrl();
        if (fromUrl) return fromUrl;
        const raw = sessionStorage.getItem(UTM_STORAGE);
        if (!raw) {
            return { utm_source: null, utm_medium: null, utm_campaign: null };
        }
        try {
            const parsed = JSON.parse(raw);
            return {
                utm_source: parsed.utm_source || null,
                utm_medium: parsed.utm_medium || null,
                utm_campaign: parsed.utm_campaign || null,
            };
        } catch (_) {
            return { utm_source: null, utm_medium: null, utm_campaign: null };
        }
    }

    function getCommonContext(defaultVariant) {
        const variant = resolveVariant(defaultVariant || 'A');
        const utm = getUtmPayload();
        const deviceType = getDeviceType();
        return {
            variant_id: variant,
            utm_source: utm.utm_source,
            utm_medium: utm.utm_medium,
            utm_campaign: utm.utm_campaign,
            device_type: deviceType,
        };
    }

    function getExperimentConfig(defaultVariant) {
        const variant = resolveVariant(defaultVariant || 'A');
        const assigned = EXPERIMENT_MATRIX[variant] || EXPERIMENT_MATRIX.A;
        return Object.assign({ variant_id: variant }, assigned);
    }

    function buildEventPayload(eventName, step, metadata, options) {
        const common = getCommonContext(options && options.defaultVariant ? options.defaultVariant : 'A');
        const experiment = getExperimentConfig(common.variant_id);
        const eventMetadata = Object.assign({}, metadata || {}, {
            hero_variant: experiment.variant_id,
            utm_source: common.utm_source,
            utm_medium: common.utm_medium,
            utm_campaign: common.utm_campaign,
            device_type: common.device_type,
            phone_capture_variant: experiment.phone_capture_variant,
            gate_aggressiveness: experiment.gate_aggressiveness,
            score_visualization: experiment.score_visualization,
            teaser_cta: experiment.teaser_cta,
        });
        return {
            event_name: eventName,
            step: step || null,
            variant_id: experiment.variant_id,
            utm_source: common.utm_source,
            utm_medium: common.utm_medium,
            utm_campaign: common.utm_campaign,
            device_type: common.device_type,
            metadata: eventMetadata,
        };
    }

    function safeGtag(eventName, params) {
        if (typeof global.gtag !== 'function') return;
        try {
            global.gtag('event', `lead_magnet_${eventName}`, params || {});
        } catch (_) {
            // noop
        }
    }

    function trackEvent(sessionId, eventName, step, metadata, options) {
        if (!sessionId) return Promise.resolve(null);
        const payload = buildEventPayload(eventName, step, metadata, options || {});
        safeGtag(eventName, {
            step: step || undefined,
            session_id: sessionId,
            hero_variant: payload.variant_id,
            device_type: payload.device_type,
            utm_source: payload.utm_source || undefined,
        });
        return fetch(`/api/cpa/lead-magnet/${sessionId}/event`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            keepalive: true,
        }).catch(function () { return null; });
    }

    function sendBeaconEvent(sessionId, eventName, step, metadata, options) {
        if (!sessionId) return;
        const payload = buildEventPayload(eventName, step, metadata, options || {});
        const serialized = JSON.stringify(payload);
        if (navigator.sendBeacon) {
            const blob = new Blob([serialized], { type: 'application/json' });
            navigator.sendBeacon(`/api/cpa/lead-magnet/${sessionId}/event`, blob);
            return;
        }
        fetch(`/api/cpa/lead-magnet/${sessionId}/event`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: serialized,
            keepalive: true,
        }).catch(function () { return null; });
    }

    function getSessionId(explicitSessionId) {
        return explicitSessionId || sessionStorage.getItem('assessment_session_id') || null;
    }

    function cacheStartSession(payload) {
        if (!payload || !payload.session_id) return;
        sessionStorage.setItem('assessment_session_id', payload.session_id);
        if (payload.cpa_profile) {
            sessionStorage.setItem('cpa_profile', JSON.stringify(payload.cpa_profile));
        }
        if (payload.variant_id) {
            const variant = normalizeVariant(payload.variant_id, 'A');
            sessionStorage.setItem(VARIANT_STORAGE, variant);
            setCookie(VARIANT_COOKIE, variant, 30);
        }
    }

    function startAssessment(cpaSlug, assessmentMode, referralSource, options) {
        const opts = options || {};
        const common = getCommonContext(opts.defaultVariant || 'A');
        const payload = {
            cpa_slug: cpaSlug || null,
            assessment_mode: assessmentMode || 'quick',
            referral_source: referralSource || document.referrer || 'direct',
            variant_id: common.variant_id,
            utm_source: common.utm_source,
            utm_medium: common.utm_medium,
            utm_campaign: common.utm_campaign,
            device_type: common.device_type,
        };
        return fetch('/api/cpa/lead-magnet/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    }

    global.LeadMagnetAnalytics = {
        resolveVariant,
        getExperimentConfig,
        getCommonContext,
        getSessionId,
        cacheStartSession,
        trackEvent,
        sendBeaconEvent,
        startAssessment,
        safeGtag,
    };
})(window);
