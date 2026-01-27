"""
Comprehensive Tests for Universal Report System

Tests cover:
1. Data accuracy and calculations
2. Visualization rendering
3. Branding application
4. Export functionality
5. Edge cases and error handling
"""

import pytest
from decimal import Decimal
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestDataCollector:
    """Tests for data normalization layer."""

    def test_chatbot_session_basic(self):
        """Test basic chatbot session data collection."""
        from universal_report.data_collector import ReportDataCollector

        collector = ReportDataCollector()

        session_data = {
            'profile': {
                'first_name': 'John',
                'last_name': 'Doe',
                'filing_status': 'single',
                'total_income': 100000,
                'w2_income': 80000,
                'investment_income': 20000,
                'retirement_401k': 15000,
            },
            'calculations': {
                'gross_income': 100000,
                'agi': 85000,
                'taxable_income': 70000,
                'federal_tax': 10500,
                'state_tax': 5000,
                'effective_rate': 15.5,
                'marginal_rate': 22,
                'deduction_type': 'standard',
            },
            'strategies': [
                {
                    'id': 'strat_1',
                    'category': 'retirement',
                    'title': 'Max 401k',
                    'summary': 'Increase contributions',
                    'estimated_savings': 2000,
                    'confidence': 'high',
                    'priority': 'current_year',
                }
            ]
        }

        data = collector.from_chatbot_session('test_123', session_data)

        # Verify taxpayer info
        assert data.taxpayer_name == 'John Doe'
        assert data.filing_status == 'single'
        assert data.tax_year == 2025

        # Verify financial data
        assert data.gross_income == Decimal('100000')
        assert data.adjusted_gross_income == Decimal('85000')
        assert data.tax_liability == Decimal('10500')
        assert data.effective_rate == 15.5

        # Verify income items created
        assert len(data.income_items) >= 2  # W-2 and investment

        # Verify recommendations
        assert len(data.recommendations) == 1
        assert data.recommendations[0].title == 'Max 401k'
        assert data.recommendations[0].estimated_savings == Decimal('2000')

    def test_empty_profile_handling(self):
        """Test handling of empty/minimal profile data."""
        from universal_report.data_collector import ReportDataCollector

        collector = ReportDataCollector()

        session_data = {
            'profile': {'filing_status': 'single'},
            'calculations': None,
            'strategies': []
        }

        data = collector.from_chatbot_session('test_empty', session_data)

        # Should not raise, should have defaults
        assert data.taxpayer_name == 'Tax Client'
        assert data.filing_status == 'single'
        assert data.gross_income == Decimal('0')
        assert len(data.recommendations) == 0

    def test_decimal_precision(self):
        """Test that decimal precision is maintained."""
        from universal_report.data_collector import ReportDataCollector

        collector = ReportDataCollector()

        session_data = {
            'profile': {
                'filing_status': 'single',
                'total_income': 123456.78,
            },
            'calculations': {
                'federal_tax': 24691.35,
            },
            'strategies': []
        }

        data = collector.from_chatbot_session('test_precision', session_data)

        # Check decimal handling
        assert data.gross_income == Decimal('123456.78')
        assert data.tax_liability == Decimal('24691.35')

    def test_all_filing_statuses(self):
        """Test all filing statuses are handled."""
        from universal_report.data_collector import ReportDataCollector

        collector = ReportDataCollector()

        statuses = [
            'single', 'married_joint', 'married_separate',
            'head_of_household', 'qualifying_widow'
        ]

        for status in statuses:
            session_data = {
                'profile': {'filing_status': status, 'total_income': 100000},
                'calculations': {},
                'strategies': []
            }

            data = collector.from_chatbot_session(f'test_{status}', session_data)
            assert data.filing_status == status


class TestVisualizations:
    """Tests for visualization components."""

    def test_savings_gauge_basic(self):
        """Test savings gauge renders valid SVG."""
        from universal_report.visualizations import SavingsGauge

        gauge = SavingsGauge()
        svg = gauge.render(
            current_liability=Decimal('25000'),
            potential_savings=Decimal('5000'),
        )

        # Verify SVG structure
        assert '<svg' in svg
        assert '</svg>' in svg
        assert 'savings-gauge' in svg

        # Verify values displayed
        assert '$25,000' in svg or '25,000' in svg  # Current tax
        assert '$5,000' in svg or '5,000' in svg    # Savings
        assert '$20,000' in svg or '20,000' in svg  # Optimized

    def test_savings_gauge_zero_values(self):
        """Test gauge handles zero/small values."""
        from universal_report.visualizations import SavingsGauge

        gauge = SavingsGauge()

        # Zero current tax
        svg = gauge.render(
            current_liability=Decimal('0'),
            potential_savings=Decimal('0'),
        )
        assert '<svg' in svg  # Should still render

        # Small values
        svg = gauge.render(
            current_liability=Decimal('100'),
            potential_savings=Decimal('10'),
        )
        assert '<svg' in svg

    def test_mini_gauge(self):
        """Test mini gauge renders."""
        from universal_report.visualizations import SavingsGauge

        gauge = SavingsGauge()
        svg = gauge.render_mini(0.25)

        assert '<svg' in svg
        assert 'mini-gauge' in svg
        assert '25%' in svg

    def test_income_pie_chart(self):
        """Test income pie chart rendering."""
        from universal_report.visualizations import ReportCharts
        from universal_report.data_collector import IncomeItem

        charts = ReportCharts()

        income_items = [
            IncomeItem(category="W-2", description="Wages", amount=Decimal('80000')),
            IncomeItem(category="Business", description="Self-employment", amount=Decimal('40000')),
            IncomeItem(category="Investment", description="Dividends", amount=Decimal('20000')),
        ]

        svg = charts.income_breakdown_pie(income_items)

        assert '<svg' in svg
        assert '</svg>' in svg
        assert '$140,000' in svg or '140,000' in svg  # Total

    def test_empty_chart(self):
        """Test empty chart placeholder."""
        from universal_report.visualizations import ReportCharts

        charts = ReportCharts()
        svg = charts.income_breakdown_pie([])

        assert '<svg' in svg
        assert 'No income data' in svg

    def test_deduction_comparison(self):
        """Test deduction comparison bar chart."""
        from universal_report.visualizations import ReportCharts

        charts = ReportCharts()
        svg = charts.deduction_comparison_bar(
            standard_deduction=Decimal('15000'),
            itemized_deduction=Decimal('22000'),
            deduction_type='itemized'
        )

        assert '<svg' in svg
        assert 'Standard' in svg
        assert 'Itemized' in svg
        assert 'SELECTED' in svg

    def test_tax_bracket_chart(self):
        """Test tax bracket visualization."""
        from universal_report.visualizations import ReportCharts

        charts = ReportCharts()

        # Single filer with $100k taxable income
        svg = charts.tax_bracket_visualization(
            taxable_income=Decimal('100000'),
            filing_status='single'
        )

        assert '<svg' in svg
        assert 'Tax Bracket' in svg

    def test_summary_cards(self):
        """Test summary cards render HTML."""
        from universal_report.visualizations import SummaryCards

        cards = SummaryCards()

        html = cards.render_metric_card(
            title="Total Tax",
            value="$15,000",
            subtitle="Effective Rate: 15%",
            color="primary"
        )

        assert 'Total Tax' in html
        assert '$15,000' in html
        assert 'Effective Rate' in html


class TestBranding:
    """Tests for branding/white-label system."""

    def test_default_theme(self):
        """Test default theme values."""
        from universal_report.branding.theme_manager import BrandTheme

        theme = BrandTheme()

        assert theme.primary_color == '#2563eb'
        assert theme.accent_color == '#10b981'
        assert theme.firm_name == 'Tax Advisory'

    def test_theme_from_cpa_profile(self):
        """Test theme creation from CPA profile."""
        from universal_report.branding.theme_manager import ThemeManager

        manager = ThemeManager()

        cpa_profile = {
            'firm_name': 'Test Tax Firm',
            'primary_color': '#1e40af',
            'accent_color': '#059669',
            'advisor_name': 'Jane Smith',
            'credentials': ['CPA', 'EA'],
            'contact_email': 'jane@test.com',
        }

        theme = manager.from_cpa_profile(cpa_profile)

        assert theme.firm_name == 'Test Tax Firm'
        assert theme.primary_color == '#1e40af'
        assert theme.accent_color == '#059669'
        assert theme.advisor_name == 'Jane Smith'
        assert theme.contact_email == 'jane@test.com'

    def test_css_generation(self):
        """Test CSS variable generation."""
        from universal_report.branding.theme_manager import BrandTheme, ThemeManager

        manager = ThemeManager()
        theme = BrandTheme(primary_color='#ff0000')

        css = manager.generate_css_variables(theme)

        assert '--color-primary: #ff0000' in css

    def test_preset_themes(self):
        """Test preset theme loading."""
        from universal_report.branding.theme_manager import ThemeManager

        manager = ThemeManager()

        presets = ['default', 'corporate', 'modern', 'classic', 'professional']

        for preset_name in presets:
            theme = manager.get_preset(preset_name)
            assert theme is not None
            assert theme.primary_color is not None

    def test_invalid_color_validation(self):
        """Test invalid color handling."""
        from universal_report.branding.theme_manager import ThemeManager

        manager = ThemeManager()

        cpa_profile = {
            'primary_color': 'not-a-color',  # Invalid
            'accent_color': '#10b981',       # Valid
        }

        theme = manager.from_cpa_profile(cpa_profile)

        # Invalid color should use default
        assert theme.primary_color == '#2563eb'  # Default
        assert theme.accent_color == '#10b981'   # Custom valid color


class TestReportEngine:
    """Tests for main report engine."""

    def test_basic_html_generation(self):
        """Test basic HTML report generation."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            'profile': {
                'filing_status': 'single',
                'total_income': 100000,
            },
            'calculations': {
                'gross_income': 100000,
                'federal_tax': 15000,
                'effective_rate': 15.0,
            },
            'strategies': []
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_data=session_data,
            output_format='html',
        )

        assert output.html_content is not None
        assert '<!DOCTYPE html>' in output.html_content
        assert output.taxpayer_name == 'Tax Client'
        assert output.tax_year == 2025

    def test_report_with_branding(self):
        """Test report with CPA branding."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        cpa_profile = {
            'firm_name': 'Acme Tax Services',
            'primary_color': '#1e40af',
        }

        session_data = {
            'profile': {'filing_status': 'single', 'total_income': 100000},
            'calculations': {},
            'strategies': []
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_data=session_data,
            cpa_profile=cpa_profile,
            output_format='html',
        )

        assert 'Acme Tax Services' in output.html_content
        assert '#1e40af' in output.html_content

    def test_tier_1_restrictions(self):
        """Test tier 1 (teaser) restricts content."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            'profile': {'filing_status': 'single', 'total_income': 100000},
            'calculations': {'federal_tax': 15000},
            'strategies': [
                {'title': 'Hidden Strategy', 'estimated_savings': 5000,
                 'category': 'retirement', 'priority': 'current_year',
                 'detailed_explanation': 'Details'}
            ]
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_data=session_data,
            tier_level=1,
        )

        # Tier 1 should have blur or upgrade messaging
        html = output.html_content.lower()
        assert 'blur' in html or 'upgrade' in html

    def test_tier_2_full_content(self):
        """Test tier 2 shows full content."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            'profile': {'filing_status': 'single', 'total_income': 100000},
            'calculations': {'federal_tax': 15000},
            'strategies': [
                {'title': 'Maximize 401k', 'estimated_savings': 3000,
                 'category': 'retirement', 'priority': 'current_year',
                 'detailed_explanation': 'Full details here'}
            ]
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_data=session_data,
            tier_level=2,
        )

        # Tier 2 should show recommendations
        assert 'Maximize 401k' in output.html_content or 'Optimization' in output.html_content

    def test_multiple_source_types(self):
        """Test different source types work."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        # Test all source types
        source_types = ['chatbot', 'lead_magnet', 'manual']

        for source_type in source_types:
            session_data = {
                'profile': {'filing_status': 'single', 'total_income': 100000},
                'calculations': {},
                'strategies': []
            }

            output = engine.generate_report(
                source_type=source_type,
                source_data=session_data,
            )

            assert output.html_content is not None, f"Failed for {source_type}"

    def test_report_output_metadata(self):
        """Test report output contains correct metadata."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            'profile': {
                'first_name': 'Jane',
                'last_name': 'Smith',
                'filing_status': 'married_joint',
                'total_income': 200000,
            },
            'calculations': {'federal_tax': 30000},
            'strategies': [
                {'title': 'S1', 'estimated_savings': 1000, 'category': 'a', 'priority': 'current_year'},
                {'title': 'S2', 'estimated_savings': 2000, 'category': 'b', 'priority': 'current_year'},
            ]
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_id='test_meta',
            source_data=session_data,
        )

        assert output.taxpayer_name == 'Jane Smith'
        assert output.tax_year == 2025
        assert output.recommendation_count == 2
        assert output.potential_savings > 0
        assert output.report_id.startswith('RPT_')


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_very_high_income(self):
        """Test handling of very high income values."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            'profile': {
                'filing_status': 'single',
                'total_income': 5000000,  # $5 million
            },
            'calculations': {
                'gross_income': 5000000,
                'federal_tax': 1850000,
            },
            'strategies': []
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_data=session_data,
        )

        assert output.html_content is not None
        assert '5,000,000' in output.html_content or '5000000' in output.html_content

    def test_zero_income(self):
        """Test handling of zero income."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            'profile': {
                'filing_status': 'single',
                'total_income': 0,
            },
            'calculations': {'federal_tax': 0},
            'strategies': []
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_data=session_data,
        )

        # Should not crash
        assert output.html_content is not None

    def test_negative_values(self):
        """Test handling of negative values (losses)."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            'profile': {
                'filing_status': 'single',
                'total_income': 50000,
                'rental_income': -10000,  # Rental loss
            },
            'calculations': {},
            'strategies': []
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_data=session_data,
        )

        assert output.html_content is not None

    def test_long_taxpayer_name(self):
        """Test handling of very long names."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            'profile': {
                'first_name': 'A' * 100,
                'last_name': 'B' * 100,
                'filing_status': 'single',
                'total_income': 100000,
            },
            'calculations': {},
            'strategies': []
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_data=session_data,
        )

        # Should not crash, may truncate
        assert output.html_content is not None

    def test_special_characters_in_name(self):
        """Test handling of special characters."""
        from universal_report import UniversalReportEngine

        engine = UniversalReportEngine()

        session_data = {
            'profile': {
                'first_name': "O'Connor",
                'last_name': 'Smith-Jones',
                'filing_status': 'single',
                'total_income': 100000,
            },
            'calculations': {},
            'strategies': []
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_data=session_data,
        )

        assert output.html_content is not None
        # Name should appear (possibly HTML escaped - html.escape uses &#x27; for apostrophes)
        assert "O'Connor" in output.html_content or "O&#39;Connor" in output.html_content or "O&#x27;Connor" in output.html_content


class TestNewSections:
    """Tests for the new report sections."""

    def test_risk_assessment_section(self):
        """Test risk assessment section renders correctly."""
        from universal_report.sections.risk_assessment import RiskAssessmentRenderer, RiskLevel
        from universal_report.data_collector import NormalizedReportData, IncomeItem
        from decimal import Decimal

        data = NormalizedReportData(
            source_type='chatbot',
            gross_income=Decimal('600000'),  # High income triggers risk factors
            adjusted_gross_income=Decimal('600000'),
            total_deductions=Decimal('250000'),  # High deduction ratio
            income_items=[
                IncomeItem(
                    category='Self-Employment',
                    description='Consulting income',
                    amount=Decimal('400000'),
                )
            ]
        )

        renderer = RiskAssessmentRenderer(data)
        html = renderer.render()

        assert html is not None
        assert 'Audit Risk Assessment' in html
        assert 'Risk Level' in html
        # Should identify high income risk
        assert 'High Income' in html or 'risk' in html.lower()

    def test_risk_assessment_low_risk(self):
        """Test risk assessment for low-risk taxpayer."""
        from universal_report.sections.risk_assessment import RiskAssessmentRenderer
        from universal_report.data_collector import NormalizedReportData
        from decimal import Decimal

        data = NormalizedReportData(
            source_type='chatbot',
            gross_income=Decimal('75000'),
            adjusted_gross_income=Decimal('75000'),
            total_deductions=Decimal('14000'),  # Standard deduction
        )

        renderer = RiskAssessmentRenderer(data)
        risks = renderer.assess_risks()
        score = renderer.calculate_risk_score(risks)

        # Should be low risk with no special factors
        assert score < 50

    def test_tax_timeline_section(self):
        """Test tax timeline section renders correctly."""
        from universal_report.sections.tax_timeline import TaxTimelineRenderer
        from universal_report.data_collector import NormalizedReportData

        data = NormalizedReportData(
            source_type='chatbot',
            tax_year=2025,
        )

        renderer = TaxTimelineRenderer(data)
        html = renderer.render()

        assert html is not None
        assert 'Important Tax Deadlines' in html
        assert 'April 15' in html
        assert 'October 15' in html  # Extension deadline

    def test_tax_timeline_with_estimated_taxes(self):
        """Test timeline shows estimated tax dates for self-employed."""
        from universal_report.sections.tax_timeline import TaxTimelineRenderer, DeadlineType
        from universal_report.data_collector import NormalizedReportData, IncomeItem
        from decimal import Decimal

        data = NormalizedReportData(
            source_type='chatbot',
            tax_year=2025,
            income_items=[
                IncomeItem(
                    category='Self-Employment',
                    description='Business income',
                    amount=Decimal('100000')
                )
            ]
        )

        renderer = TaxTimelineRenderer(data)
        deadlines = renderer.get_deadlines()

        # Should include estimated tax deadlines
        estimated = [d for d in deadlines if d.deadline_type == DeadlineType.ESTIMATED_TAX]
        assert len(estimated) >= 4  # All 4 quarterly payments

    def test_document_checklist_section(self):
        """Test document checklist section renders correctly."""
        from universal_report.sections.document_checklist import DocumentChecklistRenderer
        from universal_report.data_collector import NormalizedReportData, IncomeItem
        from decimal import Decimal

        data = NormalizedReportData(
            source_type='chatbot',
            income_items=[
                IncomeItem(
                    category='Wages',
                    description='W-2 Employment',
                    amount=Decimal('80000')
                )
            ]
        )

        renderer = DocumentChecklistRenderer(data)
        html = renderer.render()

        assert html is not None
        assert 'Document Checklist' in html
        assert 'W-2' in html
        assert 'Social Security' in html

    def test_document_checklist_self_employed(self):
        """Test checklist includes business documents for self-employed."""
        from universal_report.sections.document_checklist import DocumentChecklistRenderer
        from universal_report.data_collector import NormalizedReportData, IncomeItem
        from decimal import Decimal

        data = NormalizedReportData(
            source_type='chatbot',
            income_items=[
                IncomeItem(
                    category='Self-Employment',
                    description='Consulting',
                    amount=Decimal('150000')
                )
            ]
        )

        renderer = DocumentChecklistRenderer(data)
        required_docs = renderer.get_required_documents()

        # Should have self-employment section
        assert 'Self-Employment/Business' in required_docs
        # Should include 1099-NEC
        se_docs = required_docs.get('Self-Employment/Business', [])
        doc_names = [d.name for d in se_docs]
        assert '1099-NEC for Services' in doc_names or any('1099' in name for name in doc_names)

    def test_tax_education_section(self):
        """Test tax education section renders correctly."""
        from universal_report.sections.tax_education import TaxEducationRenderer
        from universal_report.data_collector import NormalizedReportData, IncomeItem
        from decimal import Decimal

        data = NormalizedReportData(
            source_type='chatbot',
            gross_income=Decimal('200000'),
            income_items=[
                IncomeItem(
                    category='Employment',
                    description='W-2 Salary',
                    amount=Decimal('200000')
                )
            ]
        )

        renderer = TaxEducationRenderer(data)
        html = renderer.render()

        assert html is not None
        assert 'Understanding Your Tax Strategies' in html or 'Tax Strategies' in html

    def test_tax_education_strategy_selection(self):
        """Test that relevant strategies are selected based on user data."""
        from universal_report.sections.tax_education import TaxEducationRenderer
        from universal_report.data_collector import NormalizedReportData, IncomeItem
        from decimal import Decimal

        # High-income user should get backdoor Roth strategy
        data = NormalizedReportData(
            source_type='chatbot',
            gross_income=Decimal('250000'),
            income_items=[
                IncomeItem(
                    category='Employment',
                    description='W-2 Salary',
                    amount=Decimal('250000')
                )
            ]
        )

        renderer = TaxEducationRenderer(data)
        strategies = renderer._get_relevant_strategies()

        assert 'backdoor_roth' in strategies

    def test_executive_summary_enhanced(self):
        """Test enhanced executive summary section."""
        from universal_report.sections.executive_summary import ExecutiveSummaryRenderer
        from universal_report.data_collector import NormalizedReportData, Recommendation, PriorityLevel
        from decimal import Decimal

        data = NormalizedReportData(
            source_type='chatbot',
            gross_income=Decimal('150000'),
            adjusted_gross_income=Decimal('140000'),
            tax_liability=Decimal('25000'),
            effective_rate=16.7,
            potential_savings_high=Decimal('5000'),
            recommendations=[
                Recommendation(
                    id='rec_401k',
                    title='Max 401(k)',
                    description='Increase contributions',
                    estimated_savings=Decimal('3000'),
                    priority=PriorityLevel.IMMEDIATE,
                    category='Retirement',
                    confidence=0.9,
                    action_required='Increase 401(k) contribution',
                ),
                Recommendation(
                    id='rec_hsa',
                    title='HSA Contribution',
                    description='Fund your HSA',
                    estimated_savings=Decimal('2000'),
                    priority=PriorityLevel.CURRENT_YEAR,
                    category='Healthcare',
                    confidence=0.85,
                    action_required='Open and fund HSA account',
                ),
            ],
            key_insights=['Your effective rate is reasonable', 'Retirement savings could be higher'],
        )

        renderer = ExecutiveSummaryRenderer(data)
        html = renderer.render()

        assert html is not None
        assert 'Executive Summary' in html
        assert '$150,000' in html or '150,000' in html  # Gross income
        assert '$25,000' in html or '25,000' in html  # Tax liability
        assert 'Top Savings' in html or 'Max 401(k)' in html

    def test_cover_page_enhanced(self):
        """Test enhanced cover page section."""
        from universal_report.sections.cover_page import CoverPageRenderer
        from universal_report.data_collector import NormalizedReportData
        from universal_report.branding.theme_manager import BrandTheme
        from decimal import Decimal

        data = NormalizedReportData(
            source_type='chatbot',
            taxpayer_name='John Smith',
            tax_year=2025,
            filing_status='married_joint',
            tax_liability=Decimal('35000'),
            potential_savings_high=Decimal('7000'),
        )

        theme = BrandTheme(
            firm_name='Smith Tax Advisory',
            advisor_name='Sarah Smith',
            advisor_credentials=['CPA', 'CFP'],
            report_title='Personalized Tax Strategy Report',
        )

        renderer = CoverPageRenderer(data, theme)
        html = renderer.render()

        assert html is not None
        assert 'John Smith' in html
        assert 'Smith Tax Advisory' in html or 'Personalized Tax Strategy Report' in html
        assert 'Sarah Smith' in html


class TestDetailedRecommendations:
    """Tests for enhanced recommendation cards."""

    def test_detailed_recommendation_card(self):
        """Test detailed recommendation card rendering."""
        from universal_report.visualizations.summary_cards import SummaryCards
        from decimal import Decimal

        cards = SummaryCards()
        html = cards.render_detailed_recommendation_card(
            title='Maximize 401(k) Contributions',
            description='Increase your 401(k) contributions to reduce taxable income.',
            savings=Decimal('4500'),
            priority='immediate',
            category='Retirement',
            action='Log into your benefits portal and increase contribution percentage',
            implementation_steps=[
                'Review current contribution level',
                'Calculate maximum contribution',
                'Increase deferral percentage',
                'Verify changes on next paycheck',
            ],
            irs_reference='IRC Section 401(k)',
            complexity='low',
            timeline='Before next paycheck',
            requirements=[
                'Employer offers 401(k) plan',
                'Sufficient income to contribute',
            ],
            risks=[
                'Reduced take-home pay',
                'Early withdrawal penalties if needed before 59.5',
            ],
        )

        assert html is not None
        assert 'Maximize 401(k)' in html
        assert '$4,500' in html
        assert 'Implementation Steps' in html
        assert 'IRC Section 401(k)' in html
        assert 'Easy to implement' in html  # Low complexity

    def test_comparison_table(self):
        """Test comparison table rendering."""
        from universal_report.visualizations.summary_cards import SummaryCards

        cards = SummaryCards()
        html = cards.render_comparison_table(
            title='Deduction Comparison',
            columns=['Deduction Type', 'Amount', 'Benefit'],
            rows=[
                ['Standard Deduction', '$29,200', '$7,008'],
                ['Itemized Deductions', '$32,500', '$7,800'],
            ],
            highlight_row=1,  # Highlight itemized
        )

        assert html is not None
        assert 'Deduction Comparison' in html
        assert 'Standard Deduction' in html
        assert 'Itemized Deductions' in html
        assert '$32,500' in html

    def test_stat_comparison(self):
        """Test stat comparison rendering."""
        from universal_report.visualizations.summary_cards import SummaryCards

        cards = SummaryCards()
        html = cards.render_stat_comparison(
            label='Effective Tax Rate',
            current_value='22.5%',
            optimized_value='18.2%',
            improvement='-4.3%',
        )

        assert html is not None
        assert 'Effective Tax Rate' in html
        assert '22.5%' in html
        assert '18.2%' in html
        assert '-4.3%' in html


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
