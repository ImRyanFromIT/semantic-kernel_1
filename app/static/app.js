async function doSearch(e) {
  e.preventDefault();
  const q = document.getElementById('q').value.trim();
  if (!q) return;
  const resEl = document.getElementById('results');
  resEl.innerHTML = '<p>Searching...</p>';
  try {
    const resp = await fetch('/api/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q })
    });
    const text = await resp.text();
    let data;
    try { data = JSON.parse(text); } catch { throw new Error(text || 'Internal Server Error'); }
    if (!resp.ok) throw new Error(data.detail || 'Request failed');
    renderResults(data);
  } catch (err) {
    resEl.innerHTML = `<p class="error">${err.message}</p>`;
  }
}

function renderResults(data) {
  const resEl = document.getElementById('results');
  if (!data.teams || data.teams.length === 0) {
    resEl.innerHTML = '<p>No recommendations found.</p>';
    return;
  }
  const cards = data.teams.map(t => `
    <div class="card">
      <h3>${t.name} <span class="score">${(t.score*100).toFixed(0)}%</span></h3>
      ${t.department ? `<p class="muted">${t.department}</p>` : ''}
      ${t.mission ? `<p>${t.mission}</p>` : ''}
      ${t.technologies && t.technologies.length ? `<p><strong>Tech:</strong> ${t.technologies.join(', ')}</p>` : ''}
      ${t.services_offered && t.services_offered.length ? `<p><strong>Services:</strong> ${t.services_offered.join('; ')}</p>` : ''}
      ${t.team_lead ? `<p><strong>Lead:</strong> ${t.team_lead}</p>` : ''}
      ${t.srm_suggestions && t.srm_suggestions.length ? `<p><strong>SRMs:</strong> ${t.srm_suggestions.map(s => `<a href="${s.url}" target="_blank" rel="noopener">${s.name}</a>`).join(' | ')}</p>` : ''}
      ${t.rationale ? `<p class="muted">Why: ${t.rationale}</p>` : ''}
    </div>
  `).join('');
  resEl.innerHTML = cards;
}

document.getElementById('qform').addEventListener('submit', doSearch);


