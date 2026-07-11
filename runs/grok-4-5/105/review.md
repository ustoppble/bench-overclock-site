# Code Review — Mural de Recados

**Arquivos:** `index.html`, `mural.js`  
**Escopo:** diagnóstico apenas (sem correções de código)  
**Contexto:** app legado de estagiário, candidata a produção nesta semana

---

## Resumo executivo

O mural **não está pronto para produção**. Há XSS armazenado trivial (qualquer visitante executa JS no browser dos outros), segredo de API embutido no frontend, persistência que **não é multi-usuário de verdade** (`localStorage` é por browser), e um bug de loop que **esconde o primeiro recado**. A “moderação” e o token nunca são usados. Priorize: XSS → modelo de backend/auth → bugs de dados/sync → limpeza.

---

## Crítico

### 1. XSS armazenado via `innerHTML` com dados do usuário

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~39–42 |
| **Severidade** | Crítico |

**Problema:** `autor` e `mensagem` vêm do formulário e são concatenados em HTML sem escape:

```js
el.innerHTML =
  '<span class="autor">' + r.autor + '</span>' +
  '<span class="quando">' + r.quando + '</span>' +
  "<p>" + r.mensagem + "</p>";
```

Qualquer payload como `<img src=x onerror=alert(document.cookie)>` ou `<script>...</script>` (e variantes com handlers) é persistido em `localStorage` e executado em todo `render()` — inclusive no poll a cada 3s. Em produção com backend real e cookies de sessão, isso vira roubo de sessão / defacement / phishing no domínio.

**Como corrigir:**

- Nunca usar `innerHTML` com input de usuário. Preferir `textContent` / `createElement` + `appendChild`, ou uma lib de escape HTML.
- Escapar no servidor também (defesa em profundidade) se houver API real.
- Content-Security-Policy restritiva (sem `unsafe-inline` desnecessário) reduz o dano residual.

---

### 2. Token de API exposto no JavaScript do cliente

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~4 |
| **Severidade** | Crítico |

**Problema:**

```js
var API_TOKEN = "sk_live_[REDACTED-chave-fake-da-fixture]";
```

Segredos em código frontend são públicos (View Source, DevTools, cache de CDN). O prefixo `sk_live_` sugere credencial de produção. Mesmo que hoje o token não seja usado (ver achado de código morto), o padrão é perigoso e o valor já está commitado/distribuído.

**Como corrigir:**

- Remover o token do repositório e do bundle.
- Rotacionar/revogar o token imediatamente se for real.
- Chamar APIs de moderação **só no backend**, com secret em variável de ambiente / secret manager.
- Se o token já vazou em git, considerar histórico (`git filter-repo` / BFG) + rotação.

---

### 3. “Backend multi-usuário” é só `localStorage` — dados e modelo errados para produção

| | |
|---|---|
| **Arquivo** | `mural.js` (+ copy em `index.html`) |
| **Linhas** | ~15–30, ~69–73; `index.html` ~27 |
| **Severidade** | Crítico (produto / segurança de dados) |

**Problema:**

- `localStorage` é **por origem e por browser/perfil**, não compartilhado entre usuários, dispositivos ou abas de outros PCs.
- O subtítulo promete: *“aparece pra todo mundo que abrir o mural”* — isso **não acontece** com a implementação atual.
- Qualquer script na mesma origem (XSS, extensão, console) lê/altera/apaga o mural.
- Sem autenticação, autorização, rate limit, auditoria ou backup.
- Limite típico ~5MB; sem validação de tamanho, um post enorme quebra o storage.

**Como corrigir:**

- Backend real (API REST/GraphQL) com banco; `localStorage` no máximo como cache offline.
- Auth (mesmo que anônima com rate-limit por IP/sessão) e validação server-side de payload.
- Não confiar no cliente para integridade dos recados.

---

### 4. Race condition: poll sobrescreve memória e o save grava estado stale (perda de recados)

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~24–30 (save assíncrono), ~52–67 (submit), ~69–73 (poll) |
| **Severidade** | Crítico (integridade de dados) |

**Problema:** fluxo típico de perda:

1. Usuário publica → `recados.push(novo)` → `salvarNoServidor` agenda `setTimeout` (0–400ms) que fará `JSON.stringify(recados)`.
2. Antes do timeout, o `setInterval` (3s) chama `carregarDoServidor()`, que faz `recados = JSON.parse(...)` com o snapshot **antigo** (ainda sem o post).
3. O timeout dispara e grava o `recados` **já sobrescrito** → post some do storage.
4. `render()` do poll também “some” o recado da UI até um reload inconsistente.

Várias publicações rápidas + latência aleatória aumentam last-write-wins e estados incoerentes. Não há merge, versionamento (ETag/versão), nem fila de writes.

**Como corrigir:**

- No cliente simulado: salvar **o array passado por valor** no momento do write (cópia), ou serializar antes do `setTimeout`; não reler/sobrescrever `recados` global sem merge.
- Em API real: POST atômico no servidor; GET não deve apagar writes pendentes; otimistic UI com reconciliação por `id`/timestamp; debounce/lock de sync.
- Ideal: uma única fonte de verdade no servidor; cliente só aplica respostas.

---

## Médio

### 5. Off-by-one: o primeiro recado nunca é exibido

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~35 |
| **Severidade** | Médio |

**Problema:**

```js
for (var i = recados.length - 1; i > 0; i--) {
```

A condição `i > 0` **pula o índice 0**. Com 1 recado, o mural fica vazio; com N, o mais antigo some sempre.

**Como corrigir:** usar `i >= 0` (ou `for...of` em cópia invertida / `slice().reverse()`).

---

### 6. Mês da data errado (`getMonth()` é 0-based)

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~47–50 |
| **Severidade** | Médio |

**Problema:**

```js
return d.getDate() + "/" + d.getMonth() + "/" + d.getFullYear();
```

`getMonth()` retorna 0–11. Janeiro vira `…/0/…`, dezembro `…/11/…`. Data exibida incorreta em todos os posts.

**Como corrigir:** `d.getMonth() + 1`, pad com zero se quiser `DD/MM/YYYY`, ou `toLocaleDateString('pt-BR')` / `Intl.DateTimeFormat`.

---

### 7. Variável global `status` colide com `window.status`

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~11, ~61–63 |
| **Severidade** | Médio |

**Problema:** em script clássico (não-module), `var status = document.getElementById("status")` no topo vira propriedade do `window`. Historicamente `window.status` é string da barra de status; em vários browsers o setter **coage para string**. Resultado: `status` deixa de ser o elemento DOM e `status.textContent = "Publicando..."` falha (no-op ou erro) — feedback de UI some.

**Como corrigir:** renomear (`statusEl`, `elStatus`) ou encapsular em IIFE/module (`type="module"`) para não poluir `window`.

---

### 8. IDs frágeis e colidentes

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~55 |
| **Severidade** | Médio |

**Problema:** `id: recados.length + 1` não é único se houver delete, reload com race, ou múltiplos clientes. Dois posts no mesmo comprimento de array geram o mesmo id.

**Como corrigir:** `crypto.randomUUID()`, ULID, ou id monotônico gerado **no servidor**.

---

### 9. Erros de parse/storage engolidos em silêncio

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~16–21 |
| **Severidade** | Médio |

**Problema:** `catch` vazio com comentário “qualquer erro a gente ignora”. JSON corrompido, quota excedida no `setItem`, ou valor que não é array → falha opaca, mural vazio ou crash em `render`/`push` sem mensagem ao usuário. `salvarNoServidor` não tem `try/catch` nem callback de erro.

**Como corrigir:** validar `Array.isArray(recados)` após parse; reset controlado ou recovery; log + UI de erro; tratar `QuotaExceededError`.

---

### 10. Sem validação de tamanho, tipo ou conteúdo (cliente e “servidor”)

| | |
|---|---|
| **Arquivo** | `mural.js`, `index.html` |
| **Linhas** | form ~28–30; submit ~54–58 |
| **Severidade** | Médio |

**Problema:** só `required` no HTML (bypassável). Sem `maxlength`, trim, limite de caracteres, ou schema. Facilita flood do storage, posts só com espaços, e payloads XSS enormes.

**Como corrigir:** limites no cliente **e** no servidor; trim; rejeitar HTML se a regra de negócio for texto puro; rate limiting.

---

### 11. Moderação inexistente: `ehSpam` e token são código morto

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~4, ~75–81 |
| **Severidade** | Médio (funcional / segurança de conteúdo) |

**Problema:** `ehSpam` nunca é chamada; `API_TOKEN` nunca é usado. Links spam passam direto. A checagem `indexOf("http")` ainda seria fraca (case-sensitive, fácil de contornar com ofuscação).

**Como corrigir:** ou implementar moderação de verdade no backend, ou remover código morto e o token. Não deixar stubs que dão falsa sensação de proteção.

---

### 12. Save assíncrono sem cancelamento / sem estado de loading no botão

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~52–67 |
| **Severidade** | Médio (UX + race) |

**Problema:** double-submit rápido gera dois posts e dois timeouts de save (last write wins). `form.reset()` imediato impede reenvio se o save “falhar”. Botão não desabilita durante “Publicando...”.

**Como corrigir:** desabilitar submit até callback; fila de mutações; idempotency key no POST real.

---

## Baixo

### 13. Detecção de spam ingênua (se um dia for ligada)

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~76–80 |
| **Severidade** | Baixo |

**Problema:** só substring `"http"`; não cobre muitos padrões de abuso; falso positivo em texto legítimo (“http” no meio de palavra é raro, mas a política é pobre). Melhor URL parser + lista/allowlist no servidor.

---

### 14. Sem `type="module"` / IIFE — poluição do escopo global

| | |
|---|---|
| **Arquivo** | `mural.js`, `index.html` ~35 |
| **Severidade** | Baixo |

**Problema:** `recados`, `form`, `API_TOKEN`, etc. ficam em `window`, acessíveis a qualquer outro script na página (e facilitam exploração pós-XSS).

**Como corrigir:** `<script type="module" src="mural.js">` ou IIFE.

---

### 15. Acessibilidade e semântica limitadas

| | |
|---|---|
| **Arquivo** | `index.html` |
| **Linhas** | ~28–33 |
| **Severidade** | Baixo |

**Problema:** inputs sem `<label>` associado; `#status` não usa `role="status"` / `aria-live` para leitores de tela; botão sem feedback de busy.

**Como corrigir:** labels explícitos, `aria-live="polite"` no status, `aria-busy` no form durante publish.

---

### 16. Data sem hora e sem timezone explícito

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~47–50, ~58 |
| **Severidade** | Baixo |

**Problema:** só dia/mês/ano local; posts do mesmo dia indistinguíveis; sem ISO timestamp para ordenação confiável entre fusos.

**Como corrigir:** gravar `new Date().toISOString()` e formatar na UI.

---

### 17. Ordenação só pela posição no array

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~34–35, ~60 |
| **Severidade** | Baixo |

**Problema:** assume que append = ordem cronológica. Após merges/sync futuros, pode ficar errado sem ordenar por timestamp.

**Como corrigir:** ordenar por `createdAt` antes de renderizar.

---

### 18. CSS/HTML mínimos sem proteção de headers (CSP, etc.)

| | |
|---|---|
| **Arquivo** | `index.html` (e config do servidor de produção) |
| **Linhas** | documento inteiro |
| **Severidade** | Baixo (até XSS ser resolvido; depois vira defesa em camadas) |

**Problema:** sem CSP, sem menção a headers (`X-Content-Type-Options`, etc.). Em static hosting isso se configura no servidor/CDN.

**Como corrigir:** CSP, HTTPS only, headers de segurança no deploy.

---

### 19. Comentários e tom de “funciona na minha máquina”

| | |
|---|---|
| **Arquivo** | `mural.js` |
| **Linhas** | ~1–2, ~20 |
| **Severidade** | Baixo (manutenibilidade) |

**Problema:** documenta dívida técnica mas normaliza engolir erro. Em produção, isso atrasa incident response.

**Como corrigir:** erros observáveis (log/metrics); TODOs com ticket; remover ironia do caminho crítico.

---

## Código morto / não usado

| Item | Onde | Notas |
|------|------|--------|
| `API_TOKEN` | `mural.js` ~4 | Nunca lido; risco de vazamento mesmo assim |
| `ehSpam` | `mural.js` ~76–81 | Nunca chamada; moderação não existe |

---

## Matriz rápida de priorização (para a semana)

| Prioridade | Achado | Por quê |
|------------|--------|---------|
| P0 | XSS (`innerHTML`) | Explorável por qualquer autor de recado |
| P0 | Token no cliente + rotação | Compromete qualquer API real |
| P0 | Backend de verdade | Sem isso não há “mural pra todo mundo” |
| P0 | Race save vs poll | Perda silenciosa de posts |
| P1 | Loop `i > 0` | Feature quebrada (1º recado invisível) |
| P1 | `getMonth()` | Datas erradas |
| P1 | `window.status` | UI de status possivelmente morta |
| P2 | IDs, validação, erros, double-submit | Robustez |
| P3 | a11y, CSP, limpeza de mortos | Higiene |

---

## O que *não* está “errado”, só frágil

- Estrutura HTML simples e legível; CSS básico ok para MVP interno.
- `preventDefault` no submit está correto.
- Separação `carregar` / `salvar` / `render` é um começo razoável **depois** de backend real e escape de output.

---

## Conclusão

Tratar como **protótipo de UI**, não como app multi-usuário seguro. Antes de produção: **eliminar XSS**, **tirar secrets do front**, **persistir de verdade no servidor com writes atômicos**, e **corrigir o loop de render + datas + sync**. O restante (validação, a11y, CSP, remover mortos) fecha o pacote para não voltar incidente na semana seguinte.
