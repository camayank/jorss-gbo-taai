# Visual Mockups — Complete Chat Flow (All Screens)

**Date:** 2026-03-21
**Design System:** DM Sans + DM Mono | Charcoal (#1a1a18) + Parchment (#faf9f6) + Amber (#c4975a)
**Purpose:** Show every screen of the user journey with visual fidelity

---

## Screen 1: Welcome

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  [≡]  JORSS-GBO  AI Tax Advisor                    [New Chat]   ║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║                                                                  ║
 ║  ● Profile ─── ○ Intake ─── ○ Details ─── ○ Analysis ─── ○ Report║
 ║                                                                  ║
 ╠══════════════════════════════════════════════════════════════════ ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋                                                       │   ║
 ║    │ I'm your AI tax advisor. Tell me about your 2025 tax     │   ║
 ║    │ situation and I'll give you a real estimate — not         │   ║
 ║    │ generic advice, actual numbers from a computation         │   ║
 ║    │ engine covering 22+ IRS forms and all 50 states.         │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌─────────────────────┐  ┌─────────────────────────┐         ║
 ║    │ ▶ Start my estimate │  │ 📎 Upload a W-2 or 1099 │         ║
 ║    └─────────────────────┘  └─────────────────────────┘         ║
 ║                                                                  ║
 ║                                                                  ║
 ║                                                                  ║
 ║                                                                  ║
 ║                                                                  ║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║  [📎]  Type freely or click buttons above...              [➤]   ║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║  AI estimates for planning only. Not tax advice. Terms · Privacy ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

**Visual notes:**
- Background: warm parchment (#faf9f6)
- Header: charcoal (#1a1a18) with amber brand icon
- Message bubble: white card with subtle shadow
- Buttons: white with amber text, subtle border
- Primary button: amber fill, white text
- Journey stepper: dot indicators, "Profile" active (amber dot with glow)

---

## Screen 2: Phase 1 — Filing Status

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  [≡]  JORSS-GBO  AI Tax Advisor                    [New Chat]   ║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║  ● Profile ─── ○ Intake ─── ○ Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋  What's your filing status for this tax year?         │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │   ○  Single                                              │   ║
 ║    ├──────────────────────────────────────────────────────────┤   ║
 ║    │   ○  Married Filing Jointly                    ← hover   │   ║
 ║    │      ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ amber glow ┈┈┈┈┈┈┈        │   ║
 ║    ├──────────────────────────────────────────────────────────┤   ║
 ║    │   ○  Head of Household                                   │   ║
 ║    │      Unmarried with a qualifying dependent               │   ║
 ║    ├──────────────────────────────────────────────────────────┤   ║
 ║    │   ○  Married Filing Separately                           │   ║
 ║    ├──────────────────────────────────────────────────────────┤   ║
 ║    │   ○  Qualifying Surviving Spouse                         │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║              Step 1 of 5   ━━●━━━━━━━━━━━━━━━━━                 ║
 ║                                                                  ║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║  [📎]  Type freely or click buttons above...              [➤]   ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

**Visual notes:**
- Each option is a full-width card row — NOT small buttons
- Hover state: amber border glow, slight lift (-2px translateY)
- Helper text under complex options in stone-500 gray
- Progress indicator: thin amber bar "Step 1 of 5"
- Slide-in animation: each row slides up with staggered delay (0.05s each)

---

## Screen 3: Phase 1 — Income (with smart suggestions)

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ○ Intake ─── ○ Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋  What's your approximate total annual income?         │   ║
 ║    │     Include all sources — wages, business, investments.  │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              ║
 ║    │  Under $25K  │ │  $25K-$50K  │ │ $50K-$100K  │              ║
 ║    └─────────────┘ └─────────────┘ └─────────────┘              ║
 ║    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              ║
 ║    │ $100K-$200K │ │ $200K-$500K │ │  Over $500K  │              ║
 ║    └─────────────┘ └─────────────┘ └─────────────┘              ║
 ║                                                                  ║
 ║              Step 2 of 5   ━━━━━━━●━━━━━━━━━━━━                 ║
 ║                                                                  ║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║  [📎]  Or type exact amount: "$85,000"                    [➤]   ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

**Visual notes:**
- 6 range buttons in 2×3 grid
- Input hint changes to "Or type exact amount" during income question
- Each button: white background, stone-200 border, amber on hover
- Grid layout collapses to 2 columns on mobile

---

## Screen 4: Phase 1 — Income Type (12 options with grid layout)

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ○ Intake ─── ○ Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋  What best describes your income situation?           │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌──────────────────────┐ ┌──────────────────────┐             ║
 ║    │ 💼 W-2 Employee      │ │ 💼💼 Multiple W-2 Jobs│             ║
 ║    │    (single job)      │ │                      │             ║
 ║    ├──────────────────────┤ ├──────────────────────┤             ║
 ║    │ 💼+ W-2 + Side       │ │ 📝 Self-Employed /   │             ║
 ║    │    Hustle/Freelance  │ │    Freelancer        │             ║
 ║    ├──────────────────────┤ ├──────────────────────┤             ║
 ║    │ 🏢 Business Owner    │ │ 🏖️ Retired / Pension  │             ║
 ║    │    (LLC/S-Corp)      │ │                      │             ║
 ║    ├──────────────────────┤ ├──────────────────────┤             ║
 ║    │ 📈 Investment Income │ │ 🎖️ Military           │             ║
 ║    ├──────────────────────┤ ├──────────────────────┤             ║
 ║    │ 🚗 Gig Worker        │ │ 🌾 Farmer/Agricultural│             ║
 ║    │    (Uber/DoorDash)   │ │                      │             ║
 ║    ├──────────────────────┤ ├──────────────────────┤             ║
 ║    │ ⛪ Clergy / Minister  │ │ ⬜ Not currently      │             ║
 ║    │                      │ │    working           │             ║
 ║    └──────────────────────┘ └──────────────────────┘             ║
 ║                                                                  ║
 ║              Step 5 of 5   ━━━━━━━━━━━━━━━━━━━●                 ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

**Visual notes:**
- 12 options in 2-column grid (`.many-options` class triggers grid layout)
- Each has icon + label + optional sublabel in lighter text
- On mobile: stays 2 columns but smaller text
- Staggered slide-in animation (0.05s per item)
- Hover: amber border, lift shadow

---

## Screen 5: Document Upload Offer

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ◐ Intake ─── ○ Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋                                                       │   ║
 ║    │ Want to speed things up? Upload your W-2 and I'll        │   ║
 ║    │ extract your income, withholding, and other details      │   ║
 ║    │ automatically.                                           │   ║
 ║    │                                                          │   ║
 ║    │ ┌──────────────────────────────────────────────────┐     │   ║
 ║    │ │  📄                                              │     │   ║
 ║    │ │  Drop your W-2 here or click to upload           │     │   ║
 ║    │ │  PDF, JPG, PNG accepted                          │     │   ║
 ║    │ └──────────────────────────────────────────────────┘     │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌──────────────┐ ┌──────────────┐ ┌───────────────────┐       ║
 ║    │ 📤 Upload W-2 │ │ 📤 Upload    │ │ ✏️ Enter manually  │       ║
 ║    │              │ │   1099      │ │                   │       ║
 ║    └──────────────┘ └──────────────┘ └───────────────────┘       ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

**Visual notes:**
- Drop zone: dashed border, stone-200, becomes amber on drag-over
- Upload buttons: amber fill
- "Enter manually" button: ghost style (transparent with border)
- Stepper: "Intake" is now half-filled (◐)

---

## Screen 6: Transition — Mode Choice

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ● Intake ─── ○ Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║                                                                  ║
 ║  ┌────────────────────────────────────────────────────────────┐   ║
 ║  │  Married Filing Jointly │ $120,000 │ CA │ 2 deps │ W-2    │   ║
 ║  └────────────────────────────────────────────────────────────┘   ║
 ║  ← charcoal banner with pill tags in translucent white           ║
 ║                                                                  ║
 ║  Great foundation! Now I need the details that'll save you       ║
 ║  the most money. Choose how you'd like to continue:              ║
 ║                                                                  ║
 ║  ┌────────────────────────────┐  ┌────────────────────────────┐  ║
 ║  │                            │  │                            │  ║
 ║  │     📝                      │  │     💬                      │  ║
 ║  │                            │  │                            │  ║
 ║  │  Tell Me Everything        │  │  Guide Me Step by Step     │  ║
 ║  │                            │  │                            │  ║
 ║  │  Describe your full tax    │  │  I'll ask one question     │  ║
 ║  │  situation in your own     │  │  at a time, grouped by     │  ║
 ║  │  words. I'll extract       │  │  topic. Perfect if you're  │  ║
 ║  │  every detail and only     │  │  not sure what's relevant. │  ║
 ║  │  follow up on what I need. │  │                            │  ║
 ║  │                            │  │  ~5-15 minutes             │  ║
 ║  │  Fastest if you know       │  │  ← amber accent text       │  ║
 ║  │  your numbers              │  │                            │  ║
 ║  │  ← amber accent text       │  │                            │  ║
 ║  │                            │  │                            │  ║
 ║  │  ┌──────────────────────┐  │  │  ┌──────────────────────┐  │  ║
 ║  │  │    Choose this  ▶   │  │  │  │    Choose this  ▶   │  │  ║
 ║  │  └──────────────────────┘  │  │  └──────────────────────┘  │  ║
 ║  │  ← amber button             │  │  ← amber button             │  ║
 ║  └────────────────────────────┘  └────────────────────────────┘  ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

**Visual notes:**
- Two equal-weight cards side by side
- White background, stone-200 border, 12px radius
- On hover: amber border, shadow-md, -3px translateY lift
- Amber "Choose this" button at bottom of each card
- Profile summary banner: charcoal with translucent white pill tags
- On mobile: cards stack vertically
- Slide-in animation: left card first, right card 0.15s later

---

## Screen 7A: Free-Form Mode

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ● Intake ─── ◐ Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋 Tell me about your tax situation. Include anything    │   ║
 ║    │    you think is relevant — I'll organize it all.         │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 💡 Things to mention:                                    │   ║
 ║    │  • Income sources (W-2, business, investments, rental)  │   ║
 ║    │  • Major deductions (mortgage, charity, medical)        │   ║
 ║    │  • Life changes (married, kids, bought/sold home)       │   ║
 ║    │  • Retirement accounts (401k, IRA, HSA)                 │   ║
 ║    │  • Anything unusual (crypto, foreign income, divorce)   │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║    ← stone-50 background, rounded                                ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ I make $120k W-2, my wife makes $75k also W-2. We have  │   ║
 ║    │ 2 kids ages 3 and 5 in daycare costing about $24k/year. │   ║
 ║    │ We pay $18k mortgage interest and $10k property taxes.   │   ║
 ║    │ We both max our 401ks and have HSAs. I also have some   │   ║
 ║    │ RSUs from my employer. We installed solar panels this    │   ║
 ║    │ year for $28k.                                           │   ║
 ║    │                                                          │   ║
 ║    │                                          ← amber border  │   ║
 ║    │                                             on focus     │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║                         ┌──────────┐  ┌──────────────────────┐   ║
 ║                         │ Submit ▶ │  │ Switch to guided     │   ║
 ║                         │ ← amber  │  │ mode ← ghost button  │   ║
 ║                         └──────────┘  └──────────────────────┘   ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

---

## Screen 7B: Shimmer Loading (while parsing free-form)

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ● Intake ─── ◐ Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 👤 I make $120k W-2, my wife makes $75k also W-2...     │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░                  │   ║
 ║    │  ░░░░░░░░░░░░░░░░░░░░░░░░                              │   ║
 ║    │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░              │   ║
 ║    │  ░░░░░░░░░░░░░░░░░░                                    │   ║
 ║    │                                                          │   ║
 ║    │  ← shimmer animation (gradient sweep left to right)      │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │  ● ● ●  ← typing indicator (bouncing dots)              │   ║
 ║    │  Analyzing your tax situation...                          │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

---

## Screen 8: Parsed Summary (after free-form)

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ● Intake ─── ◐ Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║                                                                  ║
 ║  ┌────────────────────────────────────────────────────────────┐   ║
 ║  │  Here's what I captured:                                   │   ║
 ║  │                                                            │   ║
 ║  │  INCOME                         ← uppercase, stone-500     │   ║
 ║  │  ✅ Total Income .............. $120,000  ← DM Mono        │   ║
 ║  │  ✅ Spouse Income ............. $75,000                     │   ║
 ║  │  ✅ RSU Compensation                                       │   ║
 ║  │                                                            │   ║
 ║  │  FAMILY                                                    │   ║
 ║  │  ✅ Dependents ................ 2 (ages 3, 5)              │   ║
 ║  │  ✅ Childcare Costs ........... $24,000                    │   ║
 ║  │                                                            │   ║
 ║  │  DEDUCTIONS                                                │   ║
 ║  │  ✅ Mortgage Interest ......... $18,000                    │   ║
 ║  │  ✅ Property Taxes ............ $10,000                    │   ║
 ║  │                                                            │   ║
 ║  │  RETIREMENT                                                │   ║
 ║  │  ✅ 401(k) .................... $23,500 × 2                │   ║
 ║  │  ✅ HSA ....................... $8,550                      │   ║
 ║  │                                                            │   ║
 ║  │  CREDITS                                                   │   ║
 ║  │  ✅ Solar Panels .............. $28,000 → ~$8,400 credit  │   ║
 ║  │                                                            │   ║
 ║  │  ─────────────────────────────────────────────────         │   ║
 ║  │  5 follow-up questions remaining  ← stone-600 text        │   ║
 ║  │                                                            │   ║
 ║  │  ┌─────────────────┐  ┌────────────────────────┐          │   ║
 ║  │  │ ✓ Looks right!  │  │ ✎ Let me fix something │          │   ║
 ║  │  │   ← amber       │  │   ← ghost              │          │   ║
 ║  │  └─────────────────┘  └────────────────────────┘          │   ║
 ║  └────────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

---

## Screen 9: Guided Mode — with Live Estimate + Topic Headers + Smart Default + Proactive Advice

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ● Intake ─── ◐ Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║ ┌───────────────────────────────────────────────────────────────┐ ║
 ║ │  +$5,264              Estimated Refund      medium confidence │ ║
 ║ │  ← GREEN #4ade80     ← parchment text       ← faded text     │ ║
 ║ └───────────────────────────────────────────────────────────────┘ ║
 ║ ← charcoal background, sticky at top, DM Mono for amount        ║
 ║                                                                  ║
 ║         Profile 45% complete — estimate getting reliable.        ║
 ║         ← centered, stone-500, 0.75rem                          ║
 ║                                                                  ║
 ║  ─────────────── INCOME DETAILS · 1/6 ───────────────────        ║
 ║  ← gradient divider line, pill tag with topic name + amber count ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋                                                       │   ║
 ║    │ 💰 With 2 children under 17, you qualify for $4,000     │   ║
 ║    │    in Child Tax Credits!                                 │   ║
 ║    │    ← green savings-badge with confetti animation 🎉     │   ║
 ║    │                                                          │   ║
 ║    │ Based on your $120,000 income filing as married joint,   │   ║
 ║    │ your federal withholding is probably around $14,400.     │   ║
 ║    │ Does that sound right?                                   │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌──────────────────────────────┐                              ║
 ║    │ Yes, ~$14,400 sounds right ✓ │  ← amber button              ║
 ║    └──────────────────────────────┘                              ║
 ║    ┌──────────────────────────────┐                              ║
 ║    │ It's different — let me enter │  ← ghost button              ║
 ║    └──────────────────────────────┘                              ║
 ║    ┌──────────────────────────────┐                              ║
 ║    │ Not sure — estimate for me   │  ← ghost button              ║
 ║    └──────────────────────────────┘                              ║
 ║                                                                  ║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║  [📎]  Type freely or click buttons above...              [➤]   ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

**This is the CORE screen. Everything comes together:**
- Live refund banner (green +$5,264 or red -$1,200)
- Progress confidence hint
- Topic section header with count
- Proactive tax advice (CTC notification with confetti)
- Smart default withholding estimate
- Clear button hierarchy (amber primary, ghost secondary)
- Amount animates with countUp on update

---

## Screen 10: Mid-Flow — Deductions with SALT Cap Warning

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ● Intake ─── ● Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║ ┌───────────────────────────────────────────────────────────────┐ ║
 ║ │  +$14,310             Estimated Refund       high confidence  │ ║
 ║ │  ← GREEN, larger now    ← parchment           ← solid text   │ ║
 ║ └───────────────────────────────────────────────────────────────┘ ║
 ║                                                                  ║
 ║         Profile 82% complete — almost there.                     ║
 ║                                                                  ║
 ║  ──────────── DEDUCTIONS & CREDITS · 5/6 ────────────────        ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋                                                       │   ║
 ║    │ ⚠️ Your property taxes alone hit the $10,000 SALT cap.   │   ║
 ║    │    ← amber warning badge                                 │   ║
 ║    │                                                          │   ║
 ║    │ 💡 With $33,000 in deductions, you'll save more by      │   ║
 ║    │    itemizing (standard deduction is $30,000).            │   ║
 ║    │    ← green insight badge                                 │   ║
 ║    │                                                          │   ║
 ║    │ How much did you donate to charity this year?             │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              ║
 ║    │  Under $1K   │ │  $1K - $5K  │ │  $5K - $20K │              ║
 ║    └─────────────┘ └─────────────┘ └─────────────┘              ║
 ║    ┌─────────────┐ ┌──────┐                                      ║
 ║    │  Over $20K   │ │ Skip │                                      ║
 ║    └─────────────┘ └──────┘                                      ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

---

## Screen 11: MFJ vs MFS Comparison

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ● Intake ─── ● Details ─── ○ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║ ┌───────────────────────────────────────────────────────────────┐ ║
 ║ │  +$14,670             Estimated Refund       high confidence  │ ║
 ║ └───────────────────────────────────────────────────────────────┘ ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋 Here's how your filing options compare:               │   ║
 ║    │                                                          │   ║
 ║    │  ┌─────────────────────┐  ┌─────────────────────┐       │   ║
 ║    │  │ MARRIED FILING      │  │ MARRIED FILING      │       │   ║
 ║    │  │ JOINTLY             │  │ SEPARATELY          │       │   ║
 ║    │  │                     │  │                     │       │   ║
 ║    │  │  Refund: +$14,670   │  │  Owed: -$2,340      │       │   ║
 ║    │  │  ← GREEN, large     │  │  ← RED, large       │       │   ║
 ║    │  │                     │  │                     │       │   ║
 ║    │  │  ★ RECOMMENDED      │  │                     │       │   ║
 ║    │  │  ← amber badge      │  │                     │       │   ║
 ║    │  └─────────────────────┘  └─────────────────────┘       │   ║
 ║    │                                                          │   ║
 ║    │  💡 Filing Jointly saves you ~$17,010                    │   ║
 ║    │     ← green text, DM Mono for amount                    │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌──────────────────────────────┐  ┌──────────────────────┐    ║
 ║    │ File as MFJ (recommended) ✓  │  │ I'll decide later    │    ║
 ║    └──────────────────────────────┘  └──────────────────────┘    ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

---

## Screen 12: Emotional Intelligence — Term Explanation

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║                                                                  ║
 ║         ┌────────────────────────────────────────────┐           ║
 ║         │ 👤 What is AMT?                            │           ║
 ║         └────────────────────────────────────────────┘           ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋 No worries — let me explain.                          │   ║
 ║    │                                                          │   ║
 ║    │ AMT (Alternative Minimum Tax) is a parallel tax          │   ║
 ║    │ system that ensures high-income taxpayers pay at          │   ║
 ║    │ least a minimum amount. It mainly affects people          │   ║
 ║    │ with large state tax deductions or stock options.         │   ║
 ║    │                                                          │   ║
 ║    │ Shall we continue?                                       │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌────────────────┐ ┌─────────────────────┐ ┌──────────────┐   ║
 ║    │ Yes, continue  │ │ Use simpler Qs      │ │ Skip to calc │   ║
 ║    └────────────────┘ └─────────────────────┘ └──────────────┘   ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

---

## Screen 13: Profile Confirmation (before calculation)

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ● Intake ─── ● Details ─── ◐ Analysis ─── ○ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║ ┌───────────────────────────────────────────────────────────────┐ ║
 ║ │  +$14,670             Estimated Refund       high confidence  │ ║
 ║ └───────────────────────────────────────────────────────────────┘ ║
 ║                                                                  ║
 ║  ┌──────────────────────────── AMBER BORDER ─────────────────┐   ║
 ║  │                                                            │   ║
 ║  │  YOUR TAX PROFILE SUMMARY                                 │   ║
 ║  │  ─────────────────────────                                 │   ║
 ║  │                                                            │   ║
 ║  │  ┌ MFJ ┐ ┌ CA ┐ ┌ 2 deps ┐ ┌ W-2 Employee ┐ ┌ Age 35 ┐  │   ║
 ║  │  └─────┘ └────┘ └────────┘ └───────────────┘ └────────┘  │   ║
 ║  │  ← pill tags in stone-50 background                       │   ║
 ║  │                                                            │   ║
 ║  │  INCOME                              ← amber, uppercase   │   ║
 ║  │  Total Income ........................ $120,000            │   ║
 ║  │  Spouse W-2 Income ................... $75,000             │   ║
 ║  │  ← label: stone-600  value: DM Mono, ink, bold            │   ║
 ║  │                                                            │   ║
 ║  │  DEDUCTIONS                                                │   ║
 ║  │  Mortgage Interest ................... $18,000             │   ║
 ║  │  Property Taxes (SALT capped) ........ $10,000             │   ║
 ║  │  Charitable Donations ................ $5,000              │   ║
 ║  │                                                            │   ║
 ║  │  CREDITS                                                   │   ║
 ║  │  Child Tax Credit (2 children) ....... $4,000              │   ║
 ║  │  Childcare Credit .................... $1,200              │   ║
 ║  │  Solar Credit (30%) .................. $8,400              │   ║
 ║  │                                                            │   ║
 ║  │  RETIREMENT & SAVINGS                                      │   ║
 ║  │  401(k) Contributions (×2) ........... $47,000             │   ║
 ║  │  HSA Contributions ................... $8,550              │   ║
 ║  │                                                            │   ║
 ║  │  TAX PAYMENTS                                              │   ║
 ║  │  Federal Withholding ................. $15,000             │   ║
 ║  │                                                            │   ║
 ║  │  ─────────────────────────────────────────────────         │   ║
 ║  │                                                            │   ║
 ║  │  ╔══════════════════════════════════════════════════╗      │   ║
 ║  │  ║  ✓ Looks right — run the numbers!               ║      │   ║
 ║  │  ║  ← AMBER fill, white text, large, prominent     ║      │   ║
 ║  │  ╚══════════════════════════════════════════════════╝      │   ║
 ║  │                                                            │   ║
 ║  │  ┌──────────────────────────────────────────────┐          │   ║
 ║  │  │  ✎ I need to change something                │          │   ║
 ║  │  │  ← ghost button                              │          │   ║
 ║  │  └──────────────────────────────────────────────┘          │   ║
 ║  │                                                            │   ║
 ║  └────────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

**This is the money screen.** Everything the user told us, organized beautifully:
- Amber border around entire card (premium feel)
- Profile basics as pill tags
- Sections with amber uppercase headers
- Values right-aligned in DM Mono
- The "Run the numbers" CTA is the most prominent element on the screen
- Slide-in animation with slight delay (0.5s)

---

## Screen 14: Calculation Result (after confirmation)

```
 ╔═══════════════════════════════════════════════════════════════════╗
 ║  ● Profile ─── ● Intake ─── ● Details ─── ● Analysis ─── ◐ Report║
 ╠═══════════════════════════════════════════════════════════════════╣
 ║ ┌───────────────────────────────────────────────────────────────┐ ║
 ║ │  +$14,670             FINAL REFUND ESTIMATE    high confidence│ ║
 ║ │  ← GREEN, 1.8rem       ← all caps              ← green badge │ ║
 ║ └───────────────────────────────────────────────────────────────┘ ║
 ║                                                                  ║
 ║  🎉 ← confetti animation bursts from center                     ║
 ║                                                                  ║
 ║    ┌──────────────────────────────────────────────────────────┐   ║
 ║    │ 📋 Great news! Based on your complete profile, here's    │   ║
 ║    │    your tax breakdown:                                   │   ║
 ║    │                                                          │   ║
 ║    │    Gross Income .................. $195,000              │   ║
 ║    │    Adjustments ................... -$79,050              │   ║
 ║    │    Adjusted Gross Income ......... $115,950              │   ║
 ║    │    Deductions .................... -$33,000              │   ║
 ║    │    Taxable Income ................ $82,950               │   ║
 ║    │                                                          │   ║
 ║    │    Federal Tax ................... $9,830                │   ║
 ║    │    Credits ....................... -$13,600              │   ║
 ║    │    Net Tax ....................... $0                     │   ║
 ║    │                                                          │   ║
 ║    │    Payments Made ................. $15,000               │   ║
 ║    │    ──────────────────────────────────────                │   ║
 ║    │    REFUND ........................ $14,670               │   ║
 ║    │    ← GREEN, bold, DM Mono                               │   ║
 ║    │                                                          │   ║
 ║    │  💡 Tax Optimization Opportunities:                      │   ║
 ║    │  • Backdoor Roth IRA could save ~$1,500/year            │   ║
 ║    │  • Mega backdoor Roth available at your income           │   ║
 ║    │  • Charitable donation bunching strategy                 │   ║
 ║    └──────────────────────────────────────────────────────────┘   ║
 ║                                                                  ║
 ║    ┌──────────────────────┐  ┌──────────────────────────────┐    ║
 ║    │ 📄 Download Report   │  │ 📧 Email to me               │    ║
 ║    └──────────────────────┘  └──────────────────────────────┘    ║
 ║    ┌──────────────────────┐  ┌──────────────────────────────┐    ║
 ║    │ 🔓 Unlock Premium    │  │ 📞 Connect with a CPA       │    ║
 ║    │    Strategies        │  │                              │    ║
 ║    └──────────────────────┘  └──────────────────────────────┘    ║
 ║                                                                  ║
 ╚═══════════════════════════════════════════════════════════════════╝
```

---

## Design System Summary

| Element | Specification |
|---------|--------------|
| **Font - Body** | DM Sans, 16px base, weight 300-700 |
| **Font - Numbers** | DM Mono, weight 400-500 |
| **Background** | Parchment #faf9f6 |
| **Text** | Charcoal #1a1a18 |
| **Accent** | Amber #c4975a (buttons, highlights, borders) |
| **Success** | Green #2d8a4e / #4ade80 (refund, credits, checkmarks) |
| **Warning** | Red #c43e3e / #f87171 (owed, penalties) |
| **Muted** | Stone palette #8a8a80 → #e0e0d8 |
| **Cards** | White #fff, 12px radius, subtle shadow |
| **Buttons - Primary** | Amber fill, white text, 8px radius |
| **Buttons - Ghost** | Transparent, stone border, stone text |
| **Animations** | slideInUp 0.3s, fadeIn 0.2s, staggered buttons 0.05s |
| **Live Banner** | Charcoal bg, sticky top, green/red amount in DM Mono 1.4rem |
| **Topic Headers** | Gradient divider + stone-50 pill with amber count |
| **Confirmation** | Amber 2px border, organized sections, large CTA |
| **Mobile** | Single column, full-width buttons, smaller text |
| **Dark Mode** | Inverted palette, charcoal bg → parchment text |
