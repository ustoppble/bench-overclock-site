# Revisão de Código — Mural de Recados

**Arquivos:** `index.html`, `mural.js`
**Data:** 2026-07-10

---

## Crítico

### 1. XSS (Cross-Site Scripting) — injeção de HTML via `innerHTML`

**Arquivo:** `mural.js`, linhas 39–42

O valor de `r.autor`, `r.quando` e `r.mensagem` são concatenados diretamente no `innerHTML` sem qualquer sanitização. Qualquer usuário pode digitar `<img src=x onerror=alert(document.cookie)>` no campo "Seu nome" ou no textarea, e o código será executado no navegador de todos que abrirem o mural.

```js
el.innerHTML =
  '<span class="autor">' + r.autor + '</span>' +   // ← entrada do usuário, sem escape
  '<span class="quando">' + r.quando + '</span>' +
  "<p>" + r.mensagem + "</p>";                       // ← idem
```

**Como corrigir:** Usar `textContent` para texto plano, ou uma função de escape HTML (`createElement` + `textContent` por nó) antes de inserir no DOM. Nunca concatenar entrada do usuário em `innerHTML`.

---

### 2. Token de API exposto no código cliente

**Arquivo:** `mural.js`, linha 4

```js
var API_TOKEN = "sk_live_[REDACTED-chave-fake-da-fixture]";
```

Um token hardcoded que parece ser de produção (`sk_live_...`) está embutido em JavaScript que vai para o navegador do usuário. Qualquer pessoa pode abri-ló no DevTools e roubar a credencial.

**Como corrigir:** Remover do frontend. Se for usado em backend, fazer a chamada server-side e nunca expor o token ao cliente.

---

### 3. Race condition: submit vs. sincronização apaga recado do usuário

**Arquivo:** `mural.js`, linhas 52–67 e 70–73

Quando o usuário submete um recado, o fluxo é:

1. `recados.push(novo)` — adiciona na memória (síncrono)
2. `salvarNoServidor(callback)` — grava no `localStorage` após `setTimeout` (até 400 ms de delay aleatório)
3. `render()` — exibe na tela

Porém, o `setInterval` a cada 3 s (linha 70) chama `carregarDoServidor()`, que **sobrescreve o array `recados` na memória** com o conteúdo do `localStorage`. Se o intervalo disparar *antes* do `salvarNoServidor` completar o `setTimeout`, o recado recém-adicionado é perdido — sai da tela e nunca é persistido.

**Como corrigir:** Implementar controle de concorrência (flag ou lock), ou eliminar o `setTimeout` fake e tornar a gravação síncrona, ou usar um mecanismo de merge em vez de sobrescrever cegamente o array.

---

## Médio

### 4. Off-by-one: primeiro recado nunca é exibido

**Arquivo:** `mural.js`, linha 35

```js
for (var i = recados.length - 1; i > 0; i--) {
```

A condição `i > 0` faz o loop parar no índice `1`, pulando o recado no índice `0` (o mais antigo). O correto é `i >= 0`.

**Como corrigir:** Trocar para `i >= 0`.

---

### 5. Bug na formatação de data: mês começa em zero

**Arquivo:** `mural.js`, linha 49

```js
return d.getDate() + "/" + d.getMonth() + "/" + d.getFullYear();
```

`getMonth()` retorna 0–11. Em 10 de julho, exibe `10/6/2026` em vez de `10/07/2026`.

**Como corrigir:** Usar `d.getMonth() + 1` e preencher com zero à esquerda se necessário.

---

### 6. IDs não-únicos por design

**Arquivo:** `mural.js`, linha 55

```js
id: recados.length + 1,
```

O ID é gerado a partir do comprimento do array. Se qualquer recado for removido (ou se o array for sobrescrito pela race condition descrita no item 3), o próximo recado receberá um ID já utilizado, criando colisão.

**Como corrigir:** Usar `Date.now()` + contador, ou `crypto.randomUUID()`, ou incrementar um contador persistente separado.

---

### 7. localStorage não é compartilhado entre usuários

**Arquivo:** `mural.js`, linhas 2 e 15–22

O comentário diz "sincroniza com um backend fake via localStorage pra simular multiusuário", mas `localStorage` é isolado por *origem* (protocolo + domínio + porta) no navegador de cada pessoa. Dois usuários em máquinas diferentes jamais verão os recados um do outro.

**Como corrigir:** Se o objetivo é multiusuário, substituir `localStorage` por um backend real (API REST, WebSocket, Firebase, etc.). Se é apenas local/single-user, remover o comentário enganoso.

---

### 8. Código morto: `API_TOKEN` e `ehSpam()` nunca usados

**Arquivo:** `mural.js`, linhas 4 e 76–81

- `API_TOKEN` é declarado mas nunca referenciado em nenhum lugar do código (além de ser um risco de segurança).
- `ehSpam()` é definida mas nunca chamada. Além disso, a lógica é redundante — o retorno de `indexOf("http") == -1` já é um booleano; a função toda poderia ser uma linha.

**Como corrigir:** Remover ambos. Se a moderação for necessária, integrar de verdade no fluxo de submit (chamar `ehSpam` e rejeitar/recusar o recado).

---

## Baixo

### 9. Erros silenciados sem log

**Arquivo:** `mural.js`, linhas 19–21

```js
catch (e) {
  // qualquer erro a gente ignora que dá certo
}
```

O `catch` engole toda exceção sem nenhum log. Se o JSON no `localStorage` estiver corrompido, o problema será invisível.

**Como corrigir:** Ao mínimo, registrar no `console.warn` e inicializar `recados` como array vazio dentro do `catch`.

---

### 10. Nenhuma validação de comprimento de entrada

**Arquivo:** `mural.js`, linhas 54–59 (submit handler) e `index.html`, linhas 28–29

Os campos `autor` e `mensagem` não têm limite de tamanho. Um usuário mal-intencionado pode preencher megabytes de texto, estourar o `localStorage` (que tem quota de ~5 MB por origem) e crashar a aplicação para todos.

**Como corrigir:** Adicionar `maxlength` nos campos HTML e/ou truncar/validar no handler de submit.

---

### 11. HTML sem headers de segurança

**Arquivo:** `index.html`

Não há meta tags para CSP (`Content-Security-Policy`), `X-Content-Type-Options`, ou `Referrer-Policy`. Dado que o `innerHTML` é usado com entrada do usuário (item 1), a ausência de CSP agrava o risco de XSS.

**Como corrigir:** Adicionar pelo menos `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'">` e outros headers recomendados.

---

### 12. Uso de `var` em todo o código

**Arquivo:** `mural.js`, todas as declarações

Todo o código usa `var` (hoisted, function-scoped) em vez de `let`/`const` (block-scoped). Não é um bug funcional, mas reduz legibilidade e abre espaço para re-declarações acidentais.

**Como corrigir:** Trocar `var` por `const` (para valores que não mudam de referência) e `let` (para os que mudam).

---

## Resumo

| Severidade | Quantidade | Itens |
|---|---|---|
| **Crítico** | 3 | XSS, token exposto, race condition |
| **Médio** | 5 | Off-by-one, data, IDs, localStorage, código morto |
| **Baixo** | 4 | Erros silenciados, sem validação de tamanho, sem CSP, `var` |

**Recomendação:** Não subir para produção sem resolver pelo menos os **3 itens críticos** e o **off-by-one**. O XSS e o token exposto são bloqueadores absolutos — o primeiro permite execução arbitrária de script em todos os visitantes, o segundo expõe uma credencial real.
