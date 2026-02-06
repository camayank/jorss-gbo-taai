/**
 * Checkbox, Radio, and Toggle Stories
 *
 * Demonstrates checkbox variants, radio groups, and toggle switches.
 */

export default {
  title: 'Components/Forms/Checkbox',
  tags: ['autodocs']
};

// Standard Checkbox
export const StandardCheckbox = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 12px;">
      <div class="form-check">
        <input type="checkbox" id="check1" name="check1" class="form-check-input">
        <label class="form-check-label" for="check1">Remember me</label>
      </div>
      <div class="form-check">
        <input type="checkbox" id="check2" name="check2" class="form-check-input" checked>
        <label class="form-check-label" for="check2">Send me email updates</label>
      </div>
      <div class="form-check">
        <input type="checkbox" id="check3" name="check3" class="form-check-input" disabled>
        <label class="form-check-label" for="check3">Disabled option</label>
      </div>
      <div class="form-check">
        <input type="checkbox" id="check4" name="check4" class="form-check-input" checked disabled>
        <label class="form-check-label" for="check4">Disabled checked</label>
      </div>
    </div>
  `
};

// Custom Styled Checkbox
export const CustomCheckbox = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 12px;">
      <label class="checkbox-custom">
        <input type="checkbox">
        <span class="checkmark"></span>
        <span class="form-check-label">Accept terms and conditions</span>
      </label>
      <label class="checkbox-custom">
        <input type="checkbox" checked>
        <span class="checkmark"></span>
        <span class="form-check-label">Subscribe to newsletter</span>
      </label>
      <label class="checkbox-custom" style="opacity: 0.6; cursor: not-allowed;">
        <input type="checkbox" disabled>
        <span class="checkmark"></span>
        <span class="form-check-label">Disabled option</span>
      </label>
    </div>
  `
};

// Radio Buttons
export const RadioButtons = {
  render: () => `
    <div class="form-group">
      <label class="form-label">Select your plan</label>
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <div class="form-check">
          <input type="radio" id="plan_free" name="plan" value="free" class="form-check-input">
          <label class="form-check-label" for="plan_free">Free - Basic features</label>
        </div>
        <div class="form-check">
          <input type="radio" id="plan_starter" name="plan" value="starter" class="form-check-input" checked>
          <label class="form-check-label" for="plan_starter">Starter - $9/month</label>
        </div>
        <div class="form-check">
          <input type="radio" id="plan_pro" name="plan" value="pro" class="form-check-input">
          <label class="form-check-label" for="plan_pro">Pro - $29/month</label>
        </div>
        <div class="form-check">
          <input type="radio" id="plan_enterprise" name="plan" value="enterprise" class="form-check-input" disabled>
          <label class="form-check-label" for="plan_enterprise">Enterprise (Contact Sales)</label>
        </div>
      </div>
    </div>
  `
};

// Inline Radio Group
export const InlineRadioGroup = {
  render: () => `
    <div class="form-group">
      <label class="form-label">Filing Status</label>
      <div style="display: flex; gap: 24px; flex-wrap: wrap;">
        <div class="form-check">
          <input type="radio" id="status_single" name="status" value="single" class="form-check-input" checked>
          <label class="form-check-label" for="status_single">Single</label>
        </div>
        <div class="form-check">
          <input type="radio" id="status_married" name="status" value="married" class="form-check-input">
          <label class="form-check-label" for="status_married">Married</label>
        </div>
        <div class="form-check">
          <input type="radio" id="status_head" name="status" value="head" class="form-check-input">
          <label class="form-check-label" for="status_head">Head of Household</label>
        </div>
      </div>
    </div>
  `
};

// Toggle Switch
export const ToggleSwitch = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <label class="toggle">
        <input type="checkbox">
        <span class="toggle-track"></span>
        <span class="toggle-label">Dark mode</span>
      </label>
      <label class="toggle">
        <input type="checkbox" checked>
        <span class="toggle-track"></span>
        <span class="toggle-label">Email notifications</span>
      </label>
      <label class="toggle">
        <input type="checkbox">
        <span class="toggle-track"></span>
        <span class="toggle-label">Two-factor authentication</span>
      </label>
      <label class="toggle" style="opacity: 0.6; cursor: not-allowed;">
        <input type="checkbox" disabled>
        <span class="toggle-track"></span>
        <span class="toggle-label">Disabled toggle</span>
      </label>
    </div>
  `
};

// Toggle with Label on Left
export const ToggleLabelLeft = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 16px; max-width: 300px;">
      <label class="toggle" style="justify-content: space-between;">
        <span class="toggle-label">Auto-save drafts</span>
        <span style="display: flex; align-items: center;">
          <input type="checkbox" checked>
          <span class="toggle-track"></span>
        </span>
      </label>
      <label class="toggle" style="justify-content: space-between;">
        <span class="toggle-label">Show preview</span>
        <span style="display: flex; align-items: center;">
          <input type="checkbox">
          <span class="toggle-track"></span>
        </span>
      </label>
      <label class="toggle" style="justify-content: space-between;">
        <span class="toggle-label">Compact view</span>
        <span style="display: flex; align-items: center;">
          <input type="checkbox">
          <span class="toggle-track"></span>
        </span>
      </label>
    </div>
  `
};

// Checkbox Group
export const CheckboxGroup = {
  render: () => `
    <div class="form-group">
      <label class="form-label required">Select your interests</label>
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <div class="form-check">
          <input type="checkbox" id="interest_tax" name="interests[]" value="tax" class="form-check-input" checked>
          <label class="form-check-label" for="interest_tax">Tax Planning</label>
        </div>
        <div class="form-check">
          <input type="checkbox" id="interest_invest" name="interests[]" value="investing" class="form-check-input" checked>
          <label class="form-check-label" for="interest_invest">Investing</label>
        </div>
        <div class="form-check">
          <input type="checkbox" id="interest_retire" name="interests[]" value="retirement" class="form-check-input">
          <label class="form-check-label" for="interest_retire">Retirement Planning</label>
        </div>
        <div class="form-check">
          <input type="checkbox" id="interest_estate" name="interests[]" value="estate" class="form-check-input">
          <label class="form-check-label" for="interest_estate">Estate Planning</label>
        </div>
      </div>
      <p class="form-helper">Select at least one interest</p>
    </div>
  `
};

// Settings Panel Example
export const SettingsPanel = {
  render: () => `
    <div style="max-width: 400px; padding: 24px; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
      <h3 style="margin: 0 0 20px; font-size: 16px; font-weight: 600; color: #111827;">Notification Settings</h3>

      <div style="display: flex; flex-direction: column; gap: 20px;">
        <label class="toggle" style="justify-content: space-between;">
          <div>
            <div style="font-weight: 500; color: #111827;">Email notifications</div>
            <div style="font-size: 13px; color: #6b7280;">Receive updates via email</div>
          </div>
          <span style="display: flex; align-items: center;">
            <input type="checkbox" checked>
            <span class="toggle-track"></span>
          </span>
        </label>

        <label class="toggle" style="justify-content: space-between;">
          <div>
            <div style="font-weight: 500; color: #111827;">Push notifications</div>
            <div style="font-size: 13px; color: #6b7280;">Get notified on your device</div>
          </div>
          <span style="display: flex; align-items: center;">
            <input type="checkbox">
            <span class="toggle-track"></span>
          </span>
        </label>

        <label class="toggle" style="justify-content: space-between;">
          <div>
            <div style="font-weight: 500; color: #111827;">SMS notifications</div>
            <div style="font-size: 13px; color: #6b7280;">Receive text message alerts</div>
          </div>
          <span style="display: flex; align-items: center;">
            <input type="checkbox">
            <span class="toggle-track"></span>
          </span>
        </label>
      </div>
    </div>
  `
};
