# Revisão de código — Mural de Recados

Escopo: revisão estática de index.html (37 linhas) e mural.js (84 linhas). As linhas abaixo são aproximadas. Nenhuma alteração foi feita no código da aplicação.

O critério de severidade considera tanto o código atual quanto a promessa explícita da interface de publicar recados para todas as pessoas. Configuração de servidor e headers HTTP não foram fornecidos, portanto só são apontados quando o próprio código não oferece a proteção necessária.

## Crítico

### C-01 — Segredo de produção exposto no JavaScript entregue ao navegador

**Arquivo / linha:** mural.js:4

**Problema e impacto:** API_TOKEN contém um token com aparência de credencial de produção (sk_live_...) no bundle público. Qualquer visitante, cache, cópia do repositório ou script executado na página consegue lê-lo. Se for válido, terceiros podem usar a API de moderação em nome da aplicação, gerar custo, consumir quota e potencialmente acessar recursos permitidos por esse token. Ele também está declarado globalmente.

**Como corrigir:** revogar e rotacionar o token imediatamente; removê-lo do histórico e dos artefatos publicados. Segredos devem ficar somente no backend, em variáveis/cofre de segredos, e o navegador deve chamar um endpoint próprio autenticado. Se for apenas um placeholder, removê-lo mesmo assim para não normalizar o padrão inseguro.

### C-02 — Injeção de HTML / XSS ao renderizar recados

**Arquivo / linha:** mural.js:39–42

**Problema e impacto:** os campos autor, quando e mensagem são concatenados em innerHTML sem escape. Conteúdo controlado por usuário ou já presente em localStorage pode fechar as tags e introduzir elementos/atributos executáveis, como um handler onerror. Isso permite JavaScript na origem do mural, alteração/leitura de todos os recados locais e exfiltração do token exposto.

No estado atual, localStorage não propaga um payload de um navegador para outro; portanto um atacante remoto não consegue usar somente este formulário para gravar no perfil de uma vítima. Ainda assim, o renderer é vulnerável a qualquer dado hostil já colocado por outro script da mesma origem e se torna XSS armazenado entre usuários assim que o mural receber o backend compartilhado que a interface promete.

**Como corrigir:** criar os elementos e preencher cada campo com textContent (ou createTextNode), nunca com innerHTML. Validar tipo, tamanho e conteúdo também no servidor. Se HTML formatado for uma necessidade real, sanitizá-lo com biblioteca robusta e uma allowlist mínima; não tentar fazê-lo com regex.

### C-03 — O “servidor” não existe: dados não são compartilhados nem confiáveis

**Arquivo / linha:** index.html:26; mural.js:15–18, 24–29 e 69–73

**Problema e impacto:** localStorage pertence à combinação de origem, navegador e perfil local. Ele não sincroniza pessoas, perfis ou dispositivos, embora a interface diga que o recado aparece para todos. Além de quebrar o requisito central, não há fonte de verdade, autenticação, autorização, auditoria ou integridade: o próprio usuário (ou qualquer JavaScript da mesma origem) pode editar, apagar ou forjar toda a coleção e qualquer nome de autor.

**Como corrigir:** substituir localStorage como persistência principal por uma API/backend e banco de dados. O backend deve validar a entrada, gerar IDs e data de criação, aplicar autorização/autoria conforme a regra de negócio e retornar a coleção canônica. localStorage pode, no máximo, guardar um rascunho não confiável.

### C-04 — Condição de corrida causa perda silenciosa de recados

**Arquivo / linha:** mural.js:24–29, 52–73

**Problema e impacto:** a gravação é adiada aleatoriamente e serializa a variável global recados somente quando o timeout roda. Se o polling chamar carregarDoServidor entre o submit e esse timeout, ele substitui recados pelo estado antigo; o timeout então grava o estado antigo e apaga o novo post. Em duas abas, ambas fazem leitura–modificação–gravação do array inteiro, sem versão ou lock: a última gravação vence e remove os recados da outra aba. Os IDs por tamanho agravam a inconsistência.

**Como corrigir:** no backend, criar cada recado em uma operação/transação atômica em vez de sobrescrever a coleção inteira; usar ID gerado pelo servidor e controle de concorrência (versão/ETag ou lock quando necessário). No cliente, tratar gravações pendentes de forma serializada, trabalhar com snapshots imutáveis e reconciliar a resposta do servidor. Um evento storage melhora atualização entre abas, mas não resolve concorrência nem substitui uma API.

## Médio

### M-01 — O feedback de publicação nunca atualiza por colisão com window.status

**Arquivo / linha:** mural.js:11, 61 e 63

**Problema e impacto:** o arquivo é um script clássico e var no topo cria/acessa propriedade de window. status já é a propriedade nativa window.status, cujo valor é uma string. A linha 11 converte o elemento p para string; depois status.textContent nas linhas 61 e 63 tenta escrever numa string primitiva em modo não estrito e falha silenciosamente. O usuário não vê “Publicando...” nem “Publicado!”.

**Como corrigir:** encapsular o arquivo em um módulo ou IIFE e usar um binding não global, por exemplo const statusEl = document.getElementById("status");. Usar statusEl.textContent nas atualizações e adicionar um teste de interface para os estados de envio, sucesso e erro.

### M-02 — O primeiro recado é sempre omitido

**Arquivo / linha:** mural.js:35

**Problema e impacto:** a condição i > 0 não inclui o índice zero. Com somente um recado, o mural fica vazio; com vários, o mais antigo nunca aparece.

**Como corrigir:** iterar enquanto i >= 0, ou usar uma cópia invertida do array. Cobrir os casos de zero, um e vários recados em teste.

### M-03 — Falhas de persistência não são tratadas e apagam o rascunho do usuário

**Arquivo / linha:** mural.js:24–29 e 61–66

**Problema e impacto:** localStorage.setItem pode lançar, por exemplo por quota excedida ou storage bloqueado. Como ele roda dentro do timeout, o erro escapa do try/catch; o callback de sucesso não é chamado, o formulário já foi limpo e o recado só existe temporariamente em memória. Ao recarregar a página, ele desaparece. O botão continua ativo durante o envio, o que também permite cliques repetidos e publicações duplicadas.

**Como corrigir:** transformar a gravação em operação com sucesso e falha explícitos (Promise/callback de erro), capturar exceções dentro do timeout, desabilitar o envio enquanto a operação estiver pendente, preservar o rascunho até confirmação e mostrar uma mensagem de erro com opção de tentar de novo. No desenho definitivo, tratar erros da API e não confirmar publicação antes da resposta do servidor.

### M-04 — Dados corrompidos ou fora do formato derrubam/mascaram o estado

**Arquivo / linha:** mural.js:15–21, 32–43 e 54–60

**Problema e impacto:** JSON.parse aceita JSON válido que não é uma lista de recados. Valores como null, {}, [null] ou campos não textuais fazem render ou submit falhar, ocultam dados ou provocam erro ao acessar r.autor. O catch só engole a exceção e mantém recados potencialmente antigo, sem recuperação ou aviso.

**Como corrigir:** após parse, verificar Array.isArray e validar o schema de cada item (id, autor, mensagem e quando com tipos e limites). Em caso inválido, preservar um backup para diagnóstico, iniciar estado seguro e avisar o usuário/telemetria. A mesma validação deve existir no backend.

### M-05 — Entradas sem normalização nem limites permitem lixo, quota e travamento

**Arquivo / linha:** index.html:28–29; mural.js:54–58

**Problema e impacto:** required só impede valor vazio; aceita texto composto apenas de espaços. Não há trim, maxlength, limite de quantidade de recados nem validação de tipo no cliente. Textos muito grandes podem tornar JSON.stringify, localStorage e a renderização lentos, esgotar a quota e acionar a falha não tratada de M-03.

**Como corrigir:** aplicar trim e regras explícitas de comprimento/charset; adicionar maxlength nos controles apenas como ajuda de UX; impor os mesmos limites, quota por usuário e rate limit no backend. Exibir erros de validação sem descartar o texto digitado.

### M-06 — A moderação é código morto e a política de spam não é aplicada

**Arquivo / linha:** mural.js:4 e 75–80

**Problema e impacto:** ehSpam nunca é chamada e API_TOKEN nunca é usada para moderação. Portanto todo recado é publicado sem qualquer controle. Mesmo se fosse chamada, procurar a substring "http" produz falsos positivos e é facilmente contornável (por exemplo, URL sem esse prefixo ou texto ofuscado); não protege contra XSS.

**Como corrigir:** remover o código se a funcionalidade não existir ou implementar moderação e controles de abuso no backend antes de publicar. Definir uma política clara, registrar decisões, limitar taxa de postagem e nunca confiar em uma checagem apenas no navegador.

### M-07 — Não há defesa em profundidade contra o XSS no código fornecido

**Arquivo / linha:** index.html:3–35

**Problema e impacto:** não há CSP declarada no documento; como a configuração HTTP não foi fornecida, não é possível confirmar que exista uma no deploy. Sem uma CSP restritiva, handlers inline inseridos pelo XSS (como onerror) executam livremente, ampliando C-02.

**Como corrigir:** configurar no servidor uma Content-Security-Policy por header, por exemplo com default-src 'self', script-src 'self', object-src 'none', base-uri 'none' e frame-ancestors 'none', adaptando style-src ao CSS. Externalizar o CSS ou usar hash/nonce se for necessário eliminar unsafe-inline. CSP complementa, mas não substitui, a remoção de innerHTML inseguro.

## Baixo

### L-01 — Data exibida com mês errado e sem horário

**Arquivo / linha:** mural.js:47–50

**Problema e impacto:** getMonth() retorna 0 para janeiro e 11 para dezembro, então toda data mostra o mês anterior. Além disso, a ausência de horário/data ISO dificulta auditar e ordenar recados.

**Como corrigir:** persistir createdAt gerado pelo servidor em ISO 8601 e formatá-lo no cliente com Intl.DateTimeFormat("pt-BR", ...). Como paliativo local, usar getMonth() + 1.

### L-02 — ID derivado do tamanho não é estável nem único

**Arquivo / linha:** mural.js:55

**Problema e impacto:** recados.length + 1 repete IDs após limpeza/corrupção do storage e em abas concorrentes. Embora o ID ainda não seja usado pela interface, ele não é uma base segura para futuros editar, excluir ou sincronizar.

**Como corrigir:** deixar o banco/backend gerar a chave. Se houver estado temporário no cliente, usar crypto.randomUUID(), mantendo a validação de unicidade no servidor.

### L-03 — Polling recria todo o DOM e não escala

**Arquivo / linha:** mural.js:32–45 e 69–73

**Problema e impacto:** a cada três segundos a página faz parse de todos os recados, apaga todo o mural e recria todos os nós. Sem paginação, limite ou atualização incremental, custo de CPU/DOM e piscadas perceptíveis crescem com o mural; o polling também aumenta a janela da corrida C-04.

**Como corrigir:** buscar somente mudanças de uma API/push, paginar ou limitar a lista e atualizar apenas nós alterados. Para o protótipo local, usar o evento storage para refletir mudanças de outra aba e renderizar somente quando houver alteração válida.

### L-04 — Estado local fica em texto claro e persiste no perfil

**Arquivo / linha:** mural.js:17 e 27

**Problema e impacto:** nomes e mensagens permanecem em texto claro no perfil do navegador. Qualquer script da mesma origem, XSS ou outra pessoa que use o mesmo perfil pode lê-los. Isso é especialmente problemático se alguém usar o mural para dados pessoais, apesar de não haver expectativa de segredo em um mural público.

**Como corrigir:** não armazenar conteúdo sensível no navegador; usar persistência no servidor com controles de acesso, retenção e exclusão adequados. Criptografar localStorage no próprio cliente não protege contra XSS.

### L-05 — Globais evitáveis e código morto aumentam a chance de novas colisões

**Arquivo / linha:** mural.js:4–15 e 75–80

**Problema e impacto:** quase todo o estado e todas as funções são var globais. A colisão de status já causa um bug real; novos scripts podem sobrescrever form, recados ou funções. API_TOKEN e ehSpam também são restos sem uso efetivo.

**Como corrigir:** usar JavaScript em módulo ou IIFE, preferir const/let com escopo mínimo e remover código/segredos obsoletos. Adicionar linting que detecte variáveis não usadas e globais acidentais.

### L-06 — Formulário e mensagens de estado têm falhas de acessibilidade

**Arquivo / linha:** index.html:28–32; CSS em index.html:12, 18 e 20

**Problema e impacto:** os controles dependem de placeholder em vez de label associado, que desaparece durante a digitação e é uma descrição frágil para tecnologias assistivas. A seção do mural não tem título/nome acessível. A mensagem de status não tem role="status" ou aria-live, portanto atualizações podem não ser anunciadas. As cores de texto secundário têm contraste baixo para texto normal (aprox. 2,6:1 em .quando sobre branco e 3,1:1 em .sub/#status sobre o fundo), abaixo do AA de 4,5:1; as bordas também parecem abaixo dos 3:1 recomendados para componentes.

**Como corrigir:** adicionar elementos label visíveis ou visualmente ocultos ligados por for/id; dar à seção um h2 ou aria-labelledby; usar role="status" e aria-live="polite" depois de corrigir M-01; ajustar as cores para ao menos 4,5:1 (texto) e 3:1 (componentes) e testar teclado/leitor de tela.

### L-07 — Não há testes automatizados no escopo entregue

**Arquivo / linha:** repositório fornecido; não há arquivos de teste ao lado de index.html e mural.js

**Problema e impacto:** regressões como o índice zero omitido, mês errado, XSS e a colisão com window.status chegaram ao código sem uma rede de segurança.

**Como corrigir:** adicionar testes de unidade para serialização/validação/data e testes de navegador para publicar, erro de persistência, render de um recado, texto malicioso e sincronização concorrente. Executá-los no CI antes do deploy.

### L-08 — Sem JavaScript, a página mostra um formulário que não funciona

**Arquivo / linha:** index.html:27–35

**Problema e impacto:** o formulário não tem action, e toda a funcionalidade depende de mural.js. Em navegador com JavaScript desativado, bloqueado por política ou que falhe ao carregar o arquivo, a pessoa preenche campos mas não tem um fluxo funcional nem um aviso claro.

**Como corrigir:** oferecer um fallback noscript que explique a indisponibilidade, ou preferencialmente disponibilizar submissão server-rendered/HTML progressivo que o JavaScript apenas aprimore.

## Prioridade sugerida antes de produção

1. Revogar o token e retirar todo segredo do cliente (C-01).
2. Implementar backend compartilhado com autenticação/autoria, validação e gravação atômica (C-03 e C-04).
3. Eliminar o XSS com textContent e defesa CSP (C-02 e M-07).
4. Corrigir os bugs visíveis de status, primeiro recado e erros de persistência (M-01 a M-04).
