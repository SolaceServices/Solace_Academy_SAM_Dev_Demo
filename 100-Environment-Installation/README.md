# Course 100: Agent Mesh — Environment and Installation

## Overview

This course introduces you to Solace Agent Mesh (SAM) and guides you through setting up your development environment. You'll learn what Agent Mesh is, why it's important for enterprise AI initiatives, and how to install and configure it for the first time.

By the end of this course, you'll have a working SAM instance running in your development environment, ready to build event-driven AI agent systems.

## What is Solace Agent Mesh?

Solace Agent Mesh addresses a fundamental challenge in enterprise AI: **most AI agents operate on stale data**.

While AI models are becoming more capable, the real value doesn't necessarily scale with model size alone. The formula for AI value looks like this:

```
AI Value = (AI Technology) + (Context × Integration)
```

In practice:
- **20%** comes from models, algorithms, and generative AI capabilities
- **80%** comes from context and how effectively your systems integrate to deliver that context in real time

Traditional agent orchestration platforms help you define agents, but they don't help those agents operate in a live environment. **Solace Agent Mesh makes agents active participants in your event-driven architecture**, allowing them to:

- React to events as they happen (not through polling)
- Access real-time operational data
- Coordinate across multiple specialized agents
- Integrate with existing enterprise systems

## Course Scenario: Acme Retail

Throughout this certification series, you'll take on the role of **Dave**, a developer at **Acme Retail**. 

Acme Retail is launching a new AI initiative to improve operational awareness and responsiveness across their omnichannel business. Your task is to build a proof-of-concept instance of Solace Agent Mesh that can:

- Answer operational questions in real time
- Integrate data from multiple retail systems (e-commerce, inventory, logistics, policy docs)
- React automatically to disruptions as they occur (shipment delays, low inventory, system errors)

## What You'll Build

The overall system will consist of:
- **5 specialized agents**, each responsible for a specific domain
- **Event gateways** that connect agents to real-time events
- **An orchestrator** that routes requests and combines responses
- **An event mesh** that enables real-time communication

In this first course, you'll focus on:
- Understanding the repository structure
- Installing SAM
- Configuring your environment
- Running SAM for the first time

## Prerequisites

Before you begin, you'll need:

- **Python 3.10.16+** (this has been pre-installed in the devcontainer)
- **pip** or **uv** (this has been pre-installed in the devcontainer)
- **Operating System**: macOS, Linux, or Windows via WSL (handled by devcontainer)
- **LLM API key** from a major provider (OpenAI, Anthropic, Google, etc.)

**Recommended LLM**: Claude 4.5 Sonnet, GPT-5, or Gemini-3 for best results. Older models may encounter issues not covered in the course.

## Development Environment Options

### Option 1: GitHub Codespaces (Recommended)

The easiest way to complete this series:

1. Go to the GitHub repository (link provided in course materials)
2. Click the green **"Code"** button
3. Click the **"Codespaces"** tab
4. Choose **"Create codespace on main"**
5. Wait for initialization (first launch takes a few minutes)
6. Access **View → Command Palette** (Cmd/Ctrl + Shift + P) → "View creation logs" to monitor progress

Once initialized, you'll see the project files on the left and a terminal at the bottom.

### Option 2: Local Development with Docker

If you can't access GitHub Codespaces:

1. Ensure **Docker Desktop** is installed and running
2. Clone the repository: `git clone <repo-url>`
3. Open the project in **Visual Studio Code**
4. Install the **"Dev Containers"** extension
5. Select **"Reopen in Container"** when prompted
6. If prompted about host requirements, increase Docker resource settings
7. Wait for the container to build

The experience is identical to Codespaces once the container is running.

## Repository Structure

The repository is organized into three categories:

### 1. Environment Configurations
- `.devcontainer/` — Codespace/container configuration
- `.vscode/` — VS Code tasks and settings

**You don't need to modify these.** They ensure everyone gets the same environment.

### 2. Course Directories
Each numbered directory maps to a specific course:

```
100-Environment-Installation/     ← You are here
200-Orchestration/
300-Agents/
400-Workflows/
500-Tooling-Plugins/
600-Troubleshooting/
700-System-Design/
```

You'll work inside the directory that corresponds to the course you're taking.

### 3. Supporting Assets
- `acme-retail/` — Shared data, scripts, tests, documentation
  - `data/knowledge/` — Documents for the RAG agent
  - `data/seed-data/` — PostgreSQL seed data (orders, inventory, incidents, logistics)
  - `scripts/` — Setup and automation scripts
  - `tests/` — Automated tests framework
  - `infrastructure/` — Docker services, MCP servers, external agents
- `.env.config` — Shared environment variables (gitignored)

**You don't need to modify these.** They are boilerplate infrastructure.


## Installation Steps

### Step 1: Navigate to the Course Directory

```bash
cd 100-Environment-Installation/sam
```

### Step 2: Create a Python Virtual Environment

```bash
python3 -m venv .venv
```

### Step 3: Activate the Virtual Environment

```bash
source .venv/bin/activate
```

**Important**: Anytime you open a **new terminal**, you'll need to:
1. Navigate into the `sam` directory
2. Re-activate the virtual environment

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `solace-agent-mesh` (core framework)
- Other required dependencies

### Step 5: Initialize SAM

```bash
sam init
```

When prompted: **"Would you like to configure your project through a web interface in your browser? [Y/n]:"**

Answer: **y**

### Step 6: Configure SAM via Web Interface

The configuration portal will open in your browser. Choose **Advanced Setup** and configure:

**Namespace & Broker**:
- Project Namespace: `Solace-Academy-SAM-Demo`
- Broker Type: `Existing Solace PubSub+ broker`
- Broker URL: `ws://localhost:8008`
- VPN Name: `default`
- Username: `admin`
- Password: `admin`

**LLM Configuration**:
- LLM Provider: Your provider (e.g., "OpenAI Compatible Provider")
- LLM Endpoint URL: Your endpoint (e.g., `https://api.openai.com/v1` or custom)
- LLM API Key: Your API key
- LLM Model Name: Your model (e.g., `claude-4-5-sonnet`, `gpt-5`)

**Web UI Configuration**:
- Session Secret Key: Create a secure random key

Click **"Initialize Project"** when ready, then close the browser tab.

### Step 7: Save Configuration for Reuse

To make things easier in the following courses, we've included some custom automation to avoid having to repeat this setup for each course:

1. Create a file called `.env.config` at the **root level** of the repository
2. Copy all values from `100-Environment-Installation/sam/.env`
3. Paste them into `.env.config`

This allows all course modules to reuse your configuration automatically. We'll go through how to use it in the next course.

### Step 8: Verify Installation

After initialization completes, you should see this structure:

```
100-Environment-Installation/sam/
├── .env                           ← Your environment config
├── configs/
│   ├── agents/
│   │   └── main_orchestrator.yaml
│   ├── gateways/
│   │   └── webui.yaml
│   ├── logging_config.yaml
│   └── shared_config.yaml
├── requirements.txt
├── src/
├── sam.log
└── .venv/
```

### Step 9: Run SAM

```bash
sam run
```

You should see output indicating SAM is starting up.

### Step 10: Access the Web UI

1. Go to the **"Ports"** tab in VS Code
2. Click the **web icon** next to port **8000**
3. The SAM Web UI will open in your browser

Alternatively, visit: `http://127.0.0.1:8000`

## Verifying Your Installation

To confirm everything is working:

1. Open the SAM Web UI
2. Create a new chat
3. Send a test prompt: *"What sort of things can you do?"* or *"In what use cases can Solace Agent Mesh be helpful?"*

If you receive a response, your installation was successful!

## How SAM Works

At this point, you have a **minimal SAM installation** with:

### 1. Orchestrator Agent
- The central coordination agent
- Receives user requests via the Web UI
- Decides how to respond (directly or by delegating to other agents)
- Manages workflow state via artifacts

### 2. Web UI Gateway
- HTTP/SSE gateway that connects the browser to SAM
- Handles user sessions and chat history
- Streams responses back to the UI

### 3. Shared Infrastructure
- **Solace PubSub+ Broker** (localhost:8008) — Event mesh for agent communication
- **PostgreSQL** (localhost:5432) — Stores session data, artifacts, chat history
- **SQLite databases** — Per-agent session storage (e.g., `orchestrator.db`)

## What Comes Out of the Box

Even with a fresh install, SAM provides:

### Projects
Logical workspaces that group related chat sessions. Projects allow you to:
- Maintain context across multiple conversations
- Share artifacts between chats in the same project
- Apply project-specific instructions

### Prompts
Globally reusable instructions that you can save and invoke with shortcuts. Instead of repeating instructions, save them as prompts for easy reuse.

### Artifacts
Structured outputs generated during workflows:
- Generated text
- Extracted data
- Transformed documents
- Results passed between agents

The orchestrator uses artifacts as "shared state" — instead of passing raw text between agents, workflows exchange artifacts which can be validated, stored, or reused.

## Troubleshooting

### Issue: "Module not found" errors
**Solution**: Ensure you've activated the virtual environment: `source .venv/bin/activate`

### Issue: Port 8000 already in use
**Solution**: Stop any other SAM instances: `pkill -f "sam run"`

### Issue: LLM connection errors
**Solution**: 
- Verify your API key is correct
- Check your endpoint URL
- Ensure your model name matches the provider's format

### Issue: Codespace creation fails
**Solution**: 
- Check GitHub Codespaces quota
- Try "Rebuild Container" from the Command Palette
- Fall back to local Docker development


## Key Takeaways

- **SAM makes AI agents event-driven participants** in your enterprise architecture
- The **80/20 rule** applies: context and integration matter more than raw model capability
- A **minimal SAM installation** includes an orchestrator, web UI gateway, and supporting infrastructure
- The **`.env.config` pattern** allows configuration reuse across all course modules
- **Projects**, **Prompts**, and **Artifacts** are core SAM concepts you'll use throughout the certification

## Next Steps

In **Course 200: Orchestration**, you'll:
- Explore the Orchestrator Agent in detail
- Learn about orchestration patterns (sequential, parallel, conditional, event-driven)
- Understand how workflows are structured
- Create your first project and prompts

Your SAM installation is now ready for the next course!