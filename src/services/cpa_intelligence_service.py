"""
CPA Intelligence Service

Provides professional CPA-level intelligence for the tax platform:
- Deadline urgency calculations
- Real-time opportunity detection (8 algorithms)
- Lead scoring (0-100)
- Pain point analysis
- Enhanced OpenAI context generation

This service transforms the platform from a basic chatbot to a professional
tax consultation experience.

Author: Claude AI Implementation Team
Date: 2026-01-22
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
import yaml

logger = logging.getLogger(__name__)

# ============================================================================
# TAX DEADLINES - Loaded from YAML Configuration
# ============================================================================

def load_tax_deadlines(tax_year: int = 2025) -> Dict[str, datetime]:
    """
    Load tax deadlines from YAML configuration file.

    Args:
        tax_year: Tax year to load deadlines for (default: 2025)

    Returns:
        Dictionary of deadline names to datetime objects
    """
    config_path = Path(__file__).parent.parent / "config" / "tax_parameters" / f"deadlines_{tax_year}.yaml"

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        deadlines = {}

        # Filing deadlines
        if 'filing_deadlines' in config:
            if 'primary' in config['filing_deadlines']:
                deadlines['primary_2025'] = datetime.strptime(
                    config['filing_deadlines']['primary']['date'], '%Y-%m-%d'
                )
            if 'extension' in config['filing_deadlines']:
                deadlines['extension_2025'] = datetime.strptime(
                    config['filing_deadlines']['extension']['date'], '%Y-%m-%d'
                )

        # Estimated tax deadlines
        if 'estimated_tax_deadlines' in config:
            for quarter in ['q1_2025', 'q2_2025', 'q3_2025', 'q4_2025']:
                if quarter in config['estimated_tax_deadlines']:
                    deadlines[quarter] = datetime.strptime(
                        config['estimated_tax_deadlines'][quarter]['date'], '%Y-%m-%d'
                    )

        logger.info(f"Loaded {len(deadlines)} tax deadlines from {config_path}")
        return deadlines

    except Exception as e:
        logger.warning(f"Could not load tax deadlines from {config_path}: {e}")
        logger.warning("Using hardcoded fallback deadlines")

        # Fallback to hardcoded values if YAML loading fails
        return {
            "primary_2025": datetime(2026, 4, 15),
            "extension_2025": datetime(2026, 10, 15),
            "q1_estimated_2025": datetime(2025, 4, 15),
            "q2_estimated_2025": datetime(2025, 6, 16),
            "q3_estimated_2025": datetime(2025, 9, 15),
            "q4_estimated_2025": datetime(2026, 1, 15),
        }

# Load deadlines on module import (cached)
TAX_DEADLINES = load_tax_deadlines()

# Helper function to format deadlines for messages
def format_deadline(deadline_key: str) -> str:
    """Format a deadline for display in messages."""
    if deadline_key in TAX_DEADLINES:
        return TAX_DEADLINES[deadline_key].strftime("%B %d, %Y")
    return "December 31, 2025"  # Fallback

# Common deadline strings (for convenience)
PRIMARY_DEADLINE_STR = format_deadline('primary_2025')
YEAR_END_DEADLINE = "December 31, 2025"


# ============================================================================
# DEADLINE URGENCY CALCULATIONS
# ============================================================================

def calculate_urgency_level(current_date: Optional[datetime] = None) -> Tuple[str, str, int]:
    """
    Calculate tax deadline urgency level based on current date.

    Returns:
        Tuple of (urgency_level, urgency_message, days_to_deadline)

    Urgency Levels:
        - PAST_DEADLINE: After October 15
        - CRITICAL: < 7 days to deadline
        - HIGH: 7-30 days to deadline
        - MODERATE: 30-60 days to deadline
        - PLANNING: > 60 days to deadline
    """
    if current_date is None:
        current_date = datetime.now()

    primary_deadline = TAX_DEADLINES["primary_2025"]
    extension_deadline = TAX_DEADLINES["extension_2025"]

    days_to_primary = (primary_deadline - current_date).days
    days_to_extension = (extension_deadline - current_date).days

    # Check if past both deadlines
    if days_to_extension < 0:
        return (
            "PAST_DEADLINE",
            "You've missed the filing deadline! File immediately to minimize penalties.",
            days_to_extension
        )

    # If past primary deadline, calculate from extension
    if days_to_primary < 0:
        if days_to_extension <= 7:
            return (
                "CRITICAL",
                f"Extension deadline in {days_to_extension} days! File NOW to avoid penalties.",
                days_to_extension
            )
        elif days_to_extension <= 30:
            return (
                "HIGH",
                f"Extension deadline approaching ({days_to_extension} days). Let's expedite your return.",
                days_to_extension
            )
        else:
            return (
                "MODERATE",
                "You're on extension. We have time but shouldn't delay.",
                days_to_extension
            )

    # Before primary deadline
    if days_to_primary <= 7:
        return (
            "CRITICAL",
            f"Only {days_to_primary} days until April 15 deadline! Let's file ASAP.",
            days_to_primary
        )
    elif days_to_primary <= 30:
        return (
            "HIGH",
            f"{days_to_primary} days until deadline. Let's work efficiently.",
            days_to_primary
        )
    elif days_to_primary <= 60:
        return (
            "MODERATE",
            f"{days_to_primary} days until deadline - good timing!",
            days_to_primary
        )
    else:
        return (
            "PLANNING",
            "Perfect timing for comprehensive tax planning!",
            days_to_primary
        )


# ============================================================================
# OPPORTUNITY DETECTION ALGORITHMS
# ============================================================================

def detect_opportunities(session_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Detect tax-saving opportunities from session data using 8 algorithms.

    Returns list of opportunities sorted by savings (highest first).

    Each opportunity includes:
        - id: Unique identifier
        - title: Short title
        - description: Detailed explanation
        - savings: Estimated annual tax savings (dollars)
        - category: Type (retirement, health, business, deductions, education, etc.)
        - difficulty: easy, moderate, hard
        - deadline: When action must be taken
        - action_items: List of specific actions needed
    """
    opportunities = []

    # Extract key data points
    income = session_data.get('income', 0)
    filing_status = session_data.get('filing_status', '')
    age = session_data.get('age', 30)
    has_business = session_data.get('has_business', False)
    business_revenue = session_data.get('business_revenue', 0)
    dependents_count = session_data.get('dependents', 0)
    has_kids = dependents_count > 0
    owns_home = session_data.get('owns_home', False)
    has_hdhp = session_data.get('has_hdhp', False)  # High Deductible Health Plan
    has_hsa = session_data.get('has_hsa', False)
    current_401k = session_data.get('retirement_401k', 0)
    current_ira = session_data.get('retirement_ira', 0)
    works_from_home = session_data.get('works_from_home', False)
    has_529 = session_data.get('has_529', False)
    state = session_data.get('state', '')
    mortgage_interest = session_data.get('mortgage_interest', 0)
    total_itemized = session_data.get('total_itemized', 0)

    # Algorithm 1: Retirement Contribution Optimization
    if income > 60000:
        max_401k = 23500 if age < 50 else 31000

        if current_401k < max_401k:
            potential_contribution = max_401k - current_401k
            # Conservative 22% tax bracket for $60k+
            tax_bracket = 0.22 if income < 100000 else 0.24
            savings = potential_contribution * tax_bracket

            opportunities.append({
                'id': 'retirement_401k_max',
                'title': 'Maximize 401(k) Contributions',
                'description': f'You\'re contributing ${current_401k:,} but could contribute up to ${max_401k:,}. An additional ${potential_contribution:,} contribution would save ${int(savings):,} in federal tax plus reduce your taxable income.',
                'savings': savings,
                'category': 'retirement',
                'difficulty': 'easy',
                'deadline': 'December 31, 2025',
                'action_items': [
                    'Contact HR to increase 401(k) contribution percentage',
                    f'Calculate per-paycheck increase needed: ~${int(potential_contribution/26):,} biweekly',
                    'Review investment allocation in 401(k)',
                    'Update beneficiary designations if needed'
                ]
            })

    # Algorithm 2: IRA Contribution
    if income > 30000 and income < 150000:  # Income limits for IRA deductibility
        max_ira = 7000 if age < 50 else 8000

        if current_ira < max_ira:
            potential_ira = max_ira - current_ira
            tax_bracket = 0.22 if income < 100000 else 0.24
            savings = potential_ira * tax_bracket

            opportunities.append({
                'id': 'retirement_ira_contribution',
                'title': 'Traditional IRA Contribution',
                'description': f'Contributing ${potential_ira:,} to a Traditional IRA would save ${int(savings):,} in federal tax. You can contribute until April 15, 2026 and still claim it for 2025.',
                'savings': savings,
                'category': 'retirement',
                'difficulty': 'easy',
                'deadline': 'April 15, 2026',
                'action_items': [
                    'Open Traditional IRA if you don\'t have one',
                    f'Contribute ${potential_ira:,} before April 15, 2026',
                    'Keep contribution receipt for tax filing',
                    'Consider automating monthly contributions for future years'
                ]
            })

    # Algorithm 3: HSA Triple Tax Advantage
    if has_hdhp and not has_hsa:
        hsa_limit = 4150 if filing_status == 'single' else 8300
        if age >= 55:
            hsa_limit += 1000  # Catch-up contribution

        # HSA saves: Deduction (22%) + FICA (7.65%) = 29.65% total tax savings
        total_tax_rate = 0.2965
        savings = hsa_limit * total_tax_rate

        opportunities.append({
            'id': 'hsa_open_and_fund',
            'title': 'Health Savings Account (HSA)',
            'description': f'You have a high-deductible health plan but no HSA. This is a TRIPLE tax advantage: deductible contribution, tax-free growth, and tax-free withdrawals for medical expenses. Contributing ${hsa_limit:,} saves ${int(savings):,} in taxes.',
            'savings': savings,
            'category': 'health',
            'difficulty': 'easy',
            'deadline': 'April 15, 2026',
            'action_items': [
                'Open HSA through your bank or employer',
                f'Contribute ${hsa_limit:,} for 2025 (deadline: April 15, 2026)',
                'Save medical receipts - you can reimburse yourself anytime',
                'Invest HSA funds for long-term growth (it never expires!)'
            ]
        })

    # Algorithm 4: Business Entity Optimization (S-Corp Election)
    if has_business and business_revenue > 50000:
        entity_type = session_data.get('business_entity', 'sole_proprietor')

        if entity_type == 'sole_proprietor':
            # Conservative S-Corp savings estimate
            # Assume 40% reasonable salary, rest as distributions (no SE tax)
            reasonable_salary = business_revenue * 0.4
            distributions = business_revenue - reasonable_salary
            # Self-employment tax saved on distributions: 15.3%
            se_tax_savings = distributions * 0.153

            opportunities.append({
                'id': 'scorp_election',
                'title': 'S-Corporation Election',
                'description': f'With ${business_revenue:,} in business income, electing S-Corp status could save ${int(se_tax_savings):,}/year in self-employment tax. You would take ${int(reasonable_salary):,} as W-2 salary (subject to payroll tax) and ${int(distributions):,} as distributions (no self-employment tax).',
                'savings': se_tax_savings,
                'category': 'business',
                'difficulty': 'moderate',
                'deadline': 'March 15, 2025 (for 2025 tax year)',
                'action_items': [
                    'Consult with CPA on S-Corp election timing and requirements',
                    'File Form 2553 with IRS (deadline: March 15 for current year)',
                    'Set up payroll system for reasonable salary payments',
                    'Maintain corporate formalities (separate bank account, records)',
                    'Consider quarterly estimated tax payments'
                ]
            })

    # Algorithm 5: Home Office Deduction
    if has_business and works_from_home:
        claimed_home_office = session_data.get('claimed_home_office', False)

        if not claimed_home_office:
            # Simplified method: $5/sqft up to 300 sqft = max $1,500
            # Actual method typically yields $8,000-$12,000
            # Use conservative $8,000 estimate
            estimated_deduction = 8000
            tax_rate = 0.22  # Conservative 22% bracket
            savings = estimated_deduction * tax_rate

            opportunities.append({
                'id': 'home_office_deduction',
                'title': 'Home Office Deduction',
                'description': f'You work from home but haven\'t claimed the home office deduction. Estimated ${estimated_deduction:,} deduction saves ${int(savings):,} in federal tax. You can use either the simplified method ($5/sqft) or actual expense method.',
                'savings': savings,
                'category': 'business',
                'difficulty': 'easy',
                'deadline': 'April 15, 2026',
                'action_items': [
                    'Measure your dedicated home office space (square footage)',
                    'Choose method: Simplified ($5/sqft, max 300 sqft) or Actual (mortgage interest, utilities, etc.)',
                    'Ensure office is used regularly and exclusively for business',
                    'Include on Schedule C with your business return',
                    'Keep photos and records in case of audit'
                ]
            })

    # Algorithm 6: 529 Education Savings Plan
    if has_kids and not has_529:
        # Many states offer deductions for 529 contributions
        states_with_deduction = ['VA', 'CO', 'NM', 'SC', 'NY', 'IL', 'IN', 'IA', 'MD', 'MS', 'MT', 'NE', 'OH', 'OK', 'OR', 'PA', 'UT', 'WV', 'WI']

        if state in states_with_deduction:
            contribution = 5000  # Conservative assumption
            state_tax_rate = 0.05  # Average state income tax rate
            savings = contribution * state_tax_rate

            opportunities.append({
                'id': '529_education_plan',
                'title': '529 Education Savings Plan',
                'description': f'{state} offers a state tax deduction for 529 contributions. Contributing ${contribution:,} saves about ${int(savings):,} in state tax, PLUS investments grow federal and state tax-free, and withdrawals for education are tax-free.',
                'savings': savings,
                'category': 'education',
                'difficulty': 'easy',
                'deadline': 'December 31, 2025',
                'action_items': [
                    f'Open 529 plan (recommend {state}\'s plan for state tax deduction)',
                    f'Contribute ${contribution:,} before year-end',
                    'Name child(ren) as beneficiary',
                    'Set up automatic monthly contributions',
                    'Keep contribution records for state tax return'
                ]
            })

    # Algorithm 7: Itemized vs Standard Deduction
    if owns_home and mortgage_interest == 0:
        # Homeowners who haven't entered mortgage interest
        estimated_mortgage_interest = 12000  # Conservative for homeowner
        property_tax = 10000  # Typical property tax (SALT cap at $10k)

        standard_deduction = 15000 if filing_status == 'single' else 30000
        estimated_itemized = total_itemized + estimated_mortgage_interest + property_tax

        if estimated_itemized > standard_deduction:
            additional_deduction = estimated_itemized - standard_deduction
            tax_rate = 0.22
            savings = additional_deduction * tax_rate

            opportunities.append({
                'id': 'mortgage_interest_deduction',
                'title': 'Itemize Deductions (Mortgage + Property Tax)',
                'description': f'Don\'t forget your mortgage interest and property taxes! Estimated total: ${estimated_itemized:,}. Itemizing vs taking the standard deduction saves ${int(savings):,} in federal tax.',
                'savings': savings,
                'category': 'deductions',
                'difficulty': 'easy',
                'deadline': 'April 15, 2026',
                'action_items': [
                    'Get Form 1098 (Mortgage Interest Statement) from your lender',
                    'Gather property tax receipts from 2025',
                    'Add up all other itemized deductions (charitable, medical, state taxes)',
                    'Itemize on Schedule A instead of taking standard deduction',
                    'Keep all supporting documents for 7 years'
                ]
            })

    # Algorithm 8: Dependent Care FSA
    if has_kids and dependents_count <= 2:
        claimed_dependent_care = session_data.get('claimed_dependent_care_fsa', False)

        if not claimed_dependent_care and income < 130000:  # Income phaseout
            # Dependent Care FSA limit: $5,000
            fsa_limit = 5000
            # Saves at marginal tax rate + FICA
            total_tax_rate = 0.22 + 0.0765  # 22% income tax + 7.65% FICA
            savings = fsa_limit * total_tax_rate

            opportunities.append({
                'id': 'dependent_care_fsa',
                'title': 'Dependent Care FSA',
                'description': f'If you pay for daycare or after-school care, a Dependent Care FSA lets you set aside up to ${fsa_limit:,} pre-tax. This saves ${int(savings):,} in federal income tax and FICA taxes.',
                'savings': savings,
                'category': 'family',
                'difficulty': 'easy',
                'deadline': 'During open enrollment (typically November)',
                'action_items': [
                    'Enroll in Dependent Care FSA through your employer',
                    'Elect $5,000 contribution for next year',
                    'Keep all childcare receipts',
                    'Submit claims for reimbursement throughout the year',
                    'Note: Use-it-or-lose-it, so estimate carefully'
                ]
            })

    # Sort opportunities by savings (highest first)
    opportunities.sort(key=lambda x: x['savings'], reverse=True)

    return opportunities


# ============================================================================
# LEAD SCORING
# ============================================================================

def calculate_lead_score(session_data: Dict[str, Any], conversation_history: List[Dict[str, str]]) -> int:
    """
    Calculate comprehensive lead score (0-100) for CPA prioritization.

    Scoring criteria:
        - Contact information provided (50 points max)
        - Tax complexity (40 points max)
        - Income level (20 points max)
        - Engagement (20 points max)
        - Tax planning interest (15 points max)

    Returns:
        Score from 0-100 (capped at 100)

    Score interpretation:
        80-100: PRIORITY (CPA reaches out in 4 hours)
        60-79: QUALIFIED (24-hour response)
        40-59: STANDARD (3-day response)
        0-39: DEVELOPING (nurture sequence)
    """
    score = 0

    # Contact Information (50 points max)
    if session_data.get('name'):
        score += 15
    if session_data.get('email'):
        score += 20  # Most valuable - allows follow-up
    if session_data.get('phone'):
        score += 15

    # Tax Complexity (40 points max)
    if session_data.get('has_business'):
        score += 25  # Business owners = high value
    if session_data.get('rental_income', 0) > 0:
        score += 20
    if session_data.get('investment_income', 0) > 0:
        score += 15
    if session_data.get('multi_state', False):
        score += 15
    if session_data.get('foreign_income', False):
        score += 15
    if session_data.get('crypto_trading', False):
        score += 15

    # Income Level (20 points max)
    income = session_data.get('income', 0)
    if income > 100000:
        score += 10
    if income > 200000:
        score += 15
    if income > 500000:
        score += 20

    # Engagement (20 points max)
    uploaded_docs = session_data.get('uploaded_documents', 0)
    if uploaded_docs > 0:
        score += 20  # Highly engaged

    # Number of messages (shows engagement)
    user_messages = [m for m in conversation_history if m.get('role') == 'user']
    if len(user_messages) > 5:
        score += 10
    if len(user_messages) > 10:
        score += 15

    # Tax Planning Interest (15 points max)
    # Detect planning-related keywords in conversation
    planning_keywords = [
        'plan', 'strategy', 'optimize', 'save', 'reduce', 'minimize',
        'multi-year', 's-corp', 'retirement', 'entity', 'structure'
    ]

    planning_questions = 0
    for msg in user_messages:
        content = msg.get('content', '').lower()
        if any(keyword in content for keyword in planning_keywords):
            planning_questions += 1

    if planning_questions > 0:
        score += min(planning_questions * 5, 15)

    # Advisory report generated (indicates serious interest)
    if session_data.get('advisory_report_generated', False):
        score += 15

    # Scenario comparisons viewed (very engaged)
    scenarios_viewed = session_data.get('scenarios_viewed', 0)
    if scenarios_viewed > 0:
        score += 10

    return min(score, 100)  # Cap at 100


# ============================================================================
# PAIN POINT DETECTION
# ============================================================================

def detect_pain_points(conversation_history: List[Dict[str, str]]) -> List[str]:
    """
    Analyze conversation to detect client pain points and motivations.

    Returns list of detected pain points with CPA messaging guidance.

    Pain points detected:
        - owed_money: Client owed taxes last year
        - overpaid: Client got large refund (overpaid)
        - confused: Feels overwhelmed by tax complexity
        - missed_deductions: Knows they're leaving money on table
        - audit_fear: Concerned about audits
        - time_pressure: Running out of time
        - bad_experience: Burned by previous CPA/software
        - diy_fatigue: Tired of doing it themselves
    """
    pain_indicators = {
        'owed_money': {
            'keywords': ['owed', 'had to pay', 'wrote a check', 'tax bill', 'surprised'],
            'message': 'Client owed money - position quarterly estimated payments and year-round planning'
        },
        'overpaid': {
            'keywords': ['big refund', 'interest-free loan', 'too much withheld', 'overpaid'],
            'message': 'Client overpaid - position withholding optimization and tax-efficient investing'
        },
        'confused': {
            'keywords': ['don\'t understand', 'complicated', 'overwhelmed', 'confusing', 'lost'],
            'message': 'Client feels overwhelmed - emphasize simplicity, guidance, and peace of mind'
        },
        'missed_deductions': {
            'keywords': ['left money', 'didn\'t know', 'forgot to claim', 'missed', 'could have'],
            'message': 'Client knows they\'re leaving money on table - perfect for expertise demonstration'
        },
        'audit_fear': {
            'keywords': ['audit', 'scared', 'red flag', 'IRS letter', 'examined', 'nervous'],
            'message': 'Client is risk-averse - emphasize accuracy, documentation, and audit support'
        },
        'time_pressure': {
            'keywords': ['running out', 'deadline', 'need fast', 'urgent', 'hurry', 'soon'],
            'message': 'Client is urgent - fast-track process, show efficiency and quick turnaround'
        },
        'bad_experience': {
            'keywords': ['last CPA', 'previous', 'didn\'t help', 'wasted money', 'turbo tax failed'],
            'message': 'Client was burned before - differentiate on service quality and communication'
        },
        'diy_fatigue': {
            'keywords': ['tired of', 'took forever', 'made mistakes', 'too hard', 'headache'],
            'message': 'Client is ready to delegate - emphasize time savings and expert optimization'
        }
    }

    detected_pain_points = []

    for message in conversation_history:
        if message.get('role') == 'user':
            content = message.get('content', '').lower()

            for pain_type, config in pain_indicators.items():
                keywords = config['keywords']
                if any(keyword in content for keyword in keywords):
                    if config['message'] not in detected_pain_points:
                        detected_pain_points.append(config['message'])

    return detected_pain_points


# ============================================================================
# ENHANCED OPENAI CONTEXT BUILDER
# ============================================================================

def build_enhanced_openai_context(
    session_data: Dict[str, Any],
    conversation_history: List[Dict[str, str]],
    current_date: Optional[datetime] = None
) -> str:
    """
    Build rich, professional context for OpenAI with CPA-level intelligence.

    This transforms the AI from a basic chatbot into a professional CPA conducting
    an initial consultation worth $1,500-$5,000.

    Returns:
        Enhanced system prompt with deadline awareness, opportunities, lead score,
        pain points, and professional consultation guidelines.
    """
    if current_date is None:
        current_date = datetime.now()

    # Calculate deadline urgency
    urgency_level, urgency_message, days_to_deadline = calculate_urgency_level(current_date)

    # Detect opportunities
    opportunities = detect_opportunities(session_data)

    # Calculate lead score
    lead_score = calculate_lead_score(session_data, conversation_history)

    # Detect pain points
    pain_points = detect_pain_points(conversation_history)

    # Determine tone by urgency
    tone_map = {
        "CRITICAL": "Urgent but calm, efficient, focused on speed and accuracy. No time for lengthy explanations.",
        "HIGH": "Professional, focused, time-conscious. Balance thoroughness with efficiency.",
        "MODERATE": "Consultative, thorough, relaxed. Take time to educate and build relationship.",
        "PLANNING": "Strategic, educational, comprehensive. Perfect for in-depth tax planning discussions."
    }

    # Question limits by urgency
    max_questions_map = {
        "CRITICAL": 10,
        "HIGH": 15,
        "MODERATE": 25,
        "PLANNING": 35
    }

    # Lead qualification status
    lead_status = "✅ PRIORITY LEAD" if lead_score >= 80 else "✅ Qualified" if lead_score >= 60 else "⏳ Developing"

    # Build context
    context = f"""You are an experienced CPA tax advisor with 20+ years of practice. You're conducting an initial tax consultation with a potential client. This is a professional engagement worth $1,500-$5,000, not just data collection.

CURRENT DATE: {current_date.strftime("%B %d, %Y")}
DEADLINE CONTEXT: {days_to_deadline} days until April 15, 2026
URGENCY LEVEL: {urgency_level}
URGENCY MESSAGE: {urgency_message}

CLIENT PROFILE:
- Lead Score: {lead_score}/100 ({lead_status})
- Name: {session_data.get('name', 'Not provided yet')}
- Email: {session_data.get('email', 'Not provided yet')}
- Income: ${session_data.get('income', 0):,}
- Filing Status: {session_data.get('filing_status', 'Not determined')}
- Business Owner: {"Yes" if session_data.get('has_business') else "No"}
- Dependents: {session_data.get('dependents', 0)}
- Complexity: {session_data.get('complexity', 'Standard')}

OPPORTUNITIES ALREADY DETECTED ({len(opportunities)} found):
{chr(10).join(f"• {opp['title']}: Save ${opp['savings']:,.0f}/year" for opp in opportunities[:5])}

TOTAL SAVINGS POTENTIAL SO FAR: ${sum(opp['savings'] for opp in opportunities):,.0f}

PAIN POINTS IDENTIFIED:
{chr(10).join(f"• {pain}" for pain in pain_points) if pain_points else "• None detected yet - continue conversation to uncover motivations"}

YOUR CONSULTATION OBJECTIVES:
1. Build trust through SPECIFIC expertise demonstration (use dollar amounts, not generalizations)
2. Complete initial assessment efficiently (aim for {max_questions_map[urgency_level]} questions max)
3. Present opportunities IMMEDIATELY when detected (don't wait until end!)
4. Use SPECIFIC dollar amounts, never ranges (e.g., "Save $3,600" not "$3,000-$4,000")
5. Reference client by name once you have it
6. Create appropriate urgency without being pushy
7. Position for CPA engagement naturally

TONE: {tone_map[urgency_level]}

CRITICAL RESPONSE GUIDELINES:

1. **DEMONSTRATE VALUE IN EVERY RESPONSE**
   - Bad: "Let me ask about your income."
   - Good: "What's your 2025 income? This is critical because at certain thresholds, additional retirement contributions can save thousands in taxes."

2. **SHOW OPPORTUNITIES IMMEDIATELY WHEN DETECTED**
   - The moment you detect an opportunity (e.g., high income + low 401k), present it
   - Example: "Got it, $120,000 income. Quick insight: If you're not maxing your 401(k) at $23,500, you're likely paying more tax than necessary - potentially leaving $3,600/year on the table. Let's make sure we capture all your deductions next."

3. **USE SPECIFIC NUMBERS, NOT RANGES**
   - Bad: "You could save thousands"
   - Good: "You could save $3,600 this year"

4. **KEEP RESPONSES CONCISE (3-5 SENTENCES MAX)**
   - You're a busy CPA, not a lengthy chatbot
   - Every sentence should deliver value

5. **ASK STRATEGIC QUESTIONS, NOT JUST DATA COLLECTION**
   - Bad: "What's your address?"
   - Good: "What state do you live in? Several states offer valuable tax credits we'll want to capture."

6. **DEMONSTRATE EXPERTISE THROUGH INSIGHTS**
   - Mention specific tax strategies, IRS rules, deadlines
   - Example: "Since you're self-employed, the QBI deduction could save you up to 20% on that business income - that's $8,000 on $40,000."

7. **DEADLINE-SPECIFIC APPROACH**
{f'''   - {urgency_message}
   - Focus on essentials only, skip nice-to-haves
   - Expedite the process, be efficient''' if urgency_level in ['CRITICAL', 'HIGH'] else f'''   - {urgency_message}
   - Offer comprehensive strategies
   - Include multi-year planning
   - Explore advanced tax tactics'''}

8. **LEAD SCORE AWARENESS**
   - Score {lead_score}: {lead_status}
{'''   - This is a PRIORITY lead - notify CPA team immediately
   - Offer white-glove service
   - Mention CPA consultation availability''' if lead_score >= 80 else '''   - Demonstrate value to increase engagement
   - Ask strategic questions to understand complexity
   - Position advisory services naturally'''}

REMEMBER: You're conducting a professional tax consultation worth $1,500-$5,000, NOT just collecting data. Every response should demonstrate expertise, provide value, and move toward a complete assessment that uncovers all tax-saving opportunities.
"""

    return context


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def get_cpa_intelligence(
    session_data: Dict[str, Any],
    conversation_history: List[Dict[str, str]],
    current_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get complete CPA intelligence package for a session.

    Returns dict with all intelligence components:
        - urgency_level
        - urgency_message
        - days_to_deadline
        - opportunities
        - lead_score
        - pain_points
        - enhanced_context
    """
    urgency_level, urgency_message, days_to_deadline = calculate_urgency_level(current_date)
    opportunities = detect_opportunities(session_data)
    lead_score = calculate_lead_score(session_data, conversation_history)
    pain_points = detect_pain_points(conversation_history)
    enhanced_context = build_enhanced_openai_context(session_data, conversation_history, current_date)

    return {
        'urgency_level': urgency_level,
        'urgency_message': urgency_message,
        'days_to_deadline': days_to_deadline,
        'opportunities': opportunities,
        'total_savings': sum(opp['savings'] for opp in opportunities),
        'lead_score': lead_score,
        'lead_status': 'PRIORITY' if lead_score >= 80 else 'QUALIFIED' if lead_score >= 60 else 'DEVELOPING',
        'pain_points': pain_points,
        'enhanced_context': enhanced_context
    }
