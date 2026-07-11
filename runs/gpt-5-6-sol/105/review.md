# Revisão de código — Mural de Recados

**Escopo:** `index.html` e `mural.js`  
**Data:** 10/07/2026  
**Parecer:** **não publicar no estado atual.** Há cinco bloqueadores críticos: uma credencial exposta, uma injeção de JavaScript persistente, ausência do backend multiusuário prometido e duas condições de corrida que perdem recados.

Critério usado: **crítico** bloqueia a publicação por permitir comprometimento, invalidar a função central ou causar perda de dados no fluxo normal; **médio** causa falha funcional, de confiabilidade, acessibilidade ou controle de abuso; **baixo** afeta correção secundária, UX, manutenção ou defesa em profundidade.

## Crítico

### C1 — Credencial “live” exposta no JavaScript

- **Arquivo/linha:** `mural.js:4`
- **Problema:** `API_TOKEN` contém uma credencial com aparência de token de produção (`sk_live_…`) no código entregue a todo visitante. Por ser um `var` global, ela também fica acessível como `window.API_TOKEN`. O token não é usado pela aplicação, portanto é simultaneamente código morto e um segredo vazado. Removê-lo do arquivo não desfaz a exposição em histórico do Git, caches ou artefatos já publicados.
- **Impacto:** se a credencial for real, terceiros podem consumir a API e os privilégios associados, gerando abuso, custo ou acesso indevido. Ela deve ser considerada comprometida mesmo que a tela ainda não tenha sido publicada publicamente.
- **Como corrigir:** revogar/rotacionar a credencial antes do deploy; remover o valor do bundle, dos artefatos e, conforme a política do projeto, do histórico; manter segredos em secret manager/variáveis do ambiente do servidor. A moderação deve ser chamada pelo backend com uma credencial de menor privilégio, nunca diretamente pelo navegador.

### C2 — XSS persistente por interpolação de dados em `innerHTML`

- **Arquivo/linha:** `mural.js:17-18, 32-43, 54-58`, principalmente `39-42`
- **Problema:** `autor`, `mensagem` e `quando` são concatenados em `el.innerHTML` sem escape nem sanitização. `autor` e `mensagem` vêm diretamente do usuário; os três campos também podem ser adulterados no `localStorage`. Por exemplo, um registro renderizado contendo ``<img src=x onerror="…">`` executa JavaScript na origem da aplicação.
- **Impacto:** execução arbitrária de script, leitura/alteração de dados da mesma origem, desfiguração da página e comprometimento de sessões ou integrações futuras. No protótipo atual o alcance remoto é limitado pelo armazenamento local, mas o sink já é persistente; ao ligar um backend compartilhado, um único recado infectado comprometeria todos os leitores.
- **Como corrigir:** criar `span`, `time` e `p` com `document.createElement` e atribuir todo texto não confiável com `textContent`. Se HTML rico for requisito, usar uma sanitização madura baseada em allowlist e validar também no servidor. CSP deve ser apenas uma camada adicional, não a correção principal.

### C3 — A funcionalidade multiusuário anunciada não existe

- **Arquivo/linha:** `index.html:26`; `mural.js:2, 15-30, 69-73`
- **Problema:** `localStorage` não é um backend. Ele só é compartilhado por documentos da mesma origem no mesmo perfil do mesmo navegador; usuários em dispositivos, navegadores ou perfis diferentes recebem murais isolados. Os nomes `carregarDoServidor`/`salvarNoServidor` e a latência aleatória apenas simulam uma rede que não existe. Os dados ainda podem ser editados, apagados ou limpos localmente sem qualquer controle de integridade.
- **Impacto:** a promessa central — “aparece pra todo mundo” — é falsa em produção, e os recados não têm persistência ou disponibilidade central. Esta versão não atende ao requisito básico do produto.
- **Como corrigir:** implementar uma API e armazenamento compartilhado reais, com leitura e append de recados, IDs e timestamps confiáveis, validação no servidor e política explícita de retenção. Se autoria tiver valor de identidade, autenticar e autorizar no servidor; se for anônima, deixar claro que o nome é autodeclarado e ainda aplicar controles de abuso.

### C4 — Atualizações concorrentes entre abas se sobrescrevem

- **Arquivo/linha:** `mural.js:15-30, 52-60`
- **Problema:** cada aba faz um ciclo não atômico de “ler o array inteiro, alterar em memória e gravar o array inteiro”. Se duas abas leem `[A]`, uma adiciona `B` e outra `C`, os timers podem gravar `[A,B]` e `[A,C]`; a última escrita apaga a outra. Uma aba que esteja atrasada também pode substituir um estado mais novo por sua cópia antiga.
- **Impacto:** perda silenciosa de recados justamente no cenário concorrente que o polling pretende simular. Não há detecção de conflito, retry nem merge confiável.
- **Como corrigir:** no backend, persistir cada recado com uma operação de append transacional, ID único e controle de versão/idempotência; nunca substituir a coleção inteira enviada pelo cliente. Para um protótipo estritamente local, seria necessário reler, versionar e serializar a seção crítica (por exemplo, com Web Locks), mas isso não resolve o requisito multiusuário real.

### C5 — O polling da própria aba pode apagar uma publicação pendente

- **Arquivo/linha:** `mural.js:24-29, 52-73`
- **Problema:** a gravação é adiada em até 400 ms e o callback serializa a variável global mutável `recados`, não um payload imutável. Exemplo: um submit aos 2,9 s adiciona `B` e agenda a gravação; o tick de 3 s carrega do storage a versão antiga `[A]` e substitui `recados`; quando o timer dispara, ele grava `[A]` novamente. `B` desaparece apesar de o formulário já ter sido limpo.
- **Impacto:** perda intermitente e silenciosa no uso de uma única aba, sem necessidade de ataque ou concorrência externa.
- **Como corrigir:** remover a latência artificial sobre uma API síncrona; em um backend real, enviar um payload imutável por publicação, manter uma fila/estado de operações pendentes e reconciliar respostas por ID/versão. Nunca substituir estado com uma leitura antiga enquanto houver escrita pendente.

## Médio

### M1 — O primeiro recado nunca é renderizado

- **Arquivo/linha:** `mural.js:35`
- **Problema:** o laço termina em `i > 0`, portanto nunca processa `recados[0]`. Com exatamente um recado, o mural fica vazio; com vários, o mais antigo sempre some da tela, embora continue armazenado.
- **Como corrigir:** iterar enquanto `i >= 0` ou gerar uma cópia invertida e percorrê-la sem excluir o índice zero.

### M2 — `status` colide com a propriedade nativa `window.status`

- **Arquivo/linha:** `mural.js:11, 61-64`; elemento em `index.html:32`
- **Problema:** o arquivo é um script clássico e declara `var status` no escopo global. Esse nome já é um atributo `DOMString` de `Window`; ao atribuir o `<p>`, o navegador converte o elemento em string. Assim, `status.textContent = ...` é um no-op em modo não estrito, e “Publicando...”/“Publicado!” nunca aparece. O comportamento decorre da API histórica [`Window.status`](https://html.spec.whatwg.org/multipage/nav-history-apis.html#dom-window-status) e foi reproduzido em navegador.
- **Como corrigir:** renomear para `statusEl` e manter a referência em escopo léxico, usando `const` dentro de um módulo (`type="module"`) ou IIFE.

### M3 — Falhas de gravação não são tratadas e o texto do usuário é descartado

- **Arquivo/linha:** `mural.js:24-29, 60-66`
- **Problema:** `JSON.stringify`/`localStorage.setItem` executam dentro do `setTimeout` sem `try/catch`. Quota esgotada, storage bloqueado ou `SecurityError` produzem uma exceção assíncrona não tratada; o callback de sucesso não roda. Mesmo assim a UI já renderizou otimisticamente e `form.reset()` já apagou os campos. No polling seguinte, o recado não persistido desaparece.
- **Como corrigir:** fazer a operação retornar sucesso/erro (idealmente uma `Promise`), capturar falhas, exibir mensagem acionável e oferecer retry. Só confirmar e limpar o formulário depois da persistência durável; em uma UI otimista, preservar um rascunho e fazer rollback explícito em caso de erro.

### M4 — Fechar ou recarregar a página durante a latência perde o recado

- **Arquivo/linha:** `mural.js:24-29, 65-66`
- **Problema:** a gravação real só ocorre no callback atrasado. Se o usuário navegar, atualizar ou fechar a aba nos até 400 ms anteriores ao timer, o callback é cancelado, embora o recado já tenha aparecido na tela e os campos já tenham sido limpos.
- **Como corrigir:** não atrasar artificialmente uma gravação local; com backend, só apresentar sucesso após o ack durável e manter o rascunho/operação pendente recuperável até então.

### M5 — Conteúdo do storage é aceito sem validação de esquema

- **Arquivo/linha:** `mural.js:15-21, 32-43, 52-60`
- **Problema:** qualquer JSON válido é atribuído a `recados`. Valores como `null`, `{}`, uma string ou um array com itens nulos quebram `render()` ou o próximo `push()`. JSON inválido e erros de leitura são engolidos pelo `catch`, sem telemetria nem aviso, deixando estado vazio ou obsoleto que pode depois sobrescrever o storage.
- **Como corrigir:** versionar o formato; verificar `Array.isArray`; validar tipo, presença e tamanho de cada campo; rejeitar/quarentenar registros inválidos e iniciar um estado seguro sem apagar silenciosamente os dados originais. Informar o usuário e registrar o erro de forma apropriada.

### M6 — Entradas sem normalização ou limites permitem lixo e esgotamento de quota

- **Arquivo/linha:** `index.html:28-29`; `mural.js:54-60`
- **Problema:** `required` aceita texto formado apenas por espaços e pode ser contornado fora do fluxo nativo do formulário. Não há `trim`, `maxlength` nem limite de tamanho no código. Uma entrada enorme aumenta JSON e DOM, pode travar a página e faz a gravação atingir a quota do storage.
- **Como corrigir:** normalizar e aplicar `trim`, rejeitar strings vazias e definir limites razoáveis de autor/mensagem no HTML e no código. Reaplicar obrigatoriamente todas as regras no backend, pois validação do cliente não é uma fronteira de segurança.

### M7 — Histórico ilimitado é reparsado e o DOM inteiro é reconstruído a cada 3 s

- **Arquivo/linha:** `mural.js:17-29, 32-45, 69-73`
- **Problema:** o histórico nunca expira nem é paginado. A cada publicação ele é serializado inteiro; a cada tick, `localStorage` e `JSON.parse` síncronos processam tudo e `render()` apaga/recria todos os artigos mesmo quando nada mudou. O custo cresce linearmente, bloqueia a main thread e destrói seleção/contexto de tecnologia assistiva. Em abas em segundo plano o timer ainda pode ser throttled, deixando a tela arbitrariamente desatualizada.
- **Como corrigir:** paginar e definir retenção; buscar/aplicar mudanças incrementais; renderizar apenas quando a versão mudar e atualizar somente os nós afetados. Para o protótipo entre abas, o evento `storage` reduz polling inútil, mas não corrige as condições de corrida.

### M8 — A “moderação” é código morto e não há controle antiabuso

- **Arquivo/linha:** `mural.js:52-67, 75-81`
- **Problema:** `ehSpam` nunca é chamada, nada é marcado ou bloqueado, e o token de moderação também nunca é usado. Mesmo conectada, a busca case-sensitive pela substring `http` é trivial de contornar (`HTTP`, `www`, `//host`, texto ofuscado) e pode gerar falsos positivos. O fluxo também não possui rate limiting ou quota por autor/origem.
- **Como corrigir:** remover a falsa proteção ou implementar política de moderação e rate limiting no backend, com normalização, tratamento explícito de falha e observabilidade. Checks no navegador podem melhorar UX, mas não podem decidir se uma publicação pública é aceita.

### M9 — Campos do formulário não têm rótulos persistentes

- **Arquivo/linha:** `index.html:27-30`
- **Problema:** `input` e `textarea` dependem apenas de `placeholder`. Ele desaparece durante a digitação e não substitui um rótulo visível explicitamente associado, prejudicando leitores de tela, controle por voz, compreensão de erro e conformidade de acessibilidade. A W3C recomenda [associar rótulos aos controles](https://www.w3.org/WAI/tutorials/forms/labels/).
- **Como corrigir:** adicionar `<label for="autor">` e `<label for="mensagem">` visíveis; manter placeholder apenas como exemplo, se necessário, e indicar visual/programaticamente que os campos são obrigatórios.

### M10 — Textos pequenos não atingem contraste mínimo

- **Arquivo/linha:** `index.html:12, 18, 20`
- **Problema:** `.sub` e `#status` têm aproximadamente 3,13:1 contra `#eef1f4`; `.quando` tem aproximadamente 2,59:1 contra branco. Como são textos normais pequenos, ficam abaixo dos 4,5:1 do [WCAG 2.2, critério 1.4.3](https://www.w3.org/TR/WCAG22/#contrast-minimum).
- **Como corrigir:** escurecer as cores e verificar todas as combinações/estados com um analisador de contraste; manter ao menos 4,5:1 para texto normal.

### M11 — Feedback assíncrono não é anunciado por tecnologia assistiva

- **Arquivo/linha:** `index.html:32`; `mural.js:61-64`
- **Problema:** mesmo depois de corrigir M2, alterar o texto de um `<p>` comum não torna a mensagem de status programaticamente determinável. Isso é uma falha conhecida para mensagens dinâmicas ([WCAG F103](https://www.w3.org/WAI/WCAG22/Techniques/failures/F103.html)).
- **Como corrigir:** usar `role="status"`, `aria-live="polite"` e `aria-atomic="true"` para progresso/sucesso; usar uma região de alerta adequada para falhas. Não tornar o mural inteiro uma live region enquanto ele for reconstruído periodicamente.

## Baixo

### B1 — O mês exibido está sempre uma unidade atrasado

- **Arquivo/linha:** `mural.js:47-50`
- **Problema:** `Date#getMonth()` é base zero. Em 10/07/2026, a função retorna `10/6/2026`. O formato também não tem zero padding, hora, fuso ou timestamp confiável para ordenar publicações concorrentes.
- **Como corrigir:** no mínimo somar 1 ao mês; preferencialmente persistir timestamp ISO/epoch gerado pelo servidor e formatá-lo com `Intl.DateTimeFormat("pt-BR", ...)`, exibindo-o em `<time datetime="...">`.

### B2 — O ID é frágil, duplicável e atualmente não serve para nada

- **Arquivo/linha:** `mural.js:54-59`, especialmente `55`
- **Problema:** `recados.length + 1` gera o mesmo ID em abas concorrentes e reutiliza IDs se houver exclusão/corrupção. Nenhum trecho lê `id`, então hoje o campo é código morto e dá uma falsa impressão de identidade estável.
- **Como corrigir:** remover o campo até existir um uso real ou gerar IDs únicos no servidor; para chave de idempotência criada no cliente, usar UUID e ainda impor unicidade no backend.

### B3 — Quebras de linha são perdidas e texto longo pode estourar o card

- **Arquivo/linha:** `index.html:19`; `mural.js:42`
- **Problema:** o conteúdo vem de um `textarea`, mas o `<p>` usa `white-space: normal`, que colapsa as quebras digitadas. Sequências longas sem espaços também podem transbordar horizontalmente.
- **Como corrigir:** após eliminar `innerHTML`, renderizar com `textContent` e aplicar `white-space: pre-wrap` e `overflow-wrap: anywhere` à mensagem.

### B4 — A região do mural não tem nome nem estado vazio

- **Arquivo/linha:** `index.html:33`; `mural.js:32-45`
- **Problema:** a `<section>` não possui heading/nome acessível, e uma lista vazia não informa se ainda não há recados ou se ocorreu falha de carregamento. Isso dificulta navegação por landmarks/headings e torna o estado inicial ambíguo.
- **Como corrigir:** adicionar um `<h2>` associado à seção (visível ou conforme o design), representar a coleção com semântica adequada e renderizar um estado vazio distinto de erro/carregamento.

### B5 — A mensagem de sucesso fica obsoleta indefinidamente

- **Arquivo/linha:** `mural.js:61-64`
- **Problema:** depois de corrigida a referência de status, “Publicado!” nunca é limpo nem associado a uma operação específica. Pode continuar visível durante uma operação posterior ou após uma falha, induzindo uma leitura errada do estado atual.
- **Como corrigir:** modelar estados por operação, substituir/limpar sucesso em momento controlado e manter erros até serem percebidos ou resolvidos.

### B6 — Todo o aplicativo está no escopo global e mistura responsabilidades

- **Arquivo/linha:** `mural.js:4-84`
- **Problema:** constantes, elementos, estado e funções usam `var`/declarações globais, expondo e permitindo colisões com APIs do navegador ou outros scripts — M2 já é um efeito concreto. Persistência, simulação de rede, estado e apresentação estão acoplados, o que dificulta testes e evolução.
- **Como corrigir:** usar módulo ou IIFE, `const`/`let` e separar adaptador de API/storage, modelo de estado, validação e renderização. Remover a latência fake e o código de moderação morto da versão de produção.

### B7 — Verificar CSP e cabeçalhos de segurança no deploy

- **Arquivo/linha:** `index.html:3-21, 35` e configuração HTTP não fornecida
- **Problema:** estes arquivos não demonstram nenhuma política de defesa em profundidade contra injeção, framing ou MIME sniffing. Isso não prova que os cabeçalhos estejam ausentes no servidor — a configuração de deploy não fez parte do escopo —, mas precisa ser verificado antes da publicação. O `<style>` inline atual também dificulta uma CSP estrita.
- **Como corrigir:** preferir cabeçalhos HTTP com CSP restritiva (`default-src 'self'`, `script-src 'self'`, `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'`), além de `X-Content-Type-Options: nosniff` e política de referrer apropriada. Mover o CSS inline ou autorizá-lo por hash/nonce; não liberar `unsafe-inline` apenas para acomodá-lo.

## Validações e limites da revisão

- Os bugs M1, M2 e B1 foram reproduzidos em navegador: o primeiro submit gerou zero artigos, o `<p id="status">` permaneceu vazio e julho foi exibido como mês 6.
- `mural.js` passa na verificação sintática do Node; os problemas encontrados são de comportamento, segurança e arquitetura, não de parsing.
- Não há dependências externas/CDN nestes dois arquivos, portanto não foi identificada uma superfície de supply chain aqui.
- Não há backend, requisições HTTP, sessão ou cookies no material recebido; por isso CSRF e controles do servidor não puderam ser auditados. Cabeçalhos HTTP também precisam ser conferidos no ambiente de deploy.

## Prioridade sugerida antes de qualquer publicação

1. Revogar/rotacionar C1 e eliminar C2.
2. Substituir o armazenamento fake por backend com append atômico, resolvendo C3-C5.
3. Corrigir M1-M8 e adicionar testes de concorrência, persistência e entradas hostis.
4. Fechar acessibilidade e itens baixos antes do aceite de produção.
