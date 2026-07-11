# Review — Mural de Recados (index.html + mural.js)

Diagnóstico completo, sem correções aplicadas. Organizado por severidade.

---

## CRÍTICO

### 1. XSS armazenado (Stored XSS) via `innerHTML`
**Arquivo:** `mural.js`, linhas 39-43 (função `render`)

```js
el.innerHTML =
  '<span class="autor">' + r.autor + '</span>' +
  '<span class="quando">' + r.quando + '</span>' +
  "<p>" + r.mensagem + "</p>";
```

`r.autor` e `r.mensagem` vêm direto do input do usuário (`campoAutor.value` / `campoMensagem.value`, linhas 56-57) e são jogados em `innerHTML` sem nenhum escaping. Qualquer visitante pode publicar um recado com `<img src=x onerror="...">` ou `<script>` e o payload roda no navegador de **todo mundo** que abrir o mural — inclusive persistido via localStorage, ou seja, ataque fica "gravado" e dispara toda vez que a página carrega.

**Correção:** nunca montar HTML por concatenação de string com dado do usuário. Usar `textContent` nos nós (`document.createElement` + `.textContent = r.autor`, etc.) ou uma função de escape de entidades HTML antes de interpolar.

---

### 2. Token de API "live" hardcoded no JS client-side
**Arquivo:** `mural.js`, linha 4

```js
var API_TOKEN = "sk_live_***"; // token da API de moderação
```

Um token de produção (`sk_live_...`) está escrito em texto puro num arquivo servido para qualquer visitante do site — basta abrir "ver código-fonte" ou o DevTools. Mesmo não sendo usado em lugar nenhum do código (ver item de código morto abaixo), o simples fato de estar no bundle client já é uma credencial vazada.

**Correção:** remover o token do client. Se a moderação depende de uma API externa, essa chamada precisa ser feita por um backend (que guarda o token em variável de ambiente/secrets manager), nunca pelo navegador do usuário. Revogar/rotacionar esse token antes de subir para produção, já que ele está potencialmente exposto neste repositório.

---

### 3. Race condition / "lost update" entre usuários e abas
**Arquivo:** `mural.js`, linhas 24-30 (`salvarNoServidor`) e 70-73 (`setInterval`)

O "backend" é o array inteiro serializado em `localStorage`. O fluxo é: `recados.push(novo)` em memória → `render()` imediato (otimista) → `salvarNoServidor` grava o array **inteiro** no `localStorage` depois de um delay aleatório de até 400ms (linha 29) → a cada 3s (`SYNC_INTERVAL_MS`), `carregarDoServidor()` **sobrescreve** `recados` em memória com o que estiver no `localStorage` (linhas 70-73).

Cenário de perda de dado: usuário A publica um recado; antes dos até 400ms do `setTimeout` completarem, o `setInterval` de sincronização dispara e recarrega `recados` a partir do `localStorage` (que ainda não tem o recado novo) — isso descarta o recado que estava só em memória. Se dois recados forem publicados quase ao mesmo tempo (duas abas, ou dois cliques rápidos), o último `salvarNoServidor` a terminar sobrescreve o array inteiro e pode apagar o recado do outro (last-write-wins sobre o array completo, não um append).

Além disso, o comentário do código ("simula multiusuário") é enganoso: `localStorage` é isolado por navegador/origem — **usuários diferentes em máquinas diferentes nunca veem os recados uns dos outros**. Isso não é uma simulação de multiusuário real, é multiusuário só entre abas do mesmo navegador. Se o objetivo de produção é um mural visível para várias pessoas em dispositivos diferentes, essa arquitetura não atende o requisito básico do produto.

**Correção:** usar um backend real com storage compartilhado (banco de dados) e operação de **append** atômica (ex.: `INSERT`), não read-modify-write do array inteiro. Se por algum motivo for mantido client-side/protótipo, no mínimo fazer merge por `id`/timestamp em vez de sobrescrever tudo.

---

## MÉDIO

### 4. Bug de off-by-one: o primeiro recado nunca aparece
**Arquivo:** `mural.js`, linha 35

```js
for (var i = recados.length - 1; i > 0; i--) {
```

A condição `i > 0` pula o índice `0` — ou seja, o recado mais antigo (o primeiro `id: 1` já publicado) nunca é renderizado, mesmo estando salvo. Fica invisível para sempre.

**Correção:** trocar para `i >= 0`.

---

### 5. `ehSpam()` existe mas nunca é chamada — moderação morta
**Arquivo:** `mural.js`, linhas 76-81 (definição) vs. 52-67 (`submit` handler)

A função de detecção de spam por link (`ehSpam`) está implementada mas não é invocada em lugar nenhum do fluxo de publicação. Isso passa a falsa impressão de que existe moderação, quando na prática qualquer recado com link é publicado sem filtro.

**Correção:** chamar `ehSpam(novo)` no handler de submit e decidir o que fazer (bloquear, marcar como spam, exigir aprovação) — ou remover a função morta se a decisão for não ter moderação.

---

### 6. Data exibida com mês errado
**Arquivo:** `mural.js`, linha 49

```js
function agora() {
  var d = new Date();
  return d.getDate() + "/" + d.getMonth() + "/" + d.getFullYear();
}
```

`Date.getMonth()` é 0-indexado (janeiro = 0, dezembro = 11). O mural vai mostrar, por exemplo, "10/6/2026" para 10 de julho de 2026 — mês sempre um a menos que o real.

**Correção:** usar `(d.getMonth() + 1)`.

---

### 7. Sem tratamento de erro ao salvar (falha silenciosa)
**Arquivo:** `mural.js`, linhas 24-30

```js
function salvarNoServidor(callback) {
  setTimeout(function () {
    localStorage.setItem("mural-recados", JSON.stringify(recados));
    if (callback) callback();
  }, Math.random() * 400);
}
```

Diferente de `carregarDoServidor` (que tem `try/catch`), aqui não há tratamento de erro. Se `localStorage.setItem` estourar a cota do navegador (`QuotaExceededError`, comum com mural que só cresce e nunca expira/pagina), a exceção sobe sem ser pega, o `callback` nunca roda, e o status fica travado em "Publicando..." para sempre — sem qualquer feedback de falha ao usuário, e o recado nunca é persistido de fato.

**Correção:** envolver o `setItem` em `try/catch` e atualizar o `status` com mensagem de erro em caso de falha.

---

### 8. Geração de ID insegura/colidível
**Arquivo:** `mural.js`, linha 55

```js
id: recados.length + 1,
```

Como cada aba/cliente mantém sua própria cópia de `recados` (recarregada periodicamente do `localStorage`, ver item 3), o `id` gerado a partir do `length` local pode colidir entre recados criados quase ao mesmo tempo em contextos diferentes.

**Correção:** gerar ID com algo globalmente único (timestamp + random, ou UUID), nunca derivado do tamanho de uma cópia local do array.

---

## BAIXO

### 9. Nenhuma autenticação — qualquer um posta como qualquer nome
**Arquivo:** `index.html`, linha 28 / `mural.js`, linha 56

O campo "autor" é texto livre sem qualquer verificação de identidade. Qualquer visitante pode se passar por outra pessoa. Pode ser aceitável para um mural informal, mas vale confirmar que é intencional antes de produção.

### 10. Inputs não são normalizados (`trim`)
**Arquivo:** `mural.js`, linhas 56-57

`campoAutor.value` e `campoMensagem.value` são usados sem `.trim()`. O atributo `required` do HTML5 aceita uma string só com espaços em branco, então é possível publicar um recado "vazio" visualmente.

**Correção:** aplicar `.trim()` nos valores e validar que não ficaram vazios após o trim.

### 11. `setInterval` nunca é limpo
**Arquivo:** `mural.js`, linha 70

Não causa vazamento nesta página única sem navegação, mas se este script for reaproveitado dentro de uma SPA com múltiplas rotas/montagens, o intervalo nunca é cancelado (`clearInterval`) e vira memory leak / múltiplos timers acumulados.

### 12. Sem Content-Security-Policy
**Arquivo:** `index.html`, `<head>` (linhas 3-22)

Dado o XSS crítico do item 1, uma CSP restritiva (bloqueando `script-src` inline, por exemplo) serviria como camada extra de defesa em profundidade, mesmo depois de corrigido o `innerHTML`.

### 13. Re-render completo a cada 3s, mesmo sem mudança
**Arquivo:** `mural.js`, linhas 32-45, 70-73

`render()` faz `mural.innerHTML = ""` e reconstrói tudo do zero a cada tick do `setInterval`, independentemente de os dados terem mudado. Isso derruba seleção de texto, scroll e foco do usuário no meio da leitura, mesmo quando não há recado novo.

**Correção:** comparar os dados antes de decidir re-renderizar (ex.: hash/tamanho do array anterior) e só atualizar o DOM quando algo de fato mudou.

---

## Resumo

| Severidade | Qtd | Itens |
|---|---|---|
| Crítico | 3 | XSS armazenado, token de API exposto, race condition/lost-update (+ arquitetura não é multiusuário de fato) |
| Médio | 5 | off-by-one no render, moderação morta, mês errado na data, falha silenciosa ao salvar, ID colidível |
| Baixo | 5 | sem autenticação, sem trim, interval nunca limpo, sem CSP, re-render desnecessário |

Recomendação de prioridade antes de subir para produção: resolver os 3 críticos primeiro (especialmente o XSS e o token exposto), depois decidir se a arquitetura via `localStorage` atende o requisito de "mural visível para todo mundo" — hoje ela não atende entre usuários/dispositivos diferentes.
