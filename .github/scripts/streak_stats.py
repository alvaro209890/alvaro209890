#!/usr/bin/env python3
"""Gera o card de sequencia de commits (streak) sem depender de servico externo.

Consulta a API GraphQL do GitHub com o token do proprio workflow e desenha o SVG.
Uso: streak_stats.py <usuario> <arquivo-de-saida.svg>
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

API = "https://api.github.com/graphql"

# Paleta (mesma do restante do perfil)
BG = "#0D1117"
RING = "#52B788"
FIRE = "#95D5B2"
CURR_LABEL = "#52B788"
SIDE_LABELS = "#CDE8D5"
DATES = "#7FBF9B"
NUMS = "#FEFEFE"
DIVIDER = "#1B4332"

MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
         "jul", "ago", "set", "out", "nov", "dez"]


def graphql(query, variables, token):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "streak-stats-selfhosted",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(json.dumps(payload["errors"]))
    return payload["data"]


def buscar_dias(user, token):
    """Devolve [(date, count)] ordenado, desde a criacao da conta ate hoje."""
    dados = graphql("query($u:String!){user(login:$u){createdAt}}", {"u": user}, token)
    criado = datetime.strptime(dados["user"]["createdAt"], "%Y-%m-%dT%H:%M:%SZ").date()
    hoje = date.today()

    dias = {}
    inicio = criado
    while inicio <= hoje:
        fim = min(date(inicio.year + 1, inicio.month, inicio.day) - timedelta(days=1), hoje) \
            if (inicio.month, inicio.day) != (2, 29) else min(inicio + timedelta(days=364), hoje)
        q = """query($u:String!,$from:DateTime!,$to:DateTime!){
                 user(login:$u){
                   contributionsCollection(from:$from,to:$to){
                     contributionCalendar{ weeks{ contributionDays{ date contributionCount } } }
                   }
                 }
               }"""
        d = graphql(q, {
            "u": user,
            "from": inicio.isoformat() + "T00:00:00Z",
            "to": fim.isoformat() + "T23:59:59Z",
        }, token)
        semanas = d["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for semana in semanas:
            for dia in semana["contributionDays"]:
                dias[date.fromisoformat(dia["date"])] = dia["contributionCount"]
        inicio = fim + timedelta(days=1)

    return sorted((d, c) for d, c in dias.items() if criado <= d <= hoje)


def calcular(dias):
    total = sum(c for _, c in dias)
    primeiro = dias[0][0] if dias else date.today()
    hoje = dias[-1][0] if dias else date.today()

    # sequencia atual: conta de tras pra frente; se hoje ainda esta zerado, comeca de ontem
    idx = len(dias) - 1
    if idx >= 0 and dias[idx][1] == 0:
        idx -= 1
    atual, fim_atual, ini_atual = 0, None, None
    while idx >= 0 and dias[idx][1] > 0:
        atual += 1
        if fim_atual is None:
            fim_atual = dias[idx][0]
        ini_atual = dias[idx][0]
        idx -= 1

    # maior sequencia
    maior, corrente = 0, 0
    ini_maior = fim_maior = ini_corrente = None
    for d, c in dias:
        if c > 0:
            corrente += 1
            if corrente == 1:
                ini_corrente = d
            if corrente > maior:
                maior, ini_maior, fim_maior = corrente, ini_corrente, d
        else:
            corrente = 0

    return {
        "total": total, "total_ini": primeiro, "total_fim": hoje,
        "atual": atual, "atual_ini": ini_atual, "atual_fim": fim_atual,
        "maior": maior, "maior_ini": ini_maior, "maior_fim": fim_maior,
    }


def num_br(n):
    return f"{n:,}".replace(",", ".")


def fmt_dia(d, com_ano=True):
    if d is None:
        return ""
    s = f"{d.day} {MESES[d.month - 1]}"
    return f"{s} {d.year}" if com_ano else s


def fmt_periodo(ini, fim):
    if ini is None or fim is None:
        return "—"
    if ini == fim:
        return fmt_dia(ini)
    mesmo_ano = ini.year == fim.year
    return f"{fmt_dia(ini, not mesmo_ano)} - {fmt_dia(fim)}"


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render(s):
    hoje = date.today()
    periodo_total = f"{fmt_dia(s['total_ini'], s['total_ini'].year != hoje.year)} - hoje"
    periodo_atual = fmt_periodo(s["atual_ini"], s["atual_fim"])
    periodo_maior = fmt_periodo(s["maior_ini"], s["maior_fim"])

    fonte = '"Segoe UI", Ubuntu, sans-serif'

    def texto(y, conteudo, tamanho, peso, cor, delay, anim="fadein"):
        estilo = (f"opacity: 0; animation: {anim} 0.5s linear forwards {delay}s"
                  if anim == "fadein"
                  else f"animation: {anim} 0.6s linear forwards")
        return (f"<text x='0' y='{y}' stroke-width='0' text-anchor='middle' fill='{cor}' "
                f"stroke='none' font-family='{fonte}' font-weight='{peso}' "
                f"font-size='{tamanho}px' font-style='normal' style='{estilo}'>"
                f"{esc(conteudo)}</text>")

    return f"""<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'
     style='isolation: isolate' viewBox='0 0 495 195' width='495px' height='195px' direction='ltr'>
  <style>
    @keyframes currstreak {{
      0%   {{ font-size: 3px;  opacity: 0.2; }}
      80%  {{ font-size: 34px; opacity: 1; }}
      100% {{ font-size: 28px; opacity: 1; }}
    }}
    @keyframes fadein {{ 0% {{ opacity: 0; }} 100% {{ opacity: 1; }} }}
    @keyframes chama {{
      0%   {{ transform: scale(1);    opacity: 0.88; }}
      50%  {{ transform: scale(1.09); opacity: 1; }}
      100% {{ transform: scale(1);    opacity: 0.88; }}
    }}
  </style>
  <defs>
    <clipPath id='outer_rectangle'><rect width='495' height='195' rx='4.5'/></clipPath>
    <mask id='mask_out_ring_behind_fire'>
      <rect width='495' height='195' fill='white'/>
      <ellipse id='mask-ellipse' cx='247.5' cy='32' rx='13' ry='18' fill='black'/>
    </mask>
  </defs>
  <g clip-path='url(#outer_rectangle)'>
    <rect stroke='none' fill='{BG}' rx='4.5' x='0.5' y='0.5' width='494' height='194'/>

    <line x1='165' y1='28' x2='165' y2='170' vector-effect='non-scaling-stroke'
          stroke-width='1' stroke='{DIVIDER}' stroke-linecap='square'/>
    <line x1='330' y1='28' x2='330' y2='170' vector-effect='non-scaling-stroke'
          stroke-width='1' stroke='{DIVIDER}' stroke-linecap='square'/>

    <!-- Total de contribuicoes -->
    <g transform='translate(82.5, 48)'>{texto(32, num_br(s['total']), 28, 700, NUMS, 0.6)}</g>
    <g transform='translate(82.5, 84)'>{texto(32, 'Contribuições totais', 14, 400, SIDE_LABELS, 0.7)}</g>
    <g transform='translate(82.5, 114)'>{texto(32, periodo_total, 12, 400, DATES, 0.8)}</g>

    <!-- Sequencia atual -->
    <g mask='url(#mask_out_ring_behind_fire)'>
      <circle cx='247.5' cy='71' r='40' fill='none' stroke='{RING}' stroke-width='5'
              style='opacity: 0; animation: fadein 0.5s linear forwards 0.4s'/>
    </g>
    <g transform='translate(247.5, 19.5)'>
     <g style='transform-origin: 0px 11px; animation: chama 2.4s ease-in-out infinite'>
      <path d='M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2
               C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99
               C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z
               M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.68 12.74
               C 1.1 12.38 2.94 11.53 3.97 10.15 C 4.36 11.44 4.57 12.8 4.57 14.19
               C 4.57 16.85 2.41 19 -0.29 19 Z'
            fill='{FIRE}' stroke-opacity='0'/>
     </g>
    </g>
    <g transform='translate(247.5, 48)'>{texto(32, num_br(s['atual']), 28, 700, NUMS, 0, 'currstreak')}</g>
    <g transform='translate(247.5, 108)'>{texto(32, 'Sequência atual', 14, 700, CURR_LABEL, 0.9)}</g>
    <g transform='translate(247.5, 145)'>{texto(21, periodo_atual, 12, 400, DATES, 0.9)}</g>

    <!-- Maior sequencia -->
    <g transform='translate(412.5, 48)'>{texto(32, num_br(s['maior']), 28, 700, NUMS, 1.2)}</g>
    <g transform='translate(412.5, 84)'>{texto(32, 'Maior sequência', 14, 400, SIDE_LABELS, 1.3)}</g>
    <g transform='translate(412.5, 114)'>{texto(32, periodo_maior, 12, 400, DATES, 1.4)}</g>
  </g>
</svg>
"""


def main():
    if len(sys.argv) < 3:
        print("uso: streak_stats.py <usuario> <saida.svg>", file=sys.stderr)
        return 2
    user, saida = sys.argv[1], sys.argv[2]
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("erro: defina GITHUB_TOKEN", file=sys.stderr)
        return 2

    dias = buscar_dias(user, token)
    s = calcular(dias)
    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    with open(saida, "w", encoding="utf-8") as f:
        f.write(render(s))

    print(f"ok: {saida}")
    print(f"  total = {s['total']} ({s['total_ini']} -> {s['total_fim']})")
    print(f"  atual = {s['atual']} ({s['atual_ini']} -> {s['atual_fim']})")
    print(f"  maior = {s['maior']} ({s['maior_ini']} -> {s['maior_fim']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
