import json
import os
from datetime import datetime

HISTORY_FILE = "jobs_history.json"
OUTPUT_FILE  = "dashboard.html"


def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_to_history(jobs_with_analysis: list):
    history = load_history()
    cycle_ts = datetime.now().strftime("%d/%m/%Y %H:%M")
    for entry in jobs_with_analysis:
        entry["saved_at"] = cycle_ts
        history.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def score_color(score: int) -> str:
    if score >= 9: return "#2ecc71"
    if score >= 7: return "#3498db"
    if score >= 5: return "#f39c12"
    return "#e74c3c"


def score_badge(score: int) -> str:
    color = score_color(score)
    return f'<span style="background:{color};color:#fff;padding:3px 10px;border-radius:12px;font-weight:bold;">{score}/10</span>'


def source_emoji(source: str) -> str:
    return {"FranceTravail": "🇫🇷", "LinkedIn": "💼", "WTTJ": "🌴"}.get(source, "📌")


def generate_dashboard():
    history = load_history()

    if not history:
        stats_html = "<p style='color:#888'>Aucune offre enregistrée pour le moment.</p>"
        cards_html = ""
    else:
        total       = len(history)
        sent        = [j for j in history if j.get("analysis")]
        avg_score   = round(sum(j["analysis"]["score"] for j in sent) / len(sent), 1) if sent else 0
        sources     = {}
        for j in history:
            sources[j["source"]] = sources.get(j["source"], 0) + 1

        source_pills = " ".join(
            f'<span style="background:#2c3e50;color:#ecf0f1;padding:3px 10px;border-radius:12px;margin:2px;display:inline-block;">'
            f'{source_emoji(s)} {s} <b>{c}</b></span>'
            for s, c in sorted(sources.items(), key=lambda x: -x[1])
        )

        stats_html = f"""
        <div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:30px;">
            <div class="stat-card">
                <div class="stat-num">{total}</div>
                <div class="stat-label">Offres analysées</div>
            </div>
            <div class="stat-card">
                <div class="stat-num">{len(sent)}</div>
                <div class="stat-label">Offres notifiées</div>
            </div>
            <div class="stat-card">
                <div class="stat-num">{avg_score}</div>
                <div class="stat-label">Score moyen</div>
            </div>
        </div>
        <div style="margin-bottom:24px;">{source_pills}</div>
        """

        cards = []
        for job in sorted(history, key=lambda j: j.get("saved_at", ""), reverse=True):
            analysis = job.get("analysis") or {}
            score    = analysis.get("score", 0)
            verdict  = analysis.get("verdict", "Non analysé")
            positifs = analysis.get("points_positifs", [])
            negatifs = analysis.get("points_negatifs", [])

            pos_html = "".join(f'<li>✅ {p}</li>' for p in positifs) or "<li style='color:#888'>—</li>"
            neg_html = "".join(f'<li>⚠️ {n}</li>' for n in negatifs) if negatifs else ""

            border_color = score_color(score) if score else "#555"

            cards.append(f"""
            <div class="card" style="border-left:4px solid {border_color};">
                <div class="card-header">
                    <div>
                        <span class="source-tag">{source_emoji(job['source'])} {job['source']}</span>
                        <h3 style="margin:6px 0 2px;">{job['title']}</h3>
                        <span style="color:#aaa;font-size:13px;">🏢 {job['company']} &nbsp;|&nbsp; 📍 {job['location']} &nbsp;|&nbsp; 📅 {job.get('saved_at','')}</span>
                    </div>
                    <div style="text-align:right;min-width:80px;">
                        {score_badge(score)}
                        <div style="color:#aaa;font-size:12px;margin-top:4px;">{verdict}</div>
                    </div>
                </div>
                <div style="margin-top:10px;display:flex;gap:20px;flex-wrap:wrap;">
                    <div style="flex:1;min-width:160px;">
                        <b style="font-size:12px;color:#aaa;text-transform:uppercase;">Points positifs</b>
                        <ul style="margin:4px 0;padding-left:16px;font-size:13px;">{pos_html}</ul>
                    </div>
                    {"<div style='flex:1;min-width:160px;'><b style='font-size:12px;color:#aaa;text-transform:uppercase;'>Points négatifs</b><ul style='margin:4px 0;padding-left:16px;font-size:13px;'>" + neg_html + "</ul></div>" if neg_html else ""}
                </div>
                <div style="margin-top:12px;">
                    <span style="background:#1a1a2e;padding:4px 8px;border-radius:6px;font-size:12px;">
                        📄 {job.get('contract') or 'Contrat non précisé'} &nbsp;|&nbsp; 💰 {job.get('salary','Non précisé')}
                    </span>
                    &nbsp;
                    <a href="{job['url']}" target="_blank" style="color:#3498db;font-size:13px;">🔗 Voir l'annonce</a>
                </div>
            </div>
            """)

        cards_html = "\n".join(cards)

    last_update = datetime.now().strftime("%d/%m/%Y à %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Hunter Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f0f1a; color: #ecf0f1; padding: 30px 20px; }}
  h1 {{ font-size: 26px; margin-bottom: 6px; }}
  .subtitle {{ color: #888; font-size: 13px; margin-bottom: 28px; }}
  .stat-card {{
    background: #1a1a2e; border-radius: 12px; padding: 20px 28px;
    text-align: center; min-width: 130px; flex: 1;
  }}
  .stat-num {{ font-size: 36px; font-weight: bold; color: #3498db; }}
  .stat-label {{ font-size: 13px; color: #aaa; margin-top: 4px; }}
  .card {{
    background: #1a1a2e; border-radius: 12px; padding: 20px;
    margin-bottom: 16px; transition: transform 0.15s;
  }}
  .card:hover {{ transform: translateY(-2px); }}
  .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }}
  .source-tag {{ font-size: 12px; background: #2c3e50; padding: 2px 8px; border-radius: 8px; color: #bbb; }}
  input[type=text] {{
    width: 100%; padding: 10px 16px; border-radius: 8px; border: 1px solid #2c3e50;
    background: #1a1a2e; color: #ecf0f1; font-size: 14px; margin-bottom: 20px; outline: none;
  }}
  input[type=text]:focus {{ border-color: #3498db; }}
  .filter-bar {{ display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }}
  .filter-btn {{
    background: #2c3e50; color: #ecf0f1; border: none; padding: 6px 14px;
    border-radius: 20px; cursor: pointer; font-size: 13px;
  }}
  .filter-btn.active {{ background: #3498db; }}
</style>
</head>
<body>

<h1>🤖 Job Hunter Dashboard</h1>
<p class="subtitle">Dernière mise à jour : {last_update}</p>

{stats_html}

<input type="text" id="search" placeholder="🔍 Rechercher par titre, entreprise, lieu..." onkeyup="filterCards()">

<div class="filter-bar">
  <button class="filter-btn active" onclick="filterSource('all', this)">Toutes</button>
  <button class="filter-btn" onclick="filterSource('FranceTravail', this)">🇫🇷 France Travail</button>
  <button class="filter-btn" onclick="filterSource('LinkedIn', this)">💼 LinkedIn</button>
  <button class="filter-btn" onclick="filterSource('WTTJ', this)">🌴 WTTJ</button>
</div>

<div id="cards-container">
{cards_html}
</div>

<script>
let currentSource = 'all';

function filterCards() {{
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('.card').forEach(c => {{
    const text = c.innerText.toLowerCase();
    const src  = c.querySelector('.source-tag') ? c.querySelector('.source-tag').innerText : '';
    const matchSearch = text.includes(q);
    const matchSource = currentSource === 'all' || src.includes(currentSource);
    c.style.display = (matchSearch && matchSource) ? '' : 'none';
  }});
}}

function filterSource(source, btn) {{
  currentSource = source;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  filterCards();
}}
</script>

</body>
</html>"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[Dashboard] dashboard.html généré ({len(history)} offres)")


if __name__ == "__main__":
    generate_dashboard()