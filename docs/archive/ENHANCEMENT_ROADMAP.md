# Enhancement Roadmap: Making Decision Intelligence Robust

## Overview

This document details what exists, current limitations, and specific enhancements to transform the platform into a production-ready Tax Decision Intelligence System addressing the 3 core CPA pain points.

---

## Pain Point #1: Pre-Return Decision Chaos (Scenario Intelligence)

### What Exists Today

#### 1. Filing Status Optimizer
**File:** `src/recommendation/filing_status_optimizer.py`

```python
# Current capability (WORKS)
class FilingStatusOptimizer:
    def analyze(self, tax_return) -> FilingStatusRecommendation:
        # Compares all eligible statuses
        # Returns: recommended status, savings, confidence
```

**Strengths:**
- Compares all 5 filing statuses automatically
- Calculates exact tax under each scenario
- Returns confidence score and warnings
- Handles MFS credit disqualifications

**Limitations:**
- Single-year analysis only
- No state tax impact included
- No visualization/comparison output

---

#### 2. Scenario Comparison Engine
**File:** `src/recommendation/recommendation_engine.py:318-385`

```python
# Current capability (WORKS)
def compare_scenarios(self, tax_return, scenarios):
    """
    scenarios = [
        {"description": "Add $10k to 401k", "retirement_contribution": 10000},
        {"description": "Donate $5k", "charitable": 5000}
    ]
    Returns: side-by-side comparison
    """
```

**Strengths:**
- True what-if comparison
- Multiple scenarios simultaneously
- Returns delta from baseline

**Limitations:**
- Limited scenario types supported
- No S-Corp vs LLC comparison
- No entity structure modeling
- No multi-year projection
- Returns data only (no formatted output)

---

#### 3. Deduction Strategy Analyzer
**File:** `src/recommendation/deduction_analyzer.py`

```python
# Current capability (WORKS)
class DeductionAnalyzer:
    def analyze(self, tax_return) -> DeductionRecommendation:
        # Standard vs itemized comparison
        # Bunching strategy recommendation
        # SALT cap impact analysis
```

**Strengths:**
- Automatic standard vs itemized optimization
- Multi-year bunching strategy
- SALT cap awareness
- Specific action recommendations

**Limitations:**
- 2-year bunching only (not 3-5 year)
- No charitable remainder trust modeling
- No donor-advised fund strategy

---

### Enhancements Needed for Scenario Intelligence

#### Enhancement 1.1: Entity Structure Comparison (HIGH PRIORITY)
**New File:** `src/recommendation/entity_optimizer.py`

```python
# PROPOSED ENHANCEMENT
class EntityStructureOptimizer:
    """Compare S-Corp, LLC, Sole Prop tax implications."""

    def compare_structures(
        self,
        gross_revenue: float,
        business_expenses: float,
        owner_salary: float = None,  # For S-Corp reasonable salary
        state: str = "CA"
    ) -> EntityComparisonResult:
        """
        Returns comparison of:
        - Sole Proprietorship (Schedule C)
        - Single-Member LLC (default Schedule C)
        - S-Corporation (Form 1120-S + W-2 + K-1)

        Key calculations:
        - Self-employment tax savings
        - Reasonable salary determination
        - QBI deduction impact
        - State-specific considerations
        """

    def calculate_scorp_savings(
        self,
        net_business_income: float,
        reasonable_salary: float
    ) -> dict:
        """
        SE Tax on sole prop: 15.3% on all income
        SE Tax on S-Corp: 15.3% on salary only
        Savings = 15.3% × (net_income - salary)
        """
        se_rate = 0.153
        sole_prop_se_tax = net_business_income * se_rate * 0.9235
        scorp_se_tax = reasonable_salary * se_rate
        savings = sole_prop_se_tax - scorp_se_tax

        return {
            "sole_prop_se_tax": sole_prop_se_tax,
            "scorp_se_tax": scorp_se_tax,
            "annual_savings": savings,
            "reasonable_salary_used": reasonable_salary,
            "qbi_impact": self._calculate_qbi_impact(net_business_income, reasonable_salary)
        }
```

**Implementation Effort:** 2-3 days
**Business Value:** HIGH - #1 requested comparison by business owners

---

#### Enhancement 1.2: Multi-Year Projection Engine (MEDIUM PRIORITY)
**New File:** `src/recommendation/multi_year_projector.py`

```python
# PROPOSED ENHANCEMENT
class MultiYearProjector:
    """Project tax implications over 3-5 years."""

    def project(
        self,
        tax_return: TaxReturn,
        assumptions: ProjectionAssumptions,
        years: int = 5
    ) -> MultiYearProjection:
        """
        Assumptions include:
        - Income growth rate
        - Inflation adjustments (brackets auto-inflate)
        - Major life events (retirement, sale of business, etc.)
        - Roth conversion ladder strategy

        Returns year-by-year:
        - Projected AGI
        - Projected tax liability
        - Cumulative tax paid
        - Strategy recommendations per year
        """

    def roth_conversion_ladder(
        self,
        traditional_ira_balance: float,
        target_conversion_years: int,
        current_bracket: float,
        projected_retirement_bracket: float
    ) -> ConversionStrategy:
        """
        Optimizes Roth conversion amount per year
        to fill lower brackets before RMDs begin.
        """
```

**Implementation Effort:** 4-5 days
**Business Value:** HIGH - Enables year-round planning revenue

---

#### Enhancement 1.3: Interactive Scenario API (HIGH PRIORITY)
**New File:** `src/api/scenario_api.py`

```python
# PROPOSED ENHANCEMENT
from fastapi import APIRouter

router = APIRouter(prefix="/api/scenarios")

@router.post("/compare")
async def compare_scenarios(request: ScenarioCompareRequest) -> ScenarioCompareResponse:
    """
    Real-time scenario comparison endpoint.

    Request:
    {
        "tax_return_id": "uuid",
        "scenarios": [
            {"name": "Base Case", "modifications": {}},
            {"name": "+$10k 401k", "modifications": {"retirement_401k": 10000}},
            {"name": "Roth Convert $50k", "modifications": {"roth_conversion": 50000}}
        ]
    }

    Response:
    {
        "comparison": [
            {"name": "Base Case", "total_tax": 24500, "effective_rate": 18.2},
            {"name": "+$10k 401k", "total_tax": 22100, "effective_rate": 16.4, "savings": 2400},
            {"name": "Roth Convert $50k", "total_tax": 35500, "effective_rate": 22.1, "cost": 11000}
        ],
        "recommendation": "+$10k 401k",
        "recommendation_reason": "Highest tax savings with lowest complexity"
    }
    """

@router.post("/filing-status")
async def compare_filing_statuses(request: FilingStatusRequest) -> FilingStatusResponse:
    """Instant filing status comparison."""

@router.post("/entity-structure")
async def compare_entities(request: EntityCompareRequest) -> EntityCompareResponse:
    """S-Corp vs LLC vs Sole Prop comparison."""
```

**Implementation Effort:** 2-3 days
**Business Value:** HIGH - Enables interactive UI and integrations

---

#### Enhancement 1.4: Client-Facing Scenario Report (MEDIUM PRIORITY)
**New File:** `src/export/scenario_report.py`

```python
# PROPOSED ENHANCEMENT
class ScenarioReportGenerator:
    """Generate client-ready scenario comparison PDFs."""

    def generate(
        self,
        scenarios: List[ScenarioResult],
        client_name: str,
        preparer_info: dict
    ) -> bytes:  # PDF bytes
        """
        Generates professional PDF with:

        Page 1: Executive Summary
        - Current situation snapshot
        - Recommended scenario with savings
        - Key decision points

        Page 2: Detailed Comparison
        - Side-by-side table of all scenarios
        - Tax breakdown per scenario
        - Effective rate comparison chart

        Page 3: Action Items
        - Immediate steps
        - Deadlines
        - Required documents

        Footer: Disclaimer, preparer info, date
        """
```

**Implementation Effort:** 2 days
**Business Value:** MEDIUM - Justifies advisory fees

---

## Pain Point #2: Client Data Quality & Interview Bottleneck

### What Exists Today

#### 1. Tax Agent (Conversational Intake)
**File:** `src/agent/tax_agent.py`

```python
# Current capability (BASIC)
class TaxAgent:
    def __init__(self):
        self.collection_stage = "personal_info"  # personal_info, income, deductions, credits, review

    def process_message(self, user_input: str) -> str:
        # Sends to GPT-4o with stage context
        # Basic regex extraction for amounts
        # Simple keyword matching for filing status
```

**Strengths:**
- Multi-stage collection flow
- OpenAI integration works
- Basic data extraction
- Stage tracking

**Limitations:**
- Generic GPT prompting (not tax-domain specific)
- Simple regex extraction (misses context)
- No intelligent follow-ups
- No validation against prior answers
- No prior year comparison
- No document-to-question linkage
- Single conversation thread only

---

#### 2. Tax Rules Engine
**File:** `src/recommendation/tax_rules_engine.py`

```python
# Current capability (EXTENSIVE)
# 350+ rules covering:
INCOME_RULES = [...]      # W-2 validation, 1099 matching
DEDUCTION_RULES = [...]   # Phase-outs, AGI limits
CREDIT_RULES = [...]      # Eligibility, phase-outs
BUSINESS_RULES = [...]    # SE tax, entity rules
# Each rule has thresholds, IRS references, recommendations
```

**Strengths:**
- Comprehensive rule coverage
- IRS references included
- Threshold values current for 2025
- Structured for validation

**Limitations:**
- Rules are passive (not driving questions)
- No integration with agent
- No dynamic question generation

---

### Enhancements Needed for Data Quality

#### Enhancement 2.1: Tax-Domain AI Agent (HIGH PRIORITY)
**Enhanced File:** `src/agent/tax_agent.py`

```python
# PROPOSED ENHANCEMENT
class TaxIntelligentAgent:
    """Tax-domain specific conversational agent."""

    def __init__(self):
        self.rules_engine = TaxRulesEngine()
        self.collection_context = CollectionContext()

    def _build_system_prompt(self) -> str:
        """
        Enhanced system prompt with:
        - Tax terminology definitions
        - Common client mistakes to watch for
        - Follow-up question triggers
        - Validation patterns
        """
        return """You are an expert tax intake specialist. Your role is to
        collect complete, accurate tax information through intelligent conversation.

        CRITICAL BEHAVIORS:
        1. When client mentions rental property, ALWAYS ask about:
           - Property address and ownership %
           - Rental income received
           - Expenses (mortgage interest, property tax, repairs, depreciation)
           - Days rented vs personal use

        2. When W-2 income seems low for stated occupation, probe:
           - "You mentioned you're a software engineer with $45k wages.
              Did you start mid-year or have other employment?"

        3. When self-employment is mentioned, ALWAYS ask about:
           - Business type (1099-NEC? Schedule C?)
           - Estimated quarterly payments made
           - Home office usage
           - Vehicle mileage for business
           - Health insurance premiums paid

        4. VALIDATE against common errors:
           - W-2 Box 1 vs Box 3/5 discrepancy
           - Missing state withholding
           - Retirement contribution limits exceeded

        5. CONTEXT-AWARE follow-ups:
           - If married, ask about spouse income
           - If children claimed, verify custody/support
           - If itemizing, probe for ALL categories
        """

    def process_with_intelligence(self, user_input: str) -> AgentResponse:
        """
        Enhanced processing with:
        1. Extract structured data
        2. Validate against rules engine
        3. Generate intelligent follow-ups
        4. Track completeness score
        """

        # Extract data
        extracted = self._extract_structured_data(user_input)

        # Validate against rules
        validation_issues = self.rules_engine.validate(extracted, self.collection_context)

        # Generate follow-up questions based on:
        # - Missing required fields
        # - Validation failures
        # - Contextual triggers (rental → expenses, SE → estimated payments)
        follow_ups = self._generate_intelligent_followups(
            extracted,
            validation_issues,
            self.collection_context
        )

        # Get GPT response with enhanced context
        response = self._get_gpt_response(
            user_input,
            follow_ups,
            self.collection_context.get_summary()
        )

        return AgentResponse(
            message=response,
            extracted_data=extracted,
            validation_issues=validation_issues,
            completeness_score=self._calculate_completeness(),
            suggested_next_questions=follow_ups
        )
```

**Implementation Effort:** 5-7 days
**Business Value:** CRITICAL - Directly addresses 30-40% CPA time on bad inputs

---

#### Enhancement 2.2: Contextual Question Generator (HIGH PRIORITY)
**New File:** `src/agent/question_generator.py`

```python
# PROPOSED ENHANCEMENT
class TaxQuestionGenerator:
    """Generate contextual follow-up questions based on collected data."""

    # Question triggers based on data patterns
    TRIGGERS = {
        "rental_income_mentioned": [
            "What is the address of the rental property?",
            "What was the total rent collected in 2025?",
            "How many days was the property rented vs. personal use?",
            "Did you have any rental expenses? (mortgage interest, repairs, etc.)"
        ],
        "self_employment_detected": [
            "What type of business do you operate?",
            "Did you receive any 1099-NEC or 1099-K forms?",
            "Did you make estimated tax payments during 2025?",
            "Do you use part of your home exclusively for business?",
            "Did you use your personal vehicle for business purposes?"
        ],
        "high_income_single": [
            "Do you have any investment income? (dividends, capital gains)",
            "Did you make any charitable contributions?",
            "Do you have a Health Savings Account (HSA)?",
            "Are you maximizing your 401(k) contributions?"
        ],
        "children_claimed": [
            "What are the ages of your children?",
            "Did you pay for childcare while you worked?",
            "Did you pay any college tuition or expenses?",
            "Did any children have earned income?"
        ],
        "w2_state_mismatch": [
            "I notice your W-2 is from {state1} but you live in {state2}. Did you work remotely?",
            "Did you physically work in {state1} or from home in {state2}?",
            "How many days did you work in each state?"
        ]
    }

    def generate_followups(
        self,
        collected_data: dict,
        validation_results: List[ValidationResult]
    ) -> List[str]:
        """Generate prioritized follow-up questions."""
        questions = []

        # Check triggers
        if collected_data.get("rental_income", 0) > 0:
            if not collected_data.get("rental_expenses"):
                questions.extend(self.TRIGGERS["rental_income_mentioned"][2:])

        if collected_data.get("self_employment_income", 0) > 0:
            if not collected_data.get("estimated_payments"):
                questions.append(self.TRIGGERS["self_employment_detected"][2])

        # Add validation-driven questions
        for result in validation_results:
            if result.severity == "WARNING":
                questions.append(result.suggested_question)

        return questions[:3]  # Return top 3 most important
```

**Implementation Effort:** 3-4 days
**Business Value:** HIGH - Makes AI intake actually intelligent

---

#### Enhancement 2.3: Prior Year Comparison (MEDIUM PRIORITY)
**New File:** `src/agent/prior_year_validator.py`

```python
# PROPOSED ENHANCEMENT
class PriorYearValidator:
    """Compare current inputs against prior year for anomaly detection."""

    def compare(
        self,
        current_data: dict,
        prior_year_return: TaxReturn
    ) -> List[PriorYearAnomaly]:
        """
        Detect significant changes that warrant follow-up:

        - Income dropped >20%: "Your wages were $95k last year but $72k this year. Was there a job change?"
        - New income type: "You didn't have rental income last year. Is this a new property?"
        - Missing recurring: "Last year you claimed $5k in charitable donations. None this year?"
        - Dependent changes: "You claimed 2 dependents last year, 1 this year. Did custody change?"
        """
        anomalies = []

        # Income comparison
        prior_wages = prior_year_return.income.get_w2_wages()
        current_wages = current_data.get("wages", 0)

        if prior_wages > 0 and current_wages < prior_wages * 0.8:
            anomalies.append(PriorYearAnomaly(
                category="income",
                description=f"Wages dropped from ${prior_wages:,.0f} to ${current_wages:,.0f}",
                suggested_question="Your wages are significantly lower than last year. Was there a job change, layoff, or did you switch to self-employment?",
                severity="high"
            ))

        # Recurring deduction check
        prior_charitable = prior_year_return.deductions.get_charitable_total()
        current_charitable = current_data.get("charitable", 0)

        if prior_charitable > 1000 and current_charitable == 0:
            anomalies.append(PriorYearAnomaly(
                category="deduction",
                description=f"Charitable donations were ${prior_charitable:,.0f} last year, $0 this year",
                suggested_question="You donated over $1,000 to charity last year. Did you make any charitable contributions this year?",
                severity="medium"
            ))

        return anomalies
```

**Implementation Effort:** 2-3 days
**Business Value:** MEDIUM - Catches common omissions

---

#### Enhancement 2.4: Document-Question Linkage (MEDIUM PRIORITY)
**New File:** `src/agent/document_questioner.py`

```python
# PROPOSED ENHANCEMENT
class DocumentQuestioner:
    """Generate questions based on uploaded documents."""

    def analyze_and_question(
        self,
        document_type: str,
        extracted_data: dict,
        collected_data: dict
    ) -> List[str]:
        """
        When a document is uploaded, generate relevant questions:

        W-2 uploaded:
        - "I see you worked at Acme Corp. Was this your only employer in 2025?"
        - "Your W-2 shows $0 in Box 12 code D. Does your employer offer a 401(k)?"
        - "I notice state withholding for CA. Did you work remotely or in California?"

        1099-INT uploaded:
        - "You received $2,500 in interest from Chase Bank. Do you have other bank accounts that paid interest?"
        - "Is this interest from a joint account with your spouse?"

        1099-B uploaded:
        - "I see you sold 100 shares of AAPL. Do you have the original purchase information?"
        - "Were there any other stock sales not shown on this 1099-B?"
        """

        questions = []

        if document_type == "W-2":
            employer = extracted_data.get("employer_name")
            questions.append(f"I see you worked at {employer}. Was this your only employer in 2025?")

            if extracted_data.get("box_12_d", 0) == 0:
                questions.append("Your W-2 shows no 401(k) contributions. Does your employer offer a retirement plan?")

        return questions
```

**Implementation Effort:** 2 days
**Business Value:** MEDIUM - Intelligent document processing

---

## Pain Point #3: Non-Productized Advisory

### What Exists Today

#### 1. Tax Strategy Advisor
**File:** `src/recommendation/tax_strategy_advisor.py`

```python
# Current capability (EXTENSIVE)
class TaxStrategyAdvisor:
    def generate_strategy_report(self, tax_return) -> TaxStrategyReport:
        # Analyzes 9 categories:
        # - Retirement (401k, IRA, catch-up)
        # - Healthcare (HSA, FSA)
        # - Investment (loss harvesting, NIIT)
        # - Education (credits)
        # - Charitable (bunching, QCD)
        # - Timing (bracket management)
        # - Business (S-Corp, SE tax)
        # - Family (income splitting)
        # - State (multi-state)

        # Returns prioritized strategies with:
        # - Estimated savings
        # - Action steps
        # - Complexity level
        # - Professional help flag
```

**Strengths:**
- Comprehensive 9-category analysis
- Prioritized recommendations (immediate/current_year/long_term)
- Savings estimates included
- Action steps provided
- Professional help flags

**Limitations:**
- Output is data structure only (no formatted report)
- No client-facing presentation
- No branded deliverables
- Strategies not saved/versioned
- No "advisory packages" template

---

#### 2. Computation Statement
**File:** `src/export/computation_statement.py`

```python
# Current capability (PROFESSIONAL-GRADE)
class TaxComputationStatement:
    def generate(self, tax_return, breakdown) -> ComputationStatement:
        # Line-by-line tax calculation
        # IRS form references
        # Assumption documentation
        # Footnotes with explanations
```

**Strengths:**
- Big4-level documentation
- Every assumption tracked
- IRS references throughout
- Confidence levels per assumption

**Limitations:**
- PDF generation is basic
- No client-facing version (too technical)
- No executive summary layer

---

#### 3. Audit Trail
**File:** `src/audit/audit_trail.py`

```python
# Current capability (COMPLETE)
class AuditTrail:
    # Tracks: return lifecycle, data changes, calculations,
    # filing events, document attachments, reviews, signatures

    # Each entry has: timestamp, user, IP, changes, hash
```

**Strengths:**
- Complete event tracking
- Tamper-evident hashing
- Full change history

**Limitations:**
- Not exposed in reports
- No compliance summary view

---

### Enhancements Needed for Productized Advisory

#### Enhancement 3.1: Client Advisory Report Generator (HIGH PRIORITY)
**New File:** `src/export/advisory_report.py`

```python
# PROPOSED ENHANCEMENT
class AdvisoryReportGenerator:
    """Generate client-facing advisory deliverables."""

    def generate_annual_tax_plan(
        self,
        tax_return: TaxReturn,
        strategy_report: TaxStrategyReport,
        firm_branding: FirmBranding
    ) -> bytes:  # PDF
        """
        Professional client-facing annual tax plan:

        COVER PAGE:
        - Firm logo and branding
        - "2025 Tax Planning Report"
        - Client name
        - Prepared by / Date

        PAGE 1: EXECUTIVE SUMMARY
        ┌─────────────────────────────────────────┐
        │  YOUR 2025 TAX SNAPSHOT                 │
        │  ─────────────────────────              │
        │  Total Tax Liability: $24,500           │
        │  Effective Rate: 18.2%                  │
        │  Marginal Bracket: 22%                  │
        │                                         │
        │  OPTIMIZATION POTENTIAL                 │
        │  ─────────────────────────              │
        │  Identified Savings: $8,450             │
        │  Recommended Actions: 5                 │
        │  Immediate Priority: 2                  │
        └─────────────────────────────────────────┘

        PAGE 2: TOP RECOMMENDATIONS
        - #1 Maximize 401(k): Save $2,400
        - #2 HSA Contribution: Save $1,100
        - #3 Charitable Bunching: Save $650
        - (with action steps for each)

        PAGE 3: DETAILED ANALYSIS
        - By category (retirement, healthcare, etc.)
        - Current vs. recommended
        - Implementation timeline

        PAGE 4: NEXT STEPS
        - Immediate actions with deadlines
        - Documents needed
        - Follow-up meeting scheduling

        FOOTER: Disclaimer, firm contact
        """

    def generate_quarterly_update(
        self,
        client_id: str,
        quarter: int
    ) -> bytes:
        """
        Quarterly planning check-in:
        - Progress on annual plan
        - Estimated tax payment reminder
        - Mid-year adjustments needed
        - Market/law changes affecting client
        """
```

**Implementation Effort:** 4-5 days
**Business Value:** CRITICAL - Justifies advisory fees, enables year-round billing

---

#### Enhancement 3.2: Advisory Templates Library (MEDIUM PRIORITY)
**New File:** `src/advisory/templates.py`

```python
# PROPOSED ENHANCEMENT
class AdvisoryTemplates:
    """Pre-built advisory packages for common scenarios."""

    TEMPLATES = {
        "business_owner_planning": {
            "name": "Business Owner Tax Planning Package",
            "components": [
                "entity_structure_analysis",
                "retirement_optimization",
                "se_tax_reduction_strategies",
                "home_office_analysis",
                "vehicle_deduction_optimization",
                "estimated_tax_planning"
            ],
            "deliverables": [
                "Entity comparison report",
                "Annual tax projection",
                "Quarterly estimated payments schedule",
                "Year-end planning checklist"
            ],
            "suggested_price": "$2,500 - $5,000"
        },

        "high_net_worth_planning": {
            "name": "High Net Worth Tax Strategy",
            "components": [
                "multi_state_optimization",
                "investment_tax_efficiency",
                "charitable_giving_strategy",
                "estate_planning_coordination",
                "amt_analysis",
                "niit_mitigation"
            ],
            "deliverables": [
                "Comprehensive tax analysis",
                "Investment location optimization",
                "Charitable giving plan",
                "Multi-year tax projection"
            ],
            "suggested_price": "$5,000 - $15,000"
        },

        "retirement_transition": {
            "name": "Retirement Transition Planning",
            "components": [
                "roth_conversion_analysis",
                "social_security_optimization",
                "rmd_planning",
                "healthcare_cost_planning",
                "income_sequencing"
            ],
            "deliverables": [
                "Roth conversion schedule",
                "Social Security claiming strategy",
                "5-year income projection",
                "Medicare premium impact analysis"
            ],
            "suggested_price": "$1,500 - $3,500"
        }
    }

    def generate_package(
        self,
        template_name: str,
        tax_return: TaxReturn,
        customizations: dict = None
    ) -> AdvisoryPackage:
        """Generate complete advisory package from template."""
```

**Implementation Effort:** 3-4 days
**Business Value:** HIGH - Makes advisory repeatable and scalable

---

#### Enhancement 3.3: Strategy Versioning & History (MEDIUM PRIORITY)
**New File:** `src/advisory/strategy_history.py`

```python
# PROPOSED ENHANCEMENT
class StrategyHistory:
    """Track advisory recommendations over time."""

    def save_recommendation(
        self,
        client_id: str,
        strategy_report: TaxStrategyReport,
        status: str = "proposed"  # proposed, accepted, implemented, declined
    ) -> str:  # recommendation_id
        """
        Save strategy with:
        - Timestamp
        - Full recommendation details
        - Client response/status
        - Implementation notes
        - Outcome tracking (did it save what we projected?)
        """

    def get_client_history(
        self,
        client_id: str,
        years: int = 3
    ) -> List[StrategyHistoryEntry]:
        """
        Retrieve recommendation history:
        - What we recommended
        - What client did
        - Actual savings achieved
        - Success rate metrics
        """

    def generate_roi_report(
        self,
        client_id: str
    ) -> ROIReport:
        """
        Show value delivered:
        - "Over 3 years, we identified $45,000 in savings"
        - "You implemented $38,000 (84%)"
        - "Actual tax reduction: $36,500"
        - "Advisory fees paid: $7,500"
        - "Net benefit: $29,000 (3.9x ROI)"
        """
```

**Implementation Effort:** 3 days
**Business Value:** MEDIUM - Proves advisory value, improves retention

---

#### Enhancement 3.4: Knowledge Capture System (LOW PRIORITY)
**New File:** `src/advisory/knowledge_base.py`

```python
# PROPOSED ENHANCEMENT
class AdvisoryKnowledgeBase:
    """Capture and reuse firm-specific advisory knowledge."""

    def add_insight(
        self,
        category: str,
        scenario: str,
        recommendation: str,
        rationale: str,
        source: str = "partner"  # partner, IRS, court_case, etc.
    ):
        """
        Capture advisory insights:

        Example:
        {
            "category": "entity_structure",
            "scenario": "Consultant with >$150k net income",
            "recommendation": "Evaluate S-Corp election",
            "rationale": "SE tax savings typically $8-15k annually when reasonable salary is 60% of net",
            "source": "Partner John Smith, based on 50+ similar clients"
        }
        """

    def get_relevant_insights(
        self,
        tax_return: TaxReturn
    ) -> List[AdvisoryInsight]:
        """Retrieve insights relevant to this client's situation."""
```

**Implementation Effort:** 4-5 days
**Business Value:** LOW initially - Long-term firm value

---

## Implementation Priority Matrix

### Phase 1: Quick Wins (Week 1-2)
| Enhancement | Effort | Impact | Priority |
|-------------|--------|--------|----------|
| Scenario API endpoints | 2-3 days | HIGH | **DO FIRST** |
| Client Advisory Report PDF | 4-5 days | HIGH | **DO FIRST** |
| Entity Structure Comparison | 2-3 days | HIGH | **DO FIRST** |

### Phase 2: Core Intelligence (Week 3-4)
| Enhancement | Effort | Impact | Priority |
|-------------|--------|--------|----------|
| Tax-Domain AI Agent | 5-7 days | CRITICAL | **DO SECOND** |
| Contextual Question Generator | 3-4 days | HIGH | **DO SECOND** |
| Advisory Templates Library | 3-4 days | HIGH | **DO SECOND** |

### Phase 3: Differentiation (Week 5-6)
| Enhancement | Effort | Impact | Priority |
|-------------|--------|--------|----------|
| Multi-Year Projector | 4-5 days | HIGH | DO THIRD |
| Prior Year Comparison | 2-3 days | MEDIUM | DO THIRD |
| Strategy Versioning | 3 days | MEDIUM | DO THIRD |

### Phase 4: Polish (Week 7-8)
| Enhancement | Effort | Impact | Priority |
|-------------|--------|--------|----------|
| Document-Question Linkage | 2 days | MEDIUM | DO FOURTH |
| Scenario Report PDF | 2 days | MEDIUM | DO FOURTH |
| Knowledge Capture | 4-5 days | LOW | DEFER |

---

## Summary: What You Have vs. What You Need

### Scenario Intelligence (Pain Point #1)
```
HAVE (75%):                    NEED (25%):
✅ Filing status optimizer      ⚠️ Entity structure comparison
✅ Scenario comparison engine   ⚠️ Multi-year projections
✅ Deduction bunching           ⚠️ Interactive API
✅ Credit optimization          ⚠️ Client-facing reports
✅ AMT analysis
```

### Data Quality (Pain Point #2)
```
HAVE (50%):                    NEED (50%):
✅ Conversational AI (basic)   ⚠️ Tax-domain AI prompting
✅ 350+ rules engine           ⚠️ Intelligent follow-ups
✅ Document OCR                ⚠️ Prior year comparison
✅ Stage tracking              ⚠️ Contextual questions
                               ⚠️ Document-question linkage
```

### Productized Advisory (Pain Point #3)
```
HAVE (70%):                    NEED (30%):
✅ Strategy recommendations    ⚠️ Client-facing PDF reports
✅ Computation statements      ⚠️ Advisory templates
✅ Audit trail                 ⚠️ Strategy history/versioning
✅ 9-category analysis         ⚠️ ROI tracking
```

---

## Estimated Total Effort

| Phase | Duration | Enhancements |
|-------|----------|--------------|
| Phase 1 | 2 weeks | API, Reports, Entity Comparison |
| Phase 2 | 2 weeks | AI Agent, Questions, Templates |
| Phase 3 | 2 weeks | Multi-Year, Prior Year, Versioning |
| Phase 4 | 2 weeks | Polish and Integration |

**Total: 8 weeks to production-ready Tax Decision Intelligence Platform**

---

## Next Steps

1. **Validate priorities** with target CPA users
2. **Start Phase 1** - highest impact, fastest delivery
3. **Build demo** of scenario comparison API
4. **Create mockups** of client advisory reports
5. **Test AI prompts** with real tax scenarios

---

*Document Version: 1.0*
*Created: January 2025*
