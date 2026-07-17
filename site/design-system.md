# Design System — Overclock Benchmark v2

Herdado do overclock-web: brutalist/industrial, fundo preto, accent vermelho `#ef4444`,
tipografia mono (Geist Mono). Fonte única de estilo: `site/assets/site.css`
(Parte 1 = landing/componentes públicos; Parte 2 = componentes das páginas internas).
O gerador `tools/publish.py` só emite classes documentadas aqui — não inventar visual novo
em template.

## Tokens

### Cores

| Token | Valor | Uso |
|---|---|---|
| `--color-bg` | `#000000` | fundo global |
| `--color-deep` | `#050505` | seções alternadas (`.site-sec-alt`), terminal |
| `--color-ink` | `#ffffff` | texto principal |
| `--color-muted` | `#6b7280` | labels, metadados |
| `--color-muted-2` | `#9ca3af` | texto secundário |
| `--color-faint` | `#4b5563` | bordas hover, célula vazia |
| `--color-faintest` | `#1f2937` | hairlines |
| `--color-brand` | `#ef4444` | accent, CTAs, destaques |
| `--color-brand-2` | `#dc2626` | hover do accent, gradientes |
| `--status-online` | `#22c55e` | veredito "entregou", custo baixo |
| `--status-busy` | `#eab308` | veredito "defeitos" |
| `--status-error` | `#ef4444` | veredito "quebrou", custo alto |

Gradientes por vendor (avatar de modelo): Anthropic vermelho, OpenAI verde, xAI âmbar,
Zhipu azul, Google roxo, Moonshot rosa — definidos em `VENDOR_GRADIENT` no publish.py.

### Tipografia

Fonte única: `--site-font-mono` (Geist Mono via Google Fonts, `@import` no CSS).
Escala: `--t-h1` (clamp 40–80px) · `--t-h2` (clamp 28–48px) · `--t-h3` 20px ·
`--t-body` 16px · `--t-body-sm` 14px · `--t-meta` 12px · `--t-caption` 11px ·
`--t-label` 10px. Labels sempre uppercase + `--ls-label` (0.18em).

### Radius e bordas

`--r-sm` 4px · `--r-md` 6px · `--r-lg` 8px · `--r-xl` 12px · `--r-pill` 999px.
Borda padrão: `--border-hair` (1px `--color-faintest`). Glow do accent:
`--glow-red-sm/md/lg`.

## Componentes — Parte 1 (landing)

- `.site-nav` / `.site-nav-in` / `.site-logo` / `.site-nav-links` — nav sticky com blur.
  Logomark: `.logo-mark` (quadrado gradiente com "OB").
- `.site-hero` + `.site-hero-grid` + `.site-hero-badge` + `.hero-rig` (dials de KPI) —
  hero da home. Dials derivam do results.json, nunca hardcode.
- `.site-sec` / `.site-sec-alt` / `.site-sec-label` / `.site-sec-head` — seção com
  label uppercase + head.
- `.site-btn` (`-brand`, `-ghost`, `-lg`) — botões.
- `.kpi-grid` / `.kpi-card` (variantes `.brand`, `.green`) — cards de estatística.
- `.table-wrap` + `.results-table` — tabela de resultados; linha `.hero` = melhor do
  teste (borda esquerda accent). Células usam `.model-row`/`.model-avatar`/`.model-name`/
  `.model-vendor`, `.verdict-badge` (`-entregou`/`-defeitos`/`-quebrou`), `.cost-bar`,
  `.cell-null` ("—").
- `.pill` (`-benchmark`, `-diaadia`) — pill de trilha do teste.
- `.track-tabs` / `.track-tab` — filtro de trilha (JS progressivo: mostra/esconde `<tr>`
  já renderizados; a tabela funciona sem JS).
- `.method-grid` / `.method-card` — cards de metodologia.
- `.comparisons-grid` / `.comparison-card` — grid de duelos em destaque.
- `.site-footer` / `.site-foot-cols` / `.site-foot-bar` — rodapé. O carimbo do gerador
  (`.gen-note`) vive no `.site-foot-bar`.

## Componentes — Parte 2 (páginas internas)

- `.crumb` — breadcrumb (`placar / teste 001`).
- `.page-head` — cabeçalho interno: `.eyebrow` (label com quadradinho accent) + `h1` +
  `.lede` + `.note`.
- `.vlogo` — logomark SVG inline do vendor (fill=currentColor).
- `.spec-grid` / `.spec-card` — ficha de specs do modelo (preço, contexto, vereditos).
- `.term` / `.term-bar` / `.term-body` — bloco terminal com o resumo do prompt canônico.
- `.runs-grid` / `.run-cell` (variante `.hero`) / `.run-head` / `.run-frame` /
  `.run-foot` — preview dos runs em iframe.
- `.runblock` / `.rb-head` / `.rb-meta` / `.rb-body` — run + narrativa na ficha do modelo.
- `.duel-hero` / `.duel-side` / `.vs` — hero do comparativo 1v1.
  `.model-avatar.lg` = avatar grande com logo do vendor.
- `.duel-chips` / `.duel-chip` — chips "vs modelo-X" na ficha do modelo.
- `.selbar` — seletor de duelo no índice de comparativos.
- `.prose` — narrativa markdown renderizada (h2/h3/p/ul/blockquote/tabela `.tblwrap`).
- `.legend` — legenda de vereditos sob tabelas.
- `.analysis` — bloco de análise com borda esquerda accent.
- `.est` — custo estimado (`≈` + `sup` "est"). `.sub`/`.bnote` — subtextos de célula.

## Regras

1. Todo número visível deriva de `site/data/results.json` (ou scores.json/enrichment.json).
   Célula sem dado = `—` (`.cell-null`). Nunca hardcode em template.
2. Veredito só existe via julgamento: `verdict=null` → badge "aguardando julgamento".
3. Conteúdo principal SEMPRE server-side no HTML (funciona via `file://`).
   JS apenas para interatividade progressiva (filtros, seletor de duelo).
4. Ícones/logos: SVG inline `fill=currentColor` (simple-icons). Sem libs externas.
5. Novo componente → adicionar aqui + no CSS antes de usar no gerador.
