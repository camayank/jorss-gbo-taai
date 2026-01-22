#!/bin/bash

# RBAC Test Runner Script
#
# Runs all RBAC and permission-related tests.
# Provides detailed output and coverage reports.

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  RBAC Permission System Test Suite  ${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed${NC}"
    echo "Install it with: pip install pytest pytest-cov pytest-asyncio"
    exit 1
fi

# Change to project root
cd "$(dirname "$0")/.."

echo -e "${YELLOW}Running RBAC Permission Tests...${NC}"
echo ""

# Run permission tests
pytest tests/test_rbac_permissions.py -v --tb=short --cov=src/rbac --cov-report=term-missing

echo ""
echo -e "${YELLOW}Running Feature Access Control Tests...${NC}"
echo ""

# Run feature access tests
pytest tests/test_feature_access.py -v --tb=short --cov=src/rbac/feature_access_control --cov-report=term-missing

echo ""
echo -e "${YELLOW}Running All RBAC Tests Together...${NC}"
echo ""

# Run all RBAC tests
pytest tests/test_rbac_permissions.py tests/test_feature_access.py -v --tb=short \
    --cov=src/rbac --cov=src/audit --cov-report=html --cov-report=term-missing

echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  Test Summary  ${NC}"
echo -e "${GREEN}=====================================${NC}"

# Count tests
total_tests=$(pytest tests/test_rbac_permissions.py tests/test_feature_access.py --collect-only -q | tail -n 1 | awk '{print $1}')
echo -e "Total tests run: ${GREEN}${total_tests}${NC}"

echo ""
echo -e "${GREEN}Coverage report generated at: ${NC}htmlcov/index.html"
echo ""

# Check if all tests passed
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All RBAC tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the output above.${NC}"
    exit 1
fi
