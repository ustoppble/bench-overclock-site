#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Processa vendas.csv (exportação suja do semestre) e gera relatorio.html.

Patologias tratadas:
  - data em 5 formatos (ISO aaaa-mm-dd, dd/mm/aaaa, d/m/aaaa, dd-mm-aa, etc.)
  - valor com ".", "," ou prefixo "R$ "
  - 15 linhas com "ERRO_IMPORT" no valor -> invalidas
  - categoria com case/espacos aleatorios
  - produto com case aleatorio
  - 39 linhas quebradas (apenas 3 campos)
  - 8 linhas em branco
  - linhas duplicadas (mesmo pedido_id)
Pipeline de cada registro: cada linha descartada conta para UM unico motivo
  (a primeira falha encontrada), evitando dupla contagem.
"""
import csv
from collections import defaultdict
from datetime import datetime

CSV_PATH = "vendas.csv"
OUT_PATH = "relatorio.html"

# Nomes canonicos de exibicao (key = casefold do nome limpo)
PROD_DISPLAY = {
    "jaqueta corta-vento": "Jaqueta corta-vento",
    "calça jeans": "Calça jeans",
    "camiseta básica": "Camiseta básica",
    "meia kit 3": "Meia kit 3",
    "boné aba reta": "Boné aba reta",
    "tênis corrida": "Tênis corrida",
    "chinelo slide": "Chinelo slide",
    "mochila urbana": "Mochila urbana",
    "bermuda tactel": "Bermuda tactel",
    "óculos de sol": "Óculos de sol",
}

# Categorias canonicas (key = casefold sem acento da categoria crua limpa)
CAT_DISPLAY = {
    "vestuario": "Vestuário",
    "calcados": "Calçados",
    "acessorios": "Acessórios",
}


def parse_valor(raw):
    """Devolve float ou None se for invalido (ex.: 'ERRO_IMPORT')."""
    s = raw.strip()
    if not s or s.upper() == "ERRO_IMPORT":
        return None
    s = s.replace("R$", "").strip()
    s = s.replace(" ", "")            # eventual espaco milhar
    # valores < 1000: troca separador decimal ',' por '.'
    s = s.replace(".", "").replace(",", ".") if ("," in s) else s
    try:
        v = float(s)
    except ValueError:
        return None
    return v if v >= 0 else None


def parse_data(raw):
    """Devolve date ou None. Aceita os 5 formatos do arquivo."""
    s = raw.strip()
    fmts = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%m-%y"]
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    return None


def norm_key(s):
    return " ".join(s.strip().split()).casefold()


# ---------------------------------------------------------------------- leitura
blank = 0
incompletas = 0          # < 7 campos
bad_valor = 0            # valor invalido / ERRO_IMPORT
bad_outro = 0            # data/quantidade/categoria invalida
duplicadas = 0
vistos = set()           # pedido_id ja validados

# metricas
pedidos_validos = 0
receita_total = 0.0
receita_cat = defaultdict(float)          # cat_key -> receita
qtd_prod = defaultdict(int)               # prod_key -> qtd total
qtd_cat = defaultdict(int)                # cat_key -> qtd total (bonus)
mes_receita = defaultdict(float)          # 'aaaa-mm' -> receita
total_linhas = 0                          # linhas fisicas exceto cabecalho

with open(CSV_PATH, newline="", encoding="utf-8") as fh:
    reader = csv.reader(fh, delimiter=";")
    header = next(reader, None)
    for row in reader:
        total_linhas += 1
        if not any(c.strip() for c in row):   # linha em branco
            blank += 1
            continue
        if len(row) < 7:                      # linha quebrada
            incompletas += 1
            continue
        pid = row[0].strip()
        d = parse_data(row[1])
        prod_key = norm_key(row[2])
        cat_raw = norm_key(row[3])
        cat_key = cat_raw.replace("á", "a").replace("ç", "c").replace("ó", "o") \
                        .replace("é", "e").replace("í", "i").replace("ã", "a")
        try:
            qtd = int(row[4])
        except ValueError:
            qtd = None
        valor = parse_valor(row[5])

        if valor is None or qtd is None or qtd <= 0 or d is None or cat_key not in CAT_DISPLAY:
            if valor is None:
                bad_valor += 1
            else:
                bad_outro += 1
            continue
        if pid in vistos:
            duplicadas += 1
            continue
        vistos.add(pid)

        pedidos_validos += 1
        sub = qtd * valor
        receita_total += sub
        receita_cat[cat_key] += sub
        qtd_cat[cat_key] += qtd
        qtd_prod[prod_key] += qtd
        mes_receita[d.strftime("%Y-%m")] += sub

descartadas = incompletas + bad_valor + bad_outro + duplicadas

# ---------------------------------------------------------------------- helpers
def brl(v):
    s = f"{v:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def intbr(n):
    """Inteiro com separador de milhar pt-BR (ponto)."""
    return f"{n:,}".replace(",", ".")

def pct(n, d):
    return f"{(100.0 * n / d):.1f}%".replace(".", ",")


print("=== RESUMO DO PROCESSAMENTO ===")
print(f"Linhas fisicas (exceto cabecalho): {total_linhas}")
print(f"  em branco (ignoradas): {blank}")
print(f"  incompletas (<7 campos, descartadas): {incompletas}")
print(f"  valor invalido/ERRO_IMPORT (descartadas): {bad_valor}")
print(f"  outro campo invalido (descartadas): {bad_outro}")
print(f"  duplicadas (mesmo pedido_id, descartadas): {duplicadas}")
print(f"TOTAL descartadas: {descartadas}")
print(f"Pedidos validos: {pedidos_validos}")
print(f"Receita total: {brl(receita_total)}")
print("\nReceita por categoria:")
for k, v in sorted(receita_cat.items(), key=lambda x: -x[1]):
    print(f"  {CAT_DISPLAY[k]:12s} {brl(v)}  ({pct(v, receita_total)})")
print("\nTop 5 produtos por quantidade:")
for k, v in sorted(qtd_prod.items(), key=lambda x: -x[1])[:5]:
    print(f"  {PROD_DISPLAY.get(k,k):22s} {v}")
print("\nReceita por mes:")
for k in sorted(mes_receita):
    print(f"  {k}: {brl(mes_receita[k])}")


# ============================================================ geracao do HTML
NOMES_MES = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}
COR_CAT = {  # cor por categoria
    "vestuario": "#4f46e5",
    "acessorios": "#0ea5e9",
    "calcados": "#f59e0b",
}
COR_PROD = "#4f46e5"
COR_MES = "#10b981"

ticket_medio = receita_total / pedidos_validos if pedidos_validos else 0.0


def bar(valor, vmax, cor):
    """Barra CSS proporcional (0-100%)."""
    w = (valor / vmax * 100) if vmax else 0
    return f'<div class="bar"><span style="width:{w:.1f}%;background:{cor}"></span></div>'


# --- categorias (ordenado por receita desc)
cats_ord = sorted(receita_cat.items(), key=lambda x: -x[1])
cat_max = max((v for _, v in cats_ord), default=1)
linhas_cat = []
for k, v in cats_ord:
    linhas_cat.append(f"""
      <tr>
        <td class="nome"><span class="dot" style="background:{COR_CAT[k]}"></span>{CAT_DISPLAY[k]}</td>
        <td class="num">{brl(v)}</td>
        <td class="barcell">{bar(v, cat_max, COR_CAT[k])}</td>
        <td class="num small">{pct(v, receita_total)}</td>
        <td class="num small">{qtd_cat[k]} un.</td>
      </tr>""")
tb_cat = "\n".join(linhas_cat)

# --- top 5 produtos por quantidade
top5 = sorted(qtd_prod.items(), key=lambda x: -x[1])[:5]
qtd_max = max((v for _, v in top5), default=1)
linhas_top = []
for k, v in top5:
    linhas_top.append(f"""
      <tr>
        <td class="rk">{top5.index((k,v))+1}</td>
        <td class="nome">{PROD_DISPLAY.get(k, k)}</td>
        <td class="num"><strong>{v}</strong> un.</td>
        <td class="barcell">{bar(v, qtd_max, COR_PROD)}</td>
      </tr>""")
tb_top = "\n".join(linhas_top)

# --- receita por mes (bonus: prova o parsing de data multi-formato)
mes_ord = sorted(mes_receita.items())
mes_max = max((v for _, v in mes_ord), default=1)
linhas_mes = []
for k, v in mes_ord:
    ano, mes = k.split("-")
    linhas_mes.append(f"""
      <tr>
        <td class="nome">{NOMES_MES[mes]}/{ano[2:]}</td>
        <td class="num">{brl(v)}</td>
        <td class="barcell">{bar(v, mes_max, COR_MES)}</td>
      </tr>""")
tb_mes = "\n".join(linhas_mes)

# --- tabela de descartes
descartes = [
    ("Linhas em branco (apenas whitespace)", blank, "ignored",
     "Ignoradas — não são registros de venda"),
    ("Linhas quebradas / incompletas (menos de 7 campos)", incompletas, "bad",
     "Ex.: “P10015;24/06/2026;Camiseta básica” — faltam categoria, qtd, valor e canal"),
    ("Valor inválido (ex.: “ERRO_IMPORT”)", bad_valor, "bad",
     "Sem preço unitário não é possível calcular receita"),
    ("Outro campo inválido (data/quantidade/categoria)", bad_outro, "bad",
     "Não houve nenhum caso após a normalização"),
    ("Linhas duplicadas (mesmo pedido_id)", duplicadas, "dup",
     "Mesmo pedido repetido — mantida apenas a 1ª ocorrência"),
]
linhas_desc = []
for nome, n, tipo, obs in descartes:
    linhas_desc.append(f"""
      <tr class="{tipo}">
        <td>{nome}</td>
        <td class="num">{n}</td>
        <td class="obs">{obs}</td>
      </tr>""")
tb_desc = "\n".join(linhas_desc)

total_lidas = total_linhas + 1  # +cabecalho

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  background:#f4f5fa;color:#1e293b;line-height:1.5;padding:32px 16px}
.wrap{max-width:980px;margin:0 auto}
header{margin-bottom:28px}
header h1{font-size:26px;font-weight:700;letter-spacing:-.3px}
header .sub{color:#64748b;font-size:14px;margin-top:4px}
header .meta{display:inline-flex;gap:8px;align-items:center;margin-top:10px;
  font-size:12px;color:#64748b;background:#fff;border:1px solid #e2e8f0;
  padding:5px 11px;border-radius:999px}
.dotmeta{width:7px;height:7px;border-radius:50%;background:#10b981}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px}
.kpi{background:#fff;border:1px solid #e8eaf2;border-radius:14px;padding:18px 18px 16px;
  box-shadow:0 1px 2px rgba(16,24,40,.04)}
.kpi .lbl{font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:.6px;font-weight:600}
.kpi .val{font-size:23px;font-weight:700;margin-top:8px;letter-spacing:-.5px}
.kpi .val.neg{color:#dc2626}
.kpi .val.ok{color:#059669}
.kpi .hint{font-size:12px;color:#94a3b8;margin-top:4px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:22px}
.card{background:#fff;border:1px solid #e8eaf2;border-radius:14px;padding:20px 22px;
  box-shadow:0 1px 2px rgba(16,24,40,.04)}
.card.full{grid-column:1/-1}
.card h2{font-size:16px;font-weight:700;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.card h2 .tag{font-size:11px;font-weight:600;color:#64748b;background:#f1f5f9;
  padding:2px 8px;border-radius:999px}
table{width:100%;border-collapse:collapse;font-size:14px}
td,th{text-align:left;padding:9px 8px;vertical-align:middle}
td.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
td.num.small{font-weight:500;color:#475569}
td.barcell{padding:9px 8px;width:34%}
td.nome{font-weight:500}
td.rk{font-weight:700;color:#94a3b8;width:26px;text-align:center}
.bar{height:10px;background:#eef1f7;border-radius:6px;overflow:hidden}
.bar span{display:block;height:100%;border-radius:6px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px;vertical-align:middle}
td.obs{font-size:12px;color:#94a3b8}
tr.dup td{color:#b45309}
tr.ignored td{color:#94a3b8}
tfoot td{border-top:2px solid #e2e8f0;font-weight:700;padding-top:11px}
tfoot td.num{color:#1e293b}
.note{font-size:12.5px;color:#64748b;background:#f8fafc;border:1px dashed #e2e8f0;
  border-radius:10px;padding:12px 14px;margin-top:16px}
.foot{margin-top:26px;color:#94a3b8;font-size:12px;text-align:center}
@media(max-width:720px){.grid{grid-template-columns:repeat(2,1fr)}.cols{grid-template-columns:1fr}}
"""

html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Relatório de Vendas — 1º Semestre 2026</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Relatório de Vendas — 1º Semestre 2026</h1>
    <div class="sub">Análise consolidada das vendas a partir de <code>vendas.csv</code></div>
    <div class="meta"><span class="dotmeta"></span> {intbr(total_lidas)} linhas lidas &nbsp;·&nbsp; {intbr(pedidos_validos)} pedidos válidos &nbsp;·&nbsp; {descartadas} linhas descartadas</div>
  </header>

  <section class="grid">
    <div class="kpi">
      <div class="lbl">Receita total</div>
      <div class="val ok">{brl(receita_total)}</div>
      <div class="hint">soma de quantidade × valor unitário</div>
    </div>
    <div class="kpi">
      <div class="lbl">Pedidos válidos</div>
      <div class="val">{intbr(pedidos_validos)}</div>
      <div class="hint">após limpeza e remoção de duplicatas</div>
    </div>
    <div class="kpi">
      <div class="lbl">Ticket médio</div>
      <div class="val">{brl(ticket_medio)}</div>
      <div class="hint">receita ÷ pedidos válidos</div>
    </div>
    <div class="kpi">
      <div class="lbl">Linhas descartadas</div>
      <div class="val neg">{descartadas}</div>
      <div class="hint">inválidas ou duplicadas</div>
    </div>
  </section>

  <section class="cols">
    <div class="card">
      <h2>Receita por categoria <span class="tag">{pct(receita_cat['vestuario'],receita_total)} líder</span></h2>
      <table>
        <tbody>{tb_cat}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>Top 5 produtos <span class="tag">por quantidade</span></h2>
      <table>
        <tbody>{tb_top}
        </tbody>
      </table>
    </div>

    <div class="card full">
      <h2>Receita por mês <span class="tag">prova do tratamento das 5 datas</span></h2>
      <table>
        <tbody>{tb_mes}
        </tbody>
      </table>
    </div>

    <div class="card full">
      <h2>Rastreabilidade das linhas descartadas <span class="tag">auditoria</span></h2>
      <table>
        <thead><tr><th>Motivo do descarte</th><th style="text-align:right">Linhas</th><th>Observação</th></tr></thead>
        <tbody>{tb_desc}
        </tbody>
        <tfoot>
          <tr><td>Total descartado (inválidas + duplicadas)</td><td class="num">{descartadas}</td><td class="obs">{pct(descartadas, total_linhas)} das {intbr(total_linhas)} linhas de dados</td></tr>
        </tfoot>
      </table>
      <div class="note">
        <strong>Como cada sujeira foi tratada:</strong> data normalizada dos 5 formatos
        (<code>aaaa-mm-dd</code>, <code>dd/mm/aaaa</code>, <code>d/m/aaaa</code>, <code>dd-mm-aa</code>)
        para <code>dd/mm/aaaa</code>; valor limpo de <code>"R$ "</code>, com <code>,</code> e <code>.</code>
        reconciliados para decimal; categoria e produto normalizados quanto a caixa e espaços;
        duplicatas resolvidas pela chave <code>pedido_id</code> (1ª ocorrência mantida).
        Cada linha descartada é contada uma única vez, pelo primeiro motivo que falha.
      </div>
    </div>
  </section>

  <div class="foot">Gerado por processar.py a partir de vendas.csv · {total_linhas+1:,} linhas brutas → {intbr(pedidos_validos)} pedidos válidos</div>
</div>
</body>
</html>
"""

with open(OUT_PATH, "w", encoding="utf-8") as fh:
    fh.write(html)
print(f"\n[OK] {OUT_PATH} gerado ({len(html):,} bytes)")
