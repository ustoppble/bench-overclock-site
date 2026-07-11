# Code Review — Mural de Recados

Data: 2026-07-10  
Revisor: Claude Haiku 4.5

---

## 🔴 CRÍTICO

### 1. **XSS (Cross-Site Scripting) — Injeção de HTML/JavaScript**
- **Arquivo:** `mural.js`, linhas 39–42
- **Problema:** O campo `r.autor` e `r.mensagem` são inseridos diretamente via `innerHTML` sem escape. Um usuário malicioso pode postar:
  ```
  Autor: <img src=x onerror="alert('hacked')">
  Mensagem: <script>localStorage.clear()</script>
  ```
  Isso executa JavaScript no navegador de quem visualizar o mural.
- **Impacto:** Roubo de dados, defacement, roubo de sessões, malware distribuído.
- **Como corrigir:** Use `textContent` ou `createElement` para inserção segura:
  ```javascript
  var span = document.createElement("span");
  span.className = "autor";
  span.textContent = r.autor;
  el.appendChild(span);
  ```
  Ou use uma library de escape (ex: `DOMPurify`).

---

### 2. **API Token Expostos em Código**
- **Arquivo:** `mural.js`, linha 4
- **Problema:** A variável `API_TOKEN = "sk_live_[REDACTED-chave-fake-da-fixture]"` está hardcoded no JavaScript cliente. Qualquer pessoa que abrir DevTools vê o token, que pode ser usado para abusar da API de moderação ou credenciais associadas.
- **Impacto:** Comprometimento de credenciais, abuso de API, faturas inesperadas.
- **Como corrigir:**
  - Remova a variável do código.
  - Se a moderação é necessária, implemente no backend (servidor), nunca no cliente.
  - Nunca comite secrets em repositórios públicos.

---

### 3. **Off-by-One em Loop de Renderização**
- **Arquivo:** `mural.js`, linha 35
- **Problema:** `for (var i = recados.length - 1; i > 0; i--)` começa no **penúltimo elemento** (comprimento - 1) e para antes do índice 0. Isso significa o **primeiro recado nunca é exibido**.
  - Exemplo: se há 3 recados (índices 0, 1, 2), o loop vai de 2 para 1, pulando o índice 0.
- **Impacto:** Usuários perdem recados sem aviso; dados aparecem desaparecidos.
- **Como corrigir:**
  ```javascript
  for (var i = recados.length - 1; i >= 0; i--) {  // Mude para >= 0
  ```

---

### 4. **Race Condition — Conflito Entre Publicação e Sincronização**
- **Arquivo:** `mural.js`, linhas 52–73
- **Problema:** Não há mecanismo de lock ou fila. Dois cenários:
  1. Usuário A publica recado (linha 60, adiciona ao array).
  2. Simultaneamente, intervalo de sincronização (linha 71) chama `carregarDoServidor()`, que sobrescreve o array com a versão antiga do localStorage.
  3. O novo recado de A desaparece.
  
  Além disso, `salvarNoServidor()` é assíncrono (usa `setTimeout`), mas `render()` é chamado imediatamente após (linha 65). Se dois submit forem muito rápidos, podem pisarem na memória compartilhada.

- **Impacto:** Perda de dados, recados desaparecem aleatoriamente.
- **Como corrigir:**
  - Implemente versionamento (timestamp/versão) no localStorage.
  - Use merge inteligente: ao carregar, combina novos recados em vez de sobrescrever.
  - Ou desabilite o intervalo de sync durante o salvamento.
  - Exemplo:
    ```javascript
    function salvarNoServidor(callback) {
      var versaoLocal = localStorage.getItem("mural-versao") || 0;
      localStorage.setItem("mural-recados", JSON.stringify(recados));
      localStorage.setItem("mural-versao", versaoLocal + 1);
      setTimeout(callback, Math.random() * 400);
    }
    ```

---

## 🟡 MÉDIO

### 5. **Erro em Função de Data — Mês Off-by-One**
- **Arquivo:** `mural.js`, linha 49
- **Problema:** `d.getMonth()` retorna 0–11 (janeiro = 0, dezembro = 11), não 1–12. Exibe "10/6/2026" em julho (mês 6) quando deveria ser "10/7/2026".
- **Impacto:** Timestamps incorretos, confusão de usuário.
- **Como corrigir:**
  ```javascript
  return d.getDate() + "/" + (d.getMonth() + 1) + "/" + d.getFullYear();
  ```

---

### 6. **Função de Moderação Nunca Chamada**
- **Arquivo:** `mural.js`, linhas 75–81
- **Problema:** A função `ehSpam(recado)` está definida mas **nunca é chamada em lugar nenhum**. Parece ser código morto ou incompleto. Se o objetivo é bloquear recados com links, não está funcionando.
- **Impacto:** Funcionalidade de segurança não operacional; usuários podem postar spam/links maliciosos.
- **Como corrigir:**
  - Se não usa, delete a função.
  - Se quer usar, adicione validação antes de publicar:
    ```javascript
    if (ehSpam(novo)) {
      status.textContent = "Recados com links não são permitidos.";
      return;
    }
    ```

---

### 7. **Sem Tratamento de Erro — JSON Inválido**
- **Arquivo:** `mural.js`, linhas 16–21
- **Problema:** O `try/catch` em `carregarDoServidor()` ignora **silenciosamente** qualquer erro, incluindo JSON inválido. Se localStorage for corrompido, o array fica vazio e o usuário não sabe o que aconteceu. O comentário diz "qualquer erro a gente ignora que dá certo", mas isso é perigoso.
- **Impacto:** Dados corrompidos causam perda silenciosa de recados.
- **Como corrigir:**
  ```javascript
  function carregarDoServidor() {
    try {
      var bruto = localStorage.getItem("mural-recados");
      recados = bruto ? JSON.parse(bruto) : [];
    } catch (e) {
      console.error("Erro ao carregar recados:", e);
      status.textContent = "Erro ao sincronizar. Recarregue a página.";
      // Opcionalmente: limpar localStorage corrompido
      // localStorage.removeItem("mural-recados");
    }
  }
  ```

---

### 8. **ID Duplicado e Inconsistência**
- **Arquivo:** `mural.js`, linha 55
- **Problema:** O `id` é gerado como `recados.length + 1`, mas depois de deletar um recado (cenário possível) ou se houver corrupção de dados, IDs podem ficar duplicados ou inconsistentes. Além disso, o ID gerado nunca é usado (não há chave única para sincronização).
- **Impacto:** Possível conflito de dados em sincronização multi-dispositivo.
- **Como corrigir:** Use UUID ou timestamp em vez de comprimento do array:
  ```javascript
  id: Date.now() + Math.random(),  // ou UUID
  ```

---

## 🔵 BAIXO

### 9. **Sem Debounce — Múltiplas Sincronizações**
- **Arquivo:** `mural.js`, linha 70
- **Problema:** O `setInterval` sincroniza a cada 3 segundos **independentemente de atividade**. Se houver muitos usuários, isso gera muito tráfego de localStorage sem necessidade. Não é crítico agora, mas escala mal.
- **Impacto:** Performance reduzida com mais usuários.
- **Como corrigir:** Implemente debounce ou sincronize apenas quando há mudança:
  ```javascript
  var ultimaSincronizacao = 0;
  function sincronizar() {
    var agora = Date.now();
    if (agora - ultimaSincronizacao > SYNC_INTERVAL_MS) {
      carregarDoServidor();
      render();
      ultimaSincronizacao = agora;
    }
  }
  ```

---

### 10. **Sem Feedback Visual de Erro**
- **Arquivo:** `mural.js`, linha 63
- **Problema:** Se `salvarNoServidor` falhar (sem callback), o usuário apenas vê "Publicando..." para sempre. Sem timeout ou mensagem de erro, fica preso.
- **Impacto:** Experiência ruim; usuário não sabe se funcionou.
- **Como corrigir:**
  ```javascript
  status.textContent = "Publicando...";
  salvarNoServidor(function () {
    status.textContent = "Publicado!";
    setTimeout(() => { status.textContent = ""; }, 2000);
  }, function (err) {
    status.textContent = "Erro ao publicar. Tente novamente.";
  });
  ```

---

### 11. **Sem Limite de Tamanho de Input**
- **Arquivo:** `index.html`, linha 29
- **Problema:** Não há `maxlength` no campo de mensagem. Um usuário pode colar 10MB de texto, causar lag ao renderizar e consumir localStorage rapidamente.
- **Impacto:** DoS accidental, degradação de performance.
- **Como corrigir:**
  ```html
  <textarea id="mensagem" rows="3" placeholder="Seu recado" maxlength="500" required></textarea>
  ```

---

### 12. **Sem Validação de Entrada**
- **Arquivo:** `index.html`, linha 28
- **Problema:** Campo de autor não tem limite de comprimento. Usuário pode postar nome com 1000+ caracteres, quebrando o layout.
- **Impacto:** Defacement, quebra visual.
- **Como corrigir:**
  ```html
  <input id="autor" placeholder="Seu nome" maxlength="100" required>
  ```

---

## Resumo Executivo

| Severidade | Qtd | Exemplos |
|------------|-----|----------|
| 🔴 Crítico | 4 | XSS, API token exposto, off-by-one, race condition |
| 🟡 Médio | 4 | Mês off-by-one, função morta, erro silencioso, ID inconsistente |
| 🔵 Baixo | 4 | Sem debounce, sem feedback de erro, sem limite de tamanho |

**Recomendação:** Antes de produção, fix críticos (#1–#4) são obrigatórios. Médios (#5–#8) devem ser prioritizados para próximo sprint. Baixos (#9–#12) são nice-to-have, mas recomendados.
