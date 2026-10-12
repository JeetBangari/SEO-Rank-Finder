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
        label { font-size: 13px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
        input { background: #0f172a; border: 1px solid #475569; border-radius: 8px; padding: 12px 16px; color: #fff; font-size: 15px; outline: none; }
        input:focus { border-color: #38bdf8; }
        .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }
        button { background: #0284c7; color: white; border: none; padding: 14px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: 0.2s; margin-top: 8px; width: 100%; }
        button:hover { background: #0369a1; }
        button:disabled { background: #475569; cursor: not-allowed; }
        #status-area { margin-top: 20px; font-size: 14px; text-align: center; color: #94a3b8; display: none; }
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
              <input type="text" id="keyword" placeholder="search here" value="" onkeydown="if(event.key === 'Enter') runSearch()" />
            </div>
            <div class="form-group">
              <label>Target Domain</label>
              <input type="text" id="target_domain" placeholder="e.g. outletmallofindia.com" value="" onkeydown="if(event.key === 'Enter') runSearch()" />
            </div>
          </div>

          <button id="search-btn" onclick="runSearch()">Check SEO Ranking</button>
          <div id="status-area">Submitting search task to Celery...</div>

          <div id="rank-badge" class="badge-box">
            <div>
              <div style="font-size: 13px; text-transform: uppercase; font-weight: 600;" id="badge-title">SEO Position</div>
              <div style="font-size: 14px; color: #cbd5e1;" id="badge-desc"></div>
            </div>
            <div class="rank-number" id="rank-val">#--</div>
          </div>

          <div class="results-list" id="results-container"></div>
        </div>
      </div>

      <script>
        async function runSearch() {
          const keyword = document.getElementById('keyword').value.trim();
          const targetDomain = document.getElementById('target_domain').value.trim().toLowerCase();
          const btn = document.getElementById('search-btn');
          const status = document.getElementById('status-area');
          const resultsContainer = document.getElementById('results-container');
          const rankBadge = document.getElementById('rank-badge');

          if (!keyword) return;

          btn.disabled = true;
          status.style.display = 'block';
          status.innerText = "Queueing background task in Redis...";
          resultsContainer.innerHTML = '';
          rankBadge.style.display = 'none';

          try {
            const postRes = await fetch('/api/v1/search', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ keyword: keyword })
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
                renderData(jobData.data.results, targetDomain);
              } else if (jobData.status === 'Failed') {
                clearInterval(pollInterval);
                btn.disabled = false;
                status.innerText = "Task failed in background worker.";
              }
            }, 1000);

          } catch (err) {
            btn.disabled = false;
            status.innerText = "Error connecting to API.";
          }
        }

        function renderData(results, targetDomain) {
          const resultsContainer = document.getElementById('results-container');
          const rankBadge = document.getElementById('rank-badge');
          const rankVal = document.getElementById('rank-val');
          const badgeDesc = document.getElementById('badge-desc');

          let matchedRank = null;
          resultsContainer.innerHTML = '';

          results.forEach((item, index) => {
            const currentRank = index + 1;
            const titleLower = item.title.toLowerCase();
            const domainLower = item.domain.toLowerCase();
            
            // 1. Check if the result matches the user-inputted Target Domain (for the badge)
            const isTargetMatch = targetDomain && domainLower.includes(targetDomain);
            if (isTargetMatch && matchedRank === null) {
              matchedRank = currentRank;
            }

            // 2. Automatically highlight rows containing your mall's brand names
            const autoHighlight = titleLower.includes("outlet mall of india") || 
                                  titleLower.includes("bhumi world") || 
                                  domainLower.includes("outletmallofindia") || 
                                  domainLower.includes("bhumiworld");
                                  
            const isHighlight = isTargetMatch || autoHighlight;

            const card = document.createElement('div');
            card.className = `result-item ${isHighlight ? 'highlight' : ''}`;
            card.innerHTML = `
              <div class="pos ${isHighlight ? 'highlight' : ''}">#${currentRank}</div>
              <div class="details">
                <h3><a href="${item.url}" target="_blank">${item.title}</a></h3>
                <div class="domain">${item.domain}</div>
              </div>
            `;
            resultsContainer.appendChild(card);
          });

          if (targetDomain) {
            rankBadge.style.display = 'flex';
            if (matchedRank) {
              rankBadge.className = 'badge-box badge-found';
              rankVal.innerText = `#${matchedRank}`;
              badgeDesc.innerText = `Found "${targetDomain}" in search results.`;
            } else {
              rankBadge.className = 'badge-box badge-missing';
              rankVal.innerText = 'N/A';
              badgeDesc.innerText = `Domain not ranked within top ${results.length} positions.`;
            }
          }
        }
      </script>
    </body>
    </html>
    """