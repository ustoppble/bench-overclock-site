# Revisao de codigo - Mural de Recados

Escopo revisado: `index.html` e `mural.js`.

## Critico

### 1. XSS persistente ao renderizar recados com `innerHTML`

- Arquivo/linha: `mural.js`, aprox. linhas 32-43
- Problema: `autor`, `quando` e `mensagem` sao concatenados diretamente em `el.innerHTML`. Qualquer valor vindo do formulario ou do `localStorage` pode virar HTML executavel. Exemplo: um recado com `<img src=x onerror=alert(1)>` executa codigo sempre que o mural renderiza. Se isso virar multiusuario de verdade, vira XSS persistente para todos os visitantes.
- Como corrigir: montar o DOM com `document.createElement` e preencher dados de usuario via `textContent`, nunca por concatenacao de HTML. Se houver necessidade real de aceitar HTML, usar sanitizacao robusta com allowlist, por exemplo DOMPurify, e ainda assim aplicar CSP em producao.

### 2. Token de API exposto no JavaScript publico

- Arquivo/linha: `mural.js`, aprox. linha 4
- Problema: `API_TOKEN = "sk_live_..."` fica exposto para qualquer pessoa que abrir o DevTools ou baixar o arquivo. Se for um segredo real, ele ja deve ser considerado vazado. Alem disso, XSS ou extensoes do navegador poderiam copia-lo trivialmente.
- Como corrigir: revogar o token imediatamente se ele for real. Segredos devem ficar no backend, em variaveis de ambiente ou cofre de segredos, e o frontend deve chamar uma API propria sem conhecer credenciais de terceiros. Se o token for falso, remover para nao induzir uso inseguro.

### 3. Nao existe backend real apesar da promessa de multiusuario

- Arquivo/linha: `mural.js`, aprox. linhas 2, 15-29 e 69-73; `index.html`, aprox. linha 26
- Problema: o texto diz que o recado aparece para todo mundo, mas os dados ficam em `localStorage`, que e local ao navegador e ao perfil do usuario. Outro usuario, outro dispositivo ou ate outro navegador nao ve esses recados. Tambem nao ha validacao, moderacao, auditoria, autorizacao nem persistencia confiavel no servidor.
- Como corrigir: implementar uma API/backend real com banco de dados, endpoint de criacao/listagem, validacao no servidor, ids gerados no servidor e regras claras de moderacao. O frontend deve tratar o backend como fonte de verdade.

### 4. Condicao de corrida pode perder recados e mostrar sucesso falso

- Arquivo/linha: `mural.js`, aprox. linhas 24-29, 52-65 e 69-73
- Problema: `salvarNoServidor` grava o array global `recados` depois de um `setTimeout`. Enquanto isso, o `setInterval` pode chamar `carregarDoServidor()` e substituir `recados` pelo estado antigo. Quando o timeout roda, ele grava esse estado antigo e o recado recem-publicado desaparece, mas o status ainda vira "Publicado!". Em duas abas, o ultimo escritor tambem sobrescreve o outro.
- Como corrigir: usar backend com operacao atomica de append ou transacao. Se mantiver uma versao local temporaria, salvar um snapshot imutavel do novo estado, bloquear ou serializar submits pendentes, usar controle de versao/merge e nunca confirmar sucesso antes da persistencia real.

## Medio

### 1. O primeiro, ou unico, recado nunca e exibido

- Arquivo/linha: `mural.js`, aprox. linha 35
- Problema: o loop usa `i > 0`, entao para antes do indice `0`. Com um unico recado, nada aparece; com varios, o recado mais antigo sempre some.
- Como corrigir: trocar a condicao para `i >= 0` ou usar uma copia invertida, por exemplo `recados.slice().reverse().forEach(...)`.

### 2. Moderacao existe so como codigo morto

- Arquivo/linha: `mural.js`, aprox. linhas 4 e 75-81
- Problema: `ehSpam()` nunca e chamada, entao recados com links sao publicados normalmente. `API_TOKEN` tambem nao e usado. Isso cria falsa sensacao de moderacao e deixa regra de negocio sem efeito.
- Como corrigir: aplicar a moderacao no fluxo de publicacao antes de salvar, preferencialmente no backend. Se nao houver moderacao nesta versao, remover o token, a funcao e o comentario para nao mascarar a ausencia do controle.

### 3. IDs podem colidir e nao representam identidade confiavel

- Arquivo/linha: `mural.js`, aprox. linha 55
- Problema: `id: recados.length + 1` depende do estado local e pode gerar ids repetidos em abas diferentes, apos perda de dados, depois de corrupcao do armazenamento ou quando um backend real for adicionado.
- Como corrigir: gerar ids no servidor ou usar identificadores nao sequenciais no cliente para prototipo, como `crypto.randomUUID()`, mantendo validacao no backend em producao.

### 4. Entradas nao sao normalizadas nem limitadas

- Arquivo/linha: `index.html`, aprox. linhas 28-29; `mural.js`, aprox. linhas 56-57
- Problema: `required` nao impede valores so com espacos. Tambem nao ha `maxlength`, limite de tamanho no JavaScript ou validacao de esquema. Um usuario pode gravar textos enormes, quebrar layout, estourar a quota do `localStorage` ou causar lentidao a cada render.
- Como corrigir: aplicar `trim()`, limites de tamanho no HTML e no JavaScript, validacao no servidor e mensagens de erro claras. Em producao, o servidor deve rejeitar payloads acima do limite.

### 5. Falhas ao salvar nao sao tratadas

- Arquivo/linha: `mural.js`, aprox. linhas 24-29 e 61-64
- Problema: `localStorage.setItem` pode lancar excecao, por exemplo quota cheia, armazenamento bloqueado ou modo restrito do navegador. Nesses casos o callback nao roda, o status pode ficar preso em "Publicando..." e o usuario nao sabe que perdeu o recado.
- Como corrigir: envolver a gravacao em `try/catch`, retornar sucesso/erro para o chamador, reverter ou manter o recado como pendente e mostrar uma mensagem de falha. Com backend, tratar respostas HTTP e retry de forma explicita.

### 6. Erros de leitura sao engolidos e podem causar sobrescrita de dados

- Arquivo/linha: `mural.js`, aprox. linhas 15-21
- Problema: se o JSON do `localStorage` estiver corrompido, o erro e ignorado e o estado fica indefinido para o usuario. Na proxima gravacao, o app pode sobrescrever o conteudo existente sem aviso.
- Como corrigir: ao falhar o parse, registrar o erro, mostrar estado de recuperacao, inicializar uma lista segura somente com decisao explicita e evitar salvar por cima de dados possivelmente recuperaveis.

## Baixo

### 1. Mes exibido incorretamente

- Arquivo/linha: `mural.js`, aprox. linhas 47-50
- Problema: `Date#getMonth()` retorna meses de `0` a `11`. Janeiro aparece como `0`, julho como `6`, etc.
- Como corrigir: usar `d.getMonth() + 1` ou `Intl.DateTimeFormat("pt-BR").format(d)`.

### 2. Regra de spam seria fragil mesmo se fosse usada

- Arquivo/linha: `mural.js`, aprox. linhas 76-80
- Problema: a checagem so procura a substring `"http"` com caixa exata. Ela nao pega `HTTP://`, links sem protocolo, dominios escritos de outras formas ou URLs ofuscadas. Tambem usa `==` em vez de `===`.
- Como corrigir: se links forem proibidos, normalizar o texto e usar uma regra bem definida no servidor. Para comparacoes em JavaScript, preferir igualdade estrita.

### 3. Variaveis globais aumentam risco de colisao

- Arquivo/linha: `mural.js`, aprox. linhas 4-13
- Problema: todo o script usa `var` no escopo global. Em uma pagina maior ou com outros scripts, nomes como `status`, `mural` ou `recados` podem colidir ou ser sobrescritos.
- Como corrigir: usar `const`/`let` dentro de um modulo (`<script type="module">`) ou envolver o codigo em uma funcao/IIFE. Evitar nomes globais genericos.

### 4. Falta de CSP deixa o impacto de XSS maior

- Arquivo/linha: `index.html`, aprox. linhas 3-21 e 35
- Problema: nao ha Content Security Policy definida. CSP nao corrige a vulnerabilidade de `innerHTML`, mas reduziria o impacto de uma falha de injecao em producao. O CSS inline atual tambem dificulta uma CSP mais restritiva sem ajustes.
- Como corrigir: configurar CSP no servidor, por exemplo bloqueando scripts inline e limitando `script-src` ao proprio dominio. Idealmente mover CSS para arquivo separado ou usar hash/nonce quando necessario.

### 5. Campos dependem apenas de placeholder como rotulo

- Arquivo/linha: `index.html`, aprox. linhas 28-29
- Problema: `placeholder` nao substitui `label`. Isso prejudica acessibilidade, navegacao por leitores de tela e usabilidade quando o usuario ja digitou algo.
- Como corrigir: adicionar `<label for="autor">` e `<label for="mensagem">`, mantendo placeholders apenas como exemplos curtos se necessario.

## Observacao de verificacao

- `node --check mural.js` nao encontrou erro de sintaxe. Os problemas acima sao de seguranca, comportamento e robustez.
