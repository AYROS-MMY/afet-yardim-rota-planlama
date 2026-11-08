"""Sunum için çevrimdışı, araç seçilebilir görev planı görünümü."""

from html import escape
from pathlib import Path

from .assignment_output import assignment_svg
from .assignment import REASONS, SERVICES


def write_assignment_html(scenario, entries, fleet, path):
    """Sunucu veya ek paket gerekmez; hesaplanmış planı gösterir, simüle etmez."""
    assigned = {e.vehicle.id: e for e in entries if e.vehicle}
    buttons = ['<button class="vehicle active" data-choice="" aria-pressed="true">'
               '<strong>Tüm görevler</strong><span>Başlangıç konumları ve bütün rotalar</span></button>']
    for vehicle in sorted(fleet.vehicles, key=lambda v: v.id):
        e = assigned.get(vehicle.id)
        state = (f'{vehicle.center} → {e.need.node.id} · {SERVICES[e.service]} · {e.demand} {e.unit}'
                 if e else f'{vehicle.center} · ' + ('Müsait değil' if not vehicle.available else 'Görev atanmadı'))
        detail = (f'Planlanan: {e.demand}/{vehicle.capacity} {e.unit} · {e.route.cost_min:.2f} dk · {e.route.distance_km:.2f} km'
                  if e else f'{SERVICES[vehicle.service]} · kapasite {vehicle.capacity} ' + ('koli' if vehicle.service == 'logistics' else 'ekip'))
        buttons.append(f'<button class="vehicle" data-choice="{escape(vehicle.id)}" aria-pressed="false">'
                       f'<strong>{escape(vehicle.id)}</strong><span>{escape(state)}</span>'
                       f'<small>{escape(detail)}</small></button>')
    regions = []
    for target in sorted({e.need.node.id for e in entries}):
        items = [e for e in entries if e.need.node.id == target]
        rows = []
        for e in items:
            status = f'{e.vehicle.id} · {e.vehicle.center} → {target} · {e.route.cost_min:.2f} dk' if e.vehicle else REASONS[e.status]
            urgency = e.task.urgency if e.task else e.need.node.urgency_level
            rows.append(f'<li><strong>{escape(SERVICES[e.service])}: {e.demand} {e.unit}</strong> · aciliyet {urgency}/5<br>{escape(status)}</li>')
        regions.append(f'<details data-region="{escape(target)}"><summary>{escape(target)} — {sum(e.vehicle is not None for e in items)}/{len(items)} görev atandı</summary><ul>{"".join(rows)}</ul><button class="region-choice" data-region-choice="{escape(target)}">Bu bölgenin rotalarını göster</button></details>')
    options = ''.join(f'<option value="{escape(t)}"'+(' selected' if t=='A08' else '')+f'>{escape(t)}</option>' for t in sorted({e.need.node.id for e in entries}))
    region_panel = '<div class="regions"><h2>Bölge ihtiyaçları</h2><label>Bölge seç: <select id="region-select">' + options + '</select></label><p>Her satır ayrı görevdir. Atama, ihtiyacın karşılandığı anlamına gelmez.</p>' + ''.join(regions) + '</div>'
    logistics = [e for e in entries if e.service == 'logistics']
    requested = sum(e.demand for e in logistics)
    planned = sum(e.demand for e in logistics if e.vehicle)
    summary = (f'<div class="plan-summary" aria-label="Başlangıç planı özeti">'
               f'<div><strong>{len(assigned)}/{len(entries)}</strong><span>Görev atandı</span></div>'
               f'<div><strong>{requested} koli</strong><span>Toplam lojistik ihtiyaç</span></div>'
               f'<div><strong>{planned} koli</strong><span>Araçlara planlandı</span></div>'
               f'<div><strong>{requested-planned} koli</strong><span>Henüz araç atanmadı</span></div></div>')
    svg = assignment_svg(scenario, entries, fleet=fleet)
    page = '''<!doctype html><html lang="tr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AYROS MMY | Araç görev planı</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f1f5f9;color:#172033;font:16px Arial,sans-serif}
header{padding:24px 30px;background:#fff;border-bottom:1px solid #dbe3ed}h1{font-size:26px;margin:0 0 10px}
p{line-height:1.5;margin:8px 0}main{display:grid;grid-template-columns:270px minmax(0,1fr);gap:18px;padding:20px}
aside{align-self:start;position:sticky;top:15px}.vehicle{display:block;width:100%;text-align:left;background:white;border:1px solid #cbd5e1;border-radius:8px;padding:13px;margin:0 0 9px;cursor:pointer;color:#172033}
.vehicle strong,.vehicle span,.vehicle small{display:block}.vehicle span{margin:6px 0;font-size:14px}.vehicle small{color:#475569}
.vehicle.active{border:2px solid #2563eb;background:#eff6ff}.vehicle:focus-visible{outline:3px solid #2563eb;outline-offset:2px}
section{min-width:0;background:white;border:1px solid #dbe3ed;border-radius:10px;overflow:hidden}svg{display:block;width:100%;height:auto}
.regions{padding:20px}details{border:1px solid #cbd5e1;padding:12px;margin-bottom:8px}summary{cursor:pointer;font-weight:bold}li{margin-bottom:10px;line-height:1.5}.region-choice{padding:9px;cursor:pointer}#selection{padding:14px 20px;background:#eff6ff;border-bottom:1px solid #dbe3ed;font-weight:bold}
.plan-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:16px}.plan-summary div{background:#eff6ff;padding:14px;border:1px solid #bfdbfe;border-radius:8px}.plan-summary strong,.plan-summary span{display:block}.plan-summary strong{font-size:22px}.plan-summary span{font-size:14px;margin-top:5px}.hint{font-size:14px;color:#475569}.scroll{overflow:auto}svg{min-width:780px}
@media(max-width:800px){main{grid-template-columns:1fr;padding:10px}aside{position:static;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.vehicle{margin:0}header{padding:20px}h1{font-size:23px}}
</style><header><h1>AYROS MMY — Araç görev planı</h1>
<p><strong>1.</strong> Soldan bir araç seç. <strong>2.</strong> Başlangıç merkezini bul. <strong>3.</strong> Okları izleyerek hedefe ulaş.</p>
<p class="hint">Başlangıç anı: bütün araçlar belirtilen merkezlerdedir. Bu ekran hesaplanmış ilk tur planını gösterir; araç hareketi, gerçekleşen teslimat veya canlı saha verisi değildir.</p>
<p class="hint">Araç seçimi yalnızca haritadaki rotaları filtreler; alttaki sonuç tablosu bütün görev planını gösterir. Telefonda haritayı yatay kaydırabilirsin.</p>
''' + summary + '''<p class="hint">Teslimat takibi henüz yoktur. Planlanan koli miktarı teslim edilmiş yardım değildir; sağlık ve kurtarma görevleri koli toplamına katılmaz.</p>
</header><main><aside aria-label="Araç seçimi">''' + ''.join(buttons) + '''</aside>
<section><div id="selection" role="status" aria-live="polite">Tüm görevler — ortak yollardaki örtüşmeyi kaldırmak için bir araç seç.</div>
''' + region_panel + '''<div class="scroll">''' + svg + r'''</div></section></main>
<script>
document.querySelectorAll('[data-region-choice]').forEach(button => button.addEventListener('click', () => {
 const target=button.dataset.regionChoice;
 document.querySelectorAll('[data-route-vehicle]').forEach(g=>{g.style.display=g.dataset.routeTarget===target?'':'none';});
 document.querySelectorAll('[data-target-vehicle]').forEach(g=>{g.style.display=g.dataset.targetRegion===target?'':'none';});
 document.querySelectorAll('[data-choice]').forEach(b=>{b.classList.remove('active');b.setAttribute('aria-pressed','false');});
 document.getElementById('selection').textContent=target+' bölgesine atanan görevlerin rotaları — ihtiyaç ayrıntıları yukarıdadır.';
}));
const regionSelect=document.getElementById('region-select');
function showRegion(){document.querySelectorAll('[data-region]').forEach(d=>{d.hidden=d.dataset.region!==regionSelect.value;d.open=!d.hidden;});}
showRegion();
regionSelect.addEventListener('change',()=>{showRegion();const d=[...document.querySelectorAll('[data-region]')].find(d=>!d.hidden);if(d)d.querySelector('button').click();});
const choices = document.querySelectorAll('[data-choice]');
choices.forEach(button => button.addEventListener('click', () => {
  const id = button.dataset.choice;
  choices.forEach(b => { const active = b === button; b.classList.toggle('active',active); b.setAttribute('aria-pressed',String(active)); });
  document.querySelectorAll('[data-route-vehicle]').forEach(g => {g.style.display = !id || g.dataset.routeVehicle === id ? '' : 'none';});
  document.querySelectorAll('[data-target-vehicle]').forEach(g => {g.style.display = !id || g.dataset.targetVehicle === id ? '' : 'none';});
  document.getElementById('selection').textContent = id ? button.innerText.replace(/\n/g,' · ') + ' — Araç başlangıç merkezindedir.' : 'Tüm görevler — ortak yollardaki örtüşmeyi kaldırmak için bir araç seç.';
}));
</script></html>'''
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding='utf-8')
