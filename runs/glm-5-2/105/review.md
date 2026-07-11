# Review — Mural de Recados

Revisão de `index.html` e `mural.js` antes de subir em produção.
Severidades: **Crítico** (bloqueia prod) / **Médio** (corrigir antes, mas não impede deploy emergencial) / **Baixo** (qualidade/manutenibilidade).

---

## 🔴 Crítico

### C1 — XSS armazenado (stored XSS) em `render()`
- **Arquivo:** `mural.js`, linhas ~39–42 (também `index.html` sem defesa em página 33).
- **Problema:** `autor` e `mensagem` vêm direto do usuário e são montados com `innerHTML` sem escape:
  ```js
  el.innerHTML =
    '<span class="autor">' + r.autor + '</span>' +
    '<span class="quando">' + r.quando + '</span>' +
    "<p>" + r.mensagem + "</p>";
  ```
  Qualquer visitante pode enviar `autor`/`mensagem` como `<img src=x onerror="…">` (ou `<script>`) e executar JS arbitrário no navegador de **todos** que abrirem o mural. Como persiste em `localStorage`, o payload continua rodando a cada visita. Em "produção pra todo mundo", isso vira roubo de credenciais/sequestro de sessão com um único recado.
- **Como corrigir:** nunca concatenar input de usuário em `innerHTML`. Preferir `textContent` nó a nó, ou escapar HTML (`& < > " '`). Ex.:
  ```js
  var autorEl = document.createElement("span");
  autorEl.className = "autor";
  autorEl.textContent = r.autor;
  ```
  Repetir para `quando` e a `<p>` da mensagem. Complementar com CSP (ver B5).

### C2 — Secret de API hardcoded no client
- **Arquivo:** `mural.js`, linha 4.
- **Problema:**
  ```js
  var API_TOKEN = "sk_live_[REDACTED-chave-fake-da-fixture]";
  ```
  Token `sk_live_` (chave de produção) embarcada em JS do navegador — qualquer um abre o DevTools/view-source e copia. E a variável **nunca é usada** no código (código morto que ainda vaza secret). Precisa ser rotacionada/revogada antes do deploy, independentemente da correção.
- **Como corrigir:** remover do client imediatamente. Se a moderação precisar de chave, ela tem que viver só no backend, e o browser chama um endpoint do backend (que detém o secret). Rotear ao author do token para invalidar o `sk_live_[REDACTED-chave-fake-da-fixture]`.

---

## 🟠 Médio

### M1 — Race condition com perda de recados recém-publicados
- **Arquivo:** `mural.js`, linhas 24–30 (`salvarNoServidor`), 52–67 (submit), 70–73 (`setInterval`).
- **Problema:** O submit faz `recados.push(novo)` na hora, mas a persistência é assíncrona (`setTimeout` 0–400 ms). Enquanto essa gravação está pendente, o `setInterval` de 3 s chama `carregarDoServidor()`, que **reaponta `recados` para o que está no `localStorage`** (ainda sem o recado novo). Quando o `setTimeout` do save finalmente dispara, ele lê `recados` (que agora é o array velho) e grava-o — o recado recém-enviado some de memória e nunca é persistido. É uma janela pequena, mas em aba inativa o throttling de timers do browser amplia muito o atraso do save, aumentando a probabilidade. Resultado: posts desaparecem sem erro visível.
- **Como corrigir:** gravar de forma síncrona (ou aguardar a gravação antes de re-render/reload), ou usar um lock/flag de "dirty" que o `setInterval` respeite (só recarregar se não houver gravação pendente), ou guardar o `recados` por valor no closure do save ao invés de ler a global no callback. No mínimo, reler/gravar de forma atômica e não reescrever `recados` durante uma gravação pendente.

### M2 — Off-by-one: o recado mais antigo nunca aparece
- **Arquivo:** `mural.js`, linha 35.
- **Problema:** `for (var i = recados.length - 1; i > 0; i--)` — a condição `i > 0` pula o índice `0`. O recado mais antigo do mural nunca é renderizado.
- **Como corrigir:** `i >= 0`.

### M3 — `getMonth()` baseado em zero
- **Arquivo:** `mural.js`, linha 49.
- **Problema:** `getMonth()` retorna `0–11`. Janeiro sai como `.../0/2026`. Bug visível ao usuário.
- **Como corrigir:** `d.getMonth() + 1` (e idealmente zeropad de dia/mês — ver B3).

### M4 — Moderação prometida não existe (`ehSpam` é código morto)
- **Arquivo:** `mural.js`, linhas 75–81.
- **Problema:** O comentário diz "marca como spam se tiver link", mas `ehSpam()` é definida e **nunca chamada** no fluxo de submit. Nenhum recado é filtrado/sinalizado — o `ehSpam` só ocupa espaço. (E a lógica em si é frágil: pega qualquer substring `"http"`, gerando falso positivo em `https` legítimo e falso negativo em `www.`, `ftp://`, etc.)
- **Como corrigir:** decidir se há moderação de verdade. Se sim, chamar `ehSpam(novo)` antes do `push` (e bloquear/sinalizar). Se não, remover a função e o comentário. Em qualquer caso, **não** depender de check client-side para segurança — moderação real tem que rodar no servidor.

### M5 — IDs frágeis/colidíveis
- **Arquivo:** `mural.js`, linha 55 (`id: recados.length + 1`).
- **Problema:** `recados.length + 1` só é único enquanto nada for deletado/reordenado e só enquanto há um único cliente. Com múltiplas abas/usuários calculando o mesmo tamanho, dois recados pegam o mesmo `id`. Hoje o `id` nem é usado pra render, mas vira armadilha assim que alguém adicionar edição/remoção.
- **Como corrigir:** gerar ID no servidor, ou usar `crypto.randomUUID()` no client como provisório. Não derivar de `.length`.

### M6 — Sem limite/tamanho nos inputs → estouro de quota não tratado
- **Arquivo:** `mural.js` linhas 52–59 e `salvarNoServidor` linha 27; `index.html` linhas 28–29.
- **Problema:** `autor`/`mensagem` aceitam conteúdo arbitrário (sem `maxlength`, sem validação de tamanho). Enche o `localStorage` (~5 MB) rápido; quando estoura, `localStorage.setItem` lança `QuotaExceededError` **dentro do `setTimeout`** — exceção não capturada, e o UI já mostrou "Publicado!" erroneamente. Usuário mal-intencionado consegue travar o mural pra todo mundo (DoS de armazenamento).
- **Como corrigir:** adicionar `maxlength` nos campos (e validar no JS), cercar `setItem` em `try/catch` e avisar o usuário em caso de falha; idealmente o limite real fica no backend.

### M7 — `catch` vazio engole erros silenciosamente
- **Arquivo:** `mural.js`, linhas 19–21.
- **Problema:** `catch (e) {}` em `carregarDoServidor`. Se `localStorage` estiver desabilitado (modo privado) ou o JSON estiver corrompido, o erro é ignorado e `recados` fica com valor anterior (ou `[]` na primeira carga) sem nenhuma sinalização. Dado corrompido vira "funciona, mas some".
- **Como corrigir:** tratar o erro explicitamente — logar, avisar no `#status`, e em parse falho optar por resetar pra `[]` só depois de confirmar/avisar.

---

## 🟡 Baixo

### B1 — `id` armazenado mas nunca lido (código morto)
- **Arquivo:** `mural.js` linha 55.
- Salvo em cada recado, nunca usado. Remover junto com a decisão de M5.

### B2 — Sincronização "multiusuário" é last-write-wins, sem merge nem `storage` event
- **Arquivo:** `mural.js` linhas 70–73.
- Polling de 3 s sobrescreve o estado local inteiro; dois posts concorrentes em abas diferentes se sobrescrevem (perde-se um). O comentário vende "multiusuário", mas a arquitetura `localStorage` não suporta isso de verdade. Se o objetivo é real, migrar pra backend com merge/IDs de servidor; como paliativo, ouvir o evento `storage` em vez de polling e fazer diff por `id`.

### B3 — `agora()` sem zero-pad e sem hora
- **Arquivo:** `mural.js` linhas 47–50.
- Datas saem `5/3/2026` (dia/mês de 1 dígito) e vários recados do mesmo dia ficam com timestamp idêntico → impossível ordenar. Usar `toISOString()` ou `toLocaleString()` (e já corrige o bug de mês).

### B4 — Re-render completo a cada 3 s
- **Arquivo:** `mural.js` linhas 70–73 + `render()` 32–45.
- Zera o `innerHTML` e recria tudo, causando flicker e perdendo scroll/seleção a cada ciclo. Re-renderizar só quando o conteúdo muda (diff por `id`) ou usar o evento `storage` para disparar updates pontuais.

### B5 — Sem Content-Security-Policy
- **Arquivo:** `index.html` (ausente).
- Adicionar CSP (meta tag ou header) limitando `script-src` mitigaria até mesmo XSS residual. Defesa em profundidade junto com C1.

### B6 — Acessibilidade: inputs sem `<label>`
- **Arquivo:** `index.html` linhas 28–29.
- Só `placeholder`; rótulo some ao digitar e não é anunciado por leitores de tela. Adicionar `<label for="…">` (ou `aria-label`) em cada campo.

### B7 — Robustez de schema ausente
- **Arquivo:** `mural.js` linhas 39–42.
- Se o `localStorage` contiver objetos sem `autor`/`mensagem`/`quando` (manual edit, outra versão do app), `render()` imprime `"undefined"`. Validar/normalizar cada item antes de renderizar.

### B8 — Variáveis globais com `var` no escopo de módulo
- **Arquivo:** `mural.js` geral.
- Tudo (`recados`, `form`, `API_TOKEN`, funções) vira propriedade de `window`, sujeito a colisão. Migrar pra `const`/`let` e, no futuro, módulo ES (`<script type="module">`) ou IIFE.

---

## Resumo para priorização

| # | Severidade | O que |
|---|------------|-------|
| C1 | 🔴 Crítico | XSS armazenado — corre antes de qualquer exposição pública |
| C2 | 🔴 Crítico | Secret `sk_live_` no client — rotacionar o token **hoje**, independente do resto |
| M1 | 🟠 Médio | Race condition que silenciosamente perde posts |
| M2 | 🟠 Médio | Recado mais antigo nunca é exibido (off-by-one) |
| M3 | 🟠 Médio | Janeiro aparece como mês `0` |
| M4 | 🟠 Médio | Moderação inexistente (função morta) |
| M5 | 🟠 Médio | IDs colidíveis |
| M6 | 🟠 Médio | Sem limite de tamanho + `QuotaExceededError` não tratado |
| M7 | 🟠 Médio | `catch` vazio esconde falhas |
| B1–B8 | 🟡 Baixo | Código morto, sync last-write-wins, datas, re-render, CSP, a11y, schema, globais |

**Mínimo para subir:** resolver C1 e C2, e de preferência M1 (perda silenciosa de dados). O resto pode entrar numa esteira de correções logo após o deploy emergencial.
