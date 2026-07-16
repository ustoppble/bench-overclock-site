# Revisão de Código — Mural de Recados

**Escopo:** `index.html` (37 linhas) + `mural.js` (84 linhas)
**Resumo:** 4 achados críticos, 5 médios, 5 baixos. **Não recomendo subir em produção no estado atual** — há stored XSS, segredo exposto no cliente, perda silenciosa de dados por race condition e, principalmente, o "backend" é um stub de `localStorage` que não é multiusuário de verdade.

---

## 🔴 Crítico

### 1. O "backend" é `localStorage` — o mural não é multiusuário
- **Arquivo/linha:** `mural.js:2`, `mural.js:15-30`, `mural.js:69-73`; promessa quebrada em `index.html:26` ("aparece pra todo mundo que abrir o mural")
- **Problema:** O comentário do estagiário admite: é um "backend fake via localStorage pra simular multiusuário". `localStorage` é **por navegador/origem** — cada visitante tem o próprio mural, os recados nunca saem da máquina de quem publicou e somem se o usuário limpar os dados do site. Em produção, a funcionalidade central do produto simplesmente não existe.
- **Como corrigir:** Antes de subir, ligar o front a um backend real (ex.: `fetch` para uma API com `GET /recados` e `POST /recados`, com banco de dados). Todo o código de `localStorage` (`carregarDoServidor`/`salvarNoServidor`) precisa ser substituído, não "adaptado".

### 2. Stored XSS via `innerHTML` com entrada do usuário
- **Arquivo/linha:** `mural.js:39-42`
- **Problema:** `r.autor` e `r.mensagem` vêm direto dos campos do formulário e são concatenados numa string atribuída a `el.innerHTML`, sem nenhum escape. Publicar `<img src=x onerror="alert(document.cookie)">` como recado executa JavaScript no navegador de qualquer pessoa que abrir o mural — e o payload fica **persistido** no armazenamento (stored XSS), reaparecendo a cada render. Hoje "só" atinge o mesmo navegador, mas no momento em que o backend real for ligado (achado #1), vira XSS armazenado para todos os usuários.
- **Como corrigir:** Nunca montar HTML com dados do usuário. Criar os elementos com `document.createElement` e preencher com `textContent` (que trata o conteúdo como texto, não HTML). Alternativa: sanitizar com uma biblioteca (ex.: DOMPurify) se HTML for realmente necessário. Adicionar também uma `Content-Security-Policy` como defesa em profundidade (ver achado baixo #14).

### 3. Token de API "live" hardcoded no código client-side
- **Arquivo/linha:** `mural.js:4` (`API_TOKEN = "sk_live_9f2b..."`)
- **Problema:** Um segredo com prefixo `sk_live_` (cara de credencial de produção) está em texto claro num arquivo servido a qualquer visitante — basta "ver código-fonte". Qualquer um pode usar a "API de moderação" em nome da aplicação. Agravante: o token **nem é usado** no código (ver achado baixo #10), ou seja, é risco puro sem benefício nenhum.
- **Como corrigir:** **Revogar/rotacionar o token imediatamente** (assumir que já vazou), removê-lo do código e do histórico do git. Regra geral: segredo nunca fica no front; chamadas a APIs autenticadas passam por um backend que guarda a credencial.

### 4. Race condition entre salvar e sincronizar → perda silenciosa de recados
- **Arquivo/linha:** `mural.js:24-30` (save assíncrono), `mural.js:52-67` (submit), `mural.js:70-73` (sync a cada 3s)
- **Problema:** Dois cenários, ambos com perda de dados sem erro aparente:
  - **Aba única:** `salvarNoServidor` grava via `setTimeout` de até 400 ms, lendo a variável global `recados` **por referência**. Se o `setInterval` de 3 s rodar antes do timeout disparar, `carregarDoServidor()` **reatribui** `recados` com a versão antiga do storage — e o timeout então grava essa versão antiga, **apagando o recado recém-publicado**. A tela ainda mostra "Publicado!". Janela de ~400 ms a cada 3 s ≈ **~13% de chance por publicação**.
  - **Multiaba/multiusuário:** duas abas leem o mesmo array, cada uma dá `push` num recado diferente e a última a gravar sobrescreve a outra (*last-write-wins*). É o clássico read-modify-write sem merge nem lock.
- **Como corrigir:** Com backend real, isso se resolve com `POST` por recado (o servidor é a fonte da verdade) e re-leitura/`merge` em vez de sobrescrever a coleção inteira. Se precisar manter o stub local por enquanto: re-ler o storage **dentro** do `salvarNoServidor`, mesclar com os recados locais antes de gravar, e nunca reatribuir o array local cegamente no sync.

---

## 🟡 Médio

### 5. Off-by-one: o recado mais antigo nunca é exibido
- **Arquivo/linha:** `mural.js:35` (`for (var i = recados.length - 1; i > 0; i--)`)
- **Problema:** A condição `i > 0` pula o índice `0` — o primeiro recado do mural simplesmente não aparece.
- **Como corrigir:** Trocar para `i >= 0`.

### 6. Data exibida com mês errado
- **Arquivo/linha:** `mural.js:47-50` (`agora()`)
- **Problema:** `Date.getMonth()` é 0-based (janeiro = 0), então todo recado sai com o mês errado (julho vira "6"). Além disso não há zero-padding, gerando formato inconsistente (`5/6/2026`).
- **Como corrigir:** Usar `getMonth() + 1` com padding, ou melhor: `new Date().toLocaleDateString("pt-BR")`. Idealmente salvar o timestamp (`Date.now()` / ISO) e formatar só na exibição.

### 7. `catch` silencioso pode destruir todos os dados
- **Arquivo/linha:** `mural.js:16-22` (`carregarDoServidor`)
- **Problema:** Se o JSON do storage estiver corrompido, o `catch` vazio engole o erro e `recados` fica com o estado anterior (ou `[]`). Na próxima chamada de `salvarNoServidor`, esse estado vazio **sobrescreve o storage**, apagando definitivamente os dados que estavam lá. O comentário "qualquer erro a gente ignora que dá certo" esconde um caminho real de perda total.
- **Como corrigir:** Logar o erro; em caso de parse inválido, fazer backup do valor bruto e **não** salvar por cima de um estado desconhecido (ou resetar de forma explícita e avisada).

### 8. Falha de gravação não tratada — status fica "Publicando..." para sempre
- **Arquivo/linha:** `mural.js:24-30` e `mural.js:61-64`
- **Problema:** `localStorage.setItem` pode lançar `QuotaExceededError` (storage cheio — e nada limita o tamanho dos recados) ou `SecurityError` (modo privado/bloqueio de cookies). Como não há `try/catch` no timeout, a exceção mata o callback e a UI trava em "Publicando...", sem feedback nem recuperação.
- **Como corrigir:** Envolver a gravação em `try/catch`, exibir mensagem de erro no `#status` e reverter/remover o recado otimista da lista (ou permitir retry).

### 9. IDs frágeis e com colisão garantida
- **Arquivo/linha:** `mural.js:55` (`id: recados.length + 1`)
- **Problema:** `length + 1` não é identificador único: duas abas publicando "ao mesmo tempo" geram o mesmo id; se algum dia houver remoção de recados, ids novos colidem com antigos. Hoje o id não é usado, mas é uma armadilha pronta para quando for (moderação, exclusão, key de render).
- **Como corrigir:** Usar `crypto.randomUUID()` (ou o id gerado pelo backend, quando ele existir).

---

## 🟢 Baixo

### 10. Código morto: `ehSpam()` nunca é chamada (e a lógica é ingênua)
- **Arquivo/linha:** `mural.js:75-81`
- **Problema:** A função de "moderação" não é invocada em lugar nenhum — é código morto que dá falsa sensação de que existe moderação. E mesmo que fosse usada, `indexOf("http")` gera falsos positivos ("comprei em httpster.com" — aliás, qualquer texto com a substring) e a função sequer é aplicada a nada (não marca, não filtra, não bloqueia). O token do achado #3 reforça: a moderação foi esquecida pela metade.
- **Como corrigir:** Remover a função, ou implementar moderação de verdade no backend (nunca só no cliente, que é contornável).

### 11. `var status` sombreia o global `window.status`
- **Arquivo/linha:** `mural.js:11`
- **Problema:** `status` é uma propriedade histórica de `window`; redeclará-la como global funciona, mas é má prática e fonte de confusão/bugs sutis.
- **Como corrigir:** Renomear para `statusEl` (e, de passagem, trocar `var` por `const`/`let` no arquivo todo).

### 12. Nenhum limite ou validação de entrada
- **Arquivo/linha:** `index.html:28-29`, `mural.js:52-67`
- **Problema:** Os campos só têm `required` — sem `maxlength`, sem trim, sem validação. Uma mensagem de 5 MB estoura a quota do storage (ver achado #8); uma string de espaços passa no `required`.
- **Como corrigir:** `maxlength` nos campos + validação no submit (`trim()`, tamanho mínimo/máximo). Com backend, validar também no servidor.

### 13. Re-render completo da lista a cada 3 segundos
- **Arquivo/linha:** `mural.js:32-45`, `mural.js:70-73`
- **Problema:** `mural.innerHTML = ""` + recriar todos os nós a cada 3 s, mesmo sem mudança nenhuma. Desnecessário e escala mal (com algumas centenas de recados vira custo perceptível; também destrói seleção de texto/foco do usuário no meio da leitura).
- **Como corrigir:** Renderizar apenas quando houver mudança (comparar revisão/hash/timestamp) e, idealmente, inserir só os itens novos.

### 14. Sem `Content-Security-Policy` nem outras defesas em profundidade
- **Arquivo/linha:** `index.html:3-21` (cabeçalho)
- **Problema:** Não há CSP, o que maximiza o impacto do XSS do achado #2. Também não há nenhuma meta de segurança.
- **Como corrigir:** Após eliminar o `innerHTML`, adicionar uma CSP restritiva (ex.: `default-src 'self'; script-src 'self'`) via header HTTP ou `<meta>`, como camada extra de proteção.

---

### Sugestão de priorização
1. **Antes de qualquer deploy:** revogar o token (#3) e decidir o backend real (#1) — sem ele não há produto.
2. **Junto com o backend:** corrigir XSS (#2) e a race condition (#4), que mudam de forma com uma API de verdade.
3. **Correções rápidas independentes:** #5, #6, #7, #8, #9 — todas são mudanças de poucas linhas.
4. **Limpeza:** #10–#14.
