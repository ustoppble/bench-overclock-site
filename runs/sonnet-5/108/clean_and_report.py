#!/usr/bin/env python3
"""Limpa vendas.csv (datas/valores/categorias sujos, linhas quebradas e duplicadas) e gera relatorio.html."""
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
CSV_PATH = BASE / "vendas.csv"
OUT_PATH = BASE / "relatorio.html"

EXPECTED_FIELDS = 7


def parse_data(raw):
    raw = raw.strip()
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", raw):
        y, m, d = raw.split("-")
        return datetime(int(y), int(m), int(d))
    if "/" in raw:
        d, m, y = raw.split("/")
        return datetime(int(y), int(m), int(d))
    if re.fullmatch(r"\d{1,2}-\d{1,2}-\d{2}", raw):
        d, m, y = raw.split("-")
        return datetime(2000 + int(y), int(m), int(d))
    raise ValueError(f"formato de data desconhecido: {raw!r}")


def parse_valor(raw):
    raw = raw.strip().replace("R$", "").strip().replace(",", ".")
    return float(raw)


def clean_texto(raw):
    return raw.strip().lower().capitalize()


def main():
    linhas = CSV_PATH.read_text(encoding="utf-8").splitlines()
    header, linhas = linhas[0], linhas[1:]

    discartes = defaultdict(int)
    validos = []
    pedidos_vistos = set()

    for linha in linhas:
        if not linha.strip():
            discartes["linha_vazia"] += 1
            continue

        campos = linha.split(";")
        if len(campos) != EXPECTED_FIELDS:
            discartes["linha_quebrada"] += 1
            continue

        pedido_id, data_raw, produto_raw, categoria_raw, qtd_raw, valor_raw, canal_raw = campos

        pedido_id = pedido_id.strip()
        if pedido_id in pedidos_vistos:
            discartes["duplicada"] += 1
            continue

        try:
            data = parse_data(data_raw)
        except ValueError:
            discartes["data_invalida"] += 1
            continue

        try:
            quantidade = int(qtd_raw.strip())
        except ValueError:
            discartes["quantidade_invalida"] += 1
            continue

        try:
            valor_unitario = parse_valor(valor_raw)
        except ValueError:
            discartes["valor_invalido"] += 1
            continue

        pedidos_vistos.add(pedido_id)
        validos.append({
            "pedido_id": pedido_id,
            "data": data,
            "produto": clean_texto(produto_raw),
            "categoria": clean_texto(categoria_raw),
            "quantidade": quantidade,
            "valor_unitario": valor_unitario,
            "canal": canal_raw.strip(),
        })

    receita_total = sum(v["quantidade"] * v["valor_unitario"] for v in validos)

    receita_por_categoria = defaultdict(float)
    qtd_por_produto = defaultdict(int)
    for v in validos:
        receita_por_categoria[v["categoria"]] += v["quantidade"] * v["valor_unitario"]
        qtd_por_produto[v["produto"]] += v["quantidade"]

    categorias_ordenadas = sorted(receita_por_categoria.items(), key=lambda x: x[1], reverse=True)
    top5_produtos = sorted(qtd_por_produto.items(), key=lambda x: x[1], reverse=True)[:5]

    total_descartadas = sum(discartes.values())
    pedidos_validos = len(validos)

    def fmt_moeda(v):
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    rows_categoria = "\n".join(
        f"<tr><td>{cat}</td><td class=\"num\">{fmt_moeda(receita)}</td></tr>"
        for cat, receita in categorias_ordenadas
    )
    rows_top5 = "\n".join(
        f"<tr><td>{i}</td><td>{produto}</td><td class=\"num\">{qtd}</td></tr>"
        for i, (produto, qtd) in enumerate(top5_produtos, start=1)
    )
    motivo_label = {
        "linha_vazia": "Linha vazia",
        "linha_quebrada": "Linha quebrada (campos faltando)",
        "duplicada": "Pedido duplicado",
        "data_invalida": "Data inválida",
        "quantidade_invalida": "Quantidade inválida",
        "valor_invalido": "Valor unitário inválido",
    }
    rows_descarte = "\n".join(
        f"<tr><td>{motivo_label.get(motivo, motivo)}</td><td class=\"num\">{qtd}</td></tr>"
        for motivo, qtd in sorted(discartes.items(), key=lambda x: x[1], reverse=True)
    ) or "<tr><td colspan=\"2\">Nenhuma linha descartada</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Relatório de Vendas — Semestre</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background: #f4f5f7; color: #1f2430; margin: 0; padding: 40px; }}
  h1 {{ font-size: 24px; margin-bottom: 4px; }}
  .subtitulo {{ color: #6b7280; margin-bottom: 32px; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 20px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); min-width: 200px; flex: 1; }}
  .card .label {{ font-size: 13px; color: #6b7280; text-transform: uppercase; letter-spacing: .04em; }}
  .card .valor {{ font-size: 28px; font-weight: 700; margin-top: 6px; }}
  section {{ background: #fff; border-radius: 10px; padding: 24px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  section h2 {{ font-size: 16px; margin-top: 0; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #eef0f2; font-size: 14px; }}
  th {{ color: #6b7280; font-weight: 600; font-size: 12px; text-transform: uppercase; }}
  td.num, th.num {{ text-align: right; }}
  tr:last-child td {{ border-bottom: none; }}
  footer {{ color: #9ca3af; font-size: 12px; margin-top: 24px; }}
</style>
</head>
<body>
  <h1>Relatório de Vendas — Semestre</h1>
  <div class="subtitulo">Gerado a partir de vendas.csv, com limpeza de datas, valores, categorias e remoção de linhas inválidas/duplicadas.</div>

  <div class="cards">
    <div class="card">
      <div class="label">Receita total</div>
      <div class="valor">{fmt_moeda(receita_total)}</div>
    </div>
    <div class="card">
      <div class="label">Pedidos válidos considerados</div>
      <div class="valor">{pedidos_validos}</div>
    </div>
    <div class="card">
      <div class="label">Linhas descartadas</div>
      <div class="valor">{total_descartadas}</div>
    </div>
  </div>

  <section>
    <h2>Receita por categoria</h2>
    <table>
      <thead><tr><th>Categoria</th><th class="num">Receita</th></tr></thead>
      <tbody>
      {rows_categoria}
      </tbody>
    </table>
  </section>

  <section>
    <h2>Top 5 produtos por quantidade vendida</h2>
    <table>
      <thead><tr><th>#</th><th>Produto</th><th class="num">Quantidade</th></tr></thead>
      <tbody>
      {rows_top5}
      </tbody>
    </table>
  </section>

  <section>
    <h2>Linhas descartadas por motivo (total: {total_descartadas})</h2>
    <table>
      <thead><tr><th>Motivo</th><th class="num">Quantidade</th></tr></thead>
      <tbody>
      {rows_descarte}
      </tbody>
    </table>
  </section>

  <footer>Relatório gerado automaticamente a partir de {len(linhas)} linhas de dados (excluindo cabeçalho).</footer>
</body>
</html>
"""
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Receita total: {fmt_moeda(receita_total)}")
    print(f"Pedidos válidos: {pedidos_validos}")
    print(f"Descartadas: {dict(discartes)} (total {total_descartadas})")


if __name__ == "__main__":
    main()
