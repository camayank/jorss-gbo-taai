/**
 * Loading Component Stories
 *
 * Demonstrates spinners, skeletons, and loading states.
 */

export default {
  title: 'Components/Feedback/Loading',
  tags: ['autodocs']
};

// Spinner sizes
export const Spinners = {
  render: () => `
    <div style="display: flex; align-items: center; gap: 24px;">
      <div style="text-align: center;">
        <div class="loading-spinner" style="width: 16px; height: 16px; border-width: 2px;"></div>
        <p style="margin-top: 8px; font-size: 12px; color: #6b7280;">Small</p>
      </div>
      <div style="text-align: center;">
        <div class="loading-spinner" style="width: 24px; height: 24px; border-width: 3px;"></div>
        <p style="margin-top: 8px; font-size: 12px; color: #6b7280;">Medium</p>
      </div>
      <div style="text-align: center;">
        <div class="loading-spinner" style="width: 40px; height: 40px; border-width: 3px;"></div>
        <p style="margin-top: 8px; font-size: 12px; color: #6b7280;">Large</p>
      </div>
      <div style="text-align: center;">
        <div class="loading-spinner" style="width: 64px; height: 64px; border-width: 4px;"></div>
        <p style="margin-top: 8px; font-size: 12px; color: #6b7280;">Extra Large</p>
      </div>
    </div>
  `
};

// Spinner colors
export const SpinnerColors = {
  render: () => `
    <div style="display: flex; align-items: center; gap: 24px;">
      <div style="text-align: center;">
        <div class="loading-spinner" style="border-top-color: var(--color-primary-600);"></div>
        <p style="margin-top: 8px; font-size: 12px; color: #6b7280;">Primary</p>
      </div>
      <div style="text-align: center;">
        <div class="loading-spinner" style="border-top-color: var(--color-accent-500);"></div>
        <p style="margin-top: 8px; font-size: 12px; color: #6b7280;">Accent</p>
      </div>
      <div style="text-align: center; background: #1f2937; padding: 16px; border-radius: 8px;">
        <div class="loading-spinner" style="border-color: rgba(255,255,255,0.2); border-top-color: white;"></div>
        <p style="margin-top: 8px; font-size: 12px; color: white;">White</p>
      </div>
      <div style="text-align: center;">
        <div class="loading-spinner" style="border-top-color: var(--color-gray-400);"></div>
        <p style="margin-top: 8px; font-size: 12px; color: #6b7280;">Gray</p>
      </div>
    </div>
  `
};

// Inline loading
export const InlineLoading = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <span style="display: inline-flex; align-items: center; gap: 8px;">
        <div class="loading-spinner" style="width: 16px; height: 16px; border-width: 2px;"></div>
        <span>Loading...</span>
      </span>
      <span style="display: inline-flex; align-items: center; gap: 8px;">
        <div class="loading-spinner" style="width: 16px; height: 16px; border-width: 2px;"></div>
        <span>Saving changes...</span>
      </span>
      <span style="display: inline-flex; align-items: center; gap: 8px;">
        <div class="loading-spinner" style="width: 16px; height: 16px; border-width: 2px;"></div>
        <span>Uploading document...</span>
      </span>
    </div>
  `
};

// Button loading states
export const ButtonLoading = {
  render: () => `
    <div style="display: flex; gap: 16px; flex-wrap: wrap;">
      <button class="btn btn-primary btn-loading" disabled>
        <span class="btn-spinner"></span>
        <span class="btn-text">Saving...</span>
      </button>
      <button class="btn btn-accent btn-loading" disabled>
        <span class="btn-spinner"></span>
        <span class="btn-text">Processing...</span>
      </button>
      <button class="btn btn-outline btn-loading" disabled>
        <span class="btn-spinner"></span>
        <span class="btn-text">Loading...</span>
      </button>
    </div>
  `
};

// Loading Overlay
export const LoadingOverlay = {
  render: () => `
    <div style="position: relative; height: 300px; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
      <div style="padding: 24px;">
        <h3 style="margin: 0 0 12px;">Dashboard Content</h3>
        <p style="color: #6b7280;">This content is behind the loading overlay.</p>
      </div>
      <div class="loading-overlay visible" style="position: absolute;">
        <div class="loading-spinner" style="width: 40px; height: 40px; border-width: 3px;"></div>
        <p class="loading-message">Loading your dashboard...</p>
      </div>
    </div>
  `
};

// Skeleton loaders
const skeletonStyle = `
  background: linear-gradient(90deg, #e5e7eb 25%, #f3f4f6 50%, #e5e7eb 75%);
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s infinite;
  border-radius: 4px;
`;

export const SkeletonText = {
  render: () => `
    <style>
      @keyframes skeleton-shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }
    </style>
    <div style="max-width: 400px; display: flex; flex-direction: column; gap: 8px;">
      <div style="${skeletonStyle} height: 16px;"></div>
      <div style="${skeletonStyle} height: 16px;"></div>
      <div style="${skeletonStyle} height: 16px; width: 60%;"></div>
    </div>
  `
};

export const SkeletonCard = {
  render: () => `
    <style>
      @keyframes skeleton-shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }
    </style>
    <div style="max-width: 300px; padding: 16px; border: 1px solid #e5e7eb; border-radius: 8px;">
      <div style="${skeletonStyle} height: 120px; margin-bottom: 16px;"></div>
      <div style="${skeletonStyle} height: 20px; width: 70%; margin-bottom: 8px;"></div>
      <div style="${skeletonStyle} height: 14px; width: 90%; margin-bottom: 4px;"></div>
      <div style="${skeletonStyle} height: 14px; width: 50%;"></div>
    </div>
  `
};

export const SkeletonAvatar = {
  render: () => `
    <style>
      @keyframes skeleton-shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }
    </style>
    <div style="display: flex; gap: 12px; align-items: center;">
      <div style="${skeletonStyle} width: 48px; height: 48px; border-radius: 50%;"></div>
      <div style="flex: 1;">
        <div style="${skeletonStyle} height: 14px; width: 120px; margin-bottom: 6px;"></div>
        <div style="${skeletonStyle} height: 12px; width: 80px;"></div>
      </div>
    </div>
  `
};

export const SkeletonTable = {
  render: () => `
    <style>
      @keyframes skeleton-shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
      }
    </style>
    <div style="max-width: 600px;">
      ${[1, 2, 3, 4].map(() => `
        <div style="display: flex; gap: 16px; padding: 12px 0; border-bottom: 1px solid #e5e7eb;">
          <div style="${skeletonStyle} height: 16px; width: 80px;"></div>
          <div style="${skeletonStyle} height: 16px; flex: 1;"></div>
          <div style="${skeletonStyle} height: 16px; width: 120px;"></div>
          <div style="${skeletonStyle} height: 16px; width: 80px;"></div>
        </div>
      `).join('')}
    </div>
  `
};

// Progress bars
export const ProgressBars = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 24px; max-width: 400px;">
      <div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 14px;">
          <span style="color: #374151;">Uploading documents...</span>
          <span style="color: #6b7280;">25%</span>
        </div>
        <div style="height: 8px; background: #e5e7eb; border-radius: 9999px; overflow: hidden;">
          <div style="height: 100%; width: 25%; background: var(--color-primary-500); border-radius: 9999px; transition: width 0.3s;"></div>
        </div>
      </div>

      <div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 14px;">
          <span style="color: #374151;">Processing tax return...</span>
          <span style="color: #6b7280;">60%</span>
        </div>
        <div style="height: 8px; background: #e5e7eb; border-radius: 9999px; overflow: hidden;">
          <div style="height: 100%; width: 60%; background: var(--color-accent-500); border-radius: 9999px; transition: width 0.3s;"></div>
        </div>
      </div>

      <div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 14px;">
          <span style="color: #374151;">Generating report...</span>
          <span style="color: #6b7280;">100%</span>
        </div>
        <div style="height: 8px; background: #e5e7eb; border-radius: 9999px; overflow: hidden;">
          <div style="height: 100%; width: 100%; background: var(--color-success-500); border-radius: 9999px; transition: width 0.3s;"></div>
        </div>
      </div>
    </div>
  `
};

// Full page loading example
export const FullPageLoading = {
  render: () => `
    <div style="border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
      <!-- Header skeleton -->
      <div style="padding: 16px 24px; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center;">
        <style>
          @keyframes skeleton-shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
          }
        </style>
        <div style="${skeletonStyle} height: 24px; width: 120px;"></div>
        <div style="display: flex; gap: 12px;">
          <div style="${skeletonStyle} height: 32px; width: 80px; border-radius: 6px;"></div>
          <div style="${skeletonStyle} height: 32px; width: 32px; border-radius: 50%;"></div>
        </div>
      </div>

      <!-- Content skeleton -->
      <div style="padding: 24px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;">
        ${[1, 2, 3].map(() => `
          <div style="padding: 16px; border: 1px solid #e5e7eb; border-radius: 8px;">
            <div style="${skeletonStyle} height: 14px; width: 60%; margin-bottom: 8px;"></div>
            <div style="${skeletonStyle} height: 32px; width: 80px;"></div>
          </div>
        `).join('')}
      </div>

      <!-- Table skeleton -->
      <div style="padding: 0 24px 24px;">
        <div style="${skeletonStyle} height: 20px; width: 150px; margin-bottom: 16px;"></div>
        ${[1, 2, 3, 4].map(() => `
          <div style="display: flex; gap: 16px; padding: 12px 0; border-bottom: 1px solid #e5e7eb;">
            <div style="${skeletonStyle} height: 16px; width: 80px;"></div>
            <div style="${skeletonStyle} height: 16px; flex: 1;"></div>
            <div style="${skeletonStyle} height: 16px; width: 100px;"></div>
          </div>
        `).join('')}
      </div>
    </div>
  `
};
