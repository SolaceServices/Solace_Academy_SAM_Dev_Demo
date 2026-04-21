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

// ===== CLEAR INBOX =====
app.post('/clear', (req, res) => {
  const count = emails.length;
  emails.length = 0;
  console.log(`🗑️  Inbox cleared (${count} email${count !== 1 ? 's' : ''} removed)`);
  res.json({ status: 'cleared', count });
});

// ===== GET INBOX DASHBOARD =====
app.get('/', (req, res) => {
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Acme Retail - Mock Email Inbox</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #f5f5f5;
          padding: 20px;
        }
        .container { max-width: 800px; margin: 0 auto; }
        header {
          background: white;
          padding: 20px;
          border-radius: 8px;
          margin-bottom: 20px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        h1 { 
          font-size: 24px; 
          margin-bottom: 10px;
          color: #333;
        }
        .count { 
          color: #666; 
          font-size: 14px; 
        }
        .email {
          background: white;
          padding: 15px;
          margin-bottom: 10px;
          border-radius: 8px;
          border-left: 4px solid #f0476c;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          transition: transform 0.2s;
        }
        .email:hover {
          transform: translateX(5px);
        }
        .subject {
          font-weight: 600;
          font-size: 16px;
          margin-bottom: 8px;
          word-break: break-word;
          color: #222;
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
          background: #f9f9f9;
          padding: 10px;
          border-radius: 4px;
        }
        .empty {
          text-align: center;
          padding: 40px;
          color: #999;
          background: white;
          border-radius: 8px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .refresh-note {
          text-align: center;
          color: #999;
          font-size: 12px;
          margin-top: 20px;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <header>
          <h1>📧 Mock Email Inbox</h1>
          <div class="count">${emails.length} email${emails.length !== 1 ? 's' : ''}</div>
        </header>
        <div id="emails">
          ${emails.length === 0 
            ? '<div class="empty">No emails yet. Trigger an incident to see emails appear here!</div>'
            : emails.slice().reverse().map(e => `
              <div class="email">
                <div class="subject">${escapeHtml(e.subject)}</div>
                <div class="meta">To: ${escapeHtml(e.to)} | ${new Date(e.timestamp).toLocaleString()}</div>
                <div class="body">${escapeHtml(e.body)}</div>
              </div>
            `).join('')
          }
        </div>
        <div class="refresh-note">Auto-refreshes every 2 seconds</div>
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

// Helper function to escape HTML
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}

// ===== HEALTH CHECK =====
app.get('/health', (req, res) => {
  res.json({ status: 'ok', emailCount: emails.length });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`\n📧 Mock Email Service running`);
  console.log(`   Inbox: http://localhost:${PORT}`);
  console.log(`   Health: http://localhost:${PORT}/health`);
  console.log(`   API: POST http://localhost:${PORT}/send-email\n`);
});
