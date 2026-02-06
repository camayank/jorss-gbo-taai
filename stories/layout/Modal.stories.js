/**
 * Modal Component Stories
 *
 * Demonstrates modal dialogs, drawers, and sheets.
 */

export default {
  title: 'Components/Layout/Modal',
  tags: ['autodocs']
};

// Basic Modal (Static Preview)
export const BasicModal = {
  render: () => `
    <div style="position: relative; min-height: 400px; background: #f3f4f6; border-radius: 8px; overflow: hidden;">
      <!-- Simulated backdrop -->
      <div style="position: absolute; inset: 0; background: rgba(0,0,0,0.5);"></div>

      <!-- Modal -->
      <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 16px;">
        <div class="modal-content" style="opacity: 1; transform: none; max-width: 500px;">
          <div class="modal-header">
            <h2 class="modal-title">Edit Profile</h2>
            <button type="button" class="modal-close">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6 6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label">Full Name</label>
              <input type="text" class="form-input" value="John Doe">
            </div>
            <div class="form-group">
              <label class="form-label">Email</label>
              <input type="email" class="form-input" value="john@example.com">
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-ghost">Cancel</button>
            <button class="btn btn-primary">Save Changes</button>
          </div>
        </div>
      </div>
    </div>
  `
};

// Modal Sizes
export const ModalSizes = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 24px;">
      <!-- Small Modal -->
      <div style="position: relative; height: 250px; background: #f3f4f6; border-radius: 8px; overflow: hidden;">
        <div style="position: absolute; inset: 0; background: rgba(0,0,0,0.5);"></div>
        <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 16px;">
          <div class="modal-content" style="opacity: 1; transform: none; max-width: 380px;">
            <div class="modal-header">
              <h2 class="modal-title">Small Modal</h2>
            </div>
            <div class="modal-body">
              <p style="margin: 0;">This is a small modal (380px max-width)</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Large Modal -->
      <div style="position: relative; height: 250px; background: #f3f4f6; border-radius: 8px; overflow: hidden;">
        <div style="position: absolute; inset: 0; background: rgba(0,0,0,0.5);"></div>
        <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 16px;">
          <div class="modal-content" style="opacity: 1; transform: none; max-width: 700px;">
            <div class="modal-header">
              <h2 class="modal-title">Large Modal</h2>
            </div>
            <div class="modal-body">
              <p style="margin: 0;">This is a large modal (700px max-width). Use for complex forms or content that needs more space.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `
};

// Confirmation Modal
export const ConfirmationModal = {
  render: () => `
    <div style="position: relative; min-height: 350px; background: #f3f4f6; border-radius: 8px; overflow: hidden;">
      <div style="position: absolute; inset: 0; background: rgba(0,0,0,0.5);"></div>
      <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 16px;">
        <div class="modal-content" style="opacity: 1; transform: none; max-width: 400px;">
          <div class="modal-body modal-confirm" style="padding: 32px;">
            <div class="modal-icon danger">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>
              </svg>
            </div>
            <h3 class="modal-title">Delete Client?</h3>
            <p class="modal-message">Are you sure you want to delete John Doe? This action cannot be undone and all associated tax returns will be permanently removed.</p>
          </div>
          <div class="modal-footer" style="justify-content: center;">
            <button class="btn btn-ghost">Cancel</button>
            <button class="btn btn-danger">Delete Client</button>
          </div>
        </div>
      </div>
    </div>
  `
};

// Confirmation Variants
export const ConfirmationVariants = {
  render: () => `
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px;">
      <!-- Warning -->
      <div style="background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); overflow: hidden;">
        <div class="modal-body modal-confirm" style="padding: 24px;">
          <div class="modal-icon warning">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3M12 9v4M12 17h.01"/>
            </svg>
          </div>
          <h3 class="modal-title">Unsaved Changes</h3>
          <p class="modal-message">You have unsaved changes. Are you sure you want to leave?</p>
        </div>
        <div class="modal-footer" style="justify-content: center;">
          <button class="btn btn-ghost btn-sm">Stay</button>
          <button class="btn btn-warning btn-sm">Leave</button>
        </div>
      </div>

      <!-- Success -->
      <div style="background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); overflow: hidden;">
        <div class="modal-body modal-confirm" style="padding: 24px;">
          <div class="modal-icon success">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>
            </svg>
          </div>
          <h3 class="modal-title">Return Submitted!</h3>
          <p class="modal-message">Your tax return has been successfully submitted to the IRS.</p>
        </div>
        <div class="modal-footer" style="justify-content: center;">
          <button class="btn btn-success btn-sm">View Confirmation</button>
        </div>
      </div>

      <!-- Info -->
      <div style="background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); overflow: hidden;">
        <div class="modal-body modal-confirm" style="padding: 24px;">
          <div class="modal-icon info">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
            </svg>
          </div>
          <h3 class="modal-title">New Feature</h3>
          <p class="modal-message">E-filing is now available for all tax years. Would you like to learn more?</p>
        </div>
        <div class="modal-footer" style="justify-content: center;">
          <button class="btn btn-ghost btn-sm">Maybe Later</button>
          <button class="btn btn-primary btn-sm">Learn More</button>
        </div>
      </div>

      <!-- Danger -->
      <div style="background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); overflow: hidden;">
        <div class="modal-body modal-confirm" style="padding: 24px;">
          <div class="modal-icon danger">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>
            </svg>
          </div>
          <h3 class="modal-title">Delete Account?</h3>
          <p class="modal-message">This will permanently delete your account and all data.</p>
        </div>
        <div class="modal-footer" style="justify-content: center;">
          <button class="btn btn-ghost btn-sm">Cancel</button>
          <button class="btn btn-danger btn-sm">Delete Account</button>
        </div>
      </div>
    </div>
  `
};

// Drawer
export const Drawer = {
  render: () => `
    <div style="position: relative; height: 400px; background: #f3f4f6; border-radius: 8px; overflow: hidden;">
      <div style="position: absolute; inset: 0; background: rgba(0,0,0,0.5);"></div>
      <div class="drawer active" style="position: absolute; right: 0; max-width: 400px;">
        <div class="modal-header">
          <h2 class="modal-title">Client Details</h2>
          <button type="button" class="modal-close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
        <div class="modal-body" style="flex: 1;">
          <div style="margin-bottom: 20px;">
            <div style="width: 64px; height: 64px; border-radius: 50%; background: #dbeafe; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: 600; color: #2563eb; margin-bottom: 12px;">JD</div>
            <h3 style="margin: 0 0 4px; font-size: 18px;">John Doe</h3>
            <p style="margin: 0; color: #6b7280;">john.doe@example.com</p>
          </div>
          <div style="border-top: 1px solid #e5e7eb; padding-top: 16px;">
            <h4 style="font-size: 14px; color: #6b7280; margin: 0 0 12px;">Tax Information</h4>
            <div style="display: grid; gap: 12px;">
              <div><span style="color: #6b7280; font-size: 13px;">Filing Status:</span> <span style="font-weight: 500;">Married Filing Jointly</span></div>
              <div><span style="color: #6b7280; font-size: 13px;">Tax Year:</span> <span style="font-weight: 500;">2024</span></div>
              <div><span style="color: #6b7280; font-size: 13px;">Status:</span> <span style="font-weight: 500; color: #059669;">Filed</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `
};

// Bottom Sheet
export const BottomSheet = {
  render: () => `
    <div style="position: relative; height: 400px; background: #f3f4f6; border-radius: 8px; overflow: hidden;">
      <div style="position: absolute; inset: 0; background: rgba(0,0,0,0.5);"></div>
      <div class="sheet active" style="position: absolute;">
        <div class="sheet-handle"></div>
        <div class="modal-header">
          <h3 class="modal-title">Select Action</h3>
        </div>
        <div class="modal-body">
          <div style="display: flex; flex-direction: column; gap: 8px;">
            <button class="btn btn-ghost" style="justify-content: flex-start; padding: 12px 16px;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 12px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg>
              Upload Document
            </button>
            <button class="btn btn-ghost" style="justify-content: flex-start; padding: 12px 16px;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 12px;"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              Edit Profile
            </button>
            <button class="btn btn-ghost" style="justify-content: flex-start; padding: 12px 16px; color: #dc2626;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 12px;"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  `
};

// Form Modal
export const FormModal = {
  render: () => `
    <div style="position: relative; min-height: 500px; background: #f3f4f6; border-radius: 8px; overflow: hidden;">
      <div style="position: absolute; inset: 0; background: rgba(0,0,0,0.5);"></div>
      <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 16px;">
        <div class="modal-content" style="opacity: 1; transform: none; max-width: 500px;">
          <div class="modal-header">
            <h2 class="modal-title">Add New Client</h2>
            <button type="button" class="modal-close">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 6 6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <form class="form">
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label required">First Name</label>
                  <input type="text" class="form-input" placeholder="John">
                </div>
                <div class="form-group">
                  <label class="form-label required">Last Name</label>
                  <input type="text" class="form-input" placeholder="Doe">
                </div>
              </div>
              <div class="form-group">
                <label class="form-label required">Email</label>
                <input type="email" class="form-input" placeholder="john@example.com">
              </div>
              <div class="form-group">
                <label class="form-label">Phone</label>
                <input type="tel" class="form-input" placeholder="(555) 555-5555">
              </div>
              <div class="form-group">
                <label class="form-label required">Filing Status</label>
                <select class="form-select">
                  <option value="" disabled selected>Select status</option>
                  <option>Single</option>
                  <option>Married Filing Jointly</option>
                  <option>Head of Household</option>
                </select>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button class="btn btn-ghost">Cancel</button>
            <button class="btn btn-primary">Add Client</button>
          </div>
        </div>
      </div>
    </div>
  `
};
