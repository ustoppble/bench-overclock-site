from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import html
import unicodedata


INPUT_CSV = Path("vendas.csv")
OUTPUT_HTML = Path("relatorio.html")


CATEGORY_DISPLAY = {
    "vestuario": "Vestuário",
    "acessorios": "Acessórios",
    "calcados": "Calçados",
}

PRODUCT_DISPLAY = {
    "bermuda tactel": "Bermuda tactel",
    "bone aba reta": "Boné aba reta",
    "calca jeans": "Calça jeans",
    "camiseta basica": "Camiseta básica",
    "chinelo slide": "Chinelo slide",
    "jaqueta corta-vento": "Jaqueta corta-vento",
    "meia kit 3": "Meia kit 3",
    "mochila urbana": "Mochila urbana",
    "oculos de sol": "Óculos de sol",
    "tenis corrida": "Tênis corrida",
}

VALID_CHANNELS = {"loja", "site", "marketplace"}


@dataclass(frozen=True)
class SaleRecord:
    order_id: str
    sold_on: date
    product_key: str
    category_key: str
    quantity: int
    unit_price: Decimal
    channel: str

    @property
    def revenue(self) -> Decimal:
        return self.unit_price * self.quantity


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_spaces(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_key(value: str) -> str:
    return strip_accents(normalize_spaces(value).lower())


def parse_date(raw: str) -> date:
    clean = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data invalida: {raw!r}")


def parse_money(raw: str) -> Decimal:
    clean = raw.strip().replace("R$", "").strip()
    if not clean:
        raise ValueError("valor vazio")
    if "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    try:
        value = Decimal(clean)
    except InvalidOperation as exc:
        raise ValueError(f"valor invalido: {raw!r}") from exc
    if value < 0:
        raise ValueError(f"valor negativo: {raw!r}")
    return value


def parse_quantity(raw: str) -> int:
    try:
        quantity = int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"quantidade invalida: {raw!r}") from exc
    if quantity <= 0:
        raise ValueError(f"quantidade nao positiva: {raw!r}")
    return quantity


def load_sales(csv_path: Path) -> tuple[list[SaleRecord], dict[str, int]]:
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("arquivo CSV vazio")

    expected_header = "pedido_id;data;produto;categoria;quantidade;valor_unitario;canal"
    if lines[0].strip() != expected_header:
        raise ValueError("cabecalho inesperado no CSV")

    invalid_counts = defaultdict(int)
    parsed_by_id: dict[str, list[SaleRecord]] = defaultdict(list)

    for raw_line in lines[1:]:
        if not raw_line.strip():
            invalid_counts["Linhas em branco"] += 1
            continue

        parts = raw_line.split(";")
        if len(parts) != 7:
            invalid_counts["Linhas truncadas ou quebradas"] += 1
            continue

        order_id, raw_date, raw_product, raw_category, raw_quantity, raw_value, raw_channel = parts

        try:
            sold_on = parse_date(raw_date)
            quantity = parse_quantity(raw_quantity)
            unit_price = parse_money(raw_value)
        except ValueError:
            invalid_counts["Campos numéricos ou data inválidos"] += 1
            continue

        product_key = normalize_key(raw_product)
        category_key = normalize_key(raw_category)
        channel = normalize_key(raw_channel)

        if product_key not in PRODUCT_DISPLAY:
            invalid_counts["Produto desconhecido"] += 1
            continue
        if category_key not in CATEGORY_DISPLAY:
            invalid_counts["Categoria inválida"] += 1
            continue
        if channel not in VALID_CHANNELS:
            invalid_counts["Canal inválido"] += 1
            continue

        parsed_by_id[order_id].append(
            SaleRecord(
                order_id=order_id,
                sold_on=sold_on,
                product_key=product_key,
                category_key=category_key,
                quantity=quantity,
                unit_price=unit_price,
                channel=channel,
            )
        )

    valid_sales: list[SaleRecord] = []
    duplicate_rows = 0

    for records in parsed_by_id.values():
        first = records[0]
        conflicting = any(record != first for record in records[1:])
        if conflicting:
            invalid_counts["Pedidos duplicados com conflito"] += len(records)
            continue
        valid_sales.append(first)
        duplicate_rows += len(records) - 1

    invalid_counts["Linhas duplicadas"] = duplicate_rows
    return valid_sales, dict(invalid_counts)


def format_currency(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"))
    text = f"{rounded:,.2f}"
    return f"R$ {text.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def format_integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def format_percentage(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"))
    return f"{rounded:.2f}".replace(".", ",") + "%"


def build_report(sales: list[SaleRecord], invalid_counts: dict[str, int]) -> str:
    total_revenue = sum((sale.revenue for sale in sales), Decimal("0"))
    revenue_by_category = defaultdict(lambda: Decimal("0"))
    quantity_by_product = defaultdict(int)
    revenue_by_product = defaultdict(lambda: Decimal("0"))

    for sale in sales:
        revenue_by_category[sale.category_key] += sale.revenue
        quantity_by_product[sale.product_key] += sale.quantity
        revenue_by_product[sale.product_key] += sale.revenue

    categories = sorted(
        revenue_by_category.items(),
        key=lambda item: (-item[1], CATEGORY_DISPLAY[item[0]]),
    )
    top_products = sorted(
        quantity_by_product.items(),
        key=lambda item: (-item[1], PRODUCT_DISPLAY[item[0]]),
    )[:5]

    discarded_total = sum(invalid_counts.values())
    valid_orders = len(sales)
    first_date = min(sale.sold_on for sale in sales)
    last_date = max(sale.sold_on for sale in sales)

    category_rows = "\n".join(
        (
            "            <tr>"
            f"<td>{html.escape(CATEGORY_DISPLAY[key])}</td>"
            f"<td>{format_currency(amount)}</td>"
            f"<td>{format_percentage(amount / total_revenue * Decimal('100'))}</td>"
            "</tr>"
        )
        for key, amount in categories
    )

    product_rows = "\n".join(
        (
            "            <tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(PRODUCT_DISPLAY[key])}</td>"
            f"<td>{format_integer(quantity)}</td>"
            f"<td>{format_currency(revenue_by_product[key])}</td>"
            "</tr>"
        )
        for index, (key, quantity) in enumerate(top_products, start=1)
    )

    discard_rows = "\n".join(
        (
            "            <tr>"
            f"<td>{html.escape(reason)}</td>"
            f"<td>{format_integer(count)}</td>"
            "</tr>"
        )
        for reason, count in sorted(invalid_counts.items(), key=lambda item: (-item[1], item[0]))
        if count
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Relatório de Vendas do Semestre</title>
  <style>
    :root {{
      --bg: #f4ede3;
      --paper: rgba(255, 251, 245, 0.92);
      --ink: #1f1b18;
      --muted: #6d6258;
      --accent: #c25b2a;
      --accent-deep: #8c3511;
      --line: rgba(73, 49, 35, 0.14);
      --shadow: 0 18px 40px rgba(78, 54, 37, 0.12);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(194, 91, 42, 0.18), transparent 28%),
        radial-gradient(circle at 85% 10%, rgba(114, 150, 118, 0.18), transparent 22%),
        linear-gradient(145deg, #f8f2ea 0%, #f0e4d6 55%, #ead8c7 100%);
    }}

    .shell {{
      width: min(1120px, calc(100% - 32px));
      margin: 32px auto;
      padding: 28px;
      border: 1px solid rgba(255, 255, 255, 0.55);
      border-radius: 28px;
      background: var(--paper);
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}

    .hero {{
      display: grid;
      gap: 8px;
      margin-bottom: 28px;
    }}

    .eyebrow {{
      font-size: 0.82rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent-deep);
    }}

    h1 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      font-size: clamp(2.2rem, 4vw, 3.5rem);
      line-height: 0.95;
    }}

    .lede {{
      margin: 0;
      max-width: 65ch;
      color: var(--muted);
      font-size: 1rem;
      line-height: 1.55;
    }}

    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin: 28px 0 34px;
    }}

    .card {{
      padding: 18px 18px 20px;
      border-radius: 22px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.68), rgba(255,255,255,0.88));
    }}

    .card .label {{
      color: var(--muted);
      font-size: 0.92rem;
      margin-bottom: 10px;
    }}

    .card .value {{
      font-size: clamp(1.5rem, 3vw, 2.35rem);
      font-weight: 800;
      line-height: 1;
      letter-spacing: -0.03em;
    }}

    .card .meta {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.88rem;
    }}

    .grid {{
      display: grid;
      grid-template-columns: 1.1fr 1fr;
      gap: 18px;
    }}

    .panel {{
      padding: 20px;
      border-radius: 24px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
    }}

    .panel h2 {{
      margin: 0 0 14px;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      font-size: 1.5rem;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
    }}

    th, td {{
      padding: 11px 0;
      text-align: left;
      border-bottom: 1px solid var(--line);
      font-size: 0.97rem;
    }}

    th {{
      color: var(--muted);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    td:last-child,
    th:last-child {{
      text-align: right;
    }}

    td:nth-child(3),
    th:nth-child(3) {{
      text-align: right;
    }}

    .footnote {{
      margin-top: 18px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.5;
    }}

    @media (max-width: 860px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}

      .shell {{
        width: min(100% - 20px, 1120px);
        margin: 10px auto;
        padding: 20px;
        border-radius: 22px;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">Semestre processado</div>
      <h1>Relatório consolidado das vendas</h1>
      <p class="lede">
        CSV higienizado com validação linha a linha. Foram considerados apenas pedidos com estrutura completa,
        campos parseáveis e identificador único. Período efetivo analisado: {first_date.strftime("%d/%m/%Y")} a {last_date.strftime("%d/%m/%Y")}.
      </p>
    </section>

    <section class="cards">
      <article class="card">
        <div class="label">Receita total</div>
        <div class="value">{format_currency(total_revenue)}</div>
        <div class="meta">Soma de {format_integer(valid_orders)} pedidos válidos.</div>
      </article>
      <article class="card">
        <div class="label">Pedidos válidos considerados</div>
        <div class="value">{format_integer(valid_orders)}</div>
        <div class="meta">Duplicatas removidas antes da consolidação.</div>
      </article>
      <article class="card">
        <div class="label">Linhas descartadas</div>
        <div class="value">{format_integer(discarded_total)}</div>
        <div class="meta">Inválidas ou duplicadas.</div>
      </article>
      <article class="card">
        <div class="label">Categorias consolidadas</div>
        <div class="value">{format_integer(len(categories))}</div>
        <div class="meta">Vestuário, acessórios e calçados.</div>
      </article>
    </section>

    <section class="grid">
      <article class="panel">
        <h2>Receita por categoria</h2>
        <table>
          <thead>
            <tr>
              <th>Categoria</th>
              <th>Receita</th>
              <th>Participação</th>
            </tr>
          </thead>
          <tbody>
{category_rows}
          </tbody>
        </table>
      </article>

      <article class="panel">
        <h2>Top 5 produtos por quantidade</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Produto</th>
              <th>Qtd.</th>
              <th>Receita</th>
            </tr>
          </thead>
          <tbody>
{product_rows}
          </tbody>
        </table>
      </article>
    </section>

    <section class="panel" style="margin-top: 18px;">
      <h2>Linhas descartadas</h2>
      <table>
        <thead>
          <tr>
            <th>Motivo</th>
            <th>Quantidade</th>
          </tr>
        </thead>
        <tbody>
{discard_rows}
        </tbody>
      </table>
      <div class="footnote">
        Critério de duplicidade: mesmo <code>pedido_id</code>. Se um identificador repetido trouxesse conteúdo divergente,
        todas as ocorrências desse pedido seriam descartadas por ambiguidade. Neste arquivo, as duplicatas encontradas eram repetições do mesmo registro.
      </div>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    sales, invalid_counts = load_sales(INPUT_CSV)
    report = build_report(sales, invalid_counts)
    OUTPUT_HTML.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
