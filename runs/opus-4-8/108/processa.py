#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Limpa o vendas.csv sujo e gera relatorio.html com as métricas do semestre."""
import csv
import html
import io
from collections import Counter, defaultdict
from datetime import datetime

SRC = "vendas.csv"
OUT = "relatorio.html"

# --- Parsers robustos --------------------------------------------------------

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"]

def parse_data(raw):
    s = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def parse_valor(raw):
    """Aceita '219.90', '129,90', 'R$ 59,90', 'R$ 1.299,90' etc."""
    s = raw.strip()
    if not s:
        return None
    s = s.replace("R$", "").replace("r$", "").strip()
    s = s.replace(" ", "").replace(" ", "")
    if not s:
        return None
    # decide separador decimal: o último ',' ou '.' que aparece é o decimal
    last_sep = max(s.rfind(","), s.rfind("."))
    if last_sep == -1:
        int_part, dec_part = s, ""
    else:
        int_part = s[:last_sep]
        dec_part = s[last_sep + 1:]
    # remove separadores de milhar remanescentes da parte inteira
    int_part = int_part.replace(".", "").replace(",", "")
    norm = int_part + ("." + dec_part if dec_part else "")
    try:
        v = float(norm)
    except ValueError:
        return None
    if v <= 0:
        return None
    return v

def parse_qtd(raw):
    s = raw.strip()
    if not s.isdigit():
        return None
    q = int(s)
    return q if q > 0 else None

def norm_key(raw):
    return " ".join(raw.strip().split()).lower()

CAT_DISPLAY = {
    "vestuario": "Vestuário",
    "calcados": "Calçados",
    "acessorios": "Acessórios",
}

# --- Processamento ------------------------------------------------------------

total_linhas = 0
descartes = Counter()          # motivo -> qtd
vistos = set()                 # pedido_id já contabilizado (dedup)

receita_total = 0.0
receita_por_cat = defaultdict(float)
qtd_por_produto = defaultdict(int)
produto_labels = defaultdict(Counter)   # chave -> Counter de grafias originais
pedidos_validos = 0

with open(SRC, encoding="utf-8", newline="") as f:
    reader = csv.reader(f, delimiter=";")
    header = next(reader, None)
    for row in reader:
        # csv.reader devolve [] para linha totalmente vazia
        if not row or all(c.strip() == "" for c in row):
            total_linhas += 1
            descartes["vazia"] += 1
            continue
        total_linhas += 1
        if len(row) != 7:
            descartes["malformada"] += 1
            continue
        pedido_id, data_raw, produto_raw, cat_raw, qtd_raw, valor_raw, canal_raw = row

        pid = pedido_id.strip()
        if not pid:
            descartes["sem_id"] += 1
            continue

        data = parse_data(data_raw)
        if data is None:
            descartes["data_invalida"] += 1
            continue

        qtd = parse_qtd(qtd_raw)
        if qtd is None:
            descartes["qtd_invalida"] += 1
            continue

        valor = parse_valor(valor_raw)
        if valor is None:
            descartes["valor_invalido"] += 1
            continue

        # dedup pela chave primária (pedido_id) — só entre linhas já válidas
        if pid in vistos:
            descartes["duplicada"] += 1
            continue
        vistos.add(pid)

        # linha VÁLIDA
        pedidos_validos += 1
        cat_key = norm_key(cat_raw)
        prod_key = norm_key(produto_raw)
        subtotal = qtd * valor
        receita_total += subtotal
        receita_por_cat[cat_key] += subtotal
        qtd_por_produto[prod_key] += qtd
        produto_labels[prod_key][produto_raw.strip()] += 1

total_descartadas = sum(descartes.values())

# rótulos de exibição
def cat_label(k):
    return CAT_DISPLAY.get(k, k.capitalize())

def prod_label(k):
    return produto_labels[k].most_common(1)[0][0]

cats_ordenadas = sorted(receita_por_cat.items(), key=lambda kv: kv[1], reverse=True)
top5 = sorted(qtd_por_produto.items(), key=lambda kv: (-kv[1], prod_label(kv[0])))[:5]

# --- Relatório de conferência no terminal ------------------------------------
print("== RESUMO ==")
print(f"Linhas de dados lidas (fora cabeçalho): {total_linhas}")
print(f"Pedidos válidos: {pedidos_validos}")
print(f"Descartadas (total): {total_descartadas}")
for motivo, n in descartes.most_common():
    print(f"  - {motivo}: {n}")
print(f"Confere soma: {pedidos_validos} + {total_descartadas} = {pedidos_validos + total_descartadas} (esperado {total_linhas})")
print(f"Receita total: R$ {receita_total:,.2f}")
print("Receita por categoria:")
for k, v in cats_ordenadas:
    print(f"  {cat_label(k)}: R$ {v:,.2f}")
print("Top 5 produtos por quantidade:")
for k, q in top5:
    print(f"  {prod_label(k)}: {q}")

# --- Formatação pt-BR ---------------------------------------------------------

def brl(v):
    s = f"{v:,.2f}"                       # 1,234,567.89
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    return "R$ " + s

def num(v):
    return f"{v:,}".replace(",", ".")

# --- Geração do HTML ----------------------------------------------------------

cat_rows = "\n".join(
    f'      <tr><td>{html.escape(cat_label(k))}</td>'
    f'<td class="num">{brl(v)}</td>'
    f'<td class="num">{v/receita_total*100:.1f}%</td></tr>'
    for k, v in cats_ordenadas
)

top_rows = "\n".join(
    f'      <tr><td class="rank">{i}</td><td>{html.escape(prod_label(k))}</td>'
    f'<td class="num">{num(q)}</td></tr>'
    for i, (k, q) in enumerate(top5, 1)
)

motivo_nomes = {
    "vazia": "Linhas em branco",
    "malformada": "Linhas quebradas / nº de colunas errado",
    "sem_id": "Sem pedido_id",
    "data_invalida": "Data ilegível",
    "qtd_invalida": "Quantidade inválida",
    "valor_invalido": "Valor inválido (ex.: ERRO_IMPORT)",
    "duplicada": "Pedidos duplicados",
}
desc_rows = "\n".join(
    f'      <tr><td>{html.escape(motivo_nomes.get(m, m))}</td>'
    f'<td class="num">{num(n)}</td></tr>'
    for m, n in descartes.most_common()
)

gerado_em = datetime.now().strftime("%d/%m/%Y %H:%M")

doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório de Vendas — Semestre</title>
<style>
  :root {{
    --bg:#0f172a; --card:#1e293b; --line:#334155; --txt:#e2e8f0;
    --muted:#94a3b8; --accent:#38bdf8; --good:#34d399; --warn:#fbbf24;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    line-height:1.5; padding:32px 16px;
  }}
  .wrap {{ max-width:920px; margin:0 auto; }}
  h1 {{ font-size:26px; margin:0 0 4px; }}
  .sub {{ color:var(--muted); font-size:14px; margin-bottom:28px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:32px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px; }}
  .card .label {{ color:var(--muted); font-size:13px; text-transform:uppercase; letter-spacing:.04em; }}
  .card .value {{ font-size:28px; font-weight:700; margin-top:6px; }}
  .card .value.accent {{ color:var(--accent); }}
  .card .value.good {{ color:var(--good); }}
  .card .value.warn {{ color:var(--warn); }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px 24px; margin-bottom:24px; }}
  h2 {{ font-size:17px; margin:0 0 14px; }}
  table {{ width:100%; border-collapse:collapse; font-size:15px; }}
  th, td {{ text-align:left; padding:10px 8px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--muted); font-weight:600; font-size:13px; text-transform:uppercase; letter-spacing:.03em; }}
  tr:last-child td {{ border-bottom:none; }}
  td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.rank {{ color:var(--accent); font-weight:700; width:40px; }}
  .foot {{ color:var(--muted); font-size:12px; text-align:center; margin-top:8px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Relatório de Vendas — Semestre</h1>
  <div class="sub">Gerado a partir de <code>vendas.csv</code> em {gerado_em}</div>

  <div class="cards">
    <div class="card">
      <div class="label">Receita total</div>
      <div class="value accent">{brl(receita_total)}</div>
    </div>
    <div class="card">
      <div class="label">Pedidos válidos</div>
      <div class="value good">{num(pedidos_validos)}</div>
    </div>
    <div class="card">
      <div class="label">Linhas descartadas</div>
      <div class="value warn">{num(total_descartadas)}</div>
    </div>
    <div class="card">
      <div class="label">Total de linhas lidas</div>
      <div class="value">{num(total_linhas)}</div>
    </div>
  </div>

  <section>
    <h2>Receita por categoria</h2>
    <table>
      <thead><tr><th>Categoria</th><th class="num">Receita</th><th class="num">% do total</th></tr></thead>
      <tbody>
{cat_rows}
      </tbody>
    </table>
  </section>

  <section>
    <h2>Top 5 produtos por quantidade vendida</h2>
    <table>
      <thead><tr><th>#</th><th>Produto</th><th class="num">Unidades</th></tr></thead>
      <tbody>
{top_rows}
      </tbody>
    </table>
  </section>

  <section>
    <h2>Linhas descartadas — por motivo</h2>
    <table>
      <thead><tr><th>Motivo</th><th class="num">Linhas</th></tr></thead>
      <tbody>
{desc_rows}
      <tr style="border-top:2px solid var(--line)"><td><strong>Total descartado</strong></td><td class="num"><strong>{num(total_descartadas)}</strong></td></tr>
      </tbody>
    </table>
  </section>

  <div class="foot">
    {num(total_linhas)} linhas lidas &nbsp;=&nbsp; {num(pedidos_validos)} válidas &nbsp;+&nbsp; {num(total_descartadas)} descartadas.
    Datas normalizadas de 4 formatos; valores com R$/vírgula/ponto unificados; categorias e produtos consolidados por nome; duplicatas removidas por pedido_id.
  </div>
</div>
</body>
</html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(doc)

print(f"\nGerado: {OUT}")
