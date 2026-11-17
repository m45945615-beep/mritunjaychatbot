"""
Phase 8: Standalone Zero-Dependency Web UI Server.
Runs on native Python standard library without requiring external frameworks.
Usage: python ui/server.py [--port 8501]
"""

import http.server
import json
import logging
import os
import re
import socketserver
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Load .env before importing any src modules ────────────────────────────────
def _load_dotenv():
    env_path = ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=str(env_path), override=False)
        except ImportError:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k, v = k.strip(), v.strip()
                        if k and k not in os.environ:
                            os.environ[k] = v

_load_dotenv()
# ─────────────────────────────────────────────────────────────────────────────

from src.pipeline import RAGPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("UIServer")

# Guardrail Patterns
PII_PATTERNS = [
    r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",  # PAN
    r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b",  # Aadhaar
    r"\b[6-9]\d{9}\b",  # Mobile
    r"\b(?:folio|account|ac)\s*#?[:\s]*\d{6,16}\b",  # Folio
]

ADVISORY_PATTERNS = [
    r"\bshould\s+i\s+(?:buy|invest|sell)\b",
    r"\bwhich\s+(?:fund|scheme)\s+is\s+(?:better|best)\b",
    r"\bwill\s+it\s+(?:beat|give)\b",
    r"\bguaranteed\s+returns?\b",
    r"\bportfolio\s+review\b",
]


def check_pii(query: str) -> bool:
    for pat in PII_PATTERNS:
        if re.search(pat, query, re.IGNORECASE):
            return True
    return False


def check_advisory(query: str) -> bool:
    for pat in ADVISORY_PATTERNS:
        if re.search(pat, query, re.IGNORECASE):
            return True
    return False


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Groww Mutual Fund Facts Assistant</title>
  <style>
    :root {
      --primary: #00D09C;
      --primary-dark: #00B084;
      --bg: #F9FAFB;
      --card-bg: #FFFFFF;
      --text: #1E293B;
      --text-muted: #64748B;
      --border: #E2E8F0;
      --warning-bg: #FFFBEB;
      --warning-border: #FDE68A;
      --warning-text: #92400E;
      --danger-bg: #FEF2F2;
      --danger-border: #FECACA;
      --danger-text: #991B1B;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }
    .container {
      max-width: 900px;
      margin: 0 auto;
    }
    header {
      margin-bottom: 20px;
    }
    h1 {
      font-size: 28px;
      font-weight: 700;
      color: #0F172A;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .tagline {
      font-size: 14px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .disclaimer {
      background: var(--warning-bg);
      border: 1px solid var(--warning-border);
      color: var(--warning-text);
      border-radius: 8px;
      padding: 12px 16px;
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .example-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 20px;
    }
    .chip {
      background: #FFFFFF;
      border: 1px solid var(--border);
      color: var(--text);
      border-radius: 20px;
      padding: 8px 14px;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .chip:hover {
      border-color: var(--primary);
      color: var(--primary-dark);
      background: #F0FDF9;
    }
    .chip.refusal-chip:hover {
      border-color: #EF4444;
      color: #DC2626;
      background: #FEF2F2;
    }
    .chat-window {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      min-height: 380px;
      max-height: 550px;
      overflow-y: auto;
      margin-bottom: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .message {
      margin-bottom: 18px;
      display: flex;
      flex-direction: column;
    }
    .message.user {
      align-items: flex-end;
    }
    .message.assistant {
      align-items: flex-start;
    }
    .bubble {
      max-width: 80%;
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 14px;
    }
    .message.user .bubble {
      background: #0F172A;
      color: #FFFFFF;
      border-bottom-right-radius: 2px;
    }
    .message.assistant .bubble {
      background: #F1F5F9;
      color: var(--text);
      border-bottom-left-radius: 2px;
      border-left: 3px solid var(--primary);
    }
    .bubble.refusal {
      background: var(--danger-bg);
      border: 1px solid var(--danger-border);
      color: var(--danger-text);
      border-left: 3px solid #EF4444;
    }
    .source-badge {
      display: inline-block;
      margin-top: 8px;
      background: #E6FBF5;
      color: #008767;
      border: 1px solid #A7F3D0;
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 600;
      text-decoration: none;
    }
    .source-badge:hover {
      background: var(--primary);
      color: white;
    }
    .meta-line {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .inspector-toggle {
      font-size: 12px;
      color: var(--primary-dark);
      cursor: pointer;
      text-decoration: underline;
      margin-top: 6px;
    }
    .inspector-panel {
      background: #F8FAFC;
      border: 1px dashed var(--border);
      border-radius: 6px;
      padding: 10px;
      margin-top: 8px;
      font-size: 12px;
      font-family: monospace;
      display: none;
      white-space: pre-wrap;
    }
    .input-row {
      display: flex;
      gap: 10px;
    }
    input[type="text"] {
      flex: 1;
      padding: 12px 16px;
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }
    input[type="text"]:focus {
      border-color: var(--primary);
    }
    button.send-btn {
      background: var(--primary);
      color: #FFFFFF;
      border: none;
      border-radius: 8px;
      padding: 0 20px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
    }
    button.send-btn:hover {
      background: var(--primary-dark);
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>📈 Groww Mutual Fund Facts Assistant</h1>
      <p class="tagline">Factual scheme information powered by Modular RAG &amp; Official Public Sources.</p>
    </header>

    <div class="disclaimer">
      ⚠️ <strong>Facts-only. No investment advice.</strong> I answer factual scheme questions only (expense ratio, exit load, lock-in, minimum SIP, riskometer, benchmark, statements).
    </div>

    <div class="example-chips">
      <button class="chip" onclick="askQuestion('What is the expense ratio and exit load of HDFC Flexi Cap Fund?')">📊 Flexi Cap Exit Load &amp; Expense Ratio</button>
      <button class="chip" onclick="askQuestion('What is the lock-in period for HDFC ELSS Tax Saver Fund?')">🔒 ELSS Tax Saver 3-Year Lock-in</button>
      <button class="chip" onclick="askQuestion('How can I download my capital-gains statement?')">📄 How to download statement</button>
      <button class="chip refusal-chip" onclick="askQuestion('Should I invest in HDFC Mid Cap Fund for 5 years?')">🚫 Should I invest in Mid Cap? (Refusal Test)</button>
    </div>

    <div class="chat-window" id="chat">
      <div class="message assistant">
        <div class="bubble">
          👋 Welcome! I am your facts-only Mutual Fund FAQ Assistant. Ask me factual details about HDFC Mutual Fund schemes. Every answer includes a verified official source link.
        </div>
      </div>
    </div>

    <form class="input-row" onsubmit="event.preventDefault(); submitQuery();">
      <input type="text" id="queryInput" placeholder="Ask a factual question (e.g. Expense ratio of HDFC Large Cap)..." autocomplete="off" />
      <button type="submit" class="send-btn" id="sendBtn">Send</button>
    </form>
  </div>

  <script>
    function askQuestion(text) {
      document.getElementById('queryInput').value = text;
      submitQuery();
    }

    async function submitQuery() {
      const input = document.getElementById('queryInput');
      const query = input.value.trim();
      if (!query) return;

      appendMessage('user', query);
      input.value = '';

      const sendBtn = document.getElementById('sendBtn');
      sendBtn.disabled = true;
      sendBtn.textContent = '...';

      try {
        const resp = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: query })
        });
        const data = await resp.json();
        appendAssistantResponse(data);
      } catch (err) {
        appendMessage('assistant', 'Error communicating with assistant server: ' + err);
      } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
      }
    }

    function appendMessage(role, text) {
      const chat = document.getElementById('chat');
      const msgDiv = document.createElement('div');
      msgDiv.className = 'message ' + role;
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = text;
      msgDiv.appendChild(bubble);
      chat.appendChild(msgDiv);
      chat.scrollTop = chat.scrollHeight;
    }

    function appendAssistantResponse(data) {
      const chat = document.getElementById('chat');
      const msgDiv = document.createElement('div');
      msgDiv.className = 'message assistant';

      const bubble = document.createElement('div');
      bubble.className = 'bubble' + (data.is_refusal ? ' refusal' : '');
      bubble.innerHTML = data.answer.replace(/\\n/g, '<br/>');

      if (data.source_url) {
        const badge = document.createElement('a');
        badge.className = 'source-badge';
        badge.href = data.source_url;
        badge.target = '_blank';
        badge.textContent = '🔗 Source: ' + data.source_url;
        bubble.appendChild(document.createElement('br'));
        bubble.appendChild(badge);
      }

      const meta = document.createElement('div');
      meta.className = 'meta-line';
      meta.textContent = '⚡ Latency: ' + data.execution_time_ms + ' ms | Chunks: ' + data.retrieved_chunks_count + ' | ' + data.last_updated;
      bubble.appendChild(meta);

      if (data.stage_info) {
        const toggle = document.createElement('div');
        toggle.className = 'inspector-toggle';
        toggle.textContent = '🔍 View RAG Stage Inspector';
        const panel = document.createElement('div');
        panel.className = 'inspector-panel';
        panel.textContent = JSON.stringify(data.stage_info, null, 2);
        toggle.onclick = () => {
          panel.style.display = panel.style.display === 'block' ? 'none' : 'block';
        };
        bubble.appendChild(toggle);
        bubble.appendChild(panel);
      }

      msgDiv.appendChild(bubble);
      chat.appendChild(msgDiv);
      chat.scrollTop = chat.scrollHeight;
    }
  </script>
</body>
</html>
"""


class StandaloneUIHandler(http.server.SimpleHTTPRequestHandler):
    pipeline = RAGPipeline()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            stats_file = Path("data/chroma_db/collection_stats.json")
            if stats_file.exists():
                self.wfile.write(stats_file.read_bytes())
            else:
                self.wfile.write(json.dumps({"total_documents": 29}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/api/chat":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            data = json.loads(body.decode("utf-8"))
            query = data.get("query", "").strip()

            start_t = time.perf_counter()

            # 1. PII Guardrail
            if check_pii(query):
                res = {
                    "query": query,
                    "answer": "For your security and privacy, never enter personal financial details such as PAN, Aadhaar, account or folio numbers.",
                    "source_url": None,
                    "last_updated": "2026-11-01",
                    "is_refusal": True,
                    "refusal_reason": "pii_detected",
                    "retrieved_chunks_count": 0,
                    "execution_time_ms": round((time.perf_counter() - start_t) * 1000, 2),
                    "stage_info": {"guardrail_trigger": "PII_SANITIZER", "status": "BLOCKED"},
                }
            # 2. Advisory Guardrail
            elif check_advisory(query):
                res = {
                    "query": query,
                    "answer": (
                        "I provide facts only and do not offer investment advice, recommendations, or return predictions. "
                        "You can learn more about mutual fund principles on the official AMFI portal."
                    ),
                    "source_url": "https://www.amfiindia.com/investor-corner/knowledge-center",
                    "last_updated": "2026-11-01",
                    "is_refusal": True,
                    "refusal_reason": "advisory_detected",
                    "retrieved_chunks_count": 0,
                    "execution_time_ms": round((time.perf_counter() - start_t) * 1000, 2),
                    "stage_info": {"guardrail_trigger": "ADVISORY_FILTER", "status": "SAFE_REFUSAL"},
                }
            # 3. RAG Execution
            else:
                retrieval = self.pipeline.retriever.retrieve(query)
                faq_resp = self.pipeline.run(query)

                res = faq_resp.to_dict()
                res["stage_info"] = {
                    "retrieved_chunks": [c.to_dict() for c in retrieval.chunks],
                    "similarity_threshold": retrieval.similarity_threshold,
                    "sufficient_context": retrieval.has_sufficient_context,
                    "top_url": retrieval.top_url,
                }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_error(404, "Endpoint Not Found")


def run_server(port: int = 8501):
    server_address = ("", port)
    httpd = socketserver.TCPServer(server_address, StandaloneUIHandler)
    logger.info(f"Groww Facts Assistant Web UI running at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped.")
        httpd.server_close()


if __name__ == "__main__":
    port = 8501
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)

