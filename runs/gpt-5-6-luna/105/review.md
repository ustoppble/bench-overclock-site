# Review de código — Mural de Recados

## Resultado executivo

Não recomendo subir esta versão para produção. Há três bloqueadores: um segredo parece estar embutido no JavaScript entregue ao navegador, a renderização permite XSS e o suposto backend é apenas `localStorage`, que não é compartilhado entre usuários nem oferece integridade dos dados.

O `mural.js` passou na checagem de sintaxe (`node --check`), mas isso não cobre os problemas de execução e arquitetura abaixo. O escopo foi `index.html` e `mural.js`; não há backend, testes ou configuração de headers neste diretório para validar.

## Crítico

### C-01 — Segredo exposto no frontend

- **Arquivo/linha:** `mural.js:4`.
- **Problema:** `API_TOKEN` contém um valor com aparência de chave de produção (`sk_live_`) em um arquivo que será baixado por qualquer visitante. Além disso, a variável nem é usada no código atual. Qualquer pessoa pode inspecionar o bundle, extrair a chave e usá-la fora da aplicação.
- **Como corrigir:** revogar/rotacionar a chave imediatamente e removê-la também do histórico do repositório se ela já foi commitada. Segredos devem ficar somente no backend, que chama a API de moderação; usar credencial de escopo mínimo e rotação. Nunca colocar uma chave secreta em JavaScript do navegador, mesmo que a intenção seja “esconder” com minificação.

### C-02 — XSS armazenado via `innerHTML`

- **Arquivo/linha:** `mural.js:39-42` (dados vêm de `mural.js:54-57` e de `localStorage` em `mural.js:17-18`).
- **Problema:** `autor`, `mensagem` e até `quando` são concatenados diretamente em HTML. Um usuário pode publicar, por exemplo, um elemento com handler de evento, e o payload será executado quando o registro for renderizado. No código atual o alcance fica limitado ao perfil/origem cujo `localStorage` recebeu o registro; se o armazenamento for trocado pelo backend prometido, o mesmo defeito vira XSS armazenado para todos os leitores.
- **Como corrigir:** criar os elementos e atribuir os valores com `textContent`/`createTextNode`, sem concatenar HTML. Se rich text for requisito, aplicar sanitização com uma biblioteca mantida e política explícita. Fazer a mesma validação no servidor e adicionar CSP como defesa em profundidade; CSP não substitui a correção do sink.

### C-03 — Não existe backend ou controle de confiança para um mural público

- **Arquivo/linha:** `mural.js:2,15-29,69-73`.
- **Problema:** `localStorage` é armazenamento local do perfil do navegador, não um servidor. Dados não são compartilhados entre dispositivos/usuários, desaparecem ao limpar o navegador e podem ser editados, apagados ou substituídos pelo próprio usuário. O `setInterval` apenas relê o mesmo armazenamento local e não implementa sincronização multiusuário, auditoria, autenticação, autorização ou integridade.
- **Como corrigir:** implementar uma API real e banco de dados com gravação atômica, autenticação/autorização conforme a regra do mural, validação e sanitização no servidor, limites/rate limiting, moderação e logs. Gerar no servidor o ID e o timestamp. O frontend deve tratar a API como não confiável e mostrar erro quando a gravação falhar.

## Médio

### M-01 — Primeiro recado nunca é renderizado

- **Arquivo/linha:** `mural.js:35`.
- **Problema:** o laço usa `i > 0`, então o índice `0` é sempre ignorado. Com exatamente um recado, o mural fica vazio; com vários, o mais antigo nunca aparece.
- **Como corrigir:** iterar até `i >= 0` ou ordenar uma cópia e usar uma iteração que inclua todos os itens. Confirmar o comportamento com testes para zero, um e vários recados.

### M-02 — Race condition e perda de atualizações

- **Arquivo/linha:** `mural.js:24-29,60-73`.
- **Problema:** `salvarNoServidor` agenda uma gravação assíncrona, mas serializa a variável global `recados` somente quando o timer dispara; não salva um snapshot da chamada. Enquanto isso, o polling pode substituir `recados` com uma versão antiga. Em duas abas, ambas fazem read-modify-write de listas diferentes e a última gravação sobrescreve a outra. Assim, mensagens podem desaparecer sem que o usuário seja informado.
- **Como corrigir:** fazer cada publicação como operação atômica no backend (`POST` de um recado), com ID/idempotency key e controle de versão quando necessário. Não usar polling de `localStorage` como mecanismo de merge. Enquanto existir um protótipo local, enfileirar snapshots e tratar conflitos explicitamente; isso não substitui um backend para multiusuário.

### M-03 — Falhas de persistência ficam sem tratamento

- **Arquivo/linha:** `mural.js:17-21,26-29`.
- **Problema:** `getItem`/`JSON.parse` são engolidos pelo `catch`, deixando a aplicação com estado antigo ou silenciosamente vazio. Já `localStorage.setItem` ocorre dentro do `setTimeout` sem `try/catch`; quota excedida, armazenamento bloqueado ou modo privado podem lançar exceção e impedir o callback. Nesse caso, o status fica em “Publicando...” e não há indicação confiável de perda.
- **Como corrigir:** validar e tratar separadamente indisponibilidade, JSON inválido e quota excedida; chamar callback de erro ou usar `Promise` com `catch`; mostrar falha e permitir retry. Registrar telemetria sem expor conteúdo sensível.

### M-04 — Entrada sem limites, normalização ou proteção contra abuso

- **Arquivo/linha:** `index.html:28-29` e `mural.js:54-60`.
- **Problema:** `required` só impede string vazia; espaços passam. Não há `maxlength`, limites no número de recados, paginação, retenção ou rate limiting. Um usuário pode enviar textos enormes e fazer o DOM ficar lento ou consumir a quota do `localStorage`, causando falhas para novas publicações. A validação existente no navegador também seria facilmente burlada.
- **Como corrigir:** aplicar `trim`, limites de tamanho e mensagens de validação no cliente para UX, e repetir limites obrigatórios no servidor. Definir quota por usuário/IP, rate limiting, paginação/limpeza e tamanho máximo de resposta. Nunca confiar apenas na validação HTML.

### M-05 — Moderação declarada não é executada

- **Arquivo/linha:** `mural.js:52-67,75-81`.
- **Problema:** `ehSpam` nunca é chamado, não altera o recado e não há qualquer campo/fluxo que marque ou rejeite spam. Portanto, a regra comentada (“marca como spam se tiver link”) não existe em runtime. Mesmo se fosse chamada, procurar apenas `"http"` com comparação case-sensitive gera falsos positivos e deixa passar outras formas de URL.
- **Como corrigir:** definir o fluxo de moderação e executá-lo antes da publicação, preferencialmente no backend. Usar parser/política de URL e regras mantidas, com revisão humana ou serviço apropriado quando necessário. A chave da API de moderação deve permanecer no servidor.

### M-06 — Dados carregados não têm schema validation

- **Arquivo/linha:** `mural.js:15-21,32-43`.
- **Problema:** qualquer JSON obtido do armazenamento é aceito como `recados`, sem verificar se é um array nem se cada item tem strings válidas. Um valor como `null` ou um registro malformado pode fazer `render()` lançar exceção; o `catch` de carga não protege a renderização posterior. Como o armazenamento é editável pelo usuário e por scripts da mesma origem, isso é uma forma simples de quebrar a tela.
- **Como corrigir:** conferir `Array.isArray`, validar cada registro e seus tipos/tamanhos, descartar itens inválidos e migrar versões de schema de forma explícita. Em erro, usar um estado seguro (`[]`) e avisar o usuário, sem continuar renderizando dados arbitrários.

### M-07 — Publicação não é idempotente nem há proteção contra duplo envio

- **Arquivo/linha:** `mural.js:52-67`.
- **Problema:** o botão continua habilitado enquanto a gravação está pendente. Duplo clique, Enter repetido ou uma resposta lenta criam vários recados iguais. Em conjunto com a gravação por lista inteira, isso agrava conflitos e torna impossível distinguir retry de nova publicação.
- **Como corrigir:** desabilitar o envio durante a operação e reabilitar em sucesso/erro, mas principalmente usar uma chave de idempotência gerada por tentativa e fazer o backend deduplicar retries. Mostrar estado de erro em vez de presumir sucesso.

## Baixo

### L-01 — Data exibida com mês errado e relógio do cliente não é confiável

- **Arquivo/linha:** `mural.js:47-50,58`.
- **Problema:** `Date#getMonth()` é baseado em zero: janeiro aparece como mês `0`, fevereiro como `1` etc. Além disso, o timestamp vem do relógio do usuário, que pode estar incorreto ou ser manipulado.
- **Como corrigir:** usar `getMonth() + 1`/`Intl.DateTimeFormat` apenas para apresentação e registrar um timestamp UTC gerado pelo servidor. Preferir armazenar ISO 8601, não uma string formatada.

### L-02 — ID baseado no tamanho é instável e atualmente é código morto

- **Arquivo/linha:** `mural.js:54-55`.
- **Problema:** `recados.length + 1` pode se repetir em abas concorrentes e após remoções/migrações. Nenhum trecho do código lê `id`, então hoje o campo não fornece nenhuma identidade real.
- **Como corrigir:** remover o campo se não houver operação que o use; caso seja necessário, gerar UUID no servidor (ou `crypto.randomUUID()` somente para um protótipo local) e tratar o ID como único no armazenamento.

### L-03 — Formulário e status têm acessibilidade incompleta

- **Arquivo/linha:** `index.html:27-32`.
- **Problema:** os campos não têm `<label>` associado; placeholders não substituem rótulos e desaparecem durante a digitação. O status de publicação não tem `aria-live`/papel apropriado, então leitores de tela podem não anunciar “Publicando...” ou “Publicado!”.
- **Como corrigir:** adicionar labels visíveis ou adequadamente associados por `for`/`id`, manter instruções fora do placeholder e usar uma região `aria-live="polite"` para o status.

### L-04 — Falta de CSP e de headers de segurança não pode ser verificada no código

- **Arquivo/linha:** `index.html:7-21,35` (e configuração do servidor de produção).
- **Problema:** não há indicação de Content Security Policy nem de headers como `X-Content-Type-Options` e `frame-ancestors`. Isso não cria o XSS por si só, mas remove uma camada importante de contenção e deixa o deploy dependente de defaults do servidor.
- **Como corrigir:** configurar headers na resposta HTTP, incluindo CSP restritiva, HSTS quando todo o site estiver em HTTPS, proteção contra framing e MIME sniffing. Para evitar exceções amplas na CSP, mover o `<style>` inline para arquivo ou usar nonce/hash; ainda assim, corrigir primeiro o `innerHTML` inseguro.

## Ordem sugerida de priorização

1. Revogar a chave exposta.
2. Corrigir a injeção de HTML e impedir publicação/renderização de dados não validados.
3. Substituir `localStorage` por API/banco real com validação, limites, autenticação/moderação e gravação atômica.
4. Corrigir o laço, a concorrência, o tratamento de erros e a idempotência.
5. Ajustar data, IDs, acessibilidade e headers de segurança.
