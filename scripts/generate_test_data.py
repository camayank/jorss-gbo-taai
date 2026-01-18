#!/usr/bin/env python3
"""
Comprehensive Test Data Generator for CPA Panel

Generates 100+ realistic test cases covering all platform capabilities:
- Clients with varied tax situations
- Leads with full signal journeys
- Tax returns with real calculations
- Recommendations and optimization opportunities
- Engagement letters and workflow items
- Documents and intake sessions
"""

import sys
import os
import json
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# =============================================================================
# REALISTIC DATA TEMPLATES
# =============================================================================

FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Lisa", "Daniel", "Nancy",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
]

OCCUPATIONS = [
    ("Software Engineer", 95000, 185000),
    ("Marketing Manager", 75000, 145000),
    ("Sales Representative", 55000, 125000),
    ("Financial Analyst", 70000, 140000),
    ("Registered Nurse", 65000, 110000),
    ("Teacher", 45000, 85000),
    ("Accountant", 60000, 120000),
    ("Project Manager", 80000, 150000),
    ("Data Scientist", 100000, 200000),
    ("Physician", 200000, 450000),
    ("Attorney", 120000, 350000),
    ("Consultant", 90000, 250000),
    ("Real Estate Agent", 50000, 200000),
    ("Small Business Owner", 60000, 500000),
    ("Dentist", 150000, 300000),
    ("Pharmacist", 110000, 150000),
    ("Architect", 70000, 140000),
    ("Executive", 150000, 500000),
    ("Entrepreneur", 80000, 1000000),
    ("Investment Banker", 150000, 500000),
]

BUSINESS_TYPES = [
    ("Consulting LLC", "consulting"),
    ("Freelance Design", "creative"),
    ("E-commerce Store", "retail"),
    ("Real Estate Investments", "real_estate"),
    ("Restaurant", "food_service"),
    ("Medical Practice", "healthcare"),
    ("Law Firm", "legal"),
    ("Tech Startup", "technology"),
    ("Construction Company", "construction"),
    ("Marketing Agency", "marketing"),
]

STATES = [
    ("CA", "California", 0.133),
    ("NY", "New York", 0.109),
    ("TX", "Texas", 0.0),
    ("FL", "Florida", 0.0),
    ("WA", "Washington", 0.0),
    ("IL", "Illinois", 0.0495),
    ("PA", "Pennsylvania", 0.0307),
    ("MA", "Massachusetts", 0.05),
    ("NJ", "New Jersey", 0.1075),
    ("CO", "Colorado", 0.044),
]

COMPLEXITY_FACTORS = {
    "simple": {
        "description": "W-2 only, standard deduction",
        "score": 1,
        "typical_fee": 150,
    },
    "moderate": {
        "description": "Multiple income sources, itemized deductions",
        "score": 2,
        "typical_fee": 350,
    },
    "complex": {
        "description": "Self-employment, investments, rental property",
        "score": 3,
        "typical_fee": 650,
    },
    "highly_complex": {
        "description": "Business ownership, K-1s, multi-state",
        "score": 4,
        "typical_fee": 1200,
    },
    "enterprise": {
        "description": "Multiple businesses, foreign income, trusts",
        "score": 5,
        "typical_fee": 2500,
    },
}


# =============================================================================
# CLIENT PROFILES (Tax Situations)
# =============================================================================

CLIENT_PROFILES = [
    # Profile 1: Simple W-2 Single
    {
        "profile_type": "simple_single",
        "filing_status": "single",
        "complexity": "simple",
        "income_range": (45000, 75000),
        "has_spouse": False,
        "has_dependents": False,
        "has_business": False,
        "has_investments": False,
        "has_rental": False,
        "itemizes": False,
        "multi_state": False,
        "weight": 15,  # 15% of population
    },
    # Profile 2: Simple W-2 Married
    {
        "profile_type": "simple_married",
        "filing_status": "married_filing_jointly",
        "complexity": "simple",
        "income_range": (80000, 150000),
        "has_spouse": True,
        "has_dependents": True,
        "dependent_count": (1, 3),
        "has_business": False,
        "has_investments": False,
        "has_rental": False,
        "itemizes": False,
        "multi_state": False,
        "weight": 20,
    },
    # Profile 3: Moderate - Homeowner with investments
    {
        "profile_type": "homeowner_investor",
        "filing_status": "married_filing_jointly",
        "complexity": "moderate",
        "income_range": (120000, 250000),
        "has_spouse": True,
        "has_dependents": True,
        "dependent_count": (1, 4),
        "has_business": False,
        "has_investments": True,
        "investment_value": (50000, 500000),
        "has_rental": False,
        "itemizes": True,
        "mortgage_interest": (8000, 25000),
        "property_tax": (5000, 20000),
        "charitable": (2000, 15000),
        "multi_state": False,
        "weight": 15,
    },
    # Profile 4: Self-employed freelancer
    {
        "profile_type": "freelancer",
        "filing_status": "single",
        "complexity": "complex",
        "income_range": (80000, 180000),
        "has_spouse": False,
        "has_dependents": False,
        "has_business": True,
        "business_type": "self_employment",
        "business_revenue": (100000, 250000),
        "business_expenses": (20000, 80000),
        "has_investments": True,
        "investment_value": (10000, 100000),
        "has_rental": False,
        "itemizes": True,
        "home_office": True,
        "multi_state": False,
        "weight": 10,
    },
    # Profile 5: High-income professional
    {
        "profile_type": "high_income_professional",
        "filing_status": "married_filing_jointly",
        "complexity": "complex",
        "income_range": (300000, 600000),
        "has_spouse": True,
        "has_dependents": True,
        "dependent_count": (2, 4),
        "has_business": False,
        "has_investments": True,
        "investment_value": (200000, 2000000),
        "has_rental": True,
        "rental_count": (1, 2),
        "rental_income": (20000, 60000),
        "itemizes": True,
        "mortgage_interest": (15000, 40000),
        "property_tax": (15000, 50000),
        "charitable": (10000, 50000),
        "multi_state": False,
        "weight": 8,
    },
    # Profile 6: Small business owner
    {
        "profile_type": "small_business_owner",
        "filing_status": "married_filing_jointly",
        "complexity": "highly_complex",
        "income_range": (150000, 400000),
        "has_spouse": True,
        "has_dependents": True,
        "dependent_count": (1, 3),
        "has_business": True,
        "business_type": "llc_scorp",
        "business_revenue": (300000, 2000000),
        "business_expenses": (150000, 1500000),
        "has_investments": True,
        "investment_value": (100000, 1000000),
        "has_rental": False,
        "itemizes": True,
        "has_k1": True,
        "multi_state": False,
        "weight": 8,
    },
    # Profile 7: Real estate investor
    {
        "profile_type": "real_estate_investor",
        "filing_status": "married_filing_jointly",
        "complexity": "highly_complex",
        "income_range": (200000, 500000),
        "has_spouse": True,
        "has_dependents": True,
        "dependent_count": (0, 2),
        "has_business": False,
        "has_investments": True,
        "investment_value": (300000, 2000000),
        "has_rental": True,
        "rental_count": (3, 8),
        "rental_income": (50000, 200000),
        "itemizes": True,
        "mortgage_interest": (20000, 80000),
        "property_tax": (20000, 80000),
        "multi_state": True,
        "state_count": (2, 4),
        "weight": 5,
    },
    # Profile 8: Tech executive with equity
    {
        "profile_type": "tech_executive",
        "filing_status": "married_filing_jointly",
        "complexity": "highly_complex",
        "income_range": (400000, 1200000),
        "has_spouse": True,
        "has_dependents": True,
        "dependent_count": (1, 3),
        "has_business": False,
        "has_investments": True,
        "investment_value": (500000, 5000000),
        "has_stock_options": True,
        "rsu_value": (100000, 1000000),
        "iso_value": (50000, 500000),
        "has_rental": True,
        "rental_count": (1, 2),
        "itemizes": True,
        "amt_exposure": True,
        "multi_state": True,
        "weight": 4,
    },
    # Profile 9: Retiree
    {
        "profile_type": "retiree",
        "filing_status": "married_filing_jointly",
        "complexity": "moderate",
        "income_range": (60000, 150000),
        "has_spouse": True,
        "has_dependents": False,
        "has_business": False,
        "has_investments": True,
        "investment_value": (500000, 3000000),
        "has_rental": False,
        "itemizes": True,
        "has_social_security": True,
        "ss_income": (30000, 70000),
        "has_pension": True,
        "pension_income": (20000, 80000),
        "has_rmd": True,
        "rmd_amount": (20000, 100000),
        "charitable": (5000, 30000),
        "multi_state": False,
        "weight": 5,
    },
    # Profile 10: Head of household single parent
    {
        "profile_type": "single_parent",
        "filing_status": "head_of_household",
        "complexity": "moderate",
        "income_range": (50000, 120000),
        "has_spouse": False,
        "has_dependents": True,
        "dependent_count": (1, 3),
        "has_business": False,
        "has_investments": False,
        "has_rental": False,
        "itemizes": False,
        "multi_state": False,
        "weight": 5,
    },
    # Profile 11: Gig worker / multiple 1099s
    {
        "profile_type": "gig_worker",
        "filing_status": "single",
        "complexity": "complex",
        "income_range": (40000, 100000),
        "has_spouse": False,
        "has_dependents": False,
        "has_business": True,
        "business_type": "gig_economy",
        "gig_platforms": (2, 5),
        "has_investments": False,
        "has_rental": False,
        "itemizes": False,
        "estimated_tax_payments": True,
        "multi_state": False,
        "weight": 5,
    },
    # Profile 12: Crypto investor
    {
        "profile_type": "crypto_investor",
        "filing_status": "single",
        "complexity": "complex",
        "income_range": (80000, 200000),
        "has_spouse": False,
        "has_dependents": False,
        "has_business": False,
        "has_investments": True,
        "investment_value": (50000, 500000),
        "has_crypto": True,
        "crypto_transactions": (50, 500),
        "crypto_gains": (-50000, 200000),
        "has_rental": False,
        "itemizes": False,
        "multi_state": False,
        "weight": 3,
    },
    # Profile 13: Multi-state worker
    {
        "profile_type": "multi_state_worker",
        "filing_status": "single",
        "complexity": "complex",
        "income_range": (100000, 200000),
        "has_spouse": False,
        "has_dependents": False,
        "has_business": False,
        "has_investments": True,
        "investment_value": (20000, 200000),
        "has_rental": False,
        "itemizes": True,
        "multi_state": True,
        "state_count": (2, 4),
        "weight": 3,
    },
    # Profile 14: Foreign income earner
    {
        "profile_type": "expat_foreign_income",
        "filing_status": "married_filing_jointly",
        "complexity": "enterprise",
        "income_range": (200000, 600000),
        "has_spouse": True,
        "has_dependents": True,
        "dependent_count": (1, 3),
        "has_business": False,
        "has_investments": True,
        "investment_value": (200000, 1000000),
        "has_rental": False,
        "itemizes": True,
        "has_foreign_income": True,
        "foreign_income": (50000, 200000),
        "has_fbar": True,
        "foreign_accounts": (100000, 2000000),
        "multi_state": False,
        "weight": 2,
    },
    # Profile 15: Trust beneficiary
    {
        "profile_type": "trust_beneficiary",
        "filing_status": "single",
        "complexity": "enterprise",
        "income_range": (150000, 500000),
        "has_spouse": False,
        "has_dependents": False,
        "has_business": False,
        "has_investments": True,
        "investment_value": (1000000, 10000000),
        "has_rental": False,
        "itemizes": True,
        "has_trust_income": True,
        "trust_distributions": (50000, 300000),
        "multi_state": False,
        "weight": 2,
    },
]


# =============================================================================
# LEAD SIGNAL JOURNEYS
# =============================================================================

LEAD_JOURNEYS = [
    # Journey 1: Quick converter (business owner)
    {
        "journey_type": "quick_converter",
        "target_state": "HIGH_LEVERAGE",
        "signals": [
            "discovery.viewed_outcome",
            "commitment.business_owner",
        ],
        "days_to_convert": (1, 3),
        "weight": 10,
    },
    # Journey 2: High income fast track
    {
        "journey_type": "high_income_fast",
        "target_state": "HIGH_LEVERAGE",
        "signals": [
            "discovery.viewed_outcome",
            "discovery.viewed_complexity",
            "commitment.high_income",
        ],
        "days_to_convert": (1, 5),
        "weight": 8,
    },
    # Journey 3: Complex situation urgent
    {
        "journey_type": "complex_urgent",
        "target_state": "HIGH_LEVERAGE",
        "signals": [
            "discovery.viewed_outcome",
            "evaluation.explored_what_if",
            "commitment.complex_situation",
            "commitment.urgency_indicated",
        ],
        "days_to_convert": (1, 2),
        "weight": 5,
    },
    # Journey 4: Thorough evaluator
    {
        "journey_type": "thorough_evaluator",
        "target_state": "ADVISORY_READY",
        "signals": [
            "discovery.viewed_outcome",
            "discovery.expanded_drivers",
            "discovery.time_on_summary",
            "evaluation.compared_scenarios",
            "evaluation.viewed_opportunities",
            "evaluation.downloaded_summary",
            "commitment.requested_cpa_review",
        ],
        "days_to_convert": (5, 14),
        "weight": 12,
    },
    # Journey 5: Contact provider
    {
        "journey_type": "contact_provider",
        "target_state": "ADVISORY_READY",
        "signals": [
            "discovery.viewed_outcome",
            "discovery.expanded_drivers",
            "evaluation.compared_scenarios",
            "commitment.provided_contact",
        ],
        "days_to_convert": (3, 7),
        "weight": 10,
    },
    # Journey 6: Feature lock hit
    {
        "journey_type": "feature_lock",
        "target_state": "ADVISORY_READY",
        "signals": [
            "discovery.viewed_outcome",
            "evaluation.viewed_opportunities",
            "commitment.hit_feature_lock",
        ],
        "days_to_convert": (2, 5),
        "weight": 8,
    },
    # Journey 7: Active evaluator (not ready yet)
    {
        "journey_type": "active_evaluator",
        "target_state": "EVALUATING",
        "signals": [
            "discovery.viewed_outcome",
            "discovery.expanded_drivers",
            "discovery.viewed_complexity",
            "evaluation.compared_scenarios",
            "evaluation.viewed_opportunities",
        ],
        "days_to_convert": (7, 21),
        "weight": 15,
    },
    # Journey 8: Returning visitor
    {
        "journey_type": "returning_visitor",
        "target_state": "EVALUATING",
        "signals": [
            "discovery.viewed_outcome",
            "discovery.returned_session",
            "discovery.time_on_summary",
            "evaluation.multiple_sessions",
            "evaluation.updated_data",
        ],
        "days_to_convert": (10, 30),
        "weight": 10,
    },
    # Journey 9: Curious browser
    {
        "journey_type": "curious_browser",
        "target_state": "CURIOUS",
        "signals": [
            "discovery.viewed_outcome",
            "discovery.expanded_drivers",
            "discovery.time_on_summary",
        ],
        "days_to_convert": (3, 14),
        "weight": 12,
    },
    # Journey 10: Just browsing
    {
        "journey_type": "just_browsing",
        "target_state": "BROWSING",
        "signals": [],
        "days_to_convert": (1, 7),
        "weight": 10,
    },
    # Journey 11: Real estate investor journey
    {
        "journey_type": "real_estate_investor",
        "target_state": "HIGH_LEVERAGE",
        "signals": [
            "discovery.viewed_outcome",
            "discovery.viewed_complexity",
            "financial.real_estate_holdings",
            "commitment.multiple_opportunities",
        ],
        "days_to_convert": (2, 7),
        "weight": 5,
    },
    # Journey 12: Self-employment journey
    {
        "journey_type": "self_employed",
        "target_state": "HIGH_LEVERAGE",
        "signals": [
            "discovery.viewed_outcome",
            "discovery.expanded_drivers",
            "financial.self_employment",
            "commitment.business_owner",
        ],
        "days_to_convert": (2, 5),
        "weight": 5,
    },
    # Journey 13: Crypto investor
    {
        "journey_type": "crypto_investor",
        "target_state": "HIGH_LEVERAGE",
        "signals": [
            "discovery.viewed_outcome",
            "financial.crypto_activity",
            "commitment.complex_situation",
        ],
        "days_to_convert": (1, 4),
        "weight": 3,
    },
    # Journey 14: Multi-state filer
    {
        "journey_type": "multi_state",
        "target_state": "HIGH_LEVERAGE",
        "signals": [
            "discovery.viewed_outcome",
            "financial.multi_state",
            "evaluation.compared_scenarios",
            "commitment.complex_situation",
        ],
        "days_to_convert": (3, 10),
        "weight": 4,
    },
    # Journey 15: Equity compensation
    {
        "journey_type": "equity_comp",
        "target_state": "HIGH_LEVERAGE",
        "signals": [
            "discovery.viewed_outcome",
            "financial.equity_compensation",
            "financial.amt_exposure",
            "commitment.high_income",
        ],
        "days_to_convert": (2, 7),
        "weight": 3,
    },
]


# =============================================================================
# RECOMMENDATION TEMPLATES
# =============================================================================

RECOMMENDATION_TEMPLATES = [
    {
        "category": "retirement",
        "title": "Maximize 401(k) Contributions",
        "description": "You're not contributing the maximum to your 401(k). Increasing contributions reduces taxable income.",
        "savings_range": (1000, 8000),
        "applicable_to": ["simple_married", "homeowner_investor", "high_income_professional", "tech_executive"],
    },
    {
        "category": "retirement",
        "title": "Consider Backdoor Roth IRA",
        "description": "Your income exceeds Roth IRA limits. A backdoor Roth conversion could provide tax-free growth.",
        "savings_range": (500, 3000),
        "applicable_to": ["high_income_professional", "tech_executive", "small_business_owner"],
    },
    {
        "category": "retirement",
        "title": "SEP-IRA for Self-Employment Income",
        "description": "As a self-employed individual, you can contribute up to 25% of net self-employment income to a SEP-IRA.",
        "savings_range": (3000, 20000),
        "applicable_to": ["freelancer", "small_business_owner", "gig_worker"],
    },
    {
        "category": "deduction",
        "title": "Home Office Deduction",
        "description": "You may qualify for the home office deduction based on your self-employment activities.",
        "savings_range": (500, 3000),
        "applicable_to": ["freelancer", "small_business_owner", "gig_worker"],
    },
    {
        "category": "deduction",
        "title": "Qualified Business Income (QBI) Deduction",
        "description": "Your pass-through business income may qualify for the 20% QBI deduction.",
        "savings_range": (2000, 25000),
        "applicable_to": ["freelancer", "small_business_owner", "real_estate_investor"],
    },
    {
        "category": "deduction",
        "title": "Charitable Contribution Bunching",
        "description": "Consider bunching 2 years of charitable contributions into one year to exceed the standard deduction.",
        "savings_range": (1000, 5000),
        "applicable_to": ["homeowner_investor", "high_income_professional", "retiree", "tech_executive"],
    },
    {
        "category": "credit",
        "title": "Child Tax Credit Optimization",
        "description": "Ensure you're claiming the full Child Tax Credit for qualifying dependents.",
        "savings_range": (2000, 6000),
        "applicable_to": ["simple_married", "homeowner_investor", "single_parent", "high_income_professional"],
    },
    {
        "category": "credit",
        "title": "Dependent Care FSA",
        "description": "You could save on childcare by using a Dependent Care FSA (up to $5,000).",
        "savings_range": (1000, 2500),
        "applicable_to": ["simple_married", "homeowner_investor", "single_parent"],
    },
    {
        "category": "credit",
        "title": "Education Credits",
        "description": "If paying for higher education, the American Opportunity or Lifetime Learning Credit may apply.",
        "savings_range": (1000, 2500),
        "applicable_to": ["simple_married", "homeowner_investor", "single_parent"],
    },
    {
        "category": "investment",
        "title": "Tax-Loss Harvesting",
        "description": "Selling investments at a loss can offset capital gains and reduce tax liability.",
        "savings_range": (500, 10000),
        "applicable_to": ["homeowner_investor", "high_income_professional", "tech_executive", "crypto_investor"],
    },
    {
        "category": "investment",
        "title": "Long-Term Capital Gains Planning",
        "description": "Holding investments over 1 year qualifies for preferential long-term capital gains rates.",
        "savings_range": (1000, 20000),
        "applicable_to": ["homeowner_investor", "high_income_professional", "tech_executive", "retiree"],
    },
    {
        "category": "investment",
        "title": "Qualified Opportunity Zone Investment",
        "description": "Defer and potentially reduce capital gains by investing in Qualified Opportunity Zones.",
        "savings_range": (5000, 50000),
        "applicable_to": ["high_income_professional", "tech_executive", "real_estate_investor"],
    },
    {
        "category": "real_estate",
        "title": "Rental Property Depreciation",
        "description": "Ensure you're taking full depreciation deductions on rental properties.",
        "savings_range": (2000, 15000),
        "applicable_to": ["real_estate_investor", "high_income_professional"],
    },
    {
        "category": "real_estate",
        "title": "1031 Exchange Planning",
        "description": "Consider a 1031 exchange to defer capital gains when selling investment property.",
        "savings_range": (10000, 100000),
        "applicable_to": ["real_estate_investor"],
    },
    {
        "category": "real_estate",
        "title": "Real Estate Professional Status",
        "description": "Qualifying as a real estate professional allows rental losses to offset ordinary income.",
        "savings_range": (5000, 50000),
        "applicable_to": ["real_estate_investor"],
    },
    {
        "category": "business",
        "title": "S-Corp Election Evaluation",
        "description": "An S-Corp election could reduce self-employment taxes through reasonable salary/distribution split.",
        "savings_range": (3000, 15000),
        "applicable_to": ["freelancer", "small_business_owner"],
    },
    {
        "category": "business",
        "title": "Business Vehicle Deduction",
        "description": "Track business miles for deduction. Consider Section 179 for a new vehicle purchase.",
        "savings_range": (1000, 10000),
        "applicable_to": ["freelancer", "small_business_owner", "real_estate_investor"],
    },
    {
        "category": "business",
        "title": "Hire Family Members",
        "description": "Employing family members can shift income to lower tax brackets while providing legitimate wages.",
        "savings_range": (1000, 8000),
        "applicable_to": ["small_business_owner"],
    },
    {
        "category": "healthcare",
        "title": "HSA Contribution Maximization",
        "description": "With a high-deductible health plan, max out your HSA for triple tax benefits.",
        "savings_range": (500, 2500),
        "applicable_to": ["simple_single", "simple_married", "freelancer", "homeowner_investor"],
    },
    {
        "category": "healthcare",
        "title": "Self-Employed Health Insurance Deduction",
        "description": "Deduct 100% of health insurance premiums as a self-employed individual.",
        "savings_range": (1000, 5000),
        "applicable_to": ["freelancer", "small_business_owner", "gig_worker"],
    },
    {
        "category": "filing",
        "title": "Filing Status Optimization",
        "description": "Review whether Married Filing Separately might provide tax benefits in your situation.",
        "savings_range": (500, 5000),
        "applicable_to": ["homeowner_investor", "high_income_professional"],
    },
    {
        "category": "estimated_tax",
        "title": "Estimated Tax Payment Review",
        "description": "Adjust quarterly estimated payments to avoid underpayment penalties.",
        "savings_range": (200, 2000),
        "applicable_to": ["freelancer", "gig_worker", "retiree"],
    },
    {
        "category": "state",
        "title": "State Tax Residency Planning",
        "description": "Consider state tax implications if you split time between multiple states.",
        "savings_range": (2000, 20000),
        "applicable_to": ["multi_state_worker", "tech_executive", "retiree"],
    },
    {
        "category": "international",
        "title": "Foreign Tax Credit",
        "description": "Claim foreign tax credits for taxes paid to other countries to avoid double taxation.",
        "savings_range": (1000, 20000),
        "applicable_to": ["expat_foreign_income"],
    },
    {
        "category": "international",
        "title": "Foreign Earned Income Exclusion",
        "description": "If you qualify, exclude up to $126,500 of foreign earned income from US taxes.",
        "savings_range": (10000, 40000),
        "applicable_to": ["expat_foreign_income"],
    },
    {
        "category": "equity",
        "title": "ISO Exercise Strategy",
        "description": "Time your ISO exercises strategically to minimize AMT impact.",
        "savings_range": (5000, 50000),
        "applicable_to": ["tech_executive"],
    },
    {
        "category": "equity",
        "title": "RSU Tax Planning",
        "description": "Plan RSU vesting around other income to optimize tax brackets.",
        "savings_range": (2000, 20000),
        "applicable_to": ["tech_executive"],
    },
    {
        "category": "crypto",
        "title": "Cryptocurrency Tax Optimization",
        "description": "Use FIFO vs specific identification to minimize gains on crypto sales.",
        "savings_range": (1000, 15000),
        "applicable_to": ["crypto_investor"],
    },
]


# =============================================================================
# DATA GENERATOR CLASS
# =============================================================================

class TestDataGenerator:
    """Generates comprehensive test data for the CPA panel."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.clients = []
        self.tax_returns = []
        self.leads = []
        self.recommendations = []
        self.engagement_letters = []
        self.documents = []

    def generate_name(self) -> tuple:
        """Generate a random full name."""
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        return first, last

    def generate_email(self, first: str, last: str) -> str:
        """Generate a realistic email."""
        domains = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "hotmail.com"]
        patterns = [
            f"{first.lower()}.{last.lower()}",
            f"{first.lower()}{last.lower()}",
            f"{first[0].lower()}{last.lower()}",
            f"{first.lower()}{random.randint(1, 99)}",
        ]
        return f"{random.choice(patterns)}@{random.choice(domains)}"

    def generate_phone(self) -> str:
        """Generate a random phone number."""
        return f"({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}"

    def generate_address(self, state_code: str) -> dict:
        """Generate a realistic address."""
        street_nums = random.randint(100, 9999)
        street_names = ["Oak", "Maple", "Main", "Cedar", "Park", "Lake", "Hill", "Valley", "River", "Forest"]
        street_types = ["St", "Ave", "Blvd", "Dr", "Ln", "Way", "Ct", "Pl"]
        cities = {
            "CA": ["Los Angeles", "San Francisco", "San Diego", "San Jose", "Sacramento"],
            "NY": ["New York", "Buffalo", "Rochester", "Albany", "Syracuse"],
            "TX": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth"],
            "FL": ["Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale"],
            "WA": ["Seattle", "Tacoma", "Spokane", "Bellevue", "Redmond"],
            "IL": ["Chicago", "Aurora", "Naperville", "Rockford", "Joliet"],
            "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading"],
            "MA": ["Boston", "Worcester", "Springfield", "Cambridge", "Lowell"],
            "NJ": ["Newark", "Jersey City", "Paterson", "Elizabeth", "Edison"],
            "CO": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Boulder"],
        }
        return {
            "street": f"{street_nums} {random.choice(street_names)} {random.choice(street_types)}",
            "city": random.choice(cities.get(state_code, ["Unknown"])),
            "state": state_code,
            "zip": f"{random.randint(10000, 99999)}",
        }

    def select_profile(self) -> dict:
        """Select a client profile based on weights."""
        total_weight = sum(p["weight"] for p in CLIENT_PROFILES)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for profile in CLIENT_PROFILES:
            cumulative += profile["weight"]
            if r <= cumulative:
                return profile
        return CLIENT_PROFILES[-1]

    def select_journey(self) -> dict:
        """Select a lead journey based on weights."""
        total_weight = sum(j["weight"] for j in LEAD_JOURNEYS)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for journey in LEAD_JOURNEYS:
            cumulative += journey["weight"]
            if r <= cumulative:
                return journey
        return LEAD_JOURNEYS[-1]

    def generate_client(self, client_id: str) -> dict:
        """Generate a single client with full profile."""
        profile = self.select_profile()
        first, last = self.generate_name()
        state = random.choice(STATES)

        # Generate spouse if applicable
        spouse = None
        if profile.get("has_spouse"):
            spouse_first, _ = self.generate_name()
            spouse = {
                "first_name": spouse_first,
                "last_name": last,
                "occupation": random.choice(OCCUPATIONS),
            }

        # Generate dependents if applicable
        dependents = []
        if profile.get("has_dependents"):
            dep_range = profile.get("dependent_count", (1, 2))
            num_deps = random.randint(*dep_range)
            for i in range(num_deps):
                dep_first, _ = self.generate_name()
                dep_age = random.randint(1, 22)
                dependents.append({
                    "first_name": dep_first,
                    "last_name": last,
                    "age": dep_age,
                    "relationship": "child" if dep_age < 19 else "dependent",
                    "qualifies_for_ctc": dep_age < 17,
                })

        # Generate income
        base_income = random.randint(*profile["income_range"])

        client = {
            "client_id": client_id,
            "session_id": f"session-{client_id}",
            "first_name": first,
            "last_name": last,
            "email": self.generate_email(first, last),
            "phone": self.generate_phone(),
            "address": self.generate_address(state[0]),
            "filing_status": profile["filing_status"],
            "profile_type": profile["profile_type"],
            "complexity": profile["complexity"],
            "state_code": state[0],
            "state_name": state[1],
            "state_tax_rate": state[2],
            "spouse": spouse,
            "dependents": dependents,
            "base_income": base_income,
            "profile": profile,
            "created_at": datetime.now() - timedelta(days=random.randint(1, 90)),
        }

        return client

    def generate_tax_return(self, client: dict) -> dict:
        """Generate a complete tax return for a client."""
        profile = client["profile"]

        # W-2 Income
        w2_income = client["base_income"]
        if client.get("spouse") and profile.get("has_spouse"):
            spouse_occ = client["spouse"]["occupation"]
            spouse_income = random.randint(int(spouse_occ[1] * 0.7), spouse_occ[2])
            w2_income += spouse_income

        # Self-employment income
        se_income = 0
        se_expenses = 0
        if profile.get("has_business"):
            if "business_revenue" in profile:
                se_revenue = random.randint(*profile["business_revenue"])
                se_expenses = random.randint(*profile["business_expenses"])
                se_income = se_revenue - se_expenses

        # Investment income
        dividend_income = 0
        capital_gains = 0
        qualified_dividends = 0
        if profile.get("has_investments"):
            inv_value = random.randint(*profile["investment_value"])
            dividend_income = int(inv_value * random.uniform(0.01, 0.03))
            qualified_dividends = int(dividend_income * 0.8)
            capital_gains = int(inv_value * random.uniform(-0.05, 0.15))

        # Rental income
        rental_income = 0
        rental_expenses = 0
        rental_depreciation = 0
        if profile.get("has_rental"):
            rental_income = random.randint(*profile.get("rental_income", (10000, 30000)))
            rental_expenses = int(rental_income * random.uniform(0.3, 0.5))
            rental_count = random.randint(*profile.get("rental_count", (1, 2)))
            rental_depreciation = rental_count * random.randint(5000, 15000)

        # Social Security and retirement
        ss_income = 0
        pension_income = 0
        rmd_income = 0
        if profile.get("has_social_security"):
            ss_income = random.randint(*profile["ss_income"])
        if profile.get("has_pension"):
            pension_income = random.randint(*profile["pension_income"])
        if profile.get("has_rmd"):
            rmd_income = random.randint(*profile["rmd_amount"])

        # Stock options
        rsu_income = 0
        iso_income = 0
        if profile.get("has_stock_options"):
            if profile.get("rsu_value"):
                rsu_income = random.randint(*profile["rsu_value"])
            if profile.get("iso_value"):
                iso_income = random.randint(*profile["iso_value"])

        # Foreign income
        foreign_income = 0
        if profile.get("has_foreign_income"):
            foreign_income = random.randint(*profile["foreign_income"])

        # Trust income
        trust_income = 0
        if profile.get("has_trust_income"):
            trust_income = random.randint(*profile["trust_distributions"])

        # Crypto gains
        crypto_gains = 0
        if profile.get("has_crypto"):
            crypto_gains = random.randint(*profile["crypto_gains"])

        # Total gross income
        gross_income = (
            w2_income + se_income + dividend_income + capital_gains +
            (rental_income - rental_expenses - rental_depreciation) +
            ss_income + pension_income + rmd_income +
            rsu_income + foreign_income + trust_income + crypto_gains
        )

        # Adjustments to income
        adjustments = {}
        retirement_contribution = 0
        if w2_income > 50000:
            retirement_contribution = min(23000, int(w2_income * random.uniform(0.05, 0.15)))
            adjustments["401k_contribution"] = retirement_contribution

        if se_income > 50000:
            sep_contribution = min(int(se_income * 0.25), 66000)
            adjustments["sep_ira"] = sep_contribution

        hsa_contribution = 0
        if random.random() < 0.3:
            hsa_contribution = random.randint(2000, 8300)
            adjustments["hsa_contribution"] = hsa_contribution

        se_tax_deduction = 0
        if se_income > 0:
            se_tax = se_income * 0.153 * 0.9235
            se_tax_deduction = se_tax / 2
            adjustments["se_tax_deduction"] = int(se_tax_deduction)

        total_adjustments = sum(adjustments.values())
        agi = gross_income - total_adjustments

        # Deductions
        standard_deduction = {
            "single": 14600,
            "married_filing_jointly": 29200,
            "married_filing_separately": 14600,
            "head_of_household": 21900,
            "qualifying_surviving_spouse": 29200,
        }[client["filing_status"]]

        itemized_deductions = {}
        if profile.get("itemizes"):
            if profile.get("mortgage_interest"):
                itemized_deductions["mortgage_interest"] = random.randint(*profile["mortgage_interest"])
            if profile.get("property_tax"):
                itemized_deductions["property_tax"] = min(10000, random.randint(*profile["property_tax"]))
            if profile.get("charitable"):
                itemized_deductions["charitable"] = random.randint(*profile["charitable"])
            itemized_deductions["state_local_taxes"] = min(10000, int(agi * client["state_tax_rate"]))

        total_itemized = sum(itemized_deductions.values())
        uses_standard = total_itemized <= standard_deduction
        deduction_amount = standard_deduction if uses_standard else total_itemized

        # QBI deduction
        qbi_deduction = 0
        if se_income > 0 and agi < 383900:  # 2024 threshold for MFJ
            qbi_deduction = int(se_income * 0.2)

        # Taxable income
        taxable_income = max(0, agi - deduction_amount - qbi_deduction)

        # Calculate federal tax (simplified)
        def calculate_tax(income: float, status: str) -> float:
            brackets = {
                "single": [(11600, 0.10), (47150, 0.12), (100525, 0.22), (191950, 0.24), (243725, 0.32), (609350, 0.35), (float('inf'), 0.37)],
                "married_filing_jointly": [(23200, 0.10), (94300, 0.12), (201050, 0.22), (383900, 0.24), (487450, 0.32), (731200, 0.35), (float('inf'), 0.37)],
                "married_filing_separately": [(11600, 0.10), (47150, 0.12), (100525, 0.22), (191950, 0.24), (243725, 0.32), (365600, 0.35), (float('inf'), 0.37)],
                "head_of_household": [(16550, 0.10), (63100, 0.12), (100500, 0.22), (191950, 0.24), (243700, 0.32), (609350, 0.35), (float('inf'), 0.37)],
                "qualifying_surviving_spouse": [(23200, 0.10), (94300, 0.12), (201050, 0.22), (383900, 0.24), (487450, 0.32), (731200, 0.35), (float('inf'), 0.37)],
            }
            tax = 0
            prev_bracket = 0
            for bracket, rate in brackets.get(status, brackets["single"]):
                if income <= bracket:
                    tax += (income - prev_bracket) * rate
                    break
                tax += (bracket - prev_bracket) * rate
                prev_bracket = bracket
            return tax

        federal_tax = calculate_tax(taxable_income, client["filing_status"])

        # Credits
        credits = {}
        num_children = len([d for d in client.get("dependents", []) if d.get("qualifies_for_ctc", False)])
        if num_children > 0 and agi < 400000:
            credits["child_tax_credit"] = num_children * 2000

        # Self-employment tax
        se_tax = 0
        if se_income > 0:
            se_tax = se_income * 0.153 * 0.9235

        # State tax
        state_tax = agi * client["state_tax_rate"]

        # Total tax
        total_credits = sum(credits.values())
        total_tax = federal_tax + se_tax + state_tax - total_credits

        # Withholding
        federal_withheld = w2_income * random.uniform(0.15, 0.25)
        state_withheld = w2_income * client["state_tax_rate"] * random.uniform(0.8, 1.1)

        # Estimated payments
        estimated_payments = 0
        if se_income > 20000 or profile.get("estimated_tax_payments"):
            estimated_payments = int(total_tax * random.uniform(0.6, 0.9))

        # Refund or owed
        total_payments = federal_withheld + state_withheld + estimated_payments
        balance = total_tax - total_payments

        return {
            "client_id": client["client_id"],
            "session_id": client["session_id"],
            "tax_year": 2024,
            "filing_status": client["filing_status"],

            # Income
            "w2_income": int(w2_income),
            "self_employment_income": int(se_income),
            "self_employment_expenses": int(se_expenses),
            "dividend_income": int(dividend_income),
            "qualified_dividends": int(qualified_dividends),
            "capital_gains": int(capital_gains),
            "rental_income": int(rental_income),
            "rental_expenses": int(rental_expenses),
            "rental_depreciation": int(rental_depreciation),
            "social_security_income": int(ss_income),
            "pension_income": int(pension_income),
            "rmd_income": int(rmd_income),
            "rsu_income": int(rsu_income),
            "iso_income": int(iso_income),
            "foreign_income": int(foreign_income),
            "trust_income": int(trust_income),
            "crypto_gains": int(crypto_gains),
            "gross_income": int(gross_income),

            # Adjustments
            "adjustments": adjustments,
            "total_adjustments": int(total_adjustments),
            "agi": int(agi),

            # Deductions
            "standard_deduction": int(standard_deduction),
            "itemized_deductions": itemized_deductions,
            "total_itemized": int(total_itemized),
            "uses_standard_deduction": uses_standard,
            "deduction_amount": int(deduction_amount),
            "qbi_deduction": int(qbi_deduction),

            # Tax calculation
            "taxable_income": int(taxable_income),
            "federal_tax": int(federal_tax),
            "self_employment_tax": int(se_tax),
            "state_tax": int(state_tax),
            "credits": credits,
            "total_credits": int(total_credits),
            "total_tax": int(total_tax),

            # Payments
            "federal_withheld": int(federal_withheld),
            "state_withheld": int(state_withheld),
            "estimated_payments": int(estimated_payments),
            "total_payments": int(total_payments),

            # Result
            "balance_due": int(balance) if balance > 0 else 0,
            "refund_amount": int(-balance) if balance < 0 else 0,

            # Complexity
            "complexity_score": COMPLEXITY_FACTORS[client["complexity"]]["score"],
            "complexity_tier": client["complexity"],
            "estimated_fee": COMPLEXITY_FACTORS[client["complexity"]]["typical_fee"],

            # Flags
            "has_amt_exposure": profile.get("amt_exposure", False),
            "has_foreign_reporting": profile.get("has_fbar", False),
            "is_multi_state": profile.get("multi_state", False),
            "has_crypto": profile.get("has_crypto", False),
            "has_rental_properties": profile.get("has_rental", False),
            "has_business": profile.get("has_business", False),
        }

    def generate_recommendations(self, client: dict, tax_return: dict) -> List[dict]:
        """Generate applicable recommendations for a client."""
        recs = []
        profile_type = client["profile_type"]

        for template in RECOMMENDATION_TEMPLATES:
            if profile_type in template["applicable_to"]:
                if random.random() < 0.7:  # 70% chance to include applicable rec
                    savings = random.randint(*template["savings_range"])
                    recs.append({
                        "rec_id": str(uuid.uuid4())[:8],
                        "client_id": client["client_id"],
                        "session_id": client["session_id"],
                        "category": template["category"],
                        "title": template["title"],
                        "description": template["description"],
                        "estimated_savings": savings,
                        "confidence": random.uniform(0.7, 0.95),
                        "priority": random.choice(["high", "medium", "low"]),
                        "status": random.choice(["pending", "reviewed", "implemented"]),
                        "created_at": datetime.now().isoformat(),
                    })

        return recs

    def generate_lead(self, lead_num: int, client: Optional[dict] = None) -> dict:
        """Generate a lead with a complete signal journey."""
        journey = self.select_journey()

        lead_id = f"lead-{lead_num:04d}"
        session_id = client["session_id"] if client else f"session-lead-{lead_num:04d}"

        # Calculate timestamps
        days_ago = random.randint(*journey["days_to_convert"])
        created_at = datetime.now() - timedelta(days=days_ago)

        return {
            "lead_id": lead_id,
            "session_id": session_id,
            "client_id": client["client_id"] if client else None,
            "client_name": f"{client['first_name']} {client['last_name']}" if client else f"Prospect {lead_num}",
            "journey_type": journey["journey_type"],
            "target_state": journey["target_state"],
            "signals": journey["signals"],
            "created_at": created_at.isoformat(),
            "tenant_id": "default",
        }

    def generate_engagement_letter(self, client: dict, tax_return: dict) -> dict:
        """Generate an engagement letter for a client."""
        complexity = client["complexity"]
        base_fee = COMPLEXITY_FACTORS[complexity]["typical_fee"]

        # Adjust fee based on specific factors
        fee_adjustments = []
        if tax_return.get("is_multi_state"):
            adjustment = base_fee * 0.25
            fee_adjustments.append(("Multi-state filing", adjustment))
        if tax_return.get("has_rental_properties"):
            adjustment = tax_return.get("rental_count", 1) * 150
            fee_adjustments.append(("Rental properties", adjustment))
        if tax_return.get("has_business"):
            adjustment = base_fee * 0.3
            fee_adjustments.append(("Business schedule", adjustment))
        if tax_return.get("has_foreign_reporting"):
            adjustment = 500
            fee_adjustments.append(("Foreign reporting (FBAR)", adjustment))

        total_adjustments = sum(a[1] for a in fee_adjustments)
        total_fee = base_fee + total_adjustments

        return {
            "engagement_id": str(uuid.uuid4())[:8],
            "client_id": client["client_id"],
            "client_name": f"{client['first_name']} {client['last_name']}",
            "client_email": client["email"],
            "service_type": "Tax Preparation & Advisory",
            "tax_year": 2024,
            "complexity_tier": complexity,
            "base_fee": base_fee,
            "fee_adjustments": fee_adjustments,
            "total_fee": int(total_fee),
            "payment_terms": "50% due upon signing, 50% upon filing",
            "scope": [
                "Federal tax return preparation",
                "State tax return preparation" if client["state_tax_rate"] > 0 else None,
                "Tax planning consultation",
                "E-file submission",
                "Audit support for 3 years",
            ],
            "status": random.choice(["draft", "sent", "signed", "paid"]),
            "created_at": datetime.now().isoformat(),
            "valid_until": (datetime.now() + timedelta(days=30)).isoformat(),
        }

    def generate_all(self, num_clients: int = 100) -> dict:
        """Generate all test data."""
        print(f"Generating {num_clients} clients with full profiles...")

        # Generate clients
        for i in range(1, num_clients + 1):
            client_id = f"client-{i:04d}"
            client = self.generate_client(client_id)
            self.clients.append(client)

            # Generate tax return
            tax_return = self.generate_tax_return(client)
            self.tax_returns.append(tax_return)

            # Generate recommendations
            recs = self.generate_recommendations(client, tax_return)
            self.recommendations.extend(recs)

            # Generate lead (80% of clients have an associated lead)
            if random.random() < 0.8:
                lead = self.generate_lead(len(self.leads) + 1, client)
                self.leads.append(lead)

            # Generate engagement letter (60% of clients)
            if random.random() < 0.6:
                engagement = self.generate_engagement_letter(client, tax_return)
                self.engagement_letters.append(engagement)

            if i % 20 == 0:
                print(f"  Generated {i} clients...")

        # Generate additional leads without clients (prospects)
        additional_leads = 20
        print(f"Generating {additional_leads} additional prospect leads...")
        for i in range(additional_leads):
            lead = self.generate_lead(len(self.leads) + 1)
            self.leads.append(lead)

        # Summary
        summary = {
            "clients": len(self.clients),
            "tax_returns": len(self.tax_returns),
            "leads": len(self.leads),
            "recommendations": len(self.recommendations),
            "engagement_letters": len(self.engagement_letters),
            "total_records": (
                len(self.clients) + len(self.tax_returns) +
                len(self.leads) + len(self.recommendations) +
                len(self.engagement_letters)
            ),
        }

        return {
            "clients": self.clients,
            "tax_returns": self.tax_returns,
            "leads": self.leads,
            "recommendations": self.recommendations,
            "engagement_letters": self.engagement_letters,
            "summary": summary,
        }


# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CPA PANEL TEST DATA GENERATOR")
    print("=" * 60)
    print()

    generator = TestDataGenerator(seed=42)
    data = generator.generate_all(num_clients=100)

    # Save to JSON file
    output_file = os.path.join(os.path.dirname(__file__), "test_data.json")
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2, default=str)

    print()
    print("=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    print()
    print(f"Clients:            {data['summary']['clients']}")
    print(f"Tax Returns:        {data['summary']['tax_returns']}")
    print(f"Leads:              {data['summary']['leads']}")
    print(f"Recommendations:    {data['summary']['recommendations']}")
    print(f"Engagement Letters: {data['summary']['engagement_letters']}")
    print(f"Total Records:      {data['summary']['total_records']}")
    print()
    print(f"Data saved to: {output_file}")
    print()

    # Profile distribution
    print("CLIENT PROFILE DISTRIBUTION:")
    profile_counts = {}
    for client in data["clients"]:
        pt = client["profile_type"]
        profile_counts[pt] = profile_counts.get(pt, 0) + 1
    for pt, count in sorted(profile_counts.items(), key=lambda x: -x[1]):
        print(f"  {pt}: {count}")

    print()
    print("LEAD STATE DISTRIBUTION:")
    state_counts = {}
    for lead in data["leads"]:
        state = lead["target_state"]
        state_counts[state] = state_counts.get(state, 0) + 1
    for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")

    print()
    print("COMPLEXITY DISTRIBUTION:")
    complexity_counts = {}
    for client in data["clients"]:
        c = client["complexity"]
        complexity_counts[c] = complexity_counts.get(c, 0) + 1
    for c, count in sorted(complexity_counts.items(), key=lambda x: -x[1]):
        print(f"  {c}: {count}")
