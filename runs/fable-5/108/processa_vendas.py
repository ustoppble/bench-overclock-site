#!/usr/bin/env python3
"""Limpa vendas.csv e gera relatorio.html com os agregados do semestre."""
import html
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent
CATEGORIAS = {"vestuario", "acessorios", "calcados"}
ROTULO_CAT = {"vestuario": "Vestuário", "acessorios": "Acessórios", "calcados": "Calçados"}


def parse_data(raw):
    raw = raw.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
        if m:
            d, mo, y = map(int, m.groups())
        else:
            m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{2})", raw)
            if m:
                d, mo, y = map(int, m.groups())
                y += 2000
            else:
                return None
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_valor(raw):
    limpo = raw.strip().removeprefix("R$").strip().replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", limpo):
        return None
    return round(float(limpo), 2)


def main():
    linhas = (BASE / "vendas.csv").read_text(encoding="utf-8").splitlines()
    invalidas = 0
    duplicadas = 0
    vistos = set()
    pedidos = []
    for linha in linhas[1:]:
        campos = [c.strip() for c in linha.split(";")]
        if len(campos) != 7:
            invalidas += 1
            continue
        pid, data_raw, produto, cat_raw, qtd_raw, valor_raw, canal = campos
        data = parse_data(data_raw)
        valor = parse_valor(valor_raw)
        cat = cat_raw.lower()
        if (
            not pid
            or data is None
            or valor is None
            or cat not in CATEGORIAS
            or not qtd_raw.isdigit()
            or int(qtd_raw) <= 0
            or not produto
        ):
            invalidas += 1
            continue
        if pid in vistos:
            duplicadas += 1
            continue
        vistos.add(pid)
        pedidos.append({"produto": produto.lower(), "cat": cat, "qtd": int(qtd_raw), "valor": valor})

    receita_total = sum(p["qtd"] * p["valor"] for p in pedidos)
    receita_cat = defaultdict(float)
    qtd_produto = Counter()
    for p in pedidos:
        receita_cat[p["cat"]] += p["qtd"] * p["valor"]
        qtd_produto[p["produto"]] += p["qtd"]
    top5 = qtd_produto.most_common(5)

    def brl(v):
        return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def cap(nome):
        return nome[0].upper() + nome[1:]

    linhas_cat = "\n".join(
        f"<tr><td>{ROTULO_CAT[c]}</td><td class='num'>{brl(v)}</td></tr>"
        for c, v in sorted(receita_cat.items(), key=lambda kv: -kv[1])
    )
    linhas_top = "\n".join(
        f"<tr><td>{i}</td><td>{html.escape(cap(nome))}</td><td class='num'>{q}</td></tr>"
        for i, (nome, q) in enumerate(top5, 1)
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relatório de Vendas — 1º Semestre 2026</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0; background: #f4f5f7; color: #1f2430; }}
  main {{ max-width: 860px; margin: 0 auto; padding: 32px 20px 48px; }}
  h1 {{ font-size: 26px; margin: 0 0 4px; }}
  p.sub {{ color: #6b7280; margin: 0 0 28px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 18px 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .card .label {{ font-size: 13px; color: #6b7280; margin-bottom: 6px; }}
  .card .value {{ font-size: 24px; font-weight: 700; }}
  h2 {{ font-size: 18px; margin: 32px 0 12px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  th, td {{ padding: 10px 16px; text-align: left; font-size: 14px; }}
  th {{ background: #eef0f4; color: #4b5563; font-weight: 600; }}
  tr + tr td {{ border-top: 1px solid #eef0f4; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
</style>
</head>
<body>
<main>
  <h1>Relatório de Vendas — 1º Semestre 2026</h1>
  <p class="sub">Gerado a partir de vendas.csv ({len(linhas) - 1} linhas de dados no arquivo original)</p>

  <div class="cards">
    <div class="card"><div class="label">Receita total</div><div class="value">{brl(receita_total)}</div></div>
    <div class="card"><div class="label">Pedidos válidos</div><div class="value">{len(pedidos)}</div></div>
    <div class="card"><div class="label">Linhas inválidas descartadas</div><div class="value">{invalidas}</div></div>
    <div class="card"><div class="label">Linhas duplicadas descartadas</div><div class="value">{duplicadas}</div></div>
  </div>

  <h2>Receita por categoria</h2>
  <table>
    <tr><th>Categoria</th><th class="num">Receita</th></tr>
    {linhas_cat}
  </table>

  <h2>Top 5 produtos por quantidade vendida</h2>
  <table>
    <tr><th>#</th><th>Produto</th><th class="num">Unidades</th></tr>
    {linhas_top}
  </table>
</main>
</body>
</html>
"""
    (BASE / "relatorio.html").write_text(html_doc, encoding="utf-8")

    print(f"linhas de dados: {len(linhas) - 1}")
    print(f"pedidos validos: {len(pedidos)}")
    print(f"invalidas: {invalidas} | duplicadas: {duplicadas}")
    print(f"soma check: {len(pedidos) + invalidas + duplicadas}")
    print(f"receita total: {receita_total:.2f}")
    for c, v in sorted(receita_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {c}: {v:.2f}")
    for nome, q in top5:
        print(f"  top: {nome} = {q}")


if __name__ == "__main__":
    main()
