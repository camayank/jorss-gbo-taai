/**
 * Feature Gate JavaScript Library
 *
 * Dynamically shows/hides UI elements based on user's feature access.
 * Integrates with backend feature access API.
 *
 * SECURITY FIXES APPLIED:
 * - Fixed memory leak from repeated event listener attachment
 * - Added URL parameter encoding to prevent injection
 * - Added request timeout handling
 * - Added callback unsubscribe mechanism
 *
 * Usage:
 *   <div data-feature="ai_chat">
 *     AI Chat feature content
 *   </div>
 *
 *   <button data-feature-require="express_lane" onclick="startExpressLane()">
 *     Start Express Lane
 *   </button>
 *
 *   <div data-feature-locked="scenario_explorer">
 *     Upgrade to access Scenario Explorer
 *   </div>
 */

class FeatureGate {
    constructor() {
        this.features = {};
        this.loaded = false;
        this.callbacks = [];
        this._callbackId = 0;

        // WeakSet to track elements that already have event listeners
        // Prevents memory leak from adding duplicate listeners
        this._processedElements = new WeakSet();

        // Bound handler for event delegation (single listener, no leak)
        this._handleNavClick = this._handleNavClick.bind(this);
        this._navListenerAttached = false;
    }

    /**
     * Initialize feature gate system
     * Fetches user's feature access from API
     */
    async init() {
        try {
            // Add timeout to prevent hanging
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000);

            const response = await fetch('/api/features/my-features', {
                signal: controller.signal,
                credentials: 'same-origin'
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                console.error('Failed to load features:', response.status);
                return;
            }

            const data = await response.json();
            this.features = data.features || {};
            this.loaded = true;

            // Apply feature gates to DOM
            this.applyFeatureGates();

            // Run callbacks (create copy to allow unsubscribe during iteration)
            const callbacksCopy = [...this.callbacks];
            callbacksCopy.forEach(({ callback }) => {
                try {
                    callback(this.features);
                } catch (e) {
                    console.error('FeatureGate callback error:', e);
                }
            });

            console.log(`FeatureGate initialized: ${data.allowed_features || 0}/${data.total_features || 0} features enabled`);
        } catch (error) {
            if (error.name === 'AbortError') {
                console.error('FeatureGate initialization timed out');
            } else {
                console.error('FeatureGate initialization failed:', error);
            }
        }
    }

    /**
     * Check if a feature is available
     * @param {string} featureCode - Feature code to check
     * @returns {boolean} True if feature is available
     */
    isAvailable(featureCode) {
        if (!this.loaded) {
            console.warn('FeatureGate not initialized. Call init() first.');
            return false;
        }

        const feature = this.features[featureCode];
        return feature && feature.allowed === true;
    }

    /**
     * Get feature information
     * @param {string} featureCode
     * @returns {object|null} Feature info or null
     */
    getFeature(featureCode) {
        return this.features[featureCode] || null;
    }

    /**
     * Apply feature gates to DOM elements
     * Hides/shows elements based on data-feature attributes
     */
    applyFeatureGates() {
        // Show elements with allowed features
        document.querySelectorAll('[data-feature]').forEach(element => {
            const featureCode = element.getAttribute('data-feature');
            if (this.isAvailable(featureCode)) {
                element.style.display = '';
                element.classList.remove('feature-disabled');
                element.classList.add('feature-enabled');
            } else {
                element.style.display = 'none';
                element.classList.remove('feature-enabled');
                element.classList.add('feature-disabled');
            }
        });

        // Enable/disable buttons/inputs based on feature access
        document.querySelectorAll('[data-feature-require]').forEach(element => {
            const featureCode = element.getAttribute('data-feature-require');
            if (this.isAvailable(featureCode)) {
                element.disabled = false;
                element.classList.remove('feature-locked');
            } else {
                element.disabled = true;
                element.classList.add('feature-locked');

                // Add tooltip with upgrade message
                const feature = this.getFeature(featureCode);
                if (feature && feature.upgrade_message) {
                    element.title = feature.upgrade_message;
                }
            }
        });

        // Show locked feature indicators
        document.querySelectorAll('[data-feature-locked]').forEach(element => {
            const featureCode = element.getAttribute('data-feature-locked');
            if (!this.isAvailable(featureCode)) {
                element.style.display = '';

                // Populate upgrade message (use textContent for safety)
                const feature = this.getFeature(featureCode);
                if (feature) {
                    const messageEl = element.querySelector('[data-upgrade-message]');
                    if (messageEl) {
                        messageEl.textContent = feature.upgrade_message || 'Upgrade to access this feature';
                    }

                    const tierEl = element.querySelector('[data-required-tier]');
                    if (tierEl && feature.upgrade_tier) {
                        tierEl.textContent = feature.upgrade_tier;
                    }
                }
            } else {
                element.style.display = 'none';
            }
        });

        // Update navigation items
        this._applyNavGates();
    }

    /**
     * Apply feature gates to navigation items
     * Uses event delegation to prevent memory leaks
     * @private
     */
    _applyNavGates() {
        // Set up single delegated click handler (only once)
        if (!this._navListenerAttached) {
            document.addEventListener('click', this._handleNavClick, true);
            this._navListenerAttached = true;
        }

        document.querySelectorAll('[data-feature-nav]').forEach(element => {
            const featureCode = element.getAttribute('data-feature-nav');

            if (!this.isAvailable(featureCode)) {
                element.classList.add('nav-locked');

                // Add lock icon only if not already present
                if (!element.querySelector('.lock-icon')) {
                    const lockIcon = document.createElement('span');
                    lockIcon.className = 'lock-icon';
                    lockIcon.textContent = '\uD83D\uDD12'; // Lock emoji
                    lockIcon.setAttribute('aria-hidden', 'true');
                    element.appendChild(lockIcon);
                }

                // Mark as processed (no duplicate listeners needed with delegation)
                this._processedElements.add(element);
            } else {
                element.classList.remove('nav-locked');

                // Remove lock icon if feature became available
                const lockIcon = element.querySelector('.lock-icon');
                if (lockIcon) {
                    lockIcon.remove();
                }
            }
        });
    }

    /**
     * Delegated click handler for nav items
     * Single listener handles all nav clicks - no memory leak
     * @private
     */
    _handleNavClick(e) {
        const navElement = e.target.closest('[data-feature-nav]');
        if (!navElement) return;

        const featureCode = navElement.getAttribute('data-feature-nav');
        if (!this.isAvailable(featureCode)) {
            e.preventDefault();
            e.stopPropagation();
            this.showUpgradePrompt(featureCode);
        }
    }

    /**
     * Show upgrade prompt when user tries to access locked feature
     * @param {string} featureCode
     */
    showUpgradePrompt(featureCode) {
        const feature = this.getFeature(featureCode);
        if (!feature) return;

        const message = feature.upgrade_message || 'This feature is not available on your current plan.';
        const tier = feature.upgrade_tier;

        // Check if custom upgrade modal exists
        const upgradeModal = document.getElementById('upgrade-modal');
        if (upgradeModal) {
            // Populate and show custom modal (use textContent for safety)
            const featureName = upgradeModal.querySelector('[data-feature-name]');
            const upgradeMessage = upgradeModal.querySelector('[data-upgrade-message]');
            const upgradeTier = upgradeModal.querySelector('[data-upgrade-tier]');
            const upgradeButton = upgradeModal.querySelector('[data-upgrade-button]');

            if (featureName) featureName.textContent = feature.name || 'Premium Feature';
            if (upgradeMessage) upgradeMessage.textContent = message;
            if (upgradeTier) upgradeTier.textContent = tier || '';

            // SECURITY FIX: Properly encode URL parameters
            if (upgradeButton && tier) {
                const params = new URLSearchParams();
                params.set('tier', tier);
                params.set('feature', featureCode);
                upgradeButton.href = `/billing/upgrade?${params.toString()}`;
            }

            upgradeModal.classList.add('active');

            // Trap focus in modal for accessibility
            this._trapFocusInModal(upgradeModal);
        } else {
            // Fallback to alert (alert is safe from XSS)
            const featureName = feature.name || 'this feature';
            if (tier) {
                alert(`${message}\n\nUpgrade to ${tier} tier to access ${featureName}.`);
            } else {
                alert(message);
            }
        }
    }

    /**
     * Trap focus inside modal for accessibility
     * @private
     */
    _trapFocusInModal(modal) {
        const focusableElements = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length > 0) {
            focusableElements[0].focus();
        }
    }

    /**
     * Check feature access before executing an action
     * @param {string} featureCode
     * @param {function} callback - Function to execute if feature is available
     * @returns {boolean} True if feature is available and callback was executed
     */
    checkAndExecute(featureCode, callback) {
        if (this.isAvailable(featureCode)) {
            try {
                callback();
            } catch (e) {
                console.error('Feature callback error:', e);
            }
            return true;
        } else {
            this.showUpgradePrompt(featureCode);
            return false;
        }
    }

    /**
     * Register a callback to run when features are loaded
     * @param {function} callback
     * @returns {number} Callback ID for unsubscribing
     */
    onFeaturesLoaded(callback) {
        const id = ++this._callbackId;

        if (this.loaded) {
            try {
                callback(this.features);
            } catch (e) {
                console.error('FeatureGate callback error:', e);
            }
        }

        this.callbacks.push({ id, callback });
        return id;
    }

    /**
     * Unsubscribe a callback
     * @param {number} callbackId - ID returned from onFeaturesLoaded
     */
    offFeaturesLoaded(callbackId) {
        this.callbacks = this.callbacks.filter(cb => cb.id !== callbackId);
    }

    /**
     * Refresh feature access (e.g., after subscription change)
     */
    async refresh() {
        await this.init();
    }

    /**
     * Get all available feature codes
     * @returns {Array<string>}
     */
    getAvailableFeatureCodes() {
        return Object.keys(this.features).filter(code => this.isAvailable(code));
    }

    /**
     * Get all locked feature codes
     * @returns {Array<string>}
     */
    getLockedFeatureCodes() {
        return Object.keys(this.features).filter(code => !this.isAvailable(code));
    }

    /**
     * Get features by category
     * @param {string} category
     * @returns {Array<object>}
     */
    getFeaturesByCategory(category) {
        return Object.values(this.features).filter(f => f.category === category);
    }

    /**
     * Cleanup method - call when component unmounts
     */
    destroy() {
        if (this._navListenerAttached) {
            document.removeEventListener('click', this._handleNavClick, true);
            this._navListenerAttached = false;
        }
        this.callbacks = [];
        this._processedElements = new WeakSet();
    }
}

// Global instance
window.featureGate = new FeatureGate();

// Auto-initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    window.featureGate.init();
});

/**
 * Helper function for inline feature checks
 * @param {string} featureCode
 * @returns {boolean}
 */
window.hasFeature = function(featureCode) {
    return window.featureGate.isAvailable(featureCode);
};

/**
 * Helper function to execute code only if feature is available
 * @param {string} featureCode
 * @param {function} callback
 */
window.ifFeature = function(featureCode, callback) {
    return window.featureGate.checkAndExecute(featureCode, callback);
};

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FeatureGate;
}
