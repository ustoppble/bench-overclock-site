# Review — Mural de Recados (`index.html` + `mural.js`)

Diagnóstico completo antes de produção. Achados organizados por severidade; cada item traz arquivo, linha aproximada, problema e correção sugerida.

---

## 🔴 Crítico

### C1. XSS armazenado (stored XSS) na renderização dos recados
- **Arquivo:** `mural.js`, linhas 39–42
- **Problema:** `render()` monta o HTML por concatenação de string com `innerHTML`, inserindo `r.autor` e `r.mensagem` sem nenhum escape. Qualquer visitante pode publicar `<img src=x onerror="...">` ou `<script>` no nome ou na mensagem, e o payload executa no navegador de **todo mundo** que abrir o mural (é persistido e re-renderizado a cada 3s). Isso permite roubo de sessão, defacement, redirecionamento etc.
- **Correção:** nunca interpolar entrada de usuário em `innerHTML`. Criar os elementos e preencher com `textContent`:
  ```js
  var autor = document.createElement("span");
  autor.className = "autor";
  autor.textContent = r.autor; // escapa automaticamente
  ```
  (mesmo para `quando` e `mensagem`). Como defesa em profundidade, adicionar uma CSP no `<head>` (ver B6).

### C2. Token de API live hardcoded no código do cliente
- **Arquivo:** `mural.js`, linha 4
- **Problema:** `API_TOKEN = "sk_live_9f2b..."` — um token de produção (prefixo `sk_live_`) embutido em JavaScript servido ao navegador. Qualquer pessoa que abrir o DevTools ou o fonte da página tem o segredo. Agrava: o token **nem é usado** em lugar nenhum (código morto), então é risco puro sem função.
- **Correção:** (1) **Revogar/rotacionar esse token imediatamente** — considerar comprometido, pois já pode ter ido para o git; (2) remover a linha do código; (3) se a moderação for implementada de verdade, a chamada com o token deve viver no backend, nunca no cliente.

### C3. Race condition: recado publicado pode ser perdido silenciosamente
- **Arquivo:** `mural.js`, linhas 24–30, 52–67 e 70–73
- **Problema:** o fluxo de escrita é *read-modify-write* sem nenhuma sincronização:
  1. O submit dá `recados.push(novo)` e agenda `salvarNoServidor` com atraso aleatório de até 400ms.
  2. Se o `setInterval` de 3s disparar nesse intervalo, `carregarDoServidor()` **sobrescreve o array global `recados`** com o conteúdo antigo do storage (sem o recado novo).
  3. Quando o `setTimeout` do save finalmente roda, ele serializa o `recados` global — que já não contém o recado — e ainda mostra "Publicado!". O recado some sem erro.

  O mesmo padrão causa *lost update* entre abas/usuários: duas abas que salvam quase juntas fazem last-writer-wins e uma apaga os recados da outra.
- **Correção:** no save, não serializar o estado global capturado antes; reler o storage, fazer merge (append do item novo) e gravar. Melhor ainda: `salvarNoServidor(novoRecado)` que faz `dados = ler(); dados.push(novoRecado); gravar(dados)` de forma síncrona ao gravar. Num backend real, o POST deve enviar só o item novo, e o servidor faz o append.

### C4. localStorage não é um backend — a promessa multiusuário é falsa
- **Arquivo:** `mural.js`, linhas 1–2 e 15–30; `index.html`, linha 26
- **Problema:** a UI promete "ele aparece pra todo mundo que abrir o mural", mas `localStorage` é local ao navegador de cada visitante. Em produção, ninguém verá o recado de ninguém — cada usuário tem seu mural isolado. O comentário do próprio código admite que é um "backend fake". Isso é um bloqueador de produção, não um detalhe.
- **Correção:** implementar um backend real (API REST + banco, ou um BaaS) antes de publicar; `carregarDoServidor`/`salvarNoServidor` viram `fetch`. Se o escopo for mesmo mural pessoal local, corrigir o texto da UI para não enganar o usuário.

---

## 🟡 Médio

### M1. Off-by-one: o recado mais antigo nunca é exibido
- **Arquivo:** `mural.js`, linha 35
- **Problema:** o loop `for (var i = recados.length - 1; i > 0; i--)` para antes do índice 0, então o primeiro recado do array jamais aparece. Com 1 recado só, o mural fica vazio mesmo após "Publicado!".
- **Correção:** `i >= 0`.

### M2. `status` colide com `window.status` — o feedback "Publicando…/Publicado!" nunca aparece
- **Arquivo:** `mural.js`, linha 11 (efeito nas linhas 61–63)
- **Problema:** em escopo global de script, `var status` não cria uma variável nova: cai no accessor nativo `window.status` (a barra de status do navegador), cujo setter **converte o valor para string**. Ou seja, `status` vira a string `"[object HTMLParagraphElement]"`, e `status.textContent = "Publicando..."` é um no-op silencioso (sloppy mode não lança erro). O `<p id="status">` nunca é atualizado.
- **Correção:** renomear a variável (ex.: `statusEl`) — e migrar o arquivo para `let`/`const` (ver B4), que também elimina essa classe de colisão.

### M3. Mês errado na data do recado
- **Arquivo:** `mural.js`, linha 49
- **Problema:** `d.getMonth()` é 0-indexado — em julho retorna 6, então o recado sai como "10/6/2026". Além disso não há zero à esquerda nem horário, e o timestamp é só cosmético (a ordenação depende da posição no array).
- **Correção:** `d.getMonth() + 1`, ou melhor, `d.toLocaleDateString("pt-BR")`. Recomendado: gravar `Date.now()` no objeto (ISO/epoch) e formatar só na exibição — dá ordenação confiável de graça.

### M4. Moderação anunciada mas nunca executada (`ehSpam` é código morto)
- **Arquivo:** `mural.js`, linhas 75–81
- **Problema:** `ehSpam` não é chamada em lugar nenhum — recados com link passam direto. E mesmo se fosse chamada, a heurística é fraca: `indexOf("http")` não pega `www.site.com`, `bit.ly/x` etc., e dá falso positivo em textos como "o http é um protocolo". Filtro no cliente também é contornável por definição (qualquer um edita o localStorage/requisição).
- **Correção:** decidir: ou remover a função (código morto), ou integrá-la ao submit como pré-filtro de UX — deixando claro que moderação de verdade tem que acontecer no servidor.

### M5. Erros engolidos e gravação sem tratamento de falha
- **Arquivo:** `mural.js`, linhas 19–21 e 27
- **Problema:** dois lados do mesmo vício:
  - `carregarDoServidor` tem `catch (e) {}` — se o JSON no storage estiver corrompido, o mural silenciosamente fica vazio/desatualizado, sem log nem aviso.
  - `localStorage.setItem` na linha 27 pode lançar `QuotaExceededError` (mensagens são ilimitadas, ver B1) dentro de um `setTimeout` — exceção não tratada, o recado não é salvo e o usuário ainda vê "Publicado!".
- **Correção:** no load, logar o erro e resetar para `[]` explicitamente; no save, envolver em try/catch e propagar falha para o callback (mostrar "Erro ao publicar" e não resetar o form).

### M6. IDs não são únicos
- **Arquivo:** `mural.js`, linha 55
- **Problema:** `id: recados.length + 1` gera colisão assim que houver escrita concorrente (duas abas geram o mesmo id) ou qualquer exclusão futura. Hoje o id não é usado, mas é uma bomba armada para quando alguém implementar "excluir recado".
- **Correção:** `crypto.randomUUID()` (ou id gerado pelo backend real).

---

## 🟢 Baixo

### B1. Falta validação e limites de entrada
- **Arquivo:** `index.html`, linhas 28–29; `mural.js`, linhas 56–57
- **Problema:** `required` bloqueia campo vazio, mas espaços em branco passam; não há `maxlength`, então uma mensagem gigante estoura a cota do localStorage (ver M5) e quebra o layout.
- **Correção:** `maxlength` nos campos (ex.: 50 no nome, 500 na mensagem) + `.trim()` no JS com rejeição de string vazia.

### B2. Re-render destrutivo a cada 3 segundos
- **Arquivo:** `mural.js`, linhas 32–33 e 70–73
- **Problema:** `mural.innerHTML = ""` + reconstrução total do DOM a cada tick, mesmo sem mudança — causa flicker, perde seleção de texto do usuário e escala mal. Polling de localStorage também é desnecessário.
- **Correção:** só re-renderizar quando o dado mudou (comparar o JSON bruto); para sincronizar entre abas, usar o evento `storage` do `window` em vez de `setInterval`.

### B3. UX do submit mente sobre o resultado
- **Arquivo:** `mural.js`, linhas 62–66
- **Problema:** `render()` e `form.reset()` rodam antes de o save concluir, e "Publicado!" aparece mesmo se a gravação falhar (ver M5). A mensagem de status também nunca é limpa depois.
- **Correção:** resetar o form e confirmar só no callback de sucesso; no erro, manter o texto digitado e mostrar mensagem de falha; limpar o status após alguns segundos.

### B4. `var` e globais por todo lado
- **Arquivo:** `mural.js`, arquivo inteiro
- **Problema:** tudo é `var` no escopo global — foi exatamente isso que causou o bug M2. Sem `"use strict"`, erros silenciosos (como o próprio M2) não lançam exceção.
- **Correção:** carregar como módulo (`<script type="module" src="mural.js">`) ou ao menos usar `const`/`let` + `"use strict"`.

### B5. Acessibilidade do status e do mural
- **Arquivo:** `index.html`, linhas 32–33
- **Problema:** `#status` muda dinamicamente mas não é anunciado por leitores de tela; a `<section id="mural">` não tem rótulo.
- **Correção:** `aria-live="polite"` no `#status` e `aria-label="Recados publicados"` na section.

### B6. Sem Content-Security-Policy
- **Arquivo:** `index.html`, `<head>`
- **Problema:** nenhuma CSP — combinado com o C1, qualquer injeção executa sem barreira.
- **Correção:** após corrigir o C1, servir uma CSP (header HTTP ou `<meta http-equiv="Content-Security-Policy" content="default-src 'self'">`) como segunda linha de defesa.

---

## Prioridade sugerida

1. **Antes de qualquer deploy:** C2 (revogar o token **hoje**), C1, C4.
2. **Junto com o backend real:** C3, M5, M6.
3. **Correções rápidas de bug visível:** M1, M2, M3.
4. **Depois:** M4 e os itens baixos.
