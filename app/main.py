from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.tasks import scrape_keyword_task

app = FastAPI(title="SEO Rank Finder API")

# --- 1. Pydantic Models ---
class SearchRequest(BaseModel):
    keyword: str
    proxy: Optional[str] = None

# --- 2. API Endpoints ---
@app.post("/api/v1/search")
async def create_search_task(request: SearchRequest):
    task = scrape_keyword_task.delay(request.keyword, request.proxy)
    return {"job_id": task.id, "status": "Queued"}

@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(job_id: str):
    task = AsyncResult(job_id, app=celery_app)
    
    if not task.ready():
        return {"job_id": job_id, "status": "Processing"}
    
    if task.successful():
        return {
            "job_id": job_id,
            "status": "Completed",
            "data": task.result
        }
    else:
        return {
            "job_id": job_id,
            "status": "Failed",
            "error": str(task.result)
        }

# --- 3. Web Dashboard ---
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>SEO Rank Tracker</title>
      <style>
        * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: #0f172a; color: #f8fafc; display: flex; justify-content: center; padding: 40px 20px; margin: 0; }
        .container { width: 100%; max-width: 800px; }
        .card { background: #1e293b; border-radius: 12px; padding: 28px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); border: 1px solid #334155; }
        h1 { margin-top: 0; font-size: 24px; color: #38bdf8; }
        .form-group { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
        .full-width { grid-column: 1 / -1; }
        label { font-size: 13px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
        input { background: #0f172a; border: 1px solid #475569; border-radius: 8px; padding: 12px 16px; color: #fff; font-size: 15px; outline: none; }
        input:focus { border-color: #38bdf8; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        button { background: #0284c7; color: white; border: none; padding: 14px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: 0.2s; margin-top: 8px; width: 100%; }
        button:hover { background: #0369a1; }
        button:disabled { background: #475569; cursor: not-allowed; }
        
        .btn-secondary { background: #334155; margin-top: 24px; display: none; }
        .btn-secondary:hover { background: #475569; }
        
        #status-area { margin-top: 20px; font-size: 14px; text-align: center; color: #94a3b8; display: none; }
        #end-message { margin-top: 24px; font-size: 14px; text-align: center; color: #10b981; display: none; font-weight: 600; }
        
        .badge-box { margin-top: 24px; padding: 20px; border-radius: 10px; display: none; align-items: center; justify-content: space-between; }
        .badge-found { background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #34d399; }
        .badge-missing { background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #f87171; }
        .rank-number { font-size: 36px; font-weight: 800; }
        .results-list { margin-top: 24px; display: flex; flex-direction: column; gap: 12px; }
        .result-item { background: #0f172a; border: 1px solid #334155; padding: 16px; border-radius: 8px; display: flex; gap: 14px; align-items: flex-start; }
        .result-item.highlight { border-color: #10b981; background: rgba(16, 185, 129, 0.05); }
        .pos { background: #334155; color: #cbd5e1; font-weight: 700; font-size: 13px; border-radius: 6px; padding: 4px 8px; height: fit-content; }
        .pos.highlight { background: #10b981; color: white; }
        .details h3 { margin: 0 0 4px 0; font-size: 16px; }
        .details h3 a { color: #38bdf8; text-decoration: none; }
        .details h3 a:hover { text-decoration: underline; }
        .details .domain { font-size: 12px; color: #64748b; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="card">
          <h1>SEO Rank Finder</h1>
          
          <div class="grid">
            <div class="form-group">
              <label>Search Keyword</label>
              <input type="text" id="keyword" placeholder="search here" onkeydown="if(event.key === 'Enter') runSearch()" />
            </div>
            <div class="form-group">
              <label>Target Word(s)</label>
              <input type="text" id="target_words" placeholder="e.g. Outlet Mall of India, Bhumi World" onkeydown="if(event.key === 'Enter') runSearch()" />
            </div>
            <div class="form-group full-width">
              <label>Proxy URL (Optional - To bypass IP blocks)</label>
              <input type="text" id="proxy" placeholder="http://user:password@ip:port" onkeydown="if(event.key === 'Enter') runSearch()" />
            </div>
          </div>

          <button id="search-btn" onclick="runSearch()">Check SEO Ranking</button>
          <div id="status-area">Submitting search task to Celery...</div>

          <div id="rank-badge" class="badge-box">
            <div>
              <div style="font-size: 13px; text-transform: uppercase; font-weight: 600;" id="badge-title">Top Position</div>
              <div style="font-size: 14px; color: #cbd5e1;" id="badge-desc"></div>
            </div>
            <div class="rank-number" id="rank-val">#--</div>
          </div>

          <div class="results-list" id="results-container"></div>
          
          <button id="load-more-btn" class="btn-secondary" onclick="renderNextPage()">Show 10 More Results</button>
          <div id="end-message">All possible SEO search results displayed.</div>
        </div>
      </div>

      <script>
        let globalResults = [];
        let currentTargetWords = [];
        let displayedCount = 0;
        const PAGE_SIZE = 10;

        async function runSearch() {
          const keyword = document.getElementById('keyword').value.trim();
          const rawTargetWords = document.getElementById('target_words').value;
          const proxy = document.getElementById('proxy').value.trim();
          
          currentTargetWords = rawTargetWords.split(',').map(w => w.trim().toLowerCase()).filter(w => w.length > 0);
          
          const btn = document.getElementById('search-btn');
          const status = document.getElementById('status-area');
          const resultsContainer = document.getElementById('results-container');
          const rankBadge = document.getElementById('rank-badge');
          const loadMoreBtn = document.getElementById('load-more-btn');
          const endMsg = document.getElementById('end-message');

          if (!keyword) return;

          btn.disabled = true;
          status.style.display = 'block';
          status.style.color = '#94a3b8';
          status.innerText = "Queueing background task in Redis...";
          resultsContainer.innerHTML = '';
          rankBadge.style.display = 'none';
          loadMoreBtn.style.display = 'none';
          endMsg.style.display = 'none';
          
          globalResults = [];
          displayedCount = 0;

          try {
            const postRes = await fetch('/api/v1/search', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ keyword: keyword, proxy: proxy || null })
            });
            const postData = await postRes.json();
            const jobId = postData.job_id;

            status.innerText = `Task running (ID: ${jobId.slice(0, 8)}...). Checking results...`;

            const pollInterval = setInterval(async () => {
              const jobRes = await fetch(`/api/v1/jobs/${jobId}`);
              const jobData = await jobRes.json();

              if (jobData.status === 'Completed') {
                clearInterval(pollInterval);
                btn.disabled = false;
                status.style.display = 'none';
                
                globalResults = jobData.data.results || [];
                updateTopBadge();
                renderNextPage();
                
              } else if (jobData.status === 'Failed') {
                clearInterval(pollInterval);
                btn.disabled = false;
                status.style.color = '#ef4444';
                status.innerText = "Task failed: " + (jobData.error || "Unknown error in background worker.");
              }
            }, 1000);

          } catch (err) {
            btn.disabled = false;
            status.style.color = '#ef4444';
            status.innerText = "Error connecting to API.";
          }
        }

        function updateTopBadge() {
          const rankBadge = document.getElementById('rank-badge');
          const rankVal = document.getElementById('rank-val');
          const badgeDesc = document.getElementById('badge-desc');
          
          if (currentTargetWords.length === 0) {
            rankBadge.style.display = 'none';
            return;
          }

          let bestRank = null;
          
          for (let i = 0; i < globalResults.length; i++) {
            const item = globalResults[i];
            const titleLower = item.title.toLowerCase();
            const domainLower = item.domain.toLowerCase();
            
            const isMatch = currentTargetWords.some(word => titleLower.includes(word) || domainLower.includes(word));
            
            if (isMatch) {
              bestRank = i + 1;
              break; 
            }
          }

          rankBadge.style.display = 'flex';
          if (bestRank !== null) {
            rankBadge.className = 'badge-box badge-found';
            rankVal.innerText = `#${bestRank}`;
            badgeDesc.innerText = `Found target match in search results.`;
          } else {
            rankBadge.className = 'badge-box badge-missing';
            rankVal.innerText = 'N/A';
            badgeDesc.innerText = `No target words ranked within top ${globalResults.length} positions.`;
          }
        }

        function renderNextPage() {
          const container = document.getElementById('results-container');
          const loadMoreBtn = document.getElementById('load-more-btn');
          const endMsg = document.getElementById('end-message');
          
          const toDisplay = globalResults.slice(displayedCount, displayedCount + PAGE_SIZE);
          
          toDisplay.forEach((item, idx) => {
            const currentRank = displayedCount + idx + 1;
            const titleLower = item.title.toLowerCase();
            const domainLower = item.domain.toLowerCase();
            
            let isHighlight = false;
            if (currentTargetWords.length > 0) {
              isHighlight = currentTargetWords.some(word => titleLower.includes(word) || domainLower.includes(word));
            }
            
            const card = document.createElement('div');
            card.className = `result-item ${isHighlight ? 'highlight' : ''}`;
            card.innerHTML = `
              <div class="pos ${isHighlight ? 'highlight' : ''}">#${currentRank}</div>
              <div class="details">
                <h3><a href="${item.url}" target="_blank">${item.title}</a></h3>
                <div class="domain">${item.domain}</div>
              </div>
            `;
            container.appendChild(card);
          });
          
          displayedCount += toDisplay.length;
          
          if (displayedCount >= globalResults.length) {
            loadMoreBtn.style.display = 'none';
            if (globalResults.length > 0) {
              endMsg.style.display = 'block';
            }
          } else {
            loadMoreBtn.style.display = 'block';
            endMsg.style.display = 'none';
          }
        }
      </script>
    </body>
    </html>
    """
