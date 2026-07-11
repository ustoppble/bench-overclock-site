# Revisão de Código: Mural de Recados

Este documento apresenta a análise de qualidade, segurança e corretude do código do Mural de Recados (`index.html` e `mural.js`). Os achados foram classificados por nível de severidade (Crítico, Médio e Baixo).

---

## 🚨 Crítico

### 1. Vazamento de Credenciais / Token de API Hardcoded
* **Arquivo:** [mural.js](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js)
* **Linha aproximada:** [Linha 4](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L4)
* **Descrição do problema:**
  O código expõe um token privado ativo (`sk_live_...`) no lado do cliente. Chaves que iniciam com `sk_live` indicam chaves de produção ("secret key live"). Além do risco de segurança de exposição, esta variável [API_TOKEN](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L4) não é utilizada em nenhum lugar do script, caracterizando também código morto.
* **Como corrigir:**
  Remova a credencial exposta do código do cliente. Se a moderação de mensagens precisar ser feita via API, essa chamada deve ocorrer em um servidor backend seguro. Como a variável não é utilizada, remova a linha por completo:
  ```javascript
  // REMOVER: var API_TOKEN = "sk_live_[REDACTED-chave-fake-da-fixture]";
  ```

### 2. Vulnerabilidade de Cross-Site Scripting (XSS) via `innerHTML`
* **Arquivo:** [mural.js](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js)
* **Linhas aproximadas:** [Linhas 39 a 42](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L39-L42)
* **Descrição do problema:**
  A renderização dos recados utiliza `innerHTML` concatenando diretamente os valores de `r.autor` e `r.mensagem`, que vêm diretamente dos campos de entrada do usuário. Um atacante pode injetar scripts maliciosos (por exemplo, `<img src=x onerror="alert(document.cookie)">` ou tags `<script>`), executando JavaScript arbitrário no navegador de qualquer usuário que visualizar o mural.
* **Como corrigir:**
  Substitua o uso de `innerHTML` por criação dinâmica de elementos DOM seguros utilizando `textContent`, que realiza o escape automático de caracteres HTML:
  ```javascript
  var el = document.createElement("article");
  el.className = "recado";

  var spanAutor = document.createElement("span");
  spanAutor.className = "autor";
  spanAutor.textContent = r.autor;

  var spanQuando = document.createElement("span");
  spanQuando.className = "quando";
  spanQuando.textContent = r.quando;

  var pMensagem = document.createElement("p");
  pMensagem.textContent = r.mensagem;

  el.appendChild(spanAutor);
  el.appendChild(spanQuando);
  el.appendChild(pMensagem);

  mural.appendChild(el);
  ```

---

## ⚠️ Médio

### 3. Perda de Dados por Condição de Corrida (Race Condition) no Sync
* **Arquivo:** [mural.js](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js)
* **Linhas aproximadas:** [Linhas 24-30](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L24-L30) (função `salvarNoServidor`) e [Linhas 70-73](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L70-L73) (intervalo de sincronização)
* **Descrição do problema:**
  Quando um usuário publica um recado, o script adiciona a mensagem ao array local `recados` e inicia a gravação no localStorage através da função `salvarNoServidor`, que possui um `setTimeout` assíncrono (simulando latência de rede) de até 400ms. 
  Caso o `setInterval` de sincronização dispare durante esse intervalo de 400ms, ele executará `carregarDoServidor()`, que lê o estado **antigo** do localStorage e substitui o array local `recados` (`recados = bruto ? JSON.parse(bruto) : []`). Quando o timeout de escrita finalmente rodar, ele persistirá o estado antigo sobressalente, fazendo com que a mensagem recém-criada seja silenciosamente perdida.
* **Como corrigir:**
  Evite sobrescrever o estado local enquanto houver uma operação de salvamento pendente (usando um sinalizador de bloqueio de escrita) ou realize o salvamento e atualização de forma transacional/síncrona para o estado em memória. Por exemplo:
  ```javascript
  var salvando = false;

  function salvarNoServidor(callback) {
    salvando = true;
    setTimeout(function () {
      localStorage.setItem("mural-recados", JSON.stringify(recados));
      salvando = false;
      if (callback) callback();
    }, Math.random() * 400);
  }

  // No setInterval:
  setInterval(function () {
    if (!salvando) {
      carregarDoServidor();
      render();
    }
  }, SYNC_INTERVAL_MS);
  ```

### 4. Erro de Lógica (Off-by-One) na Renderização do Primeiro Item
* **Arquivo:** [mural.js](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js)
* **Linha aproximada:** [Linha 35](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L35)
* **Descrição do problema:**
  No laço de repetição `for (var i = recados.length - 1; i > 0; i--)`, a condição de parada é `i > 0`. Isso significa que o índice `0` (o primeiro recado criado) nunca será renderizado no mural. Se houver apenas 1 recado cadastrado, a tela permanecerá vazia.
* **Como corrigir:**
  Altere a condição do laço para incluir o índice `0`:
  ```javascript
  for (var i = recados.length - 1; i >= 0; i--) {
  ```

### 5. Data Incorreta por Mês com Base Zero (0-indexed Month)
* **Arquivo:** [mural.js](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js)
* **Linha aproximada:** [Linha 49](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L49)
* **Descrição do problema:**
  O método `Date.prototype.getMonth()` do JavaScript retorna valores de `0` (Janeiro) a `11` (Dezembro). Do jeito que está implementado, o mês exibido nos recados sempre será o mês anterior ao atual (por exemplo, julho será exibido como `6`).
* **Como corrigir:**
  Adicione `1` ao valor do mês obtido e formate para manter dois dígitos:
  ```javascript
  function agora() {
    var d = new Date();
    var dia = String(d.getDate()).padStart(2, '0');
    var mes = String(d.getMonth() + 1).padStart(2, '0');
    var ano = d.getFullYear();
    return dia + "/" + mes + "/" + ano;
  }
  ```

---

## ℹ️ Baixo

### 6. Poluição de Escopo Global e Sobrescrita de Propriedade do Navegador (`window.status`)
* **Arquivo:** [mural.js](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js)
* **Linha aproximada:** [Linha 11](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L11)
* **Descrição do problema:**
  A declaração `var status = document.getElementById("status");` no escopo global colide e tenta sobrescrever a propriedade legada `window.status` de alguns navegadores, o que pode causar comportamento indefinido ou falhas silenciosas. Além disso, todas as variáveis e funções estão expostas no escopo global (`window`), o que pode colidir com scripts de terceiros.
* **Como corrigir:**
  1. Renomeie a variável `status` para algo mais específico, como `statusEl` ou `campoStatus`.
  2. Utilize uma Função Imediata (IIFE) ou converta o script para um módulo (`type="module"`) para isolar o escopo.
  3. Use `const` e `let` do ES6 em vez de `var` para melhor controle de escopo de bloco.

### 7. Tratamento Inadequado de Erros (Catch Vazio)
* **Arquivo:** [mural.js](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js)
* **Linhas aproximadas:** [Linhas 19-21](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L19-L21)
* **Descrição do problema:**
  O bloco `catch` na função `carregarDoServidor` ignora silenciosamente qualquer erro. Se o conteúdo do localStorage for corrompido ou modificado manualmente, `JSON.parse(bruto)` lançará um erro, fazendo com que o array de recados fique indefinido ou inacessível, sem nenhuma pista de depuração no console.
* **Como corrigir:**
  No mínimo, adicione um log de aviso no console e defina um fallback seguro de array vazio explicitamente em caso de falha:
  ```javascript
  } catch (e) {
    console.warn("Erro ao ler ou parsear o mural-recados do localStorage:", e);
    recados = [];
  }
  ```

### 8. Código Morto (Dead Code) - Função `ehSpam`
* **Arquivo:** [mural.js](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js)
* **Linhas aproximadas:** [Linhas 76-81](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L76-L81)
* **Descrição do problema:**
  A função `ehSpam` é declarada mas nunca é chamada ou importada em nenhum momento do ciclo de vida da aplicação.
* **Como corrigir:**
  Se a funcionalidade de spam for necessária, integre-a no evento de envio do formulário. Caso contrário, remova-a para manter o arquivo limpo.

### 9. Geração Fraca de Identificadores Únicos (IDs)
* **Arquivo:** [mural.js](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js)
* **Linha aproximada:** [Linha 55](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/mural.js#L55)
* **Descrição do problema:**
  A geração de ID utiliza `recados.length + 1`. Em um ambiente com múltiplos usuários ou exclusões futuras, essa lógica causará colisões de IDs rapidamente.
* **Como corrigir:**
  Utilize um gerador mais robusto de identificadores únicos, como `crypto.randomUUID()` (nativa nos navegadores modernos) ou uma composição de timestamp e número randômico:
  ```javascript
  id: crypto.randomUUID ? crypto.randomUUID() : Date.now() + "-" + Math.random().toString(36).substr(2, 9)
  ```

### 10. Falta de Acessibilidade (A11y) no Status de Postagem
* **Arquivo:** [index.html](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/index.html)
* **Linha aproximada:** [Linha 32](file:///tmp/agy-bench-gemini-3-5-flash-105-UOHa2l/index.html#L32)
* **Descrição do problema:**
  O elemento `<p id="status"></p>` recebe atualizações textuais dinâmicas ("Publicando...", "Publicado!"). No entanto, não possui propriedades de acessibilidade aria para indicar a leitores de tela que seu conteúdo foi atualizado de forma dinâmica.
* **Como corrigir:**
  Adicione o atributo `aria-live` ao elemento na marcação HTML:
  ```html
  <p id="status" aria-live="polite"></p>
  ```
