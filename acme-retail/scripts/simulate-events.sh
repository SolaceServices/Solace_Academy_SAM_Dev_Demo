#!/bin/bash
# Acme Retail Event Simulator with CLI Support
# Can be run interactively or with --scenario flag for VSCode tasks

# Configuration
BROKER_URL="${BROKER_URL:-tcp://localhost:8000}"
VPN_NAME="${VPN_NAME:-default}"
USERNAME="${USERNAME:-default}"
PASSWORD="${PASSWORD:-default}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Track overall success
PUBLISH_ERRORS=0

# Get current timestamp
get_timestamp() {
    date +%s
}

# Check prerequisites before running
check_prerequisites() {
    echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"

    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}✗ Docker is not running. Please start Docker and try again.${NC}"
        exit 1
    fi

    if ! docker ps --format '{{.Names}}' | grep -q "^solace$"; then
        echo -e "${RED}✗ Solace container is not running.${NC}"
        echo -e "${YELLOW}  Run 'Course Setup' first to initialize your environment.${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Prerequisites met${NC}"
    echo ""
}

# Publish event using sdkperf
publish_event() {
    local topic="$1"
    local payload="$2"
    local icon="$3"

    echo -e "${CYAN}${icon} Publishing:${NC} ${topic}"
    echo -e "${GREEN}   Payload:${NC} ${payload}"

    echo "${payload}" | docker exec -i solace /usr/sw/loads/currentload/bin/sdkperf_c \
        -cip="${BROKER_URL}" \
        -cu="${USERNAME}@${VPN_NAME}" \
        -cp="${PASSWORD}" \
        -mt=persistent \
        -mn=1 \
        -mr=1 \
        -msa="${topic}" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}   ✓ Published successfully${NC}"
    else
        echo -e "${RED}   ✗ Failed to publish to ${topic}${NC}"
        echo -e "${YELLOW}   Hint: Check that your Solace broker is running and agents are deployed.${NC}"
        PUBLISH_ERRORS=$((PUBLISH_ERRORS + 1))
    fi

    echo ""
}

# Print summary at the end
print_summary() {
    echo ""
    if [ $PUBLISH_ERRORS -eq 0 ]; then
        echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  ✅ All events published successfully                  ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    else
        echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║  ⚠️  Scenario completed with ${PUBLISH_ERRORS} error(s)               ║${NC}"
        echo -e "${RED}║  Check that your agents are deployed and running       ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
    fi
}

#═══════════════════════════════════════════════════════════════════
# SCENARIO FUNCTIONS
#═══════════════════════════════════════════════════════════════════

scenario_low_stock() {
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  SCENARIO 1: Low Stock Alert Chain                     ║${NC}"
    echo -e "${MAGENTA}║  Agent: Inventory Monitor                              ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    publish_event "acme/inventory/updated" \
        "{\"sku\":\"WIDGET-001\",\"quantity\":15,\"warehouse\":\"WH-EAST\",\"threshold\":10,\"timestamp\":$(get_timestamp)}" \
        "📦"
    sleep 2

    publish_event "acme/inventory/updated" \
        "{\"sku\":\"WIDGET-001\",\"quantity\":8,\"warehouse\":\"WH-EAST\",\"threshold\":10,\"timestamp\":$(get_timestamp)}" \
        "📦"
    sleep 2

    publish_event "acme/inventory/updated" \
        "{\"sku\":\"WIDGET-001\",\"quantity\":3,\"warehouse\":\"WH-EAST\",\"threshold\":10,\"timestamp\":$(get_timestamp)}" \
        "📦"

    echo -e "${GREEN}✅ Expected: acme/inventory/alert/low-stock → acme/incidents/created${NC}"
    print_summary
}

scenario_order_fulfillment() {
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  SCENARIO 2: Order Fulfillment Validation              ║${NC}"
    echo -e "${MAGENTA}║  Agent: Order Fulfillment                              ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    publish_event "acme/orders/created" \
        "{\"order_id\":\"ORD-$(get_timestamp)\",\"items\":[{\"sku\":\"WIDGET-001\",\"quantity\":2}],\"customer_id\":\"CUST-789\",\"timestamp\":$(get_timestamp)}" \
        "🛒"
    sleep 2

    publish_event "acme/orders/created" \
        "{\"order_id\":\"ORD-$(get_timestamp)\",\"items\":[{\"sku\":\"GADGET-202\",\"quantity\":100}],\"customer_id\":\"CUST-790\",\"timestamp\":$(get_timestamp)}" \
        "🛒"

    echo -e "${GREEN}✅ Expected: acme/orders/validated or acme/orders/blocked${NC}"
    print_summary
}

scenario_incident_response() {
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  SCENARIO 3: Multi-Event Incident Creation             ║${NC}"
    echo -e "${MAGENTA}║  Agent: Incident Response                              ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    publish_event "acme/logistics/shipment-delayed" \
        "{\"tracking_number\":\"TRK-$(get_timestamp)\",\"delay_hours\":48,\"carrier\":\"FastShip\",\"timestamp\":$(get_timestamp)}" \
        "🚚"
    sleep 2

    publish_event "acme/pos/system-down" \
        "{\"store_id\":\"STORE-42\",\"location\":\"Downtown\",\"severity\":\"critical\",\"timestamp\":$(get_timestamp)}" \
        "💳"

    echo -e "${GREEN}✅ Expected: acme/incidents/created (multiple)${NC}"
    print_summary
}

scenario_knowledge_query() {
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  SCENARIO 4: Policy Knowledge Retrieval                ║${NC}"
    echo -e "${MAGENTA}║  Agent: Retail Knowledge (RAG)                         ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    echo -e "${YELLOW}ℹ️  This scenario requires A2A query via chat interface${NC}"
    echo "   Ask: 'What is Acme Retail's refund policy?'"
    echo ""

    publish_event "acme/knowledge/document-updated" \
        "{\"document_id\":\"refund_policy_v2\",\"document_path\":\"knowledge/refund_policy.md\",\"timestamp\":$(get_timestamp)}" \
        "📚"

    echo -e "${GREEN}✅ Expected: RAG agent re-indexes document${NC}"
    print_summary
}

scenario_analytics_dashboard() {
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  SCENARIO 5: Real-Time Analytics Aggregation           ║${NC}"
    echo -e "${MAGENTA}║  Agent: Analytics Dashboard                            ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    for i in {1..3}; do
        publish_event "acme/orders/validated" \
            "{\"order_id\":\"ORD-$(get_timestamp)-$i\",\"total_amount\":$((50 + RANDOM % 200)),\"timestamp\":$(get_timestamp)}" \
            "✅"
        sleep 1
    done

    publish_event "acme/analytics/query" \
        "{\"metric\":\"orders_validated_today\",\"correlation_id\":\"QUERY-$(get_timestamp)\",\"timestamp\":$(get_timestamp)}" \
        "📈"

    echo -e "${GREEN}✅ Expected: acme/analytics/response with metrics${NC}"
    print_summary
}

scenario_full_day() {
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  SCENARIO 6: Complete Retail Day Simulation            ║${NC}"
    echo -e "${MAGENTA}║  All Agents Working Together                           ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    echo -e "${YELLOW}🌅 Morning: Opening inventory${NC}"
    publish_event "acme/inventory/updated" \
        "{\"sku\":\"WIDGET-001\",\"quantity\":50,\"warehouse\":\"WH-EAST\",\"timestamp\":$(get_timestamp)}" \
        "📦"
    sleep 2

    echo -e "${YELLOW}☕ Orders arriving${NC}"
    for i in {1..2}; do
        publish_event "acme/orders/created" \
            "{\"order_id\":\"ORD-$(get_timestamp)-$i\",\"items\":[{\"sku\":\"WIDGET-001\",\"quantity\":5}],\"customer_id\":\"CUST-10$i\",\"timestamp\":$(get_timestamp)}" \
            "🛒"
        sleep 1
    done

    echo -e "${YELLOW}🌤️  Afternoon: Inventory depleting${NC}"
    publish_event "acme/inventory/updated" \
        "{\"sku\":\"WIDGET-001\",\"quantity\":8,\"warehouse\":\"WH-EAST\",\"timestamp\":$(get_timestamp)}" \
        "📦"
    sleep 2

    echo -e "${YELLOW}⚠️  Disruptions${NC}"
    publish_event "acme/logistics/shipment-delayed" \
        "{\"tracking_number\":\"TRK-$(get_timestamp)\",\"delay_hours\":24,\"timestamp\":$(get_timestamp)}" \
        "🚚"
    sleep 1

    echo -e "${YELLOW}🔴 Critical low inventory${NC}"
    publish_event "acme/inventory/updated" \
        "{\"sku\":\"WIDGET-001\",\"quantity\":2,\"warehouse\":\"WH-EAST\",\"timestamp\":$(get_timestamp)}" \
        "📦"

    echo -e "${GREEN}✅ Full day simulation complete${NC}"
    print_summary
}

#═══════════════════════════════════════════════════════════════════
# CLI ARGUMENT HANDLING
#═══════════════════════════════════════════════════════════════════

run_scenario_from_cli() {
    local scenario="$1"

    case $scenario in
        low-stock)           scenario_low_stock ;;
        order-fulfillment)   scenario_order_fulfillment ;;
        incident-response)   scenario_incident_response ;;
        knowledge-query)     scenario_knowledge_query ;;
        analytics-dashboard) scenario_analytics_dashboard ;;
        full-day)            scenario_full_day ;;
        *)
            echo -e "${RED}Unknown scenario: $scenario${NC}"
            echo "Available: low-stock, order-fulfillment, incident-response, knowledge-query, analytics-dashboard, full-day"
            exit 1
            ;;
    esac
}

#═══════════════════════════════════════════════════════════════════
# INTERACTIVE MENU
#═══════════════════════════════════════════════════════════════════

show_menu() {
    clear
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║      🏪  Acme Retail Event Simulator  🏪                ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  ${GREEN}1)${NC} Low Stock Alert          → Inventory Monitor"
    echo "  ${GREEN}2)${NC} Order Fulfillment        → Order Fulfillment Agent"
    echo "  ${GREEN}3)${NC} Incident Response        → Incident Response Agent"
    echo "  ${GREEN}4)${NC} Knowledge Query          → Retail Knowledge (RAG)"
    echo "  ${GREEN}5)${NC} Analytics Dashboard      → Analytics Dashboard"
    echo "  ${GREEN}6)${NC} Full Retail Day          → All Agents"
    echo "  ${GREEN}q)${NC} Quit"
    echo ""
}

interactive_mode() {
    while true; do
        show_menu
        read -p "$(echo -e ${CYAN}"Select (1-6, q): "${NC})" choice

        case $choice in
            1) scenario_low_stock ;;
            2) scenario_order_fulfillment ;;
            3) scenario_incident_response ;;
            4) scenario_knowledge_query ;;
            5) scenario_analytics_dashboard ;;
            6) scenario_full_day ;;
            q|Q) exit 0 ;;
            *) echo -e "${RED}Invalid choice${NC}"; sleep 2 ;;
        esac

        read -p "$(echo -e ${YELLOW}"Press Enter..."${NC})"
    done
}

#═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
#═══════════════════════════════════════════════════════════════════

main() {
    check_prerequisites

    if [ "$1" == "--scenario" ] && [ -n "$2" ]; then
        run_scenario_from_cli "$2"
    else
        interactive_mode
    fi
}

main "$@"