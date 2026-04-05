#!/usr/bin/env python
"""
Test script to verify Celery workers are functioning correctly.

Usage:
    python scripts/test_celery_workers.py
"""

import sys
import time
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, "src")

from tasks.celery_app import celery_app, get_task_info

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_worker_connectivity():
    """Test that Celery can connect to the broker."""
    logger.info("Testing worker connectivity...")
    try:
        with celery_app.connection() as conn:
            conn.default_channel.queue_declare(queue="test", passive=True)
        logger.info("✓ Worker connectivity OK")
        return True
    except Exception as e:
        logger.error(f"✗ Worker connectivity failed: {e}")
        return False


def test_task_queue():
    """Test queueing a simple task."""
    logger.info("Testing task queueing...")

    # Define a simple test task
    @celery_app.task(name="test.simple_task")
    def simple_task(x, y):
        return {"result": x + y, "timestamp": str(datetime.now())}

    try:
        # Queue the task
        result = simple_task.delay(2, 3)
        logger.info(f"Task queued: {result.id}")

        # Wait for result (with timeout)
        timeout = 10
        start = time.time()
        while time.time() - start < timeout:
            if result.ready():
                if result.successful():
                    logger.info(f"✓ Task executed successfully: {result.result}")
                    return True
                else:
                    logger.error(f"✗ Task failed: {result.result}")
                    return False
            time.sleep(1)

        logger.error(f"✗ Task timed out after {timeout} seconds")
        return False

    except Exception as e:
        logger.error(f"✗ Task queueing failed: {e}")
        return False


def test_worker_status():
    """Check worker status and active tasks."""
    logger.info("Checking worker status...")
    try:
        stats = celery_app.control.inspect().stats()
        active = celery_app.control.inspect().active()

        if not stats:
            logger.warning("⚠ No workers found (workers may not be running yet)")
            return True  # Not necessarily a failure

        for worker, info in stats.items():
            logger.info(f"✓ Worker {worker}: {info.get('pool', {}).get('max-concurrency')} concurrent tasks")

        if active:
            for worker, tasks in active.items():
                logger.info(f"  Active tasks on {worker}: {len(tasks)}")

        return True

    except Exception as e:
        logger.error(f"✗ Worker status check failed: {e}")
        return False


def run_all_tests():
    """Run all tests and report results."""
    logger.info("=" * 60)
    logger.info("Celery Worker Verification Tests")
    logger.info("=" * 60)

    tests = [
        ("Connectivity", test_worker_connectivity),
        ("Task Queueing", test_task_queue),
        ("Worker Status", test_worker_status),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            logger.error(f"Exception in {name}: {e}")
            results.append((name, False))
        logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("Test Summary:")
    passed_count = sum(1 for _, passed in results if passed)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        logger.info(f"  {name}: {status}")

    logger.info(f"\nTotal: {passed_count}/{len(results)} passed")
    logger.info("=" * 60)

    return passed_count == len(results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
