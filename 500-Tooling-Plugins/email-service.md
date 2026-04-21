# Email Service for Course Agents

A lightweight, mock email service that runs locally in each student's Codespace. Agents can send "emails" and students can view them in a real-time inbox dashboard.

## Overview

- **Zero student setup**: Automatically starts when Codespace opens
- **No authentication**: Simplified since it's isolated to each Codespace
- **Real-time dashboard**: Auto-refreshing inbox at `http://localhost:3000`
- **Perfect for demos**: Students see emails appear as their agent runs

---

## 1. Email Service Code

Create `email-service.js` in your repo root:

```javascript
const express = require('express');
const app = express();

app.use(express.json());

const emails = []; // All emails stored in memory

// ===== SEND EMAIL =====
app.post('/send-email', (req, res) => {
  const { recipient, subject, body } = req.body;

  // Validate required fields
  if (!recipient || !subject || !body) {
    return res.status(400).json({
      error: 'Missing required fields: recipient, subject, body'
    });
  }

  // Create email object
  const email = {
    id: `email_${Date.now()}`,
    timestamp: new Date().toISOString(),
    to: recipient,
    subject: subject,
    body: body
  };

  // Store email
  emails.push(email);
  console.log(`✅ Email sent to ${recipient}: "${subject}"`);

  res.json({
    status: 'sent',
    messageId: email.id,
    timestamp: email.timestamp
  });
});

// ===== GET INBOX DASHBOARD =====
app.get('/', (req, res) => {
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Inbox</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #f5f5f5;
          padding: 20px;
        }
        .container { max-width: 600px; margin: 0 auto; }
        header {
          background: white;
          padding: 20px;
          border-radius: 8px;
          margin-bottom: 20px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        h1 { font-size: 24px; margin-bottom: 10px; }
        .count { color: #666; font-size: 14px; }
        .email {
          background: white;
          padding: 15px;
          margin-bottom: 10px;
          border-radius: 8px;
          border-left: 4px solid #f0476c;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .subject {
          font-weight: 600;
          font-size: 16px;
          margin-bottom: 8px;
          word-break: break-word;
        }
        .meta {
          font-size: 12px;
          color: #999;
          margin-bottom: 10px;
        }
        .body {
          font-size: 14px;
          line-height: 1.6;
          color: #333;
          white-space: pre-wrap;
          word-break: break-word;
        }
        .empty {
          text-align: center;
          padding: 40px;
          color: #999;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <header>
          <h1>📧 Inbox</h1>
          <div class="count">${emails.length} email${emails.length !== 1 ? 's' : ''}</div>
        </header>
        <div id="emails">
          ${emails.length === 0 
            ? '<div class="empty">No emails yet. Run your test to see emails appear here!</div>'
            : emails.map(e => \`
              <div class="email">
                <div class="subject">\${e.subject}</div>
                <div class="meta">To: \${e.to} | \${new Date(e.timestamp).toLocaleString()}</div>
                <div class="body">\${e.body}</div>
              </div>
            \`).join('')
          }
        </div>
      </div>
      <script>
        // Auto-refresh every 2 seconds
        setInterval(() => location.reload(), 2000);
      </script>
    </body>
    </html>
  `;
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.send(html);
});

// ===== HEALTH CHECK =====
app.get('/health', (req, res) => {
  res.json({ status: 'ok', emailCount: emails.length });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`\n📧 Email service running at http://localhost:${PORT}`);
  console.log(`   View inbox at: http://localhost:${PORT}\n`);
});
```

---

## 2. Configuration Files

### `package.json`

Add or update the `scripts` and `dependencies` sections:

```json
{
  "name": "course-incident-responder",
  "version": "1.0.0",
  "scripts": {
    "start": "node email-service.js"
  },
  "dependencies": {
    "express": "^4.18.2"
  }
}
```

### `.devcontainer/devcontainer.json`

Create this file to auto-start the service:

```json
{
  "name": "Course Environment",
  "image": "mcr.microsoft.com/devcontainers/javascript-node:18",
  "forwardPorts": [3000],
  "portsAttributes": {
    "3000": {
      "label": "Email Inbox",
      "onAutoForward": "notify"
    }
  },
  "postCreateCommand": "npm install && npm start"
}
```

---

## 3. Agent Tool Definition

Add this tool to your agent configuration. The format depends on how you're building the agent:

### Option A: YAML Config (if using Claude Agents or similar)

```yaml
tools:
  - name: send_alert_email
    type: http
    method: POST
    url: http://localhost:3000/send-email
    description: Send an alert email about a high-priority incident
    input_schema:
      type: object
      properties:
        recipient:
          type: string
          description: Email address to send to (e.g., admin@company.com)
        subject:
          type: string
          description: Email subject line (e.g., [ALERT] High Priority Incident)
        body:
          type: string
          description: Email body with incident details
      required:
        - recipient
        - subject
        - body
```

### Option B: Python (if using Claude SDK)

```python
from anthropic import Anthropic

client = Anthropic()

tools = [
    {
        "name": "send_alert_email",
        "description": "Send an alert email when a high-priority incident is detected",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "Email address to send to"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject"
                },
                "body": {
                    "type": "string",
                    "description": "Email body with details"
                }
            },
            "required": ["recipient", "subject", "body"]
        }
    }
]

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=tools,
    messages=[
        {
            "role": "user",
            "content": "Check incidents.json for critical issues and send alerts"
        }
    ]
)

# Handle tool calls
for block in response.content:
    if block.type == "tool_use":
        if block.name == "send_alert_email":
            # Agent called the tool with these inputs
            print(f"Email sent: {block.input}")
```

### Option C: JavaScript (if using Anthropic SDK)

```javascript
const Anthropic = require("@anthropic-ai/sdk");
const axios = require("axios");

const client = new Anthropic();

const tools = [
  {
    name: "send_alert_email",
    description: "Send an alert email when a high-priority incident is detected",
    input_schema: {
      type: "object",
      properties: {
        recipient: {
          type: "string",
          description: "Email address to send to"
        },
        subject: {
          type: "string",
          description: "Email subject"
        },
        body: {
          type: "string",
          description: "Email body with incident details"
        }
      },
      required: ["recipient", "subject", "body"]
    }
  }
];

async function runAgent() {
  const response = await client.messages.create({
    model: "claude-3-5-sonnet-20241022",
    max_tokens: 1024,
    tools: tools,
    messages: [
      {
        role: "user",
        content: "Check incidents.json and alert on critical issues"
      }
    ]
  });

  // Handle tool calls
  for (const block of response.content) {
    if (block.type === "tool_use") {
      if (block.name === "send_alert_email") {
        // Call the email service
        const result = await axios.post("http://localhost:3000/send-email", {
          recipient: block.input.recipient,
          subject: block.input.subject,
          body: block.input.body
        });
        console.log("Email sent:", result.data);
      }
    }
  }
}

runAgent();
```

---

## 4. Agent Instructions

Give your students these instructions:

### For Students Using Claude

> **Step 1**: The email service is already running. You don't need to do anything to start it.
>
> **Step 2**: Add the `send_alert_email` tool to your agent (see tool definition above for your language).
>
> **Step 3**: Tell your agent to check `incidents.json` and send alerts when it finds high-priority incidents.
>
> **Example prompt**:
> ```
> Check the incidents.json file. If you find any incidents with priority "high", 
> send an alert email to admin@company.com with the subject "[ALERT] High Priority: {incident_title}" 
> and the incident details in the body.
> ```
>
> **Step 4**: View your inbox at `http://localhost:3000` and watch emails appear as your agent runs!

### Data Format

Your agent should send emails with this JSON structure:

```json
{
  "recipient": "admin@company.com",
  "subject": "[ALERT] High Priority: Database Connection Failed",
  "body": "Incident: Database Connection Failed\nStatus: open\nSeverity: critical\nTimestamp: 2026-03-30T14:00:00Z"
}
```

### Example `incidents.json`

Students can create this file to test:

```json
[
  {
    "id": "incident_001",
    "title": "Database connection timeout",
    "status": "open",
    "priority": "high",
    "timestamp": "2026-03-30T14:00:00Z"
  },
  {
    "id": "incident_002",
    "title": "Memory usage warning",
    "status": "open",
    "priority": "low",
    "timestamp": "2026-03-30T14:05:00Z"
  }
]
```

---

## 5. Testing the Service

Students can test manually with `curl`:

```bash
curl -X POST http://localhost:3000/send-email \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": "admin@company.com",
    "subject": "Test Alert",
    "body": "This is a test email"
  }'
```

Then visit `http://localhost:3000` to see the email appear.

---

## What Students See

1. **Codespace opens** → service starts automatically (they see nothing, it just works)
2. **They add the tool** → their agent can now call it
3. **They run their test** → agent detects incident and calls the tool
4. **They visit the inbox URL** → emails appear in real-time, auto-refreshing every 2 seconds

---

## File Structure

```
your-repo/
├── .devcontainer/
│   └── devcontainer.json          ← Auto-starts service
├── email-service.js               ← The service (ready to go)
├── package.json                   ← Dependencies
├── incidents.json                 ← Test data (students create/edit)
├── agent.js                       ← Student's agent code
└── email-service.md               ← This file
```

---

## Notes

- All emails are stored in memory and cleared when the service restarts
- No database needed
- No authentication required (it's isolated to each Codespace)
- Service runs automatically when Codespace opens
- Students just need to add the tool definition and tell the agent what to do