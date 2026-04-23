const express = require('express');
const app = express();

app.use(express.json());

const emails = []; // All emails stored in memory

// ===== SEND EMAIL =====
app.post('/send-email', (req, res) => {
  const { recipient, subject, body } = req.body;

  if (!recipient || !subject || !body) {
    return res.status(400).json({
      error: 'Missing required fields: recipient, subject, body'
    });
  }

  const email = {
    id: `email_${Date.now()}`,
    timestamp: new Date().toISOString(),
    to: recipient,
    subject: subject,
    body: body
  };

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

// ===== GET EMAILS (JSON) =====
app.get('/emails', (req, res) => {
  res.json(emails.slice().reverse());
});

// ===== GET INBOX DASHBOARD =====
app.get('/', (req, res) => {
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Acme Inbox</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f0f0f0;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }

    /* ── Top bar ── */
    .topbar {
      background: #0078d4;
      color: white;
      padding: 10px 16px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
    .topbar .logo { font-size: 18px; font-weight: 700; }
    .topbar .badge {
      background: rgba(255,255,255,0.25);
      border-radius: 10px;
      font-size: 11px;
      padding: 2px 8px;
      font-weight: 600;
    }
    .topbar .spacer { flex: 1; }
    .topbar .clear-btn {
      background: rgba(255,255,255,0.15);
      color: white;
      border: 1px solid rgba(255,255,255,0.35);
      border-radius: 4px;
      font-size: 12px;
      padding: 4px 12px;
      cursor: pointer;
    }
    .topbar .clear-btn:hover { background: rgba(255,255,255,0.25); }

    /* ── Two-pane layout ── */
    .panes { display: flex; flex: 1; overflow: hidden; }

    /* ── Left: email list ── */
    .email-list {
      width: 300px;
      flex-shrink: 0;
      background: #fafafa;
      border-right: 1px solid #ddd;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .list-header {
      padding: 10px 14px 8px;
      font-size: 11px;
      font-weight: 700;
      color: #888;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border-bottom: 1px solid #e8e8e8;
      flex-shrink: 0;
    }
    .list-scroll { flex: 1; overflow-y: auto; }
    .email-row {
      padding: 10px 14px;
      border-bottom: 1px solid #efefef;
      cursor: pointer;
      border-left: 3px solid transparent;
    }
    .email-row.unread { background: #fff; border-left-color: #0078d4; }
    .email-row.selected { background: #e6f2fb; border-left-color: #0078d4; }
    .email-row:hover:not(.selected) { background: #f0f0f0; }
    .row-subject {
      font-size: 13px;
      font-weight: 700;
      color: #1a1a1a;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-bottom: 3px;
    }
    .email-row:not(.unread) .row-subject { font-weight: 400; color: #444; }
    .row-meta {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: #888;
      margin-bottom: 3px;
    }
    .row-preview {
      font-size: 11px;
      color: #aaa;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .list-empty {
      padding: 30px 14px;
      font-size: 13px;
      color: #bbb;
      text-align: center;
    }

    /* ── Right: reading pane ── */
    .reading-pane {
      flex: 1;
      background: white;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .reading-header {
      padding: 16px 20px 12px;
      border-bottom: 1px solid #e8e8e8;
      flex-shrink: 0;
    }
    .reading-subject {
      font-size: 18px;
      font-weight: 600;
      color: #1a1a1a;
      margin-bottom: 8px;
      word-break: break-word;
    }
    .reading-meta { font-size: 12px; color: #888; display: flex; gap: 16px; flex-wrap: wrap; }
    .reading-meta span strong { color: #555; }
    .reading-body {
      flex: 1;
      padding: 20px;
      overflow-y: auto;
      font-size: 14px;
      line-height: 1.7;
      color: #333;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .reading-empty {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #ccc;
      gap: 10px;
    }
    .reading-empty .icon { font-size: 40px; }
    .reading-empty p { font-size: 14px; }
  </style>
</head>
<body>

  <div class="topbar">
    <span class="logo">📬 Acme Inbox</span>
    <span class="badge" id="unread-badge" style="display:none"></span>
    <span class="spacer"></span>
    <button class="clear-btn" onclick="clearInbox()">Clear All</button>
  </div>

  <div class="panes">

    <div class="email-list">
      <div class="list-header">Inbox</div>
      <div class="list-scroll" id="email-list">
        <div class="list-empty">No emails yet.</div>
      </div>
    </div>

    <div class="reading-pane" id="reading-pane">
      <div class="reading-empty">
        <div class="icon">📭</div>
        <p>Select an email to read</p>
      </div>
    </div>

  </div>

  <script>
    const escapeHtml = s => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
    const preview = body => body.replace(/\\n/g,' ').replace(/\\s+/g,' ').slice(0, 80);
    const formatTime = iso => new Date(iso).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
    const formatFull = iso => new Date(iso).toLocaleString();

    let knownIds = new Set();
    let unreadIds = new Set();
    let selectedId = null;
    let allEmails = [];

    function renderList() {
      const list = document.getElementById('email-list');
      if (allEmails.length === 0) {
        list.innerHTML = '<div class="list-empty">No emails yet. Trigger an incident to see emails appear here!</div>';
        return;
      }
      list.innerHTML = allEmails.map(e => {
        const isUnread = unreadIds.has(e.id);
        const isSelected = e.id === selectedId;
        const cls = ['email-row', isUnread ? 'unread' : '', isSelected ? 'selected' : ''].filter(Boolean).join(' ');
        return \`<div class="\${cls}" onclick="selectEmail('\${e.id}')" data-id="\${e.id}">
          <div class="row-subject">\${escapeHtml(e.subject)}</div>
          <div class="row-meta"><span>\${escapeHtml(e.to)}</span><span>\${formatTime(e.timestamp)}</span></div>
          <div class="row-preview">\${escapeHtml(preview(e.body))}</div>
        </div>\`;
      }).join('');
    }

    function renderReading() {
      const pane = document.getElementById('reading-pane');
      if (!selectedId) {
        pane.innerHTML = '<div class="reading-empty"><div class="icon">📭</div><p>Select an email to read</p></div>';
        return;
      }
      const e = allEmails.find(x => x.id === selectedId);
      if (!e) {
        pane.innerHTML = '<div class="reading-empty"><div class="icon">📭</div><p>Select an email to read</p></div>';
        return;
      }
      pane.innerHTML = \`
        <div class="reading-header">
          <div class="reading-subject">\${escapeHtml(e.subject)}</div>
          <div class="reading-meta">
            <span><strong>To:</strong> \${escapeHtml(e.to)}</span>
            <span><strong>Received:</strong> \${formatFull(e.timestamp)}</span>
          </div>
        </div>
        <div class="reading-body">\${escapeHtml(e.body)}</div>
      \`;
    }

    function updateBadge() {
      const badge = document.getElementById('unread-badge');
      const count = unreadIds.size;
      if (count > 0) {
        badge.textContent = count + ' unread';
        badge.style.display = '';
      } else {
        badge.style.display = 'none';
      }
    }

    function selectEmail(id) {
      selectedId = id;
      unreadIds.delete(id);
      renderList();
      renderReading();
      updateBadge();
    }

    async function clearInbox() {
      await fetch('/clear', { method: 'POST' });
      allEmails = [];
      knownIds = new Set();
      unreadIds = new Set();
      selectedId = null;
      renderList();
      renderReading();
      updateBadge();
    }

    async function poll() {
      try {
        const res = await fetch('/emails');
        const emails = await res.json();
        // Track new arrivals as unread
        emails.forEach(e => {
          if (!knownIds.has(e.id)) {
            knownIds.add(e.id);
            unreadIds.add(e.id);
          }
        });
        allEmails = emails;
        renderList();
        updateBadge();
      } catch (_) {}
    }

    poll();
    setInterval(poll, 2000);
  </script>

</body>
</html>`;
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
  console.log(`\n📬 Acme Inbox running`);
  console.log(`   Inbox: http://localhost:${PORT}`);
  console.log(`   Health: http://localhost:${PORT}/health`);
  console.log(`   API: POST http://localhost:${PORT}/send-email\n`);
});
