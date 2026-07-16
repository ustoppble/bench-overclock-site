#!/usr/bin/env python3
"""Processa vendas.csv (export sujo do sistema da loja) e gera relatorio.html.

Sujeiras tratadas:
  - datas em 3 formatos: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YY
  - valores com virgula ("129,90"), ponto ("129.90") ou prefixo "R$ "
  - categoria/produto com caixa aleatoria e espacos extras ("  VESTUARIO ", "tÊnis")
  - linhas quebradas (campos faltando), linhas vazias, valor "ERRO_IMPORT"
  - pedidos duplicados (mesmo pedido_id) -> mantida a 1a ocorrencia
"""

import re
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

ARQ_CSV = "vendas.csv"
ARQ_HTML = "relatorio.html"
SEM_INI, SEM_FIM = date(2026, 1, 1), date(2026, 6, 30)

RE_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
RE_DATA_BR = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
RE_DATA_CURTA = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{2})$")
RE_ID = re.compile(r"^P\d+$")


def parse_data(s):
    for rx, (ia, im, id_) in ((RE_DATA_ISO, (1, 2, 3)), (RE_DATA_BR, (3, 2, 1)),
                              (RE_DATA_CURTA, (3, 2, 1))):
        m = rx.match(s)
        if m:
            a, m_, d = int(m.group(ia)), int(m.group(im)), int(m.group(id_))
            if a < 100:
                a += 2000
            try:
                return date(a, m_, d)
            except ValueError:
                return None
    return None


def parse_valor(s):
    s = s.strip().replace("R$", "").strip()
    if not re.fullmatch(r"\d+([.,]\d{1,2})?", s):  # nunca tem , e . juntos
        return None
    return Decimal(s.replace(",", "."))


def canon_produto(s):
    base = " ".join(s.strip().split()).casefold()
    return base[0].upper() + base[1:] if base else base


ROTULO_CATEGORIA = {
    "vestuario": "Vestuário",
    "calcados": "Calçados",
    "acessorios": "Acessórios",
}


def num(n):
    return f"{n:,}".replace(",", ".")


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------- leitura e validacao ----------
descarte = Counter()           # motivo -> qtd de linhas
conflito_dup = 0               # dups com conteudo diferente da 1a ocorrencia
pedidos = {}                   # pedido_id -> dict (primeira ocorrencia valida)
total_linhas = 0

with open(ARQ_CSV, encoding="utf-8") as f:
    linhas = f.read().splitlines()

cabecalho = linhas[0]
for _nr, linha in enumerate(linhas[1:], start=2):
    total_linhas += 1
    if not linha.strip():
        descarte["vazia"] += 1
        continue
    campos = linha.split(";")
    if len(campos) != 7:
        descarte["incompleta"] += 1
        continue
    pid, dta, prod, cat, qtd, val, canal = (c.strip() for c in campos)

    if not RE_ID.match(pid):
        descarte["id_invalido"] += 1
        continue
    d = parse_data(dta)
    if d is None:
        descarte["data_invalida"] += 1
        continue
    if not (SEM_INI <= d <= SEM_FIM):
        descarte["data_fora_semestre"] += 1
        continue
    if not qtd.isdigit() or int(qtd) < 1:
        descarte["quantidade_invalida"] += 1
        continue
    v = parse_valor(val)
    if v is None or v <= 0:
        descarte["valor_invalido"] += 1
        continue
    if not prod.strip() or not cat.strip():
        descarte["campo_vazio"] += 1
        continue

    reg = {
        "data": d, "produto": canon_produto(prod),
        "categoria": " ".join(cat.split()).casefold(),
        "qtd": int(qtd), "valor": v,
        "assinatura": (d, canon_produto(prod), int(qtd), v),
    }
    if pid in pedidos:
        descarte["duplicada"] += 1
        if pedidos[pid]["assinatura"] != reg["assinatura"]:
            conflito_dup += 1
        continue
    pedidos[pid] = reg

# ---------- agregacoes ----------
validos = list(pedidos.values())
receita_total = sum(r["qtd"] * r["valor"] for r in validos)
rec_cat = defaultdict(lambda: [0, Decimal(0)])       # cat -> [qtd, receita]
qtd_prod = Counter()
rec_prod = defaultdict(Decimal)
datas = [r["data"] for r in validos]
for r in validos:
    rec_cat[r["categoria"]][0] += r["qtd"]
    rec_cat[r["categoria"]][1] += r["qtd"] * r["valor"]
    qtd_prod[r["produto"]] += r["qtd"]
    rec_prod[r["produto"]] += r["qtd"] * r["valor"]

top5 = qtd_prod.most_common(5)
cat_ord = sorted(rec_cat.items(), key=lambda kv: kv[1][1], reverse=True)
n_invalidas = sum(v for k, v in descarte.items() if k != "duplicada")
n_descartadas = n_invalidas + descarte["duplicada"]

MOTIVOS = [
    ("vazia", "Linhas vazias no meio do arquivo"),
    ("incompleta", "Linhas quebradas (campos faltando)"),
    ("valor_invalido", "Valor inválido (ex.: ERRO_IMPORT)"),
    ("data_invalida", "Data irreconhecível"),
    ("data_fora_semestre", "Data fora do semestre (jan–jun/2026)"),
    ("quantidade_invalida", "Quantidade inválida"),
    ("id_invalido", "ID de pedido inválido"),
    ("campo_vazio", "Campo obrigatório vazio"),
]

# ---------- html ----------
def barra(pct, cor):
    return (f'<div class="bar-wrap"><div class="bar" style="width:{pct:.2f}%;'
            f'background:{cor}"></div></div>')


CORES = ["#4f7cff", "#22b8a5", "#f5a623", "#e05d5d", "#8c6ff0"]
linhas_cat = ""
max_cat = cat_ord[0][1][1] if cat_ord else 1
for i, (cat, (qtd, rec)) in enumerate(cat_ord):
    pct = float(rec / max_cat * 100) if max_cat else 0
    share = float(rec / receita_total * 100)
    linhas_cat += (f"<tr><td><strong>{ROTULO_CATEGORIA.get(cat, cat.title())}</strong></td>"
                   f"<td class='num'>{num(qtd)}</td>"
                   f"<td class='num'>{brl(rec)}</td>"
                   f"<td class='bar-cell'>{barra(pct, CORES[i % len(CORES)])}"
                   f"<span class='share'>{share:.1f}%</span></td></tr>\n")

linhas_top = ""
max_top = top5[0][1] if top5 else 1
for i, (prod, qtd) in enumerate(top5):
    pct = qtd / max_top * 100
    linhas_top += (f"<tr><td class='rank'>{i + 1}º</td><td><strong>{prod}</strong></td>"
                   f"<td class='num'>{qtd}</td><td class='num'>{brl(rec_prod[prod])}</td>"
                   f"<td class='bar-cell'>{barra(pct, CORES[i % len(CORES)])}</td></tr>\n")

linhas_motivos = "".join(
    f"<tr><td>{rotulo}</td><td class='num'>{descarte[cod]}</td></tr>"
    for cod, rotulo in MOTIVOS if descarte[cod]
)

html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório de Vendas — 1º semestre 2026</title>
<style>
  :root {{ --bg:#f4f6fb; --card:#fff; --ink:#1d2333; --mut:#6b7280; --line:#e5e8f0; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
        background:var(--bg); color:var(--ink); padding:32px 16px; }}
  .wrap {{ max-width:920px; margin:0 auto; }}
  header h1 {{ font-size:26px; }}
  header p {{ color:var(--mut); margin-top:6px; font-size:14px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
           gap:14px; margin:24px 0; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:18px 20px; box-shadow:0 1px 2px rgba(20,30,60,.04); }}
  .card .label {{ font-size:12px; text-transform:uppercase; letter-spacing:.06em;
                 color:var(--mut); }}
  .card .value {{ font-size:28px; font-weight:700; margin-top:6px; }}
  .card .sub {{ font-size:12px; color:var(--mut); margin-top:4px; }}
  .card.warn .value {{ color:#c0392b; }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
            padding:22px 24px; margin-bottom:20px;
            box-shadow:0 1px 2px rgba(20,30,60,.04); }}
  section h2 {{ font-size:17px; margin-bottom:14px; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th {{ text-align:left; font-size:12px; text-transform:uppercase; letter-spacing:.05em;
       color:var(--mut); padding:8px 10px; border-bottom:2px solid var(--line); }}
  td {{ padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:middle; }}
  tr:last-child td {{ border-bottom:none; }}
  td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.rank {{ color:var(--mut); font-weight:700; width:36px; }}
  td.bar-cell {{ width:34%; min-width:160px; }}
  .bar-wrap {{ background:#eef1f7; border-radius:6px; height:12px; overflow:hidden; }}
  .bar {{ height:100%; border-radius:6px; }}
  .share {{ font-size:11px; color:var(--mut); }}
  footer {{ color:var(--mut); font-size:12px; text-align:center; margin-top:8px; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Relatório de Vendas — 1º semestre de 2026</h1>
    <p>Fonte: <code>vendas.csv</code> · período considerado: {min(datas):%d/%m/%Y} a {max(datas):%d/%m/%Y} ·
       {num(total_linhas)} linhas de dados no arquivo</p>
  </header>

  <div class="cards">
    <div class="card">
      <div class="label">Receita total</div>
      <div class="value">{brl(receita_total)}</div>
      <div class="sub">soma de quantidade × valor unitário</div>
    </div>
    <div class="card">
      <div class="label">Pedidos válidos</div>
      <div class="value">{num(len(validos))}</div>
      <div class="sub">pedidos únicos considerados</div>
    </div>
    <div class="card warn">
      <div class="label">Linhas descartadas</div>
      <div class="value">{n_descartadas}</div>
      <div class="sub">{n_invalidas} inválidas · {descarte["duplicada"]} duplicadas</div>
    </div>
  </div>

  <section>
    <h2>Receita por categoria</h2>
    <table>
      <tr><th>Categoria</th><th class="num">Unidades</th><th class="num">Receita</th><th></th></tr>
      {linhas_cat}
    </table>
  </section>

  <section>
    <h2>Top 5 produtos por quantidade vendida</h2>
    <table>
      <tr><th></th><th>Produto</th><th class="num">Unidades</th><th class="num">Receita</th><th></th></tr>
      {linhas_top}
    </table>
  </section>

  <section>
    <h2>Limpeza do arquivo — o que foi descartado</h2>
    <table>
      <tr><th>Motivo</th><th class="num">Linhas</th></tr>
      {linhas_motivos}
      <tr><td>Pedidos duplicados (mesmo ID — mantida a 1ª ocorrência)</td>
          <td class="num">{descarte["duplicada"]}</td></tr>
      <tr><td><strong>Total descartado</strong></td>
          <td class="num"><strong>{n_descartadas}</strong></td></tr>
    </table>
    <p style="margin-top:12px;font-size:13px;color:var(--mut)">
      Normalizações aplicadas às linhas válidas (sem descarte): datas em 3 formatos
      (<code>AAAA-MM-DD</code>, <code>DD/MM/AAAA</code>, <code>DD-MM-AA</code>) convertidas para data real;
      valores com vírgula, ponto ou prefixo <code>R$</code> convertidos para número;
      categorias e produtos com caixa/espaços inconsistentes padronizados.
      {"Todas as duplicatas eram cópias exatas do pedido original." if conflito_dup == 0
       else f"Atenção: {conflito_dup} duplicata(s) com conteúdo divergente do original — foi mantida a 1ª ocorrência."}
    </p>
  </section>

  <footer>Gerado automaticamente a partir de vendas.csv — conferência por linha, sem amostragem.</footer>
</div>
</body>
</html>
"""

with open(ARQ_HTML, "w", encoding="utf-8") as f:
    f.write(html)

# ---------- resumo no terminal ----------
print(f"linhas de dados no csv : {total_linhas}")
print(f"pedidos validos        : {len(validos)}")
print(f"descartadas invalidas  : {n_invalidas}  {dict((k, v) for k, v in descarte.items() if k != 'duplicada')}")
print(f"descartadas duplicadas : {descarte['duplicada']} (conflitantes: {conflito_dup})")
print(f"receita total          : {brl(receita_total)}")
for cat, (q, r) in cat_ord:
    print(f"  {cat:<12} qtd={q:>5}  receita={brl(r)}")
for i, (p, q) in enumerate(top5, 1):
    print(f"  top{i}: {p:<20} qtd={q}")
print(f"periodo: {min(datas)} .. {max(datas)}")
print(f"-> {ARQ_HTML} gerado")
