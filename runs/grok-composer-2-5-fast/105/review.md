# Revisão de código — Mural de Recados

**Arquivos analisados:** `index.html`, `mural.js`  
**Data da revisão:** 10/07/2026  
**Contexto:** app client-side que persiste recados em `localStorage` e re-renderiza a cada 3 s.

---

## Crítico

### 1. XSS — conteúdo do usuário injetado via `innerHTML`

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linha** | ~39–42 |
| **Problema** | `r.autor`, `r.mensagem` e `r.quando` são concatenados diretamente em `innerHTML`. Um recado com `<img src=x onerror=alert(1)>` ou `<script>...</script>` executa JavaScript no navegador de quem abrir o mural. Em produção, isso vira armazenamento persistente de payload malicioso (stored XSS) — qualquer visitante é afetado. |
| **Como corrigir** | Nunca usar `innerHTML` com dados de usuário. Criar nós com `document.createElement` + `textContent`, ou escapar HTML (`&`, `<`, `>`, `"`, `'`). Se precisar de links, usar uma allowlist e `URL`/`DOMPurify`. |

---

### 2. Token de API exposto no código-fonte do cliente

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linha** | ~4 |
| **Problema** | `API_TOKEN = "sk_live_[REDACTED-chave-fake-da-fixture]"` está hardcoded no JS que vai pro browser. Qualquer pessoa abre DevTools ou o bundle e obtém a chave. O prefixo `sk_live_` sugere credencial real de produção. Mesmo não sendo usada hoje, vai parar no repositório, no cache do CDN e em histórico de deploy. |
| **Como corrigir** | Revogar/rotacionar o token imediatamente se for real. Segredos só no servidor (variável de ambiente). Chamadas de moderação via backend proxy autenticado; o cliente nunca vê a chave. Remover a constante morta. |

---

### 3. Race condition — recado novo pode sumir antes de ser salvo

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linhas** | ~24–30, ~52–67, ~70–73 |
| **Problema** | Fluxo ao publicar: `push` → `salvarNoServidor` (assíncrono, 0–400 ms) → `render`. Em paralelo, `setInterval` a cada 3 s chama `carregarDoServidor()`, que **substitui** `recados` pelo que está no `localStorage` (ainda sem o recado novo). Se o intervalo disparar entre o `push` e o `setTimeout` do save, o recado some da memória; o callback de save grava o array **sem** ele. Perda silenciosa de dados. |
| **Como corrigir** | Usar backend com writes atômicos, ou fila de saves com mutex/flag `salvando`. Não recarregar do storage enquanto há write pendente. Ouvir `storage` event entre abas em vez de polling cego. Merge por `id` + timestamp em vez de substituir o array inteiro. |

---

### 4. Race condition — múltiplas abas / múltiplos usuários (last-write-wins)

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linhas** | ~15–22, ~24–30, ~70–73 |
| **Problema** | Cada aba mantém cópia em memória, lê o snapshot inteiro, altera e grava de volta. Duas abas publicando quase ao mesmo tempo: a segunda grava por cima da primeira — recados somem. O comentário no topo fala em “simular multiusuário”, mas `localStorage` não oferece concorrência; em produção com vários usuários o comportamento é imprevisível. |
| **Como corrigir** | Backend real (REST/WebSocket) com persistência transacional. Se ficar só no cliente, no mínimo `storage` event + merge por `id` e retry em conflito — ainda assim inadequado para produção multiusuário. |

---

### 5. Bug — o recado mais antigo (índice 0) nunca é exibido

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linha** | ~35 |
| **Problema** | O loop usa `for (var i = recados.length - 1; i > 0; i--)`. A condição `i > 0` exclui `i === 0`. Com 1 recado, o mural fica vazio; com N recados, sempre falta o primeiro inserido. |
| **Como corrigir** | Trocar para `i >= 0`. Ex.: `for (var i = recados.length - 1; i >= 0; i--)`. |

---

## Médio

### 6. `localStorage` como “backend” não é adequado para produção

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linhas** | ~2–3, ~15–30, ~69–73 |
| **Problema** | Dados ficam só no browser do usuário: outro dispositivo não vê os recados; limpar cache apaga tudo; modo privado pode bloquear gravação. O subtítulo do HTML promete “aparece pra todo mundo que abrir o mural” — isso não é verdade com a implementação atual. |
| **Como corrigir** | API HTTP (POST/GET) com banco de dados. O cliente só consome a API; `localStorage` no máximo como cache offline opcional. |

---

### 7. Moderação anti-spam declarada mas nunca aplicada

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linhas** | ~4, ~75–81, ~52–67 |
| **Problema** | Há token de “API de moderação” e função `ehSpam()`, mas nenhuma é chamada no `submit`. Links, spam e conteúdo ofensivo passam direto. A detecção (`indexOf("http")`) também é frágil (`HTTP`, `www.`, encurtadores, etc.). |
| **Como corrigir** | Chamar moderação no fluxo de publicação (servidor-side). Regras no backend; bloquear ou colocar em fila antes de persistir. Remover código morto ou integrar de fato. |

---

### 8. IDs de recado colidem e não são únicos globalmente

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linha** | ~55 |
| **Problema** | `id: recados.length + 1` assume array contínuo. Após exclusão, reload, merge entre abas ou corrupção do JSON, dois recados podem ter o mesmo `id`. Impossibilita deduplicação, edição ou sync confiável. |
| **Como corrigir** | `crypto.randomUUID()` ou ULID gerado no servidor. Nunca derivar ID do tamanho do array. |

---

### 9. Data exibida incorreta (`getMonth()` base 0)

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linha** | ~49 |
| **Problema** | `d.getMonth()` retorna 0–11. Janeiro vira `15/0/2026`, dezembro `3/11/2026`. Confunde usuários e quebra ordenação se um dia migrar para string ISO. |
| **Como corrigir** | `d.toLocaleDateString("pt-BR")` ou `getMonth() + 1` com zero-padding. Melhor: gravar `ISO 8601` no dado e formatar só na UI. |

---

### 10. Erros de carga/salvamento engolidos silenciosamente

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linhas** | ~16–21, ~24–30 |
| **Problema** | `carregarDoServidor`: `catch` vazio — JSON corrompido ou quota não comunicada; usuário vê mural vazio sem saber por quê. `salvarNoServidor`: sem `try/catch`; `QuotaExceededError` ou storage bloqueado falham sem feedback; o status mostra “Publicado!” mesmo se nada foi persistido. |
| **Como corrigir** | Tratar erros e mostrar em `#status`. Em falha de parse, backup/recovery ou reset explícito com aviso. Só mostrar “Publicado!” após confirmação de persistência. |

---

### 11. Re-render completo a cada 3 s destrói o DOM

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linhas** | ~32–44, ~70–73 |
| **Problema** | `mural.innerHTML = ""` e recriação de todos os nós a cada sync causam flicker, custo de CPU e perda de estado de UI (seleção, foco, leitores de tela reanunciam tudo). |
| **Como corrigir** | Diff incremental por `id` (atualizar só o que mudou). Ou push do servidor (SSE/WebSocket) em vez de polling + rebuild total. |

---

### 12. Sem validação ou limite de tamanho nos campos

| Campo | Valor |
|-------|-------|
| **Arquivo** | `index.html` / `mural.js` |
| **Linhas** | ~28–29 (HTML), ~56–57 (JS) |
| **Problema** | Sem `maxlength`, sem `trim()`. Espaços em branco passam no `required` HTML. Mensagens enormes podem estourar quota do `localStorage` (~5 MB) ou degradar performance do mural. |
| **Como corrigir** | `maxlength` no HTML + validação no JS/servidor (`trim`, tamanho máximo, caracteres proibidos). Rejeitar com mensagem clara. |

---

## Baixo

### 13. Código morto — `API_TOKEN` e `ehSpam()`

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linhas** | ~4, ~75–81 |
| **Problema** | Constante e função nunca referenciadas. Aumenta superfície de confusão e risco (token exposto sem uso). |
| **Como corrigir** | Remover ou integrar no fluxo real de moderação. |

---

### 14. Acessibilidade — inputs sem `<label>` associado

| Campo | Valor |
|-------|-------|
| **Arquivo** | `index.html` |
| **Linhas** | ~28–29 |
| **Problema** | Só `placeholder`, sem `<label for="...">`. Leitores de tela e navegação por teclado ficam piores; placeholders somem ao digitar. |
| **Como corrigir** | `<label for="autor">Seu nome</label>` etc., ou `aria-label` explícito. |

---

### 15. Comentários enganosos / débito técnico documentado

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linhas** | ~1–3, ~20, ~25, ~69 |
| **Problema** | Comentários admitem código “às pressas” e backend fake, mas a UI promete mural público compartilhado. Quem for dar manutenção pode achar que já existe sync real. |
| **Como corrigir** | Atualizar comentários após migrar para API real, ou marcar `@deprecated` / TODO com link para issue. |

---

### 16. Polling fixo de 3 s sem backoff nem visibilidade

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linhas** | ~5, ~70–73 |
| **Problema** | `setInterval` roda com aba em background, gastando bateria/CPU sem necessidade. Sem pausa quando `document.hidden`. |
| **Como corrigir** | `document.visibilitychange` para pausar; ou eventos push; aumentar intervalo com backoff quando inativo. |

---

### 17. Campo `id` criado mas ignorado na renderização

| Campo | Valor |
|-------|-------|
| **Arquivo** | `mural.js` |
| **Linhas** | ~55, ~32–44 |
| **Problema** | Objetos têm `id`, mas `render()` não usa — dificulta diff, testes e sync futuro. |
| **Como corrigir** | `el.dataset.id = r.id` ou `key` estável ao implementar render incremental. |

---

### 18. Sem charset/escaping explícito em meta de segurança (defesa em profundidade)

| Campo | Valor |
|-------|-------|
| **Arquivo** | `index.html` |
| **Linhas** | ~3–6 |
| **Problema** | Falta CSP (`Content-Security-Policy`) para limitar inline script e `eval`. Não substitui corrigir XSS, mas reduz impacto. |
| **Como corrigir** | Header CSP no servidor: `default-src 'self'; script-src 'self'; object-src 'none'`. Ajustar se adicionar CDN. |

---

## Resumo executivo

| Severidade | Quantidade | Bloqueia produção? |
|------------|------------|--------------------|
| Crítico    | 5          | **Sim** — XSS, token vazado, perda de dados e recado invisível |
| Médio      | 7          | Parcial — UX incorreta, promessa de produto vs implementação |
| Baixo      | 6          | Não — qualidade, a11y, manutenção |

**Prioridade sugerida antes do deploy:**

1. Revogar o token `sk_live_...` se for credencial real.  
2. Eliminar XSS (trocar `innerHTML` por `textContent`).  
3. Corrigir o loop `i >= 0`.  
4. Resolver persistência (API real + writes atômicos) — `localStorage` + polling não sustentam “mural pra todo mundo”.  
5. Tratar race conditions (não recarregar durante save pendente; merge por ID).  
6. Ligar moderação no servidor ou remover o código/token morto.

---

*Revisão estática do código-fonte; não inclui testes em runtime nem auditoria de infraestrutura de deploy.*