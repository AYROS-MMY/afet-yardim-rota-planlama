"""Öncelik sonucunun açıklanabilir JSON ve SVG çıktıları."""

from dataclasses import asdict
from html import escape
import json
from pathlib import Path

from .priority import PriorityAssessment
from .scenario import Scenario


def assessment_dict(result: PriorityAssessment) -> dict:
    """Ham puanlar korunur; süre ölçümü yerine rota süresi ve erişim aktarılır."""
    return {
        'schema_version': 1,
        'start': result.start,
        'algorithm': result.algorithm,
        'damage_factor': result.cost_model.damaged_factor,
        'policy': asdict(result.policy),
        'tie_break': ['score_desc', 'urgency_desc', 'injured_desc', 'affected_desc', 'id_asc'],
        'entries': [{
            'rank': entry.rank, 'node': asdict(entry.need.node), 'score': entry.need.score,
            'contributions': {'urgency': entry.need.urgency_points,
                              'injured': entry.need.injured_points,
                              'affected': entry.need.affected_points},
            'capped': {'injured': entry.need.injured_capped, 'affected': entry.need.affected_capped},
            'reachable': entry.route.found,
            'route': {'cost_min': entry.route.cost_min, 'distance_km': entry.route.distance_km,
                      'path': entry.route.path, 'road_ids': entry.route.road_ids}
        } for entry in result.entries]
    }


def write_priority_json(scenario: Scenario, result: PriorityAssessment,
                        path: str | Path, *, scenario_sha256: str) -> None:
    payload = assessment_dict(result)
    payload.update(scenario=scenario.name, scenario_sha256=scenario_sha256)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                           encoding='utf-8')


def write_priority_svg(scenario: Scenario, result: PriorityAssessment, path: str | Path) -> None:
    width, row_height = 1320, 48
    height = 300 + len(result.entries) * row_height
    p = result.policy
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
             '<title id="title">İhtiyaç öncelikleri ve erişilebilirlik</title>',
             '<desc id="desc">Azalan ihtiyaç puanı. Çubuklar aciliyet, yaralı ve afetzede katkılarını gösterir. Ulaşılamayan noktalar puan sıralamasında korunur.</desc>',
             f'<rect width="{width}" height="{height}" fill="#f8fafc"/>',
             '<g font-family="Arial, sans-serif" fill="#17263c">',
             '<text x="36" y="42" font-size="26" font-weight="bold">İhtiyaç öncelikleri ve erişilebilirlik</text>',
             f'<text x="36" y="73" font-size="16">{escape(scenario.name)} | Merkez {escape(result.start)} | {escape(result.algorithm)} | Hasar katsayısı {result.cost_model.damaged_factor:g}</text>',
             f'<text x="36" y="101" font-size="15">Ağırlıklar: aciliyet %{p.urgency_weight*100:g}, yaralı %{p.injured_weight*100:g}, afetzede %{p.affected_weight*100:g}. Referanslar: {p.injured_reference} yaralı, {p.affected_reference} afetzede.</text>',
             '<text x="36" y="127" font-size="14">İhtiyaç sırası araç ataması veya ziyaret sırası değildir. Rota süresi puana eklenmez.</text>']
    columns = [(36,'Sıra'),(100,'Nokta'),(200,'Puan katkıları 0–100'),(728,'Puan'),
               (820,'Aciliyet'),(920,'Yaralı'),(1020,'Afetzede'),(1130,'Merkezden süre')]
    parts.append('<rect x="24" y="145" width="1272" height="38" rx="5" fill="#e2e8f0"/>')
    parts += [f'<text x="{x}" y="170" font-size="14" font-weight="bold">{label}</text>' for x,label in columns]
    for index, entry in enumerate(result.entries):
        n = entry.need
        y = 190 + index * row_height
        status = f'{entry.route.cost_min:.2f} dk' if entry.route.found else 'ULAŞILAMIYOR'
        detail = (f'{n.node.name}; ihtiyaç {n.score:.4f}; katkılar {n.urgency_points:.4f} + '
                  f'{n.injured_points:.4f} + {n.affected_points:.4f}; '
                  f'referans aşımı yaralı={n.injured_capped}, afetzede={n.affected_capped}')
        parts.append(f'<g data-node="{escape(n.node.id)}" data-rank="{entry.rank}" data-score="{n.score}" data-reachable="{str(entry.route.found).lower()}"><title>{escape(detail)}</title>')
        parts.append(f'<rect x="24" y="{y}" width="1272" height="44" fill="{"#fff1f2" if not entry.route.found else "#ffffff" if index%2==0 else "#f1f5f9"}"/>')
        parts.append(f'<rect x="200" y="{y+11}" width="500" height="22" rx="3" fill="#e2e8f0"/>')
        x = 200.0
        for field, value, color in (('urgency',n.urgency_points,'#1d4ed8'),
                                    ('injured',n.injured_points,'#b45309'),
                                    ('affected',n.affected_points,'#15803d')):
            parts.append(f'<rect data-contribution="{field}" x="{x:.4f}" y="{y+11}" width="{value*5:.4f}" height="22" fill="{color}"/>')
            x += value * 5
        values = [str(entry.rank), n.node.id, None, f'{n.score:.2f}', str(n.node.urgency_level)+'/5',
                  str(n.node.injured_count), str(n.node.affected_count), status]
        for (x,_), value in zip(columns,values):
            if value is not None:
                parts.append(f'<text x="{x}" y="{y+28}" font-size="14">{escape(value)}</text>')
        parts.append('</g>')
    footer = 215 + len(result.entries) * row_height
    for x,color,label in ((36,'#1d4ed8','Aciliyet'),(200,'#b45309','Yaralı sayısı'),(400,'#15803d','Afetzede sayısı')):
        parts += [f'<rect x="{x}" y="{footer-14}" width="16" height="16" fill="{color}"/>',
                  f'<text x="{x+24}" y="{footer}" font-size="15">{label}</text>']
    parts += [f'<text x="36" y="{footer+28}" font-size="14">Eşit puanda: aciliyet, yaralı, afetzede azalan; son eşitlikte kimlik artan. Gösterimde puanlar yuvarlanır.</text>',
              f'<text x="36" y="{footer+52}" font-size="14">Eğitim amaçlı deneysel politika. Referansı aşan sayılar puanı büyütmez; ham değerler çıktıda korunur.</text>',
              '</g></svg>']
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('\n'.join(parts)+'\n', encoding='utf-8')
