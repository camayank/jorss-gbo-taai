/**
 * Form Layout Stories
 *
 * Demonstrates form layouts, groups, and complete form examples.
 */

export default {
  title: 'Components/Forms/FormLayout',
  tags: ['autodocs']
};

// Basic Form Layout
export const BasicFormLayout = {
  render: () => `
    <form class="form" style="max-width: 400px;">
      <div class="form-group">
        <label class="form-label required" for="name">Full Name</label>
        <input type="text" id="name" name="name" class="form-input" placeholder="John Doe" required>
      </div>

      <div class="form-group">
        <label class="form-label required" for="email">Email Address</label>
        <input type="email" id="email" name="email" class="form-input" placeholder="john@example.com" required>
      </div>

      <div class="form-group">
        <label class="form-label" for="phone">Phone Number</label>
        <input type="tel" id="phone" name="phone" class="form-input" placeholder="(555) 555-5555">
        <p class="form-helper">Optional</p>
      </div>

      <div class="form-actions" style="display: flex; gap: 12px; justify-content: flex-end; padding-top: 16px;">
        <button type="button" class="btn btn-ghost">Cancel</button>
        <button type="submit" class="btn btn-primary">Submit</button>
      </div>
    </form>
  `
};

// Form Row (Side by Side)
export const FormRowLayout = {
  render: () => `
    <form class="form" style="max-width: 600px;">
      <div class="form-row">
        <div class="form-group">
          <label class="form-label required" for="first_name">First Name</label>
          <input type="text" id="first_name" name="first_name" class="form-input" placeholder="John" required>
        </div>
        <div class="form-group">
          <label class="form-label required" for="last_name">Last Name</label>
          <input type="text" id="last_name" name="last_name" class="form-input" placeholder="Doe" required>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label required" for="email2">Email</label>
        <input type="email" id="email2" name="email2" class="form-input" placeholder="john@example.com" required>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label class="form-label" for="city">City</label>
          <input type="text" id="city" name="city" class="form-input" placeholder="San Francisco">
        </div>
        <div class="form-group">
          <label class="form-label" for="state">State</label>
          <select id="state" name="state" class="form-select">
            <option value="" disabled selected>Select state</option>
            <option value="CA">California</option>
            <option value="NY">New York</option>
            <option value="TX">Texas</option>
          </select>
        </div>
        <div class="form-group" style="flex: 0.5;">
          <label class="form-label" for="zip">ZIP</label>
          <input type="text" id="zip" name="zip" class="form-input" placeholder="94102">
        </div>
      </div>
    </form>
  `
};

// Form Sections
export const FormWithSections = {
  render: () => `
    <form class="form" style="max-width: 600px;">
      <fieldset style="border: none; padding: 0; margin: 0 0 24px 0;">
        <legend style="font-size: 18px; font-weight: 600; color: #111827; margin-bottom: 4px;">Personal Information</legend>
        <p style="font-size: 14px; color: #6b7280; margin-bottom: 16px;">Enter your basic details</p>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label required" for="fname">First Name</label>
            <input type="text" id="fname" name="fname" class="form-input" required>
          </div>
          <div class="form-group">
            <label class="form-label required" for="lname">Last Name</label>
            <input type="text" id="lname" name="lname" class="form-input" required>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label required" for="email3">Email</label>
          <input type="email" id="email3" name="email3" class="form-input" required>
        </div>
      </fieldset>

      <fieldset style="border: none; padding: 0; margin: 0 0 24px 0;">
        <legend style="font-size: 18px; font-weight: 600; color: #111827; margin-bottom: 4px;">Tax Information</legend>
        <p style="font-size: 14px; color: #6b7280; margin-bottom: 16px;">Required for tax preparation</p>

        <div class="form-row">
          <div class="form-group">
            <label class="form-label required" for="ssn">SSN</label>
            <input type="text" id="ssn" name="ssn" class="form-input" placeholder="XXX-XX-XXXX" required>
          </div>
          <div class="form-group">
            <label class="form-label required" for="dob">Date of Birth</label>
            <input type="date" id="dob" name="dob" class="form-input" required>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label required" for="filing_status">Filing Status</label>
          <select id="filing_status" name="filing_status" class="form-select" required>
            <option value="" disabled selected>Select status</option>
            <option value="single">Single</option>
            <option value="married_joint">Married Filing Jointly</option>
            <option value="married_separate">Married Filing Separately</option>
            <option value="head">Head of Household</option>
          </select>
        </div>
      </fieldset>

      <div class="form-actions" style="display: flex; gap: 12px; justify-content: flex-end; padding-top: 16px; border-top: 1px solid #e5e7eb;">
        <button type="button" class="btn btn-ghost">Cancel</button>
        <button type="submit" class="btn btn-primary">Continue</button>
      </div>
    </form>
  `
};

// File Upload
export const FileUpload = {
  render: () => `
    <div class="form-group" style="max-width: 400px;">
      <label class="form-label">Upload Documents</label>
      <label class="file-input" for="file_upload">
        <input type="file" id="file_upload" name="file_upload" accept=".pdf,.jpg,.png" multiple>
        <svg class="file-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2M12 4v12M8 8l4-4 4 4"/>
        </svg>
        <p class="file-input-text">
          <strong>Click to upload</strong> or drag and drop<br>
          PDF, JPG, or PNG (max 10MB)
        </p>
      </label>
      <p class="form-helper">Upload your W-2s, 1099s, or other tax documents</p>
    </div>
  `
};

// Search Form
export const SearchForm = {
  render: () => `
    <form class="form" style="max-width: 600px;">
      <div class="form-row" style="align-items: flex-end;">
        <div class="form-group" style="flex: 2;">
          <div class="search-input">
            <span class="search-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
            </span>
            <input type="search" class="form-input" placeholder="Search clients by name, email, or SSN...">
          </div>
        </div>
        <div class="form-group" style="flex: 1;">
          <select class="form-select">
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="pending">Pending</option>
            <option value="completed">Completed</option>
          </select>
        </div>
        <div class="form-group" style="flex: 0;">
          <button type="submit" class="btn btn-primary">Search</button>
        </div>
      </div>
    </form>
  `
};

// Complete Contact Form
export const ContactForm = {
  render: () => `
    <div style="max-width: 500px; padding: 32px; background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
      <h2 style="margin: 0 0 8px; font-size: 24px; font-weight: 600; color: #111827;">Get in Touch</h2>
      <p style="margin: 0 0 24px; color: #6b7280;">We'd love to hear from you. Send us a message!</p>

      <form class="form">
        <div class="form-row">
          <div class="form-group">
            <label class="form-label required" for="contact_first">First Name</label>
            <input type="text" id="contact_first" name="contact_first" class="form-input" required>
          </div>
          <div class="form-group">
            <label class="form-label required" for="contact_last">Last Name</label>
            <input type="text" id="contact_last" name="contact_last" class="form-input" required>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label required" for="contact_email">Email</label>
          <input type="email" id="contact_email" name="contact_email" class="form-input" placeholder="you@example.com" required>
        </div>

        <div class="form-group">
          <label class="form-label" for="contact_phone">Phone</label>
          <input type="tel" id="contact_phone" name="contact_phone" class="form-input" placeholder="(555) 555-5555">
        </div>

        <div class="form-group">
          <label class="form-label required" for="contact_subject">Subject</label>
          <select id="contact_subject" name="contact_subject" class="form-select" required>
            <option value="" disabled selected>Select a topic</option>
            <option value="general">General Inquiry</option>
            <option value="support">Technical Support</option>
            <option value="billing">Billing Question</option>
            <option value="feedback">Feedback</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label required" for="contact_message">Message</label>
          <textarea id="contact_message" name="contact_message" class="form-textarea" rows="4" placeholder="How can we help you?" required></textarea>
        </div>

        <div class="form-check" style="margin-bottom: 16px;">
          <input type="checkbox" id="contact_consent" name="contact_consent" class="form-check-input" required>
          <label class="form-check-label" for="contact_consent">I agree to the privacy policy and terms of service</label>
        </div>

        <button type="submit" class="btn btn-primary btn-full">Send Message</button>
      </form>
    </div>
  `
};

// Login Form
export const LoginForm = {
  render: () => `
    <div style="max-width: 400px; padding: 32px; background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
      <h2 style="margin: 0 0 8px; font-size: 24px; font-weight: 600; color: #111827; text-align: center;">Welcome Back</h2>
      <p style="margin: 0 0 24px; color: #6b7280; text-align: center;">Sign in to your account</p>

      <form class="form">
        <div class="form-group">
          <label class="form-label" for="login_email">Email</label>
          <input type="email" id="login_email" name="login_email" class="form-input" placeholder="you@example.com">
        </div>

        <div class="form-group">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <label class="form-label" for="login_password" style="margin: 0;">Password</label>
            <a href="#" style="font-size: 13px; color: #0d9488; text-decoration: none;">Forgot password?</a>
          </div>
          <input type="password" id="login_password" name="login_password" class="form-input" placeholder="Enter your password">
        </div>

        <div class="form-check" style="margin-bottom: 20px;">
          <input type="checkbox" id="remember" name="remember" class="form-check-input">
          <label class="form-check-label" for="remember">Remember me for 30 days</label>
        </div>

        <button type="submit" class="btn btn-primary btn-full">Sign In</button>

        <p style="text-align: center; margin-top: 20px; font-size: 14px; color: #6b7280;">
          Don't have an account? <a href="#" style="color: #0d9488; text-decoration: none; font-weight: 500;">Sign up</a>
        </p>
      </form>
    </div>
  `
};
