#!/usr/bin/env python3
"""Gera o grafico de atividade de contribuicoes dos ultimos 30 dias em SVG nativo.

Consulta a API GraphQL do GitHub com o token do workflow e renderiza
um grafico de area/linha moderno com a paleta do perfil (verde #52B788 + dark #0D1117).
Uso: activity_graph.py <usuario> <arquivo-de-saida.svg>
"""

import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta

API = "https://api.github.com/graphql"

# Paleta do perfil
BG = "#0D1117"
LINE = "#52B788"
POINT = "#FEFEFE"
AREA_TOP = "rgba(82, 183, 136, 0.45)"
AREA_BOTTOM = "rgba(27, 67, 50, 0.05)"
GRID = "#1B4332"
TEXT = "#CDE8D5"
TITLE = "#52B788"
NUMS = "#FEFEFE"

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
         "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def graphql(query, variables, token):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "activity-graph-selfhosted",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(json.dumps(payload["errors"]))
    return payload["data"]


def buscar_ultimos_dias(user, token, dias_total=31):
    hoje = date.today()
    inicio = hoje - timedelta(days=dias_total - 1)
    
    q = """query($u:String!,$from:DateTime!,$to:DateTime!){
             user(login:$u){
               contributionsCollection(from:$from,to:$to){
                 contributionCalendar{
                   totalContributions
                   weeks{
                     contributionDays{
                       date
                       contributionCount
                     }
                   }
                 }
               }
             }
           }"""
    d = graphql(q, {
        "u": user,
        "from": inicio.isoformat() + "T00:00:00Z",
        "to": hoje.isoformat() + "T23:59:59Z",
    }, token)
    
    dias = {}
    semanas = d["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    for semana in semanas:
        for dia in semana["contributionDays"]:
            dt = date.fromisoformat(dia["date"])
            if inicio <= dt <= hoje:
                dias[dt] = dia["contributionCount"]
                
    lista = []
    curr = inicio
    while curr <= hoje:
        lista.append((curr, dias.get(curr, 0)))
        curr += timedelta(days=1)
        
    return lista


def render_svg(dias_lista):
    w, h = 850, 300
    pad_left, pad_right = 65, 40
    pad_top, pad_bottom = 75, 45
    
    graph_w = w - pad_left - pad_right
    graph_h = h - pad_top - pad_bottom
    
    counts = [c for _, c in dias_lista]
    max_c = max(max(counts), 5)
    # arredondar max_c para multiplo agradavel
    if max_c <= 10:
        y_max = max(max_c, 6)
    elif max_c <= 25:
        y_max = ((max_c + 4) // 5) * 5
    else:
        y_max = ((max_c + 9) // 10) * 10
        
    n = len(dias_lista)
    
    # Calcular coordenadas
    pontos = []
    for i, (dt, count) in enumerate(dias_lista):
        x = pad_left + (i / (n - 1)) * graph_w
        y = pad_top + graph_h - (count / y_max) * graph_h
        pontos.append((x, y, dt, count))
        
    # Construir caminhos SVG
    path_d = f"M {pontos[0][0]:.1f} {pontos[0][1]:.1f}"
    for i in range(len(pontos) - 1):
        p0 = pontos[i]
        p1 = pontos[i+1]
        cx1 = p0[0] + (p1[0] - p0[0]) * 0.45
        cy1 = p0[1]
        cx2 = p0[0] + (p1[0] - p0[0]) * 0.55
        cy2 = p1[1]
        path_d += f" C {cx1:.1f} {cy1:.1f}, {cx2:.1f} {cy2:.1f}, {p1[0]:.1f} {p1[1]:.1f}"
        
    # Caminho da area sombreada
    area_d = path_d + f" L {pontos[-1][0]:.1f} {pad_top + graph_h:.1f} L {pontos[0][0]:.1f} {pad_top + graph_h:.1f} Z"
    
    # Linhas de grade Y
    grid_lines = []
    y_steps = 4
    for s in range(y_steps + 1):
        val = int(round((s / y_steps) * y_max))
        gy = pad_top + graph_h - (val / y_max) * graph_h
        grid_lines.append(f"""
        <line x1='{pad_left}' y1='{gy:.1f}' x2='{w - pad_right}' y2='{gy:.1f}' stroke='{GRID}' stroke-width='1' stroke-dasharray='3,3'/>
        <text x='{pad_left - 12}' y='{gy + 4:.1f}' fill='{TEXT}' font-size='11px' font-family='"Segoe UI", sans-serif' text-anchor='end'>{val}</text>
        """)
        
    # Rotulos de data no eixo X
    x_labels = []
    step_x = max(1, n // 6)
    for i in range(0, n, step_x):
        dt = dias_lista[i][0]
        lbl = f"{dt.day} {MESES[dt.month - 1]}"
        px = pontos[i][0]
        x_labels.append(f"<text x='{px:.1f}' y='{h - 18}' fill='{TEXT}' font-size='11px' font-family='\"Segoe UI\", sans-serif' text-anchor='middle'>{lbl}</text>")
    # Garantir ultimo dia
    if (n - 1) % step_x != 0:
        dt = dias_lista[-1][0]
        lbl = f"{dt.day} {MESES[dt.month - 1]}"
        px = pontos[-1][0]
        x_labels.append(f"<text x='{px:.1f}' y='{h - 18}' fill='{TEXT}' font-size='11px' font-family='\"Segoe UI\", sans-serif' text-anchor='middle'>{lbl}</text>")

    # Circulos de pontos com valor > 0
    circles = []
    for x, y, dt, c in pontos:
        if c > 0:
            circles.append(f"""
            <circle cx='{x:.1f}' cy='{y:.1f}' r='3.5' fill='{POINT}' stroke='{LINE}' stroke-width='2'/>
            """)

    total_mes = sum(counts)
    fonte = '"Segoe UI", Ubuntu, -apple-system, sans-serif'

    return f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='100%' height='{h}px' style='background:{BG}; border-radius: 8px;'>
  <defs>
    <linearGradient id='activityGrad' x1='0' y1='0' x2='0' y2='1'>
      <stop offset='0%' stop-color='{LINE}' stop-opacity='0.4'/>
      <stop offset='100%' stop-color='{LINE}' stop-opacity='0.0'/>
    </linearGradient>
    <filter id='glow' x='-20%' y='-20%' width='140%' height='140%'>
      <feGaussianBlur stdDeviation='2' result='blur' />
      <feMerge>
        <feMergeNode in='blur' />
        <feMergeNode in='SourceGraphic' />
      </feMerge>
    </filter>
  </defs>

  <!-- Titulo e Resumo -->
  <text x='{pad_left}' y='38' fill='{TITLE}' font-size='18px' font-weight='700' font-family='{fonte}'>Atividade de Contribuições</text>
  <text x='{pad_left}' y='56' fill='{TEXT}' font-size='12px' font-family='{fonte}'>Últimos 30 dias: <tspan fill='{NUMS}' font-weight='bold'>{total_mes} contribuições</tspan></text>

  <!-- Grade -->
  {''.join(grid_lines)}

  <!-- Area do Grafico -->
  <path d='{area_d}' fill='url(#activityGrad)' />
  <path d='{path_d}' fill='none' stroke='{LINE}' stroke-width='3' stroke-linecap='round' stroke-linejoin='round' filter='url(#glow)'/>

  <!-- Pontos -->
  {''.join(circles)}

  <!-- Rotulos Eixo X -->
  {''.join(x_labels)}
</svg>
"""


def main():
    if len(sys.argv) < 3:
        print("uso: activity_graph.py <usuario> <saida.svg>", file=sys.stderr)
        return 2
    user, saida = sys.argv[1], sys.argv[2]
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("erro: defina GITHUB_TOKEN", file=sys.stderr)
        return 2

    dias = buscar_ultimos_dias(user, token, 31)
    svg = render_svg(dias)
    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    with open(saida, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"ok: {saida} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
