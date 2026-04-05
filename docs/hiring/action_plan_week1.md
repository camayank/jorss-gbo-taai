# Week 1 Action Plan — Getting to First CPA Demo
**Date:** Starting 2026-03-31
**Goal:** 1 CPA firm onboarded (at least one client completes the advisor)

---

## Day 1 (Today) — Post + Send

### Morning (1 hour)
- [ ] Post EA/CPA auditor job on Upwork (`job_post_upwork_ea_auditor.md`)
  - URL to post: https://www.upwork.com/nx/create-profile/
  - Budget: $2,250–$3,000 fixed price
  - Category: Accounting & Consulting > Tax Preparation

- [ ] Post LLM engineer job on Upwork (`job_post_upwork_llm_engineer.md`)
  - Budget: $100–120/hr, 40–50 hrs
  - Category: AI & Machine Learning > AI Model Integration

### Afternoon (1 hour)
Send the first 5 cold emails from `cpa_outreach_batch_1.md`.

**Start with these 5 — highest response probability:**
1. Real Estate CPA — Dallas, TX (Email #4) — real estate investors, cost segregation angle
2. Self-Employed Specialist — Austin, TX (Email #5) — tech contractors + consultants
3. S-Corp / Small Business CPA — San Francisco (Email #2) — Bay Area founders
4. Real Estate CPA — Los Angeles (Email #1) — §1031 + STR angle
5. High-Income Specialist — Seattle (Email #13) — RSU + ISO options angle

**Before sending each:**
1. Find the firm principal's name on their website or LinkedIn
2. Add their name to `Hi [Name]`
3. Add ONE specific line about their firm (e.g., "Saw your specialization in short-term rental properties on your website")
4. Send from rakeshanita@gmail.com, NOT a marketing platform

---

## Day 2 — Next 5 emails + LinkedIn post

### Morning
Send next 5 emails from batch 1 (Emails #6–#10).

### Afternoon (30 min)
Post on LinkedIn:

> **Subject:** I built a free AI tax advisor for CPA firms. Looking for 10 pilot partners.
>
> If you run a CPA practice and feel squeezed by TurboTax taking your simple clients — I built something for you.
>
> It's a free AI tax advisor your clients use before they decide whether to hire you. They do a 15-minute questionnaire, get a personalized analysis with your firm's name on it, and you get their full tax profile in a dashboard.
>
> No cost to you or the client. I'm looking for 10 firms to pilot with.
>
> Takes 30 minutes to set up. 15-minute demo if you're curious.
>
> DM me or reply here. 👇
>
> #CPA #TaxPlanning #TaxAdvisor #AccountingTech

---

## Day 3 — Demo prep

### Set up your demo environment
1. Log into your CPA dashboard at `/cpa/dashboard`
2. Go to Launch Setup (`/cpa/onboarding`) and complete all 3 steps:
   - [ ] Firm name + email + specialty checkboxes
   - [ ] Add your Calendly link (or create one free at calendly.com)
   - [ ] Copy your embed link and verify it loads
3. Do a full run-through of the advisor as a test client:
   - Go to your public landing page
   - Complete the full questionnaire as a $200K self-employed taxpayer in CA
   - Note every question that feels confusing or slow
   - Fix anything that breaks the flow

---

## Day 4–5 — Follow-ups + first demo

- [ ] Send remaining 5 emails from batch 1 (Emails #11–#15)
- [ ] Follow up on Day 1 emails if no reply (use the follow-up template in `cpa_cold_outreach_email.md`)
- [ ] Check Upwork for EA/CPA and LLM engineer applicants — schedule calls

### When a CPA replies and wants a demo:
1. Book a 15-minute Zoom
2. Screen share your branded advisor (`/lead-magnet?cpa=YOUR_SLUG`)
3. Walk through it as if you're a client — $180K SE taxpayer, owns home, CA
4. Show them the dashboard with their name on it
5. Show them a completed session in the Advisor Sessions tab
6. End with: "Takes 30 minutes to set up. Want to try it with 3 clients this week?"

---

## Week 1 targets
| Metric | Target |
|---|---|
| Cold emails sent | 15 |
| LinkedIn post | 1 |
| Upwork jobs posted | 2 |
| Demo calls booked | 2–3 |
| CPA firms onboarded | 1 |
| EA/CPA auditor screened | 2–3 candidates |

---

## Env vars to set before going live
These need to be in your `.env` / deployment environment:

```bash
SENTRY_DSN=<your Sentry DSN from sentry.io>
STRIPE_SECRET_KEY=<from Stripe dashboard>
STRIPE_PRICE_ID=<$50/month price ID from Stripe>
STRIPE_WEBHOOK_SECRET=<from Stripe webhook settings>
ANTHROPIC_API_KEY=<already set>
```

**Sentry setup (5 min):**
1. Go to sentry.io → New Project → Python → FastAPI
2. Copy DSN → set `SENTRY_DSN` env var
3. Done — errors will surface automatically

**Stripe setup (15 min):**
1. Go to dashboard.stripe.com → Products → Add product
2. Name: "CA4CPA Advisor — CPA Portal", Price: $50/month recurring
3. Copy Price ID → set `STRIPE_PRICE_ID`
4. Copy Secret Key → set `STRIPE_SECRET_KEY`
5. Set up webhook → copy secret → set `STRIPE_WEBHOOK_SECRET`
