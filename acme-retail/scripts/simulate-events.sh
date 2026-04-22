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

get_timestamp() {
    date +%s
}

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

publish_event() {
    local topic="$1"
    local payload="$2"
    local icon="$3"
    
    echo -e "${CYAN}${icon} Publishing:${NC} ${topic}"
    echo -e "${GREEN}   Payload:${NC} ${payload}"
    
    # Publish via Solace REST API
    curl -X POST "http://localhost:9000/TOPIC/${topic}" \
        -u "default:default" \
        -H "Content-Type: application/json" \
        -d "${payload}" > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}   ✓ Published successfully${NC}"
    else
        echo -e "${RED}   ✗ Failed to publish to ${topic}${NC}"
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


scenario_order_fulfillment() {
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  SCENARIO: Order Fulfillment Agent — Full E2E Test     ║${NC}"
    echo -e "${MAGENTA}║  Tests all three event triggers for OrderFulfillment   ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # ── Step 1: Validate a fulfillable order ─────────────────────────
    echo -e "${YELLOW}Step 1: New order — should VALIDATE (Mouse, 185 in stock)${NC}"
    publish_event "acme/orders/created" \
        "{\"order_id\":\"ORD-$(get_timestamp)\",\"items\":[{\"sku\":\"SKU-MOUSE-042\",\"quantity\":2}],\"customer_id\":\"CUST-789\",\"timestamp\":$(get_timestamp)}" \
        "🛒"
    sleep 2

    # ── Step 2: Block an order due to out-of-stock ───────────────────
    echo -e "${YELLOW}Step 2: New order — should BLOCK (Tablet, 0 in stock)${NC}"
    publish_event "acme/orders/created" \
        "{\"order_id\":\"ORD-$(get_timestamp)\",\"items\":[{\"sku\":\"SKU-TABLET-055\",\"quantity\":1}],\"customer_id\":\"CUST-790\",\"timestamp\":$(get_timestamp)}" \
        "🛒"
    sleep 2

    # ── Step 3: Restock the tablet — agent should unblock ORD-2026-004
    echo -e "${YELLOW}Step 3: Inventory restock — should UNBLOCK blocked tablet orders${NC}"
    publish_event "acme/inventory/updated" \
        "{\"sku\":\"SKU-TABLET-055\",\"quantity\":30,\"warehouse\":\"WH-A-103\",\"timestamp\":$(get_timestamp)}" \
        "📦"
    sleep 2

    # ── Step 4: Shipment delay — agent updates order estimated_delivery; IncidentResponseAgent creates incident via acme/logistics/updated
    echo -e "${YELLOW}Step 4: Shipment delay — should UPDATE order estimated_delivery (incident handled by IncidentResponseAgent)${NC}"
    publish_event "acme/logistics/shipment-delayed" \
        "{\"tracking_number\":\"1Z999AA10123456791\",\"delay_hours\":24,\"carrier\":\"ExpressAir Priority\",\"timestamp\":$(get_timestamp)}" \
        "🚚"

    echo ""
    echo -e "${GREEN}✅ Expected outcomes:${NC}"
    echo -e "${GREEN}   Step 1 → acme/orders/decision (validated)${NC}"
    echo -e "${GREEN}   Step 2 → acme/orders/decision (blocked)${NC}"
    echo -e "${GREEN}   Step 3 → acme/orders/decision (ORD-2026-004 unblocked/validated)${NC}"
    echo -e "${GREEN}   Step 4 → acme/orders/decision (ETA updated); acme/incidents/created via IncidentResponseAgent${NC}"
    print_summary
}

scenario_knowledge_query() {
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  Testing: RAG Agent (Knowledge Retrieval)              ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # First verify documents are indexed
    echo -e "${CYAN}📊 Checking document index...${NC}"
    POINT_COUNT=$(curl -s http://localhost:6333/collections/acme-retail-knowledge | grep -o '"points_count":[0-9]*' | cut -d: -f2)
    
    if [ "$POINT_COUNT" -gt 0 ]; then
        echo -e "${GREEN}   ✓ Found $POINT_COUNT document chunks indexed${NC}"
    else
        echo -e "${RED}   ✗ No documents indexed yet${NC}"
        PUBLISH_ERRORS=$((PUBLISH_ERRORS + 1))
        print_summary
        return
    fi
    
    echo ""
    echo -e "${CYAN}📤 Publishing query via event mesh...${NC}"
    
    if
    publish_event "SOLACE_ACADEMY_SAM_DEMO/a2a/orchestrator/request" \
        "{\"task\":\"What is Acme Retail's refund policy?\",\"user\":\"event_test\"}" \
        "🔍"; 
    then
    echo ""
    echo -e "${GREEN}✅ Query sent via event mesh${NC}"
    echo -e "${CYAN}   • Orchestrator routes to RAG agent${NC}"
    echo -e "${CYAN}   • Agent searches $POINT_COUNT document chunks${NC}"
    echo -e "${CYAN}   • Response delivered asynchronously${NC}"
    echo ""
    else 
    echo ""
        echo -e "${RED}✗ Event publish failed${NC}"
    fi
    
    print_summary
}

scenario_inventory_management() {
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║  SCENARIO 3: Inventory Management Agent                ║${NC}"
    echo -e "${MAGENTA}║  Tests restock and write-off event handling             ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # ── Step 1: Supplier restock for out-of-stock item ───────────────
    echo -e "${YELLOW}Step 1: Supplier restock — SKU-TABLET-055 receives 50 units${NC}"
    publish_event "acme/suppliers/restock-received" \
        "{\"item_id\":\"SKU-TABLET-055\",\"quantity_received\":50,\"supplier_id\":\"SUP-001\",\"supplier_name\":\"TechSupply Global\"}" \
        "📦"
    sleep 3

    # ── Step 2: Write-off adjustment ─────────────────────────────────
    echo -e "${YELLOW}Step 2: Write-off — SKU-LAPTOP-002 loses 3 units (damaged)${NC}"
    publish_event "acme/inventory/adjustment" \
        "{\"item_id\":\"SKU-LAPTOP-002\",\"adjustment_type\":\"write_off\",\"quantity_delta\":-3,\"reason\":\"Damaged during warehouse inspection\"}" \
        "📉"

    echo ""
    echo -e "${GREEN}✅ Expected outcomes:${NC}"
    echo -e "${GREEN}   Step 1 → acme/inventory/updated (qty +50, status in_stock — unblocks blocked orders)${NC}"
    echo -e "${GREEN}   Step 2 → acme/inventory/updated (qty -3, status out_of_stock)${NC}"
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
        order-fulfillment)      scenario_order_fulfillment ;;
        inventory-management)   scenario_inventory_management ;;
        knowledge-query)        scenario_knowledge_query ;;
        full-day)               scenario_full_day ;;
        *)
            echo -e "${RED}Unknown scenario: $scenario${NC}"
            echo "Available: order-fulfillment, inventory-management, knowledge-query, full-day"
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
    echo "  ${GREEN}1)${NC} Order Fulfillment        → Order Fulfillment Agent"
    echo "  ${GREEN}2)${NC} Inventory Management     → Inventory Management Agent"
    echo "  ${GREEN}3)${NC} Knowledge Query          → Retail Knowledge (RAG)"
    echo "  ${GREEN}4)${NC} Full Retail Day          → All Agents"
    echo "  ${GREEN}q)${NC} Quit"
    echo ""
}

interactive_mode() {
    while true; do
        show_menu
        read -p "$(echo -e ${CYAN}"Select (1-4, q): "${NC})" choice

        case $choice in
            1) scenario_order_fulfillment ;;
            2) scenario_inventory_management ;;
            3) scenario_knowledge_query ;;
            4) scenario_full_day ;;
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