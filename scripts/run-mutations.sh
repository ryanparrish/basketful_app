#!/bin/bash
# Quick mutation testing script for local development

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   🧬 Mutation Testing Runner          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}\n"

# Get target from argument or use default
TARGET="${1:-apps/orders/models.py}"

echo -e "${YELLOW}Target:${NC} $TARGET\n"

# Clean previous cache
if [ -d .mutmut-cache ]; then
    echo -e "${YELLOW}Cleaning previous cache...${NC}"
    rm -rf .mutmut-cache
fi

# Run mutations
echo -e "\n${GREEN}Running mutations...${NC}\n"
mutmut run --paths-to-mutate="$TARGET" --tests-dir=apps/ || true

# Generate reports
echo -e "\n${GREEN}Generating reports...${NC}"
mutmut results | tee mutation-results.txt || echo "No mutations completed yet" > mutation-results.txt
mutmut html || echo "Could not generate HTML report"

# Parse and display score
echo ""
if [ -f mutation-results.txt ]; then
    SCORE=$(grep -oP '(?<=mutation score: )\d+\.\d+' mutation-results.txt || echo "0.0")
    SURVIVED=$(grep -oP '(?<=Survived: )\d+' mutation-results.txt || echo "0")
    
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  ${GREEN}Mutation Score: ${SCORE}%${NC}               ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    
    if [ "$SURVIVED" -gt 0 ]; then
        echo -e "\n${RED}⚠️  $SURVIVED mutations survived${NC}"
        echo -e "${YELLOW}Run 'mutmut show' to see details${NC}\n"
        echo -e "${YELLOW}Tip: Review survivors with 'mutmut show <id>'${NC}"
        echo -e "${YELLOW}Apply a mutation with 'mutmut apply <id>' to see changes${NC}\n"
    else
        echo -e "\n${GREEN}✅ All mutations killed! Excellent test coverage.${NC}\n"
    fi
fi

# Open HTML report
if command -v open &> /dev/null; then
    echo -e "${GREEN}Opening HTML report...${NC}"
    open htmlmut/index.html
elif command -v xdg-open &> /dev/null; then
    xdg-open htmlmut/index.html
fi

echo -e "${GREEN}Done!${NC}"
