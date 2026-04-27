# Course 500: Tooling and Plugins — Mock Email Service Integration

## Overview

In this hands-on course, you'll learn how to extend agent capabilities by attaching new tools to existing agents. You'll add a **mock email service tool** to the IncidentResponseAgent, enabling it to send alert emails when high-severity incidents are detected.

This module demonstrates the plugin lifecycle using real tools already in your SAM environment, then guides you through adding a custom tool step-by-step.

---

## Learning Objectives

By the end of this course, you'll understand:

1. **Plugin Architecture** — What are plugins vs. tools? (Core, Community, Private)
2. **Plugin Lifecycle** — How SAM loads and initializes tools
3. **Attaching Tools** — How to add a new tool to an existing agent
4. **Tool Invocation** — Observing tool inputs, outputs, latency, and errors
5. **Production Migration** — How to swap mock services for real services

---

## Prerequisites

- Completed **Course 300** (Agent Mesh Architecture)
- Familiarity with YAML configuration
- Basic understanding of REST APIs
- PostgreSQL and SAM environment running

---

## Quick Setup

\`\`\`bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/scripts
bash 500-setup.sh /workspaces/Solace_Academy_SAM_Dev_Demo/500-Tooling-Plugins
\`\`\`

**What the setup script does:**

✅ Sets up Solace broker, PostgreSQL, and all agents from Module 300  
✅ **Starts mock email service** on port 3000 (background process)  
✅ **Installs npm dependencies** for the email service (Express.js)  
✅ **Creates Python email tool wrapper** at \`/acme-retail/services/email_tool.py\`  
✅ **Enables scheduler service** in WebUI gateway (for scheduled tasks)  
✅ Seeds test incident data

**What you'll do manually (hands-on learning):**

📝 Add email tool configuration to IncidentResponseAgent YAML  
📝 Update agent instruction to send emails for high-severity incidents  
🧪 Test the integration by triggering incidents  
👀 Observe tool invocation in SAM UI

---

## Verifying Setup

After running the setup script, verify everything is working:

**1. Check SAM is running:**
\`\`\`bash
curl http://localhost:8000/api/v1/health
# Should return: {"status":"healthy"}
\`\`\`

**2. Check email service is running:**
\`\`\`bash
curl http://localhost:3000/health
# Should return: {"status":"ok","emailCount":0}
\`\`\`

**3. Access the email inbox:**
Open your browser to \`http://localhost:3000\` - you should see an empty inbox dashboard.

**4. Check SAM logs for errors:**
\`\`\`bash
tail -50 /workspaces/Solace_Academy_SAM_Dev_Demo/500-Tooling-Plugins/sam/sam.log
\`\`\`

If you see any errors related to the \`EmailTool\` or \`IncidentResponseAgent\`, see the Troubleshooting section below.


---

## What Are Tools and Plugins?

### Tools

**Tools** are capabilities that agents can use to accomplish tasks:

- Query databases → \`SqlDatabaseTool\`
- Send emails → \`EmailTool\`
- Read files → MCP filesystem tool
- Call APIs → Custom HTTP tools
- Create charts → Builtin \`create_chart_from_plotly_config\`

### Plugins

**Plugins** are pre-packaged bundles of tools + configurations + dependencies.

**Plugin Types:**

1. **Core Plugins** — Built into SAM (no installation needed)
   - Example: \`create_chart_from_plotly_config\`, \`create_artifact\`

2. **Community Plugins** — Available in SAM catalog
   - Example: \`sam-sql-database-tool\`, \`sam-rag\`, \`sam-event-mesh-gateway\`
   - Install with: \`sam plugin add agent_name --plugin plugin_name\`

3. **Private Plugins** — Custom tools you build yourself
   - Example: The \`EmailTool\` you'll create in this course
   - Stored in \`/acme-retail/infrastructure/\`

---

## Key Implementation Details

### EmailTool Architecture

The \`EmailTool\` is a Python class that inherits from SAM's \`DynamicTool\` base class. It must implement:

1. **\`tool_name\`** property — The function name the LLM will call (e.g., \`send_alert_email\`)
2. **\`tool_description\`** property — What the tool does (helps LLM decide when to use it)
3. **\`parameters_schema\`** property — Defines the function signature (recipient, subject, body)
4. **\`_run_async_impl()\`** method — Framework entry point (extracts args, calls \`run()\`)
5. **\`run()\`** async method — Your actual implementation (makes HTTP call to email service)

### Critical Import Requirements

SAM tools **must** import types from \`google.genai\`, not \`google.adk\`:

\`\`\`python
# ✅ CORRECT
from google.genai import types as adk_types

# ❌ WRONG (will cause ImportError and prevent agent from loading)
from google.adk import types as adk_types
\`\`\`

This is the same pattern used by all built-in SAM tools (\`web_tools.py\`, \`dynamic_tool.py\`, etc.).

### Mock Email Service

The email service is a simple Express.js server that:
- Listens on port 3000
- Accepts POST requests to \`/send-email\`
- Stores emails in memory (resets on restart)
- Serves a real-time inbox dashboard at \`/\` (auto-refreshes every 2 seconds)
- Provides health check at \`/health\`

**Production Replacement:** In production, you'd swap this for AWS SES, SendGrid, or SMTP. Only the \`service_url\` in the tool config would change.

---

For the complete hands-on walkthrough, learning activities, and production migration guide, see the full Module 500 documentation in the FINAL_MASTER_GUIDE.md file.

**Quick Start Steps:**

1. Run setup script (above)
2. Open \`500-Tooling-Plugins/sam/configs/agents/incident_response_agent_agent.yaml\`
3. Add email tool configuration to the \`tools:\` section
4. Update agent instruction to send emails for high-severity incidents
5. Test using the VS Code task: **Simulate Events → 7️⃣ Email Tool Integration**
6. View emails at: \`http://localhost:3000\`

**Email Tool Configuration to Add:**

\`\`\`yaml
      # NEW: Email alert tool (Module 500)
      - tool_type: python
        component_module: "email_tool"
        component_base_path: "/workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/services"
        class_name: "EmailTool"
        tool_config:
          tool_name: "send_alert_email"
          service_url: "http://localhost:3000"
\`\`\`

**Agent Instruction Addition:**

Add this to the \`instruction:\` section:

\`\`\`yaml
        When creating high-severity incidents (severity='high'):
        1. Create the incident record using the incidents_db tool
        2. After successful creation, use send_alert_email to notify admin@acme.com
        3. Email format:
           - Recipient: admin@acme.com
           - Subject: [ALERT] High Priority: {incident_title}
           - Body: Include incident_id, severity, type, title, and description
\`\`\`

---

## Troubleshooting

### SAM Won't Start / IncidentResponseAgent Fails to Load

**Symptom:** SAM shuts down immediately after startup, or logs show:
\`\`\`
ERROR ... Failed to load tool config ... EmailTool ... cannot import name 'types' from 'google.adk'
ERROR ... IncidentResponseAgent ... Error during async initialization
\`\`\`

**Cause:** The \`EmailTool\` has an incorrect import statement.

**Fix:** Verify that \`/acme-retail/services/email_tool.py\` has the **correct import**:

\`\`\`python
# CORRECT:
from google.genai import types as adk_types

# WRONG (will cause ImportError):
from google.adk import types as adk_types
\`\`\`

If you see the wrong import, update it to use \`google.genai\` instead of \`google.adk\`.

---

### Scheduler Service Error During Shutdown

**Symptom:** When SAM shuts down, you see:
\`\`\`
ERROR ... Error stopping scheduler service: 'NoneType' object has no attribute 'call_soon_threadsafe'
\`\`\`

**Impact:** This is a **harmless cleanup error** that occurs during shutdown. It does not affect SAM operation and is not the cause of any startup failures.

**Action:** Ignore this error. If SAM is shutting down unexpectedly, the real issue is likely elsewhere (check for agent initialization errors above this message in the logs).

---

### Email Service Not Responding

**Symptom:** \`curl http://localhost:3000/health\` returns connection refused.

**Fix:**
1. Check if the service is running:
   \`\`\`bash
   ps aux | grep email-service
   \`\`\`

2. Check the service logs:
   \`\`\`bash
   cat /tmp/email-service.log
   \`\`\`

3. Restart manually if needed:
   \`\`\`bash
   cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/services
   node email-service.js </dev/null >/tmp/email-service.log 2>&1 &
   echo $! > /tmp/email-service.pid
   \`\`\`

---

### Agent Doesn't Send Emails

**Symptom:** High-severity incidents are created but no emails appear in the inbox.

**Checklist:**
1. ✅ Did you add the email tool to the agent's YAML configuration?
2. ✅ Did you update the agent instruction to send emails for high-severity incidents?
3. ✅ Is the email service running? (\`curl http://localhost:3000/health\`)
4. ✅ Check SAM logs for tool invocation errors

**Debug:**
\`\`\`bash
# Watch SAM logs in real-time
tail -f /workspaces/Solace_Academy_SAM_Dev_Demo/500-Tooling-Plugins/sam/sam.log | grep -i "email\|incident"
\`\`\`

---

## Reference: Complete Tutorial

For the step-by-step tutorial with detailed explanations, see `/docs/FINAL_MASTER_GUIDE.md` → **Module 500: Tooling and Plugins — Mock Email Service Integration**

That section includes:
- Part 1: Observe Existing Plugins (Conceptual — 10 min)
- Part 2: Mock Email Service Architecture (Overview — 5 min)
- Part 3: Add Email Tool to Agent (Hands-On — 15 min)
- Part 4: Test the Integration (Hands-On — 20 min)
- Part 5: Observe Tool Invocation (Observational — 10 min)
- Part 6: Production Considerations (Discussion — 10 min)
- Troubleshooting Guide
- Key Takeaways

**Congratulations!** You're extending agent capabilities with custom tools. This is the foundation for building production-ready agentic systems! 🎉
