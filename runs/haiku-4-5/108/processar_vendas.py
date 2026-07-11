#!/usr/bin/env python3
import csv
import re
from datetime import datetime
from collections import defaultdict
import json

# Lê o CSV
with open('vendas.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f, delimiter=';')
    linhas_brutas = list(reader)

vendas_validas = []
linhas_descartadas = []
ids_vistos = set()

for idx, linha in enumerate(linhas_brutas[1:], start=2):
    try:
        # Valida quantidade de campos
        if len(linha) < 7:
            linhas_descartadas.append((idx, 'Linha quebrada (campos faltantes)'))
            continue

        pedido_id = linha[0].strip()
        data_str = linha[1].strip()
        produto = linha[2].strip()
        categoria = linha[3].strip()
        quantidade_str = linha[4].strip()
        valor_str = linha[5].strip()

        # Valida campos obrigatórios
        if not all([pedido_id, data_str, produto, categoria, quantidade_str, valor_str]):
            linhas_descartadas.append((idx, 'Campo vazio'))
            continue

        # Detecta duplicata por pedido_id
        if pedido_id in ids_vistos:
            linhas_descartadas.append((idx, f'Duplicata: {pedido_id}'))
            continue

        # Normaliza data (3 formatos possíveis)
        data_obj = None
        try:
            # YYYY-MM-DD
            data_obj = datetime.strptime(data_str, '%Y-%m-%d')
        except ValueError:
            try:
                # DD/MM/YYYY
                data_obj = datetime.strptime(data_str, '%d/%m/%Y')
            except ValueError:
                try:
                    # DD-MM-YY
                    data_obj = datetime.strptime(data_str, '%d-%m-%y')
                except ValueError:
                    linhas_descartadas.append((idx, f'Data inválida: {data_str}'))
                    continue

        # Normaliza categoria (trim espaço, lowercase)
        categoria = categoria.strip().lower().replace('calcados', 'calçados')

        # Valida quantidade
        try:
            quantidade = int(quantidade_str)
            if quantidade <= 0:
                linhas_descartadas.append((idx, f'Quantidade inválida: {quantidade_str}'))
                continue
        except ValueError:
            linhas_descartadas.append((idx, f'Quantidade não é número: {quantidade_str}'))
            continue

        # Normaliza valor (remove R$, converte vírgula/ponto)
        valor_clean = valor_str.replace('R$', '').strip()
        valor_clean = valor_clean.replace(',', '.')

        # Rejeita valores especiais de erro
        if 'ERRO_IMPORT' in valor_clean or valor_clean == '':
            linhas_descartadas.append((idx, f'Valor inválido: {valor_str}'))
            continue

        try:
            valor = float(valor_clean)
            if valor <= 0:
                linhas_descartadas.append((idx, f'Valor <= 0: {valor}'))
                continue
        except ValueError:
            linhas_descartadas.append((idx, f'Valor não é número: {valor_str}'))
            continue

        # Linha válida!
        ids_vistos.add(pedido_id)
        vendas_validas.append({
            'pedido_id': pedido_id,
            'data': data_obj,
            'produto': produto,
            'categoria': categoria,
            'quantidade': quantidade,
            'valor_unitario': valor,
            'receita': quantidade * valor
        })

    except Exception as e:
        linhas_descartadas.append((idx, f'Erro genérico: {str(e)}'))
        continue

# Calcula métricas
receita_total = sum(v['receita'] for v in vendas_validas)
receita_por_categoria = defaultdict(float)
produtos_quantidade = defaultdict(int)

for venda in vendas_validas:
    receita_por_categoria[venda['categoria']] += venda['receita']
    produtos_quantidade[venda['produto']] += venda['quantidade']

# Top 5 produtos por quantidade
top5_produtos = sorted(produtos_quantidade.items(), key=lambda x: x[1], reverse=True)[:5]

# Estatísticas
total_linhas = len(linhas_brutas) - 1  # Exclui header
linhas_validas = len(vendas_validas)
linhas_invalidas = len(linhas_descartadas)

# Gera HTML
html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório de Vendas</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .content {{
            padding: 40px;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 30px;
            margin-bottom: 50px;
        }}
        .metric-card {{
            background: #f8f9fa;
            padding: 25px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            text-align: center;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }}
        .metric-label {{
            color: #666;
            font-size: 0.95em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            font-size: 1.5em;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th {{
            background: #f0f0f0;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #333;
            border-bottom: 2px solid #667eea;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background: #f9f9f9;
        }}
        .currency {{
            font-family: 'Courier New', monospace;
            font-weight: 600;
            color: #2d7a2d;
        }}
        .quality {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .quality-item {{
            background: #f0f7ff;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #2196F3;
        }}
        .quality-value {{
            font-size: 1.3em;
            font-weight: bold;
            color: #2196F3;
            margin: 5px 0;
        }}
        .quality-label {{
            color: #555;
            font-size: 0.9em;
        }}
        .footer {{
            background: #f5f5f5;
            padding: 20px 40px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Relatório de Vendas</h1>
            <p>Semestre 2026 - Dados Processados e Validados</p>
        </div>

        <div class="content">
            <!-- Métricas Principais -->
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-label">Receita Total</div>
                    <div class="metric-value currency">R$ {receita_total:,.2f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Pedidos Válidos</div>
                    <div class="metric-value">{linhas_validas}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Linhas Descartadas</div>
                    <div class="metric-value" style="color: #d32f2f;">{linhas_invalidas}</div>
                </div>
            </div>

            <!-- Qualidade dos Dados -->
            <div class="section">
                <h2>🔍 Qualidade dos Dados</h2>
                <div class="quality">
                    <div class="quality-item">
                        <div class="quality-label">Total de Linhas Processadas</div>
                        <div class="quality-value">{total_linhas}</div>
                    </div>
                    <div class="quality-item">
                        <div class="quality-label">Linhas Válidas</div>
                        <div class="quality-value">{linhas_validas} ({linhas_validas/total_linhas*100:.1f}%)</div>
                    </div>
                    <div class="quality-item">
                        <div class="quality-label">Linhas Descartadas</div>
                        <div class="quality-value" style="color: #d32f2f;">{linhas_invalidas} ({linhas_invalidas/total_linhas*100:.1f}%)</div>
                    </div>
                </div>
            </div>

            <!-- Receita por Categoria -->
            <div class="section">
                <h2>📈 Receita por Categoria</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Categoria</th>
                            <th style="text-align: right;">Receita Total</th>
                        </tr>
                    </thead>
                    <tbody>
"""

for categoria in sorted(receita_por_categoria.keys()):
    valor = receita_por_categoria[categoria]
    html_content += f"""                        <tr>
                            <td style="text-transform: capitalize;">{categoria}</td>
                            <td style="text-align: right;" class="currency">R$ {valor:,.2f}</td>
                        </tr>
"""

html_content += """                    </tbody>
                </table>
            </div>

            <!-- Top 5 Produtos -->
            <div class="section">
                <h2>🏆 Top 5 Produtos por Quantidade Vendida</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Posição</th>
                            <th>Produto</th>
                            <th style="text-align: right;">Quantidade</th>
                        </tr>
                    </thead>
                    <tbody>
"""

for pos, (produto, qtd) in enumerate(top5_produtos, 1):
    html_content += f"""                        <tr>
                            <td><strong>#{pos}</strong></td>
                            <td>{produto}</td>
                            <td style="text-align: right;"><strong>{qtd}</strong></td>
                        </tr>
"""

html_content += f"""                    </tbody>
                </table>
            </div>

            <!-- Detalhes das Linhas Descartadas -->
            <div class="section">
                <h2>⚠️ Linhas Descartadas ({len(linhas_descartadas)})</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Linha</th>
                            <th>Motivo</th>
                        </tr>
                    </thead>
                    <tbody>
"""

for linha_num, motivo in sorted(linhas_descartadas)[:20]:  # Mostra primeiras 20
    html_content += f"""                        <tr>
                            <td><code>{linha_num}</code></td>
                            <td><small>{motivo}</small></td>
                        </tr>
"""

if len(linhas_descartadas) > 20:
    html_content += f"""                        <tr>
                            <td colspan="2" style="text-align: center; color: #999;">
                                ... e mais {len(linhas_descartadas) - 20} linhas descartadas
                            </td>
                        </tr>
"""

html_content += f"""                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer">
            <p>✓ Relatório gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</p>
            <p>Todos os valores foram normalizados, datas corrigidas e duplicatas removidas.</p>
        </div>
    </div>
</body>
</html>
"""

# Salva HTML
with open('relatorio.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"✅ Relatório gerado com sucesso!")
print(f"📊 Total de pedidos válidos: {linhas_validas}")
print(f"❌ Linhas descartadas: {linhas_invalidas}")
print(f"💰 Receita total: R$ {receita_total:,.2f}")
