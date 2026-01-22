#!/usr/bin/env python3
"""
Quick test of advisory report generation (bypassing CSRF).
This creates a sample report directly to verify the system works.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income
from models.deductions import Deductions
from models.credits import TaxCredits
from advisory import generate_advisory_report, ReportType
from export import export_advisory_report_to_pdf
from database.advisory_models import create_advisory_report_from_result
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_advisory_report():
    """Test advisory report generation end-to-end."""

    print("🧪 Testing Advisory Report System...\n")

    # Step 1: Create sample tax return
    print("1. Creating sample tax return...")
    tax_return = TaxReturn(
        tax_year=2025,
        taxpayer=TaxpayerInfo(
            first_name="Test",
            last_name="User",
            ssn="000-00-0000",
            filing_status=FilingStatus.MARRIED_JOINT,
            state="CA"
        ),
        income=Income(
            w2_income=120000,
            total_income=120000
        ),
        deductions=Deductions(
            itemized_deductions={
                "mortgage_interest": 15000,
                "property_tax": 10000
            }
        ),
        credits=TaxCredits(
            child_tax_credit=4000
        )
    )
    print("✅ Sample tax return created")

    # Step 2: Generate advisory report
    print("\n2. Generating advisory report...")
    try:
        report_result = generate_advisory_report(
            tax_return=tax_return,
            report_type=ReportType.FULL_ANALYSIS,
            include_entity_comparison=True,
            include_multi_year=True,
            years_ahead=3
        )
        print(f"✅ Report generated: {report_result.report_id}")
        print(f"   - Taxpayer: {report_result.taxpayer_name}")
        print(f"   - Tax liability: ${report_result.current_tax_liability:,.0f}")
        print(f"   - Potential savings: ${report_result.potential_savings:,.0f}")
        print(f"   - Recommendations: {report_result.top_recommendations_count}")
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 3: Save to database
    print("\n3. Saving to database...")
    try:
        db_path = Path(__file__).parent / "data" / "tax_returns.db"
        engine = create_engine(f"sqlite:///{db_path}")
        SessionLocal = sessionmaker(bind=engine)
        db_session = SessionLocal()

        db_report = create_advisory_report_from_result(
            result=report_result,
            session_id="test_session_123",
            session=db_session
        )

        db_session.add(db_report)
        db_session.commit()

        print(f"✅ Report saved to database")
        print(f"   - Database ID: {db_report.id}")
        print(f"   - Report ID: {db_report.report_id}")

        db_session.close()
    except Exception as e:
        print(f"❌ Error saving to database: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Generate PDF
    print("\n4. Generating PDF...")
    try:
        output_dir = Path(__file__).parent / "temp_reports"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"{report_result.report_id}.pdf"

        pdf_path = export_advisory_report_to_pdf(
            report=report_result,
            output_path=str(output_path),
            watermark="TEST"
        )
        print(f"✅ PDF generated: {pdf_path}")
        print(f"   - File size: {Path(pdf_path).stat().st_size / 1024:.1f} KB")
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 5: Verify in database
    print("\n5. Verifying database entry...")
    try:
        db_session = SessionLocal()
        from database.advisory_models import get_advisory_report_by_id
        retrieved = get_advisory_report_by_id(db_report.report_id, db_session)

        if retrieved:
            print(f"✅ Report retrieved from database")
            print(f"   - Report ID: {retrieved.report_id}")
            print(f"   - Taxpayer: {retrieved.taxpayer_name}")
            print(f"   - PDF path: {retrieved.pdf_path or 'Not set'}")
        else:
            print(f"❌ Could not retrieve report from database")
            return False

        db_session.close()
    except Exception as e:
        print(f"❌ Error verifying: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED!")
    print("="*60)
    print(f"\nReport Details:")
    print(f"  - Report ID: {report_result.report_id}")
    print(f"  - Taxpayer: {report_result.taxpayer_name}")
    print(f"  - Tax Year: {report_result.tax_year}")
    print(f"  - Current Tax: ${report_result.current_tax_liability:,.0f}")
    print(f"  - Potential Savings: ${report_result.potential_savings:,.0f}")
    print(f"  - Recommendations: {report_result.top_recommendations_count}")
    print(f"  - PDF: {pdf_path}")
    print("\n✅ Advisory report system is fully operational!")

    return True


if __name__ == "__main__":
    try:
        success = test_advisory_report()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
