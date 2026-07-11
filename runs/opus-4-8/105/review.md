# Review de Código — Mural de Recados

Revisão de `index.html` e `mural.js` antes de subir para produção.
Achados organizados por severidade. **Nada foi corrigido** — é só o diagnóstico.

> Resumo executivo: **não subir como está.** Há um XSS armazenado explorável por
> qualquer visitante, um segredo de produção exposto no client e uma race
> condition que corrompe/perde recados. Qualquer um dos três já é bloqueador.

---

## 🔴 Crítico

### C1 — XSS armazenado (Stored XSS) via `innerHTML`
- **Arquivo:** `mural.js`, linhas ~39–42 (`render()`)
- **Problema:** `autor`, `mensagem` e `quando` são concatenados direto em
  `el.innerHTML` sem nenhum escaping. Como esses valores vêm do formulário
  (`campoAutor.value` / `campoMensagem.value`) e são persistidos, qualquer
  visitante pode publicar um recado com
  `<img src=x onerror="/* código */">` ou `<script>` e o código roda no
  navegador de **todo mundo** que abrir o mural. É XSS persistente, o tipo mais
  grave, ainda por cima em um mural que "aparece pra todo mundo".
- **Como corrigir:** nunca montar HTML por concatenação com dado do usuário.
  Usar `textContent` para inserir os campos, criando os nós separadamente
  (`document.createElement` + `el.textContent = r.autor`). Alternativa: escapar
  cada campo (`&`, `<`, `>`, `"`, `'`) antes de interpolar. `textContent` é o
  caminho seguro e mais simples aqui.

### C2 — Segredo de produção hardcoded e exposto no client
- **Arquivo:** `mural.js`, linha 4 (`var API_TOKEN = "sk_live_…"`)
- **Problema:** um token com prefixo `sk_live_` (padrão de chave secreta de
  produção) está no JavaScript entregue ao navegador. Qualquer pessoa abre o
  "Ver código-fonte" / DevTools e copia o token. Se ele for válido, é
  comprometimento imediato da conta da API de moderação. Além disso, o token
  nunca é usado no código (ver B1) — está lá só vazando.
- **Como corrigir:** (1) **Revogar/rotacionar o token agora** — considere-o
  comprometido no momento em que foi commitado. (2) Remover do client. Qualquer
  chamada que precise dele tem que sair de um backend, com o segredo em variável
  de ambiente, nunca embarcado no front. (3) Garantir que não fique no histórico
  do git (limpar histórico se já foi commitado).

### C3 — Race condition / perda de dados no sync
- **Arquivo:** `mural.js`, linhas 24–30 (`salvarNoServidor`), 60–66 (`submit`),
  70–73 (`setInterval`)
- **Problema:** o modelo é *last-write-wins com o array inteiro*.
  `carregarDoServidor()` **substitui** o array `recados` local inteiro pelo
  conteúdo do storage a cada 3s, e `salvarNoServidor()` grava o array local
  inteiro de volta (com atraso aleatório de até 400ms). Dois cenários quebram:
  1. **Perda de recados de outros:** o usuário A digita e publica; o save é
     agendado com latência. Antes de salvar, ele grava por cima do que o usuário
     B publicou nesse meio-tempo → recados de B somem.
  2. **Sobrescrita do próprio recado:** entre o `push` local e o `setItem`
     atrasado, o `setInterval` pode rodar `carregarDoServidor()` e descartar o
     recado recém-adicionado que ainda não foi persistido.
  Ou seja, sob concorrência real (o propósito declarado do mural), há corrupção
  e perda silenciosa de dados.
- **Como corrigir:** não regravar o array inteiro. Persistir por operação
  (append de um único recado) e, na leitura, mesclar por `id` em vez de
  substituir. Num backend real, isso é um `POST /recados` que insere uma linha,
  não um "salvar o mundo inteiro". Enquanto for localStorage, ler → mesclar →
  gravar de forma atômica por item, com IDs estáveis (ver M3).

---

## 🟡 Médio

### M1 — Off-by-one: o recado mais antigo nunca aparece
- **Arquivo:** `mural.js`, linha 35 (`for (var i = recados.length - 1; i > 0; i--)`)
- **Problema:** a condição `i > 0` para no índice 1; o índice `0` (o primeiro
  recado publicado) **nunca é renderizado**. O mural sempre "come" o recado mais
  antigo.
- **Como corrigir:** trocar por `i >= 0`.

### M2 — `agora()` gera data errada (mês) e sem zero-padding
- **Arquivo:** `mural.js`, linhas 47–50
- **Problema:** `d.getMonth()` retorna 0–11, então julho vira `6` — todo mês sai
  com um a menos. Também não há zero-padding (dia 5 de julho → `5/6/2026`) e não
  há hora, então recados do mesmo dia ficam indistinguíveis. Data exibida é
  enganosa.
- **Como corrigir:** `d.getMonth() + 1`, aplicar `padStart(2, '0')` em dia/mês,
  e considerar guardar um timestamp ISO (`d.toISOString()`) para ordenar e
  formatar corretamente. Guardar o timestamp também ajuda a ordenar de verdade
  em vez de confiar na ordem do array.

### M3 — `id` gerado por `recados.length + 1` (colisão)
- **Arquivo:** `mural.js`, linha 55
- **Problema:** o id é derivado do tamanho do array. Depois de sincronizar com
  recados de outros usuários (ou após qualquer remoção futura), `length + 1`
  gera ids repetidos. Hoje o `id` nem chega a ser usado (ver B1), mas ao
  implementar a mesclagem correta (C3) esse esquema quebra na hora.
- **Como corrigir:** usar identificador único de verdade —
  `crypto.randomUUID()` — no momento da criação.

### M4 — `catch` vazio engole erros de leitura
- **Arquivo:** `mural.js`, linhas 15–22 (`carregarDoServidor`)
- **Problema:** se o JSON no storage estiver corrompido, o erro é silenciado
  (o comentário "qualquer erro a gente ignora que dá certo" é justamente o
  antipadrão). `recados` fica com o valor anterior e o problema vira invisível —
  difícil de diagnosticar em produção.
- **Como corrigir:** ao menos logar o erro (`console.error`) e decidir
  explicitamente o fallback (ex.: resetar para `[]` ou mostrar aviso no
  `#status`). Não silenciar.

---

## 🟢 Baixo

### B1 — Código morto: `ehSpam()` e `API_TOKEN` nunca são usados
- **Arquivo:** `mural.js`, linhas 4 e 76–81
- **Problema:** a função `ehSpam()` está definida mas **nunca é chamada** — a
  "moderação" anunciada nos comentários simplesmente não acontece. O
  `API_TOKEN` de moderação também nunca é referenciado. Além de código morto,
  passa uma falsa sensação de que há proteção contra spam. (O risco de
  segurança do token continua sendo o C2.)
- **Como corrigir:** ou remover o código morto, ou de fato aplicar a moderação
  no fluxo de publicação — mas moderação/anti-spam confiável tem que ser no
  backend, não no client, onde é trivial burlar.

### B2 — Detecção de spam frágil (se vier a ser usada)
- **Arquivo:** `mural.js`, linhas 76–81
- **Problema:** `mensagem.indexOf("http") == -1` é fácil de burlar (link sem
  `http`, `hxxp`, encurtadores) e dá falso positivo em qualquer texto que
  contenha a substring "http". Também usa `==` em vez de `===`.
- **Como corrigir:** se manter filtro no client, tratar como dica de UX apenas;
  a decisão real de spam precisa ser server-side. Usar `===`.

### B3 — `var status` sombreia `window.status`
- **Arquivo:** `mural.js`, linha 11
- **Problema:** `status` é uma propriedade global do `window`. A `var status`
  local funciona por sombreamento, mas é frágil e confunde. Vale renomear para
  `elStatus` (e o mesmo cuidado com nomes muito genéricos).
- **Como corrigir:** renomear a variável.

### B4 — Sem `trim`/validação real dos campos
- **Arquivo:** `mural.js`, linhas 56–57
- **Problema:** `required` no HTML barra campo vazio, mas espaços em branco
  (`"   "`) passam e viram recado "válido". Nenhum limite de tamanho — dá pra
  colar um texto gigante e estourar a quota do localStorage.
- **Como corrigir:** `.value.trim()` + checagem de não-vazio antes de publicar,
  e um `maxLength` no `<textarea>`/validação de tamanho.

### B5 — `render()` reconstrói o DOM inteiro a cada 3s
- **Arquivo:** `mural.js`, linhas 32–33 e 70–73
- **Problema:** o `setInterval` chama `render()` mesmo quando nada mudou,
  fazendo `mural.innerHTML = ""` e recriando tudo. Isso pisca a lista, perde
  scroll/seleção e desperdiça CPU. Em produção com muitos recados, fica pesado.
- **Como corrigir:** só re-renderizar quando os dados realmente mudarem
  (comparar com o estado anterior) e/ou fazer render incremental. Fora do escopo
  imediato, mas pesa na UX.

### B6 — `localStorage.setItem` pode lançar `QuotaExceededError`
- **Arquivo:** `mural.js`, linha 27
- **Problema:** sem tratamento; se a quota estourar, o `submit` quebra
  silenciosamente e o "Publicado!" nunca aparece.
- **Como corrigir:** envolver em `try/catch` e sinalizar falha ao usuário no
  `#status`.

---

## Nota sobre a arquitetura

Os comentários chamam o localStorage de "backend" e "servidor". Isso **não é**
multiusuário: cada navegador tem o seu próprio storage isolado — recados de um
visitante nunca chegam a outro. Se a expectativa de produto é "aparece pra todo
mundo que abrir o mural" (como diz o `index.html`), isso **não vai funcionar**
sem um backend real. C3 descreve os bugs *dentro* do modelo atual, mas o modelo
em si não entrega o requisito. Vale alinhar isso antes de priorizar as
correções pontuais.
