# Course 200: Agent Mesh — Orchestration

## Overview

This course explores the **Orchestrator Agent** — the central coordination component in Solace Agent Mesh. You'll learn how the orchestrator manages workflows, routes tasks between agents, and maintains state through artifacts.

By the end of this course, you'll understand:
- What the orchestrator does and why it's essential
- The five orchestration patterns (sequential, parallel, conditional, event-driven, human-in-the-loop)
- How to use projects, prompts, and artifacts effectively

## Prerequisites

- Completed course **100-Environment-Installation**
- A working SAM installation with `.env.config` file created
- Basic understanding of AI agents and LLMs

## Quick Setup

We've included some setup automation to make our lives easier going forward, so as long as you've completed course `100-Environment-Installation` and created a `.env.config` file, setting up your environment this time is much simpler. 

At the bottom of your code editor, click the `Run Course Setup` button, then select `200-Orchestration` from the drop down list. 
#### This will:
- automatically activate the virtual environment
- install the dependencies
- initalize sam using the configurations we added to the `.env.config` file previously.


Once it's running, access the Web UI by naigating to the "Ports" tab and click the web icon next to port `8000`

## What is the Orchestrator Agent?

The **Orchestrator** is the central coordination agent in Solace Agent Mesh. When you send a message through the Web UI, the Orchestrator receives it and decides what to do.

### The Orchestrator's 3 Main Responsibilities

#### 1. Define Workflow Structure
The orchestrator determines which agents will be involved and how artifacts move between them.

**Example**: A user asks for a comprehensive sales report. The orchestrator might structure a workflow where:
- **Agent A** pulls sales data from the database
- **Agent B** analyzes trends
- **Agent C** generates visualizations
- **Agent D** writes the executive summary

#### 2. Handle Routing
The orchestrator decides which agent runs and in what order. This can be:
- **Sequential** — one agent runs, then the next, then the next
- **Parallel** — multiple agents run simultaneously
- **Conditional** — routing depends on intermediate results
- **Event-driven** — triggered by external events

#### 3. Keep Track of State
Agent outputs are stored as **artifacts**, and those artifacts can be used to inform decisions later in the workflow.

**Example**: If Agent A returns a "high risk" classification, the orchestrator might route to Agent X instead of Agent Y.

### Dynamic Routing: The Key Mechanic

Instead of following hardcoded steps, the orchestrator makes **runtime decisions** based on:
- What data was returned
- What state currently exists
- Whether an event was triggered

This makes workflows **adaptive** rather than rigid.

## Orchestrator vs. Regular Agents

You might wonder: *Can't agents communicate directly with each other? Why do we need an orchestrator?*

### What Regular Agents Do
- Interpret prompts
- Apply logic
- Generate outputs
- Can collaborate via agent-to-agent communication (A2A protocol)

**But**: They don't manage the overall workflow or decide what happens before/after their task.

### What the Orchestrator Does Differently
The orchestrator operates at a **system level**. It has visibility across the entire workflow and knows what capabilities are available.

When a user makes a request, the orchestrator analyzes it and decides:

1. **Can a single specialized agent handle this?** → Delegate to that agent
2. **Does this need multiple agents working together?** → Coordinate a multi-agent workflow
3. **Is this something I can handle directly?** → Execute it myself

### Model Flexibility

SAM doesn't tie you to a specific model provider. Different agents can use different LLMs:
- Orchestrator might use GPT-5
- Knowledge agent might use Claude 4.5 Sonnet
- Data extraction agent might use a smaller, faster model

The orchestrator doesn't care which model each agent uses — the workflow logic stays the same.

## The 5 Orchestration Patterns

Understanding these patterns helps you design better workflows and predict how the orchestrator will behave.

### 1. Sequential Orchestration

**Definition**: One agent runs, produces an artifact, and that artifact becomes the input for the next agent.

**When to Use**:
- Each step genuinely depends on the previous one
- The logic is predictable
- Order matters (transform → enrich → validate → summarize)

**Example Workflow**:
```
User Request
    ↓
Agent A: Extract data from database
    ↓ (Artifact: raw_data)
Agent B: Validate and clean data
    ↓ (Artifact: clean_data)
Agent C: Analyze trends
    ↓ (Artifact: analysis_results)
Agent D: Generate summary report
    ↓ (Artifact: final_report)
User Response
```

**Characteristics**:
- Clean, linear progression
- Easy to reason about
- No parallelism
- Each step waits for the previous

### 2. Parallel Orchestration

**Definition**: The orchestrator sends the same artifact to multiple agents simultaneously. Once they all finish, their outputs are combined.

**When to Use**:
- You want multiple perspectives on the same input
- Agents work independently (no dependencies)
- Speed matters (parallel execution is faster)

**Example Workflow**:
```
User Request: "Analyze this customer complaint"
    ↓
    ├─→ Sentiment Agent: Determines emotional tone
    ├─→ Category Agent: Classifies complaint type
    ├─→ Risk Agent: Assesses escalation risk
    └─→ Action Agent: Recommends next steps
         ↓
    (All outputs combined)
         ↓
User Response: Multi-dimensional analysis
```

**Characteristics**:
- Faster than sequential (agents run concurrently)
- Each agent sees the same input
- Outputs are independent
- Orchestrator combines results at the end

### 3. Conditional Orchestration

**Definition**: The orchestrator makes decisions at runtime based on what's in the artifact.

**When to Use**:
- The workflow path depends on intermediate results
- Different inputs require different processing
- You need adaptive, intelligent routing

**Example Workflow**:
```
User Request: "Process this order"
    ↓
Classifier Agent: Determines order type
    ↓ (Artifact: order_classification)
    ├─ If "standard" → Standard Processing Agent
    ├─ If "bulk" → Bulk Processing Agent
    ├─ If "international" → International Agent
    └─ If "high_risk" → Fraud Review Agent
         ↓
    (Appropriate handler processes)
         ↓
User Response
```

**Characteristics**:
- Makes the system adaptive
- Routing is data-driven
- Different paths for different scenarios
- Can include confidence thresholds

### 4. Event-Driven Orchestration

**Definition**: Workflows are triggered by events, not just user requests.

**When to Use**:
- You need to react to system changes automatically
- Integration with real-time event streams
- Proactive automation (not just reactive responses)

**Example Workflow**:
```
External System: Inventory drops below threshold
    ↓ (Event: inventory_low)
Orchestrator: Detects event and starts workflow
    ↓
Agent A: Calculate reorder quantity
    ↓ (Artifact: reorder_recommendation)
Agent B: Check supplier availability
    ↓ (Artifact: supplier_options)
Agent C: Generate purchase order
    ↓ (Artifact: purchase_order)
Orchestrator: Publishes order to procurement system
```

**Characteristics**:
- Workflow starts without user action
- Integrates naturally with event-driven architectures
- Enables proactive automation
- **This is what makes SAM powerful in production environments**

### 5. Human-in-the-Loop Orchestration

**Definition**: The orchestrator runs automated steps up to a certain point, then pauses for human review before continuing.

**When to Use**:
- Full automation isn't acceptable or appropriate
- High-stakes decisions require human judgment
- Regulatory compliance requires human approval
- Quality control and oversight are critical

**Example Workflow**:
```
User Request: "Draft a press release about our Q4 earnings"
    ↓
Agent A: Generate initial draft based on financial data
    ↓ (Artifact: draft_press_release)
Orchestrator: PAUSE — Send to human for review
    ↓
Human Reviews: Approves / Edits / Rejects
    ↓ (Artifact: approved_press_release)
Orchestrator: Resume workflow
    ↓
Agent B: Format for distribution
    ↓ (Artifact: formatted_release)
Agent C: Schedule publication
    ↓
Orchestrator: Publish to distribution channels
```

**Characteristics**:
- Combines AI efficiency with human judgment
- Workflow pauses at defined checkpoints
- Human can approve, edit, or reject artifacts
- System continues with updated state after human input
- Critical for compliance, legal, financial, or sensitive operations

**Implementation Pattern**:
- Agent generates artifact (draft, recommendation, analysis)
- Orchestrator stores artifact and sends notification
- Human reviews via UI, API, or external system
- Human provides feedback (approve/edit/reject)
- Orchestrator incorporates feedback and continues

**Example Use Cases**:
- **Legal Documents**: AI drafts contract, lawyer reviews before sending
- **Financial Approvals**: AI recommends investment, CFO approves before execution
- **Content Moderation**: AI flags content, human makes final moderation decision
- **Medical Diagnosis**: AI suggests diagnosis, doctor reviews and confirms
- **Pricing Changes**: AI calculates optimal price, manager approves before deployment

**Benefits**:
- Maintains human oversight for critical decisions
- Accelerates workflows (AI handles routine parts, humans focus on judgment)
- Reduces risk of autonomous errors in sensitive domains
- Enables gradual automation (start with human approval, remove as confidence grows)
- Provides audit trail with human checkpoints

**Key Insight**: You don't have to choose between automation and oversight — human-in-the-loop orchestration gives you both working together.

## Working with the SAM Web UI

Let's explore the built-in features you'll use throughout the certification.

### The Left-Hand Menu

#### Chat Icon
- Create new chat sessions
- Return to previous conversations
- Each chat maintains its own context

#### Agents Icon
- View all configured agents
- See agent details (tools, configuration, status)
- Right now you should only see "OrchestratorAgent"

#### Projects Icon
- Create logical workspaces
- Group related chat sessions
- Maintain context across multiple conversations

### Creating Your First Project

Let's create a project for this certification series:

1. Click the **Projects** icon
2. Click **"New Project"**
3. Name it: `Solace Academy SAM Demo`
4. Give it a description: `Acme Retail SAM Development`
5. Add project-specific instructions:

```markdown
# Project-Specific Instructions

Keep your responses concise and to-the-point. Focus on delivering actionable insights rather than explanations.

Use bullet points and formatted tables when presenting data. Include visual elements when they enhance understanding.

Format all outputs with executive summaries (1 page max).

Remember that your outputs will inform critical decisions - accuracy and clarity are paramount.
```

These instructions will apply to **all chats** within this project, tailoring responses to your needs.

## Understanding Prompts

**Prompts** are globally reusable instructions that you can save and invoke with shortcuts.

### Why Use Prompts?

Instead of repeating the same instructions every time, save them as prompts for:
- Consistency across workflows
- Faster task execution
- Easy sharing across team members
- Version control of instructions

### Creating a Prompt

Let's create a prompt that lists all available agents and tools:

1. Click the **Prompts** menu
2. Click **"New Prompt"**
3. Name it: `List Agents and Tools`
4. Give it a description: `List of all agents and tools available to the orchestrator`
5. Tag: `No Tag`
6. Chat Shortcut: `list-agents-tools`
7. Add the prompt content:

```markdown
Please provide a full list of all agents and tools available to the orchestrator.

Create this as a downloadable markdown document artifact with the following format:

**Agents:**
- Agent name: brief description

**Tools:**
- Tool name: brief description

Keep descriptions to one line each for easy reference.
```

5. Save the prompt

### Using Prompts in Chat

1. Create a new chat
2. Type `/` in the message box
3. Select your prompt from the dropdown
4. Press enter to send the prompt

The orchestrator will execute the prompt and generate the requested output.

### Prompt Features

- **Edit**: Modify prompts as your needs evolve
- **Export**: Share prompts with team members
- **Version**: Track changes over time
- **Organize**: Group prompts by category or project

## Understanding Artifacts

**Artifacts** are structured outputs generated during a workflow. They're how agents pass information to each other.

### What Counts as an Artifact?

- Generated text or documents
- Extracted data (JSON, CSV, tables)
- Transformed documents
- Analysis results
- Visualizations or charts
- Intermediate processing results

### Why Artifacts Matter

Instead of embedding raw data directly in messages, agents store and reference artifacts that can be:
- **Stored** - Persisted across storage backends (filesystem, cloud, or memory)
- **Scoped** - Isolated by session or shared across agents namespace-wide
- **Managed** - Created, retrieved, and manipulated by agents via built-in tools
- **Shared** - Accessible across multiple agents within the same deployment

### The Orchestrator Uses Artifacts as Shared State

When Agent A produces an artifact, the orchestrator:
1. Stores it in the session
2. Makes it available to downstream agents
3. Can route based on artifact properties
4. Maintains the artifact across the workflow

**Example**:
```
Agent A → produces artifact: { "risk_level": "high", "data": {...} }
Orchestrator → sees "risk_level": "high"
Orchestrator → routes to high-risk handler (not standard handler)
Agent B → receives artifact, performs specialized processing
```

### Viewing Artifacts

When a workflow completes, you'll see artifacts in the chat:
- Click on an artifact to view its contents
- Download artifacts as files
- Reference artifacts in follow-up prompts


## What You've Learned

By completing this course, you now understand:

### Conceptual Knowledge
- The orchestrator is the central coordination agent that manages workflows
- It operates at a system level with visibility across all agents
- Dynamic routing allows adaptive, runtime decision-making
- Five orchestration patterns: sequential, parallel, conditional, event-driven, human-in-the-loop

### Practical Skills
- How to set up a new course module using the setup script
- Creating and configuring projects
- Creating and using reusable prompts
- Understanding artifacts

### Architectural Insights
- Model flexibility: Different agents can use different LLMs
- State management: Artifacts serve as shared state

## Common Patterns You'll See

As you build more complex systems, you'll recognize these patterns:

### Fan-Out, Fan-In
```
Orchestrator → splits task → [Agent A, Agent B, Agent C] (parallel)
              ← gathers results ← [Result A, Result B, Result C]
              → combines into single artifact
```

### Pipeline with Conditional Branching
```
Agent A → validates input
         ↓ (if valid)
Agent B → processes
         ↓ (if high priority)
Agent C → escalates
         ↓ (if normal priority)
Agent D → standard handling
```

### Event-Triggered Cascade
```
Event → triggers orchestrator
       → Agent A (immediate response)
       → Agent B (notification)
       → Agent C (logging)
       → Agent D (analytics update)
```


## Key Takeaways

- **The Orchestrator** is the system-level coordinator
- **Dynamic routing** enables adaptive workflows based on runtime conditions
- **Artifacts are shared state** that flows through the workflow
- **Projects** group related work
- **Prompts** enable reusable instructions
- **Event-driven orchestration** is what makes SAM powerful in production environments
- **The five orchestration patterns:** sequential, parallel, conditional, event-driven, human-in-the-loop 

## Next Steps

In **Course 300: Creating AI Agents**, you'll:
- Build 5 specialized agents for the Acme Retail use case
- Learn 5 different methods for creating agents (catalog, CLI, GUI, Context7, 3rd party integration)
- Integrate agents with tools (SQL databases, MCP servers, file systems)
- Create event gateways that connect agents to real-time events
- Implement agent-to-agent communication (A2A protocol)