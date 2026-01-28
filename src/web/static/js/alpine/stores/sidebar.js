/**
 * Sidebar Alpine.js Store
 * Mobile navigation state management.
 *
 * Usage:
 *   import { registerSidebarStore } from '/static/js/alpine/stores/sidebar.js';
 *   document.addEventListener('alpine:init', () => registerSidebarStore(Alpine));
 *
 *   // In templates:
 *   <button @click="$store.sidebar.toggle()">Toggle Menu</button>
 *   <aside :class="{ 'open': $store.sidebar.isOpen }">
 */

/**
 * Register the sidebar store with Alpine.js
 * @param {Object} Alpine - Alpine.js instance
 */
export function registerSidebarStore(Alpine) {
  Alpine.store('sidebar', {
    // ========================================
    // STATE
    // ========================================
    isOpen: false,
    isCollapsed: false,
    isMobile: false,
    activeSection: null,
    expandedMenus: [],

    // ========================================
    // INITIALIZATION
    // ========================================

    /**
     * Initialize sidebar store
     */
    init() {
      // Check initial screen size
      this.checkMobile();

      // Load collapsed state from localStorage
      const savedCollapsed = localStorage.getItem('sidebar-collapsed');
      if (savedCollapsed !== null) {
        this.isCollapsed = savedCollapsed === 'true';
      }

      // Load expanded menus from localStorage
      const savedExpanded = localStorage.getItem('sidebar-expanded');
      if (savedExpanded) {
        try {
          this.expandedMenus = JSON.parse(savedExpanded);
        } catch (e) {
          this.expandedMenus = [];
        }
      }

      // Listen for window resize
      window.addEventListener('resize', () => this.checkMobile());

      // Close sidebar on escape key
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.isOpen) {
          this.close();
        }
      });

      // Close sidebar on route change (for SPAs)
      window.addEventListener('popstate', () => this.close());
    },

    // ========================================
    // ACTIONS
    // ========================================

    /**
     * Toggle sidebar open/closed (mobile)
     */
    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    },

    /**
     * Open sidebar (mobile)
     */
    open() {
      this.isOpen = true;
      document.body.style.overflow = 'hidden';
      document.body.classList.add('sidebar-open');
    },

    /**
     * Close sidebar (mobile)
     */
    close() {
      this.isOpen = false;
      document.body.style.overflow = '';
      document.body.classList.remove('sidebar-open');
    },

    /**
     * Toggle sidebar collapsed state (desktop)
     */
    toggleCollapsed() {
      this.isCollapsed = !this.isCollapsed;
      localStorage.setItem('sidebar-collapsed', this.isCollapsed);
    },

    /**
     * Expand sidebar (desktop)
     */
    expand() {
      this.isCollapsed = false;
      localStorage.setItem('sidebar-collapsed', 'false');
    },

    /**
     * Collapse sidebar (desktop)
     */
    collapse() {
      this.isCollapsed = true;
      localStorage.setItem('sidebar-collapsed', 'true');
    },

    /**
     * Check if we're on mobile
     */
    checkMobile() {
      const wasMobile = this.isMobile;
      this.isMobile = window.innerWidth < 769;

      // Auto-close sidebar when switching to desktop
      if (wasMobile && !this.isMobile && this.isOpen) {
        this.close();
      }
    },

    /**
     * Set active section (for highlighting)
     */
    setActiveSection(section) {
      this.activeSection = section;
    },

    /**
     * Toggle submenu expansion
     */
    toggleMenu(menuId) {
      const index = this.expandedMenus.indexOf(menuId);
      if (index === -1) {
        this.expandedMenus.push(menuId);
      } else {
        this.expandedMenus.splice(index, 1);
      }
      localStorage.setItem('sidebar-expanded', JSON.stringify(this.expandedMenus));
    },

    /**
     * Check if submenu is expanded
     */
    isMenuExpanded(menuId) {
      return this.expandedMenus.includes(menuId);
    },

    /**
     * Expand a submenu
     */
    expandMenu(menuId) {
      if (!this.expandedMenus.includes(menuId)) {
        this.expandedMenus.push(menuId);
        localStorage.setItem('sidebar-expanded', JSON.stringify(this.expandedMenus));
      }
    },

    /**
     * Collapse a submenu
     */
    collapseMenu(menuId) {
      const index = this.expandedMenus.indexOf(menuId);
      if (index !== -1) {
        this.expandedMenus.splice(index, 1);
        localStorage.setItem('sidebar-expanded', JSON.stringify(this.expandedMenus));
      }
    },

    /**
     * Collapse all submenus
     */
    collapseAllMenus() {
      this.expandedMenus = [];
      localStorage.setItem('sidebar-expanded', '[]');
    },

    // ========================================
    // GETTERS
    // ========================================

    /**
     * Get sidebar CSS classes
     */
    get sidebarClasses() {
      return {
        open: this.isOpen,
        collapsed: this.isCollapsed && !this.isMobile,
      };
    },

    /**
     * Get overlay visibility
     */
    get showOverlay() {
      return this.isOpen && this.isMobile;
    },
  });

  // Initialize on Alpine start
  document.addEventListener('alpine:initialized', () => {
    Alpine.store('sidebar').init();
  });
}

// Export for non-module usage
if (typeof window !== 'undefined') {
  window.registerSidebarStore = registerSidebarStore;
}
