# Phase 0: Foundation Validation - Quick Start Guide
## Week 1 Critical Path

**Duration**: 3-5 days
**Team**: 1 Senior Developer + 0.5 CPA
**Goal**: Validate existing infrastructure before building

---

## DAY 1: INFRASTRUCTURE AUDIT

### Morning (4 hours)
```bash
# 1. Run complete test suite
cd /Users/rakeshanita/Jorss-Gbo
pytest tests/ -v --tb=short

# 2. Check test coverage
pytest tests/ --cov=src --cov-report=html

# 3. Review coverage report
open htmlcov/index.html
```

**Expected Output**:
- ✅ 80%+ tests passing
- ⚠️ Identify any failing tests
- 📊 Coverage report showing gaps

**Tasks**:
- [ ] Document all failing tests
- [ ] Identify root causes
- [ ] Create fix priority list

### Afternoon (4 hours)
```bash
# 4. Test existing engines individually
pytest tests/test_tax_calculator.py -v
pytest tests/test_recommendation_engine.py -v
pytest tests/test_scenario_api.py -v
pytest tests/test_realtime_estimator.py -v

# 5. Check if entity optimizer works
pytest tests/test_entity_optimizer.py -v || echo "Need to create this test"

# 6. Check if multi-year projector works
pytest tests/test_multi_year_projections.py -v || echo "Need to create this test"
```

**Deliverables**:
- ✅ List of working engines
- ⚠️ List of broken engines
- 📝 Missing test file list

---

## DAY 2: DEPENDENCY INSTALLATION & INTEGRATION TESTS

### Morning (4 hours)
```bash
# 1. Install missing dependencies
pip install reportlab matplotlib pillow

# 2. Verify installations
python -c "import reportlab; print('ReportLab:', reportlab.Version)"
python -c "import matplotlib; print('Matplotlib:', matplotlib.__version__)"
python -c "import PIL; print('Pillow:', PIL.__version__)"

# 3. Optional: Background job processing
# pip install celery redis
```

**Create Integration Test**:
```python
# tests/test_advisory_integration.py

import pytest
from src.calculator.tax_calculator import TaxCalculator
from src.recommendation.recommendation_engine import RecommendationEngine
from src.services.scenario_service import ScenarioService
from src.projection.multi_year_projections import MultiYearProjector
from src.recommendation.entity_optimizer import EntityOptimizer

@pytest.fixture
def sample_session():
    """Create sample tax session for testing."""
    return {
        "session_id": "test_123",
        "filing_status": "single",
        "wages": 85000,
        "withholding": 16000,
        "num_dependents": 0,
        "retirement_401k": 12000,
        "mortgage_interest": 0,
        "property_tax": 0,
        "charitable_contributions": 500
    }

def test_end_to_end_calculation(sample_session):
    """Test: Session → Calculator → Recommendations."""
    # Calculate taxes
    calc = TaxCalculator()
    result = calc.calculate(sample_session)

    assert result['total_income'] > 0
    assert result['federal_tax'] > 0
    assert 'refund_or_owed' in result

    # Get recommendations
    recommender = RecommendationEngine(calc)
    recs = recommender.get_top_recommendations(sample_session, limit=3)

    assert len(recs) > 0
    assert all('annual_savings' in r for r in recs)

def test_scenario_comparison(sample_session):
    """Test: Session → Scenario Service → Multiple results."""
    scenarios = ScenarioService()
    results = scenarios.run_comprehensive_scenarios(sample_session)

    assert "current" in results
    assert "max_401k" in results
    assert results["max_401k"]['result']['net_tax'] < results["current"]['result']['net_tax']

def test_multi_year_projection(sample_session):
    """Test: Session → Projector → 3-year forecast."""
    projector = MultiYearProjector()
    projections = projector.project_years(sample_session, years_ahead=3)

    assert len(projections) == 4  # Current + 3 future
    assert projections[1].year == projections[0].year + 1
    assert projections[1].gross_income > projections[0].gross_income  # Growth

def test_entity_optimization(sample_session):
    """Test: Business session → Entity Optimizer → S-Corp vs LLC."""
    business_session = {
        **sample_session,
        "business_income": 150000,
        "business_expenses": 30000
    }

    optimizer = EntityOptimizer()
    comparison = optimizer.compare_all_entities(
        business_income=150000,
        business_expenses=30000,
        filing_status="single",
        state="CA"
    )

    assert "sole_proprietor" in comparison
    assert "s_corp" in comparison
    assert comparison["s_corp"].net_benefit != 0

def test_full_advisory_pipeline(sample_session):
    """Test: Complete pipeline for advisory report data."""
    # Step 1: Calculate taxes
    calc = TaxCalculator()
    tax_result = calc.calculate(sample_session)

    # Step 2: Generate scenarios
    scenarios = ScenarioService()
    scenario_results = scenarios.run_comprehensive_scenarios(sample_session)

    # Step 3: Project future years
    projector = MultiYearProjector()
    future_projections = projector.project_years(sample_session, years_ahead=3)

    # Step 4: Get recommendations
    recommender = RecommendationEngine(calc)
    recommendations = recommender.get_top_recommendations(sample_session, limit=10)

    # Verify all data is present
    assert tax_result is not None
    assert len(scenario_results) > 0
    assert len(future_projections) > 0
    assert len(recommendations) > 0

    # This is the data structure for advisory report
    advisory_data = {
        "current_tax_position": tax_result,
        "scenario_comparison": scenario_results,
        "multi_year_projection": future_projections,
        "recommendations": recommendations
    }

    print("\n✅ ADVISORY REPORT DATA STRUCTURE VALIDATED")
    print(f"  - Tax calculation: {tax_result['net_tax']}")
    print(f"  - Scenarios analyzed: {len(scenario_results)}")
    print(f"  - Years projected: {len(future_projections)}")
    print(f"  - Recommendations: {len(recommendations)}")

    return advisory_data
```

### Afternoon (4 hours)
```bash
# Run integration tests
pytest tests/test_advisory_integration.py -v -s

# If tests fail, debug and fix
pytest tests/test_advisory_integration.py::test_end_to_end_calculation -v -s
pytest tests/test_advisory_integration.py::test_scenario_comparison -v -s
pytest tests/test_advisory_integration.py::test_multi_year_projection -v -s
```

**Deliverables**:
- ✅ All dependencies installed
- ✅ Integration tests passing
- ✅ Advisory data pipeline validated

---

## DAY 3: TAX RULES VALIDATION

### Morning (4 hours)
```python
# tests/test_tax_rules_2025.py

def test_2025_tax_brackets_single():
    """Verify 2025 tax brackets for Single filers."""
    from src.calculator.tax_year_config import get_tax_brackets

    brackets = get_tax_brackets(2025, "single")

    expected = [
        (11925, 0.10),   # 10% up to $11,925
        (48475, 0.12),   # 12% up to $48,475
        (103350, 0.22),  # 22% up to $103,350
        (197300, 0.24),  # 24% up to $197,300
        (250525, 0.32),  # 32% up to $250,525
        (626350, 0.35),  # 35% up to $626,350
        (float('inf'), 0.37)  # 37% above
    ]

    assert brackets == expected, f"2025 brackets incorrect! Got: {brackets}"

def test_2025_standard_deductions():
    """Verify 2025 standard deduction amounts."""
    from src.calculator.tax_year_config import get_standard_deduction

    assert get_standard_deduction(2025, "single") == 14600
    assert get_standard_deduction(2025, "married_jointly") == 29200
    assert get_standard_deduction(2025, "head_of_household") == 21900

def test_2025_contribution_limits():
    """Verify 2025 retirement contribution limits."""
    from src.calculator.tax_year_config import get_contribution_limits

    limits = get_contribution_limits(2025)

    assert limits["401k"] == 23500  # 2025 limit
    assert limits["401k_catchup"] == 7500  # Age 50+
    assert limits["ira"] == 7000    # 2025 limit
    assert limits["ira_catchup"] == 1000   # Age 50+
    assert limits["hsa_individual"] == 4300  # 2025 limit
    assert limits["hsa_family"] == 8550      # 2025 limit

def test_2025_qbi_thresholds():
    """Verify 2025 QBI deduction thresholds."""
    from src.calculator.qbi_calculator import QBICalculator

    qbi = QBICalculator()

    # Single filer thresholds
    assert qbi.get_threshold(2025, "single") == 191950
    assert qbi.get_phaseout_range(2025, "single") == 50000

    # MFJ thresholds
    assert qbi.get_threshold(2025, "married_jointly") == 383900
    assert qbi.get_phaseout_range(2025, "married_jointly") == 100000

def test_2025_se_tax_rates():
    """Verify 2025 self-employment tax rates and wage base."""
    from src.calculator.tax_calculator import TaxCalculator

    calc = TaxCalculator()

    # Verify constants
    assert calc.SE_TAX_RATE == 0.153  # 15.3%
    assert calc.SE_WAGE_BASE_2025 == 168600  # Social Security cap
    assert calc.MEDICARE_RATE == 0.029  # 2.9%
    assert calc.ADDITIONAL_MEDICARE_THRESHOLD == 200000  # 0.9% above
```

### Afternoon (4 hours)
```bash
# Run tax rules validation
pytest tests/test_tax_rules_2025.py -v

# If any fail, update tax_year_config.py
# Check IRS Publication 17 (2025) for correct values
```

**Deliverables**:
- ✅ All 2025 tax rules validated
- ✅ Any missing constants added
- ✅ Documentation of changes

---

## DAY 4: DATA MODEL EXTENSIONS

### Morning (4 hours)
```python
# src/database/advisory_models.py

from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class AdvisoryReport(Base):
    """Advisory report storage."""
    __tablename__ = "advisory_reports"

    id = Column(Integer, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    report_type = Column(String, nullable=False)  # "full", "summary", "comparison"
    generated_at = Column(DateTime, default=datetime.utcnow)
    pdf_path = Column(String, nullable=True)
    report_data = Column(JSON, nullable=False)  # Full report structure
    status = Column(String, default="generating")  # "generating", "ready", "expired"
    version = Column(Integer, default=1)

class ReportSection(Base):
    """Individual report sections for caching."""
    __tablename__ = "report_sections"

    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey("advisory_reports.id"))
    section_type = Column(String, nullable=False)  # "executive_summary", "form_1040", etc.
    content_data = Column(JSON, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
```

### Afternoon (4 hours)
```bash
# Create migration
# migrations/add_advisory_reports.sql

CREATE TABLE IF NOT EXISTS advisory_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pdf_path TEXT,
    report_data JSON NOT NULL,
    status TEXT DEFAULT 'generating',
    version INTEGER DEFAULT 1
);

CREATE INDEX idx_advisory_reports_session ON advisory_reports(session_id);
CREATE INDEX idx_advisory_reports_status ON advisory_reports(status);

CREATE TABLE IF NOT EXISTS report_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    section_type TEXT NOT NULL,
    content_data JSON NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES advisory_reports(id)
);

CREATE INDEX idx_report_sections_report ON report_sections(report_id);
```

```bash
# Run migration
sqlite3 data/jorss.db < migrations/add_advisory_reports.sql

# Verify tables created
sqlite3 data/jorss.db "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'advisory%' OR name LIKE 'report%';"
```

**Deliverables**:
- ✅ Advisory report models created
- ✅ Database migration complete
- ✅ Tables verified in database

---

## DAY 5: API ARCHITECTURE & SCHEMAS

### Morning (4 hours)
```python
# src/web/schemas/advisory_schemas.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class AdvisoryReportRequest(BaseModel):
    """Request to generate advisory report."""
    session_id: str = Field(..., description="Tax session ID")
    include_scenarios: bool = Field(True, description="Include scenario comparison")
    include_multi_year: bool = Field(True, description="Include 3-year projection")
    include_entity_comparison: bool = Field(False, description="Include entity comparison")
    include_state: bool = Field(True, description="Include state tax analysis")
    report_format: str = Field("pdf", description="Output format: pdf or json")

class AdvisoryReportResponse(BaseModel):
    """Response with report status."""
    report_id: str
    status: str  # "generating", "ready", "failed"
    estimated_completion: Optional[datetime]
    download_url: Optional[str]
    preview_url: Optional[str]

class ReportSectionResponse(BaseModel):
    """Individual section data."""
    section_type: str
    content: Dict[str, Any]
    generated_at: datetime

class ScenarioComparisonRequest(BaseModel):
    """Request to compare scenarios."""
    session_id: str
    scenario_types: List[str] = Field(
        default=["current", "max_401k", "hsa", "itemize", "all_optimizations"],
        description="Scenarios to compare"
    )

class MultiYearProjectionRequest(BaseModel):
    """Request for multi-year projection."""
    session_id: str
    years_ahead: int = Field(3, ge=1, le=10, description="Years to project (1-10)")
    wage_growth_rate: float = Field(0.03, description="Annual wage growth (default 3%)")
    inflation_rate: float = Field(0.025, description="Annual inflation (default 2.5%)")
    roth_conversion_strategy: str = Field("bracket_fill", description="Roth conversion approach")
```

### Afternoon (4 hours)
```python
# src/web/advisory_report_api.py (stub for now)

from fastapi import APIRouter, HTTPException, BackgroundTasks
from src.web.schemas.advisory_schemas import (
    AdvisoryReportRequest,
    AdvisoryReportResponse,
    ScenarioComparisonRequest,
    MultiYearProjectionRequest
)

router = APIRouter(prefix="/api/v1/advisory-report", tags=["advisory"])

@router.post("/generate", response_model=AdvisoryReportResponse)
async def generate_advisory_report(
    request: AdvisoryReportRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate comprehensive advisory report.

    Returns immediately with report_id.
    Report generation happens in background.
    Poll /api/v1/advisory-report/{report_id} for status.
    """
    # TODO: Implement in Phase 1
    raise HTTPException(501, "Not implemented yet - Phase 1 task")

@router.get("/{report_id}", response_model=AdvisoryReportResponse)
async def get_report_status(report_id: str):
    """Get report generation status."""
    # TODO: Implement in Phase 1
    raise HTTPException(501, "Not implemented yet - Phase 1 task")

@router.get("/{report_id}/pdf")
async def download_report_pdf(report_id: str):
    """Download generated PDF report."""
    # TODO: Implement in Phase 2
    raise HTTPException(501, "Not implemented yet - Phase 2 task")
```

**Deliverables**:
- ✅ API schemas defined
- ✅ API stubs created
- ✅ Documentation ready for Phase 1

---

## PHASE 0 COMPLETION CHECKLIST

### Infrastructure ✅
- [ ] All existing tests passing (>80%)
- [ ] Dependencies installed (ReportLab, Matplotlib, Pillow)
- [ ] Integration tests created and passing

### Validation ✅
- [ ] 2025 tax rules verified correct
- [ ] All calculation engines tested individually
- [ ] End-to-end pipeline validated

### Data Layer ✅
- [ ] Advisory report models created
- [ ] Database migration complete
- [ ] Tables verified

### API Layer ✅
- [ ] Request/response schemas defined
- [ ] API endpoints stubbed
- [ ] Documentation complete

---

## READY FOR PHASE 1

Once Phase 0 complete:
✅ **Foundation validated**
✅ **All dependencies installed**
✅ **Data models ready**
✅ **API architecture defined**

**Next**: Begin Phase 1 (Advisory Report Engine) on Monday

---

## QUICK COMMANDS REFERENCE

```bash
# Run all tests
pytest tests/ -v

# Run integration tests only
pytest tests/test_advisory_integration.py -v -s

# Run tax rules validation
pytest tests/test_tax_rules_2025.py -v

# Check test coverage
pytest tests/ --cov=src --cov-report=html

# Install dependencies
pip install reportlab matplotlib pillow

# Run migrations
sqlite3 data/jorss.db < migrations/add_advisory_reports.sql

# Start development server
python -m src.web.app
```

---

**Phase 0 Duration**: 3-5 days
**Next Phase**: Phase 1 starts immediately after
**Critical Success Factor**: All integration tests must pass
