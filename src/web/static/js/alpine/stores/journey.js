/**
 * Journey Alpine.js Store
 * Tracks client tax journey progress across all pages.
 */

export function registerJourneyStore(Alpine) {
  Alpine.store('journey', {
    // STATE
    currentStage: 'intake',
    stages: [],
    completionPct: 0,
    nextStep: null,
    dismissed: false,
    loaded: false,

    // INITIALIZATION
    init() {
      this.dismissed = sessionStorage.getItem('journey-banner-dismissed') === 'true';
      this.refresh();
    },

    // ACTIONS
    async refresh() {
      try {
        const [progressRes, nextRes] = await Promise.all([
          fetch('/api/journey/progress'),
          fetch('/api/journey/next-step'),
        ]);

        if (progressRes.ok) {
          const progress = await progressRes.json();
          this.currentStage = progress.current_stage;
          this.stages = progress.stages;
          this.completionPct = progress.completion_pct;
        }

        if (nextRes.ok) {
          this.nextStep = await nextRes.json();
        }

        this.loaded = true;
      } catch (err) {
        console.warn('[Journey] Failed to load progress:', err.message);
      }
    },

    dismissBanner() {
      this.dismissed = true;
      sessionStorage.setItem('journey-banner-dismissed', 'true');
    },

    // GETTERS
    get hasNextStep() {
      return this.nextStep && this.nextStep.action && !this.dismissed;
    },

    get stageLabel() {
      return this.currentStage.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    },
  });

  document.addEventListener('alpine:initialized', () => {
    Alpine.store('journey').init();
  });
}

if (typeof window !== 'undefined') {
  window.registerJourneyStore = registerJourneyStore;
}
