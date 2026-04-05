#!/usr/bin/env python3
"""
Pre-compute IRS RAG FAISS indices for Docker image build stage.

Runs during Docker build to pre-warm indices so they're baked into the image.
This eliminates cold-start latency on container startup.

Usage:
    python scripts/precompute_irs_indices.py [--tax-years 2025 2024]

Exit codes:
    0: Success (all indices computed)
    1: Partial success (some indices computed)
    2: Failure (no indices computed)
"""

import sys
import logging
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Pre-compute indices for all requested tax years."""
    import argparse

    parser = argparse.ArgumentParser(description="Pre-compute IRS RAG indices for Docker build")
    parser.add_argument(
        "--tax-years",
        type=int,
        nargs="+",
        default=[2025, 2024],
        help="Tax years to pre-compute (default: 2025 2024)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        from services.irs_rag import warm_irs_indices

        logger.info(f"Pre-computing IRS RAG indices for tax years: {args.tax_years}")
        result = await warm_irs_indices(tax_years=args.tax_years)

        if result["success"]:
            logger.info("✓ All indices pre-computed successfully")
            logger.info(f"  Ready tax years: {result['ready_tax_years']}")
            return 0
        else:
            if result["ready_tax_years"]:
                logger.warning(f"✓ Partial success: {result['ready_tax_years']} ready")
                logger.warning(f"  Error: {result['error']}")
                return 1
            else:
                logger.error(f"✗ Pre-computation failed: {result['error']}")
                return 2

    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}", exc_info=True)
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
