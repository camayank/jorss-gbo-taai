/**
 * Auto-Save Alpine.js Store
 * Handles automatic saving of form data with debouncing.
 *
 * Usage:
 *   import { registerAutoSaveStore } from '/static/js/alpine/stores/auto-save.js';
 *   document.addEventListener('alpine:init', () => registerAutoSaveStore(Alpine));
 *
 *   // In templates:
 *   <span x-text="$store.autoSave.statusText"></span>
 */

/**
 * Register the auto-save store with Alpine.js
 * @param {Object} Alpine - Alpine.js instance
 */
export function registerAutoSaveStore(Alpine) {
  Alpine.store('autoSave', {
    // ========================================
    // STATE
    // ========================================
    isEnabled: true,
    isSaving: false,
    lastSaved: null,
    saveError: null,
    pendingChanges: false,
    saveTimeout: null,
    debounceMs: 2000, // Wait 2 seconds after last change
    saveEndpoint: '/api/sessions/{sessionId}/save',
    sessionId: null,

    // ========================================
    // INITIALIZATION
    // ========================================

    /**
     * Initialize auto-save
     * @param {Object} options
     */
    init(options = {}) {
      if (options.sessionId) this.sessionId = options.sessionId;
      if (options.debounceMs) this.debounceMs = options.debounceMs;
      if (options.saveEndpoint) this.saveEndpoint = options.saveEndpoint;
      if (options.enabled !== undefined) this.isEnabled = options.enabled;

      // Listen for page unload to warn about unsaved changes
      window.addEventListener('beforeunload', (e) => {
        if (this.pendingChanges) {
          e.preventDefault();
          e.returnValue = '';
        }
      });

      // Try to recover unsaved data from localStorage
      this.recoverLocalData();
    },

    // ========================================
    // ACTIONS
    // ========================================

    /**
     * Mark that changes have been made
     */
    markDirty() {
      this.pendingChanges = true;
      this.saveError = null;

      if (this.isEnabled) {
        this.scheduleSave();
      }
    },

    /**
     * Schedule a save after debounce period
     */
    scheduleSave() {
      // Clear existing timeout
      if (this.saveTimeout) {
        clearTimeout(this.saveTimeout);
      }

      // Schedule new save
      this.saveTimeout = setTimeout(() => {
        this.save();
      }, this.debounceMs);
    },

    /**
     * Save immediately
     */
    async save() {
      if (!this.pendingChanges || this.isSaving || !this.sessionId) {
        return;
      }

      // Clear any scheduled save
      if (this.saveTimeout) {
        clearTimeout(this.saveTimeout);
        this.saveTimeout = null;
      }

      this.isSaving = true;
      this.saveError = null;

      try {
        // Get data to save from taxReturn store
        const taxReturn = Alpine.store('taxReturn');
        const data = taxReturn ? taxReturn.toJSON() : {};

        // Save to localStorage first (backup)
        this.saveToLocal(data);

        // Save to server
        const endpoint = this.saveEndpoint.replace('{sessionId}', this.sessionId);
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': this.getCsrfToken(),
          },
          credentials: 'same-origin',
          body: JSON.stringify(data),
        });

        if (!response.ok) {
          throw new Error(`Save failed: ${response.status}`);
        }

        // Success
        this.lastSaved = new Date();
        this.pendingChanges = false;

        // Clear local backup since server save succeeded
        this.clearLocalData();

        // Update taxReturn store
        if (taxReturn) {
          taxReturn.isDirty = false;
          taxReturn.lastSaved = this.lastSaved;
        }
      } catch (error) {
        console.error('Auto-save failed:', error);
        this.saveError = error.message || 'Failed to save';

        // Data is still in localStorage as backup
      } finally {
        this.isSaving = false;
      }
    },

    /**
     * Force immediate save (for manual save button)
     */
    async forceSave() {
      this.pendingChanges = true;
      await this.save();
    },

    /**
     * Save data to localStorage
     */
    saveToLocal(data) {
      try {
        const key = `tax-return-backup-${this.sessionId}`;
        localStorage.setItem(
          key,
          JSON.stringify({
            data,
            timestamp: Date.now(),
          })
        );
      } catch (e) {
        console.warn('Failed to save to localStorage:', e);
      }
    },

    /**
     * Clear local backup data
     */
    clearLocalData() {
      try {
        const key = `tax-return-backup-${this.sessionId}`;
        localStorage.removeItem(key);
      } catch (e) {
        // Ignore
      }
    },

    /**
     * Try to recover data from localStorage
     */
    recoverLocalData() {
      if (!this.sessionId) return null;

      try {
        const key = `tax-return-backup-${this.sessionId}`;
        const stored = localStorage.getItem(key);
        if (!stored) return null;

        const { data, timestamp } = JSON.parse(stored);

        // Only recover if less than 24 hours old
        const maxAge = 24 * 60 * 60 * 1000;
        if (Date.now() - timestamp > maxAge) {
          localStorage.removeItem(key);
          return null;
        }

        return data;
      } catch (e) {
        return null;
      }
    },

    /**
     * Get CSRF token
     */
    getCsrfToken() {
      const meta = document.querySelector('meta[name="csrf-token"]');
      if (meta) return meta.getAttribute('content');

      const cookies = document.cookie.split(';');
      for (const cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrf_token') return decodeURIComponent(value);
      }

      return '';
    },

    /**
     * Enable auto-save
     */
    enable() {
      this.isEnabled = true;
      if (this.pendingChanges) {
        this.scheduleSave();
      }
    },

    /**
     * Disable auto-save
     */
    disable() {
      this.isEnabled = false;
      if (this.saveTimeout) {
        clearTimeout(this.saveTimeout);
        this.saveTimeout = null;
      }
    },

    /**
     * Reset state
     */
    reset() {
      this.isSaving = false;
      this.lastSaved = null;
      this.saveError = null;
      this.pendingChanges = false;
      if (this.saveTimeout) {
        clearTimeout(this.saveTimeout);
        this.saveTimeout = null;
      }
    },

    // ========================================
    // GETTERS
    // ========================================

    /**
     * Get human-readable status text
     */
    get statusText() {
      if (this.isSaving) return 'Saving...';
      if (this.saveError) return 'Save failed';
      if (this.pendingChanges) return 'Unsaved changes';
      if (this.lastSaved) return `Saved ${this.formatTime(this.lastSaved)}`;
      return 'All changes saved';
    },

    /**
     * Get status type for styling
     */
    get statusType() {
      if (this.isSaving) return 'saving';
      if (this.saveError) return 'error';
      if (this.pendingChanges) return 'pending';
      return 'saved';
    },

    /**
     * Format time for display
     */
    formatTime(date) {
      if (!date) return '';
      const now = new Date();
      const diff = now - date;

      if (diff < 60000) return 'just now';
      if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;

      return date.toLocaleDateString();
    },
  });
}

// Export for non-module usage
if (typeof window !== 'undefined') {
  window.registerAutoSaveStore = registerAutoSaveStore;
}
