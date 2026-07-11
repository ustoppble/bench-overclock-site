# Review de Código — Mural de Recados

## Crítico

### 1. O produto não é realmente multiusuário
- Arquivo: `index.html` (~26), `mural.js` (~2, 15-30, 69-73)
- Problema: a interface promete que o recado "aparece pra todo mundo", mas toda a persistência usa `localStorage`, que é isolado por navegador/perfil. Em produção, usuários em máquinas ou navegadores diferentes não compartilham o mesmo mural. O polling de 3 segundos só recarrega o armazenamento local do próprio usuário.
- Como corrigir: implementar um backend real com armazenamento compartilhado (API + banco/fila, mesmo que simples). Até isso existir, remover da UI qualquer promessa de mural global.

### 2. XSS persistente ao renderizar recados com `innerHTML`
- Arquivo: `mural.js` (~32-43, 54-58)
- Problema: `autor`, `mensagem` e `quando` entram no DOM por concatenação de HTML. Qualquer valor salvo em `localStorage` ou digitado no formulário pode injetar markup/script. Exemplo: um recado com `<img src=x onerror=alert(1)>` executa código quando o mural renderiza.
- Como corrigir: montar os elementos com `createElement` e preencher texto via `textContent`; tratar todo dado persistido como não confiável; adicionar uma CSP como defesa em profundidade.

### 3. Segredo exposto no cliente
- Arquivo: `mural.js` (~4)
- Problema: existe um `API_TOKEN` hardcoded em JavaScript entregue ao navegador. Se isso for um token real, qualquer visitante consegue copiá-lo e usá-lo fora do sistema. Como ele ainda está no cliente e sem uso, isso parece vazamento puro.
- Como corrigir: remover o token do frontend imediatamente, rotacionar/revogar o segredo exposto e mover qualquer integração de moderação para o servidor.

### 4. Condição de corrida com perda silenciosa de recados
- Arquivo: `mural.js` (~13-30, 52-73)
- Problema: o estado global `recados` é alterado localmente, salvo com `setTimeout` aleatório e sobrescrito periodicamente por `carregarDoServidor()`. Isso cria cenários de "last write wins": duas abas podem gravar listas diferentes no mesmo `localStorage`, e a última gravação apaga a outra. Se o polling rodar antes do `setTimeout`, a aba também pode regravar um estado antigo.
- Como corrigir: não usar gravação cega em `localStorage` para concorrência. Se insistir nessa abordagem temporária, ler/mesclar antes de salvar, versionar os dados e reagir ao evento `storage`. Em produção, preferir backend com operação atômica.

## Médio

### 5. O primeiro recado nunca é renderizado
- Arquivo: `mural.js` (~35)
- Problema: o loop usa `i > 0`, então o índice `0` nunca entra na renderização. Resultado: quando existe um único recado, o mural fica vazio; quando existem vários, o mais antigo some sempre.
- Como corrigir: ajustar a condição para incluir o índice zero (`i >= 0`) ou iterar sobre uma cópia invertida.

### 6. Falhas de persistência deixam a UI inconsistente
- Arquivo: `mural.js` (~24-29, 61-65)
- Problema: `localStorage.setItem()` pode lançar exceção (`QuotaExceededError`, bloqueio de storage, modo privado, etc.). Como isso acontece dentro do `setTimeout` e sem `try/catch`, a exceção fica solta, o usuário não recebe erro claro e o `render()` já mostrou um recado que talvez nunca tenha sido persistido.
- Como corrigir: envolver a escrita em `try/catch`, sinalizar falha no `status`, limitar tamanho de entrada e desfazer/confirmar a atualização otimista conforme o resultado da gravação.

### 7. Corrupção de dados é mascarada por `catch` vazio
- Arquivo: `mural.js` (~15-21)
- Problema: se o JSON em `localStorage` estiver inválido, o erro é engolido silenciosamente. Isso esconde incidente de dados, dificulta suporte e pode deixar a tela mostrando um estado antigo em memória sem qualquer aviso.
- Como corrigir: registrar o erro, informar o usuário, resetar ou colocar em quarentena o valor inválido e validar explicitamente a estrutura carregada.

### 8. Entradas e dados persistidos não são validados nem limitados
- Arquivo: `index.html` (~28-29), `mural.js` (~17-18, 54-58)
- Problema: nome e mensagem aceitam qualquer tamanho e conteúdo; `required` não impede texto só com espaços; o que sai de `localStorage` também entra direto no fluxo sem checagem de tipo/shape. Isso facilita estouro de quota, dados quebrados e comportamentos inconsistentes no render.
- Como corrigir: aplicar `trim`, validar tipos/campos, definir `maxlength` no HTML e no JavaScript e rejeitar registros malformados antes de salvar/renderizar.

### 9. A "moderação" não existe de fato
- Arquivo: `mural.js` (~4, 75-80)
- Problema: há um token e uma função `ehSpam`, mas ela nunca é chamada. Na prática, links e spam passam normalmente. Isso é especialmente ruim porque o código sugere uma proteção que o sistema não entrega.
- Como corrigir: ou remover o código/comentários mortos para não criar falsa sensação de segurança, ou implementar a moderação de verdade no backend antes de publicar.

## Baixo

### 10. Data exibida está errada em todos os meses
- Arquivo: `mural.js` (~47-49)
- Problema: `getMonth()` retorna mês zero-based (`0` a `11`). Janeiro sai como `0`, fevereiro como `1` e assim por diante.
- Como corrigir: somar `1` ao mês ou usar uma API de formatação (`Intl.DateTimeFormat`).

### 11. IDs podem colidir e não são confiáveis
- Arquivo: `mural.js` (~55)
- Problema: `id: recados.length + 1` gera IDs repetidos entre abas, após corrupção de dados ou em qualquer fluxo de concorrência. Hoje o campo nem é usado, mas ele não serve como identificador estável.
- Como corrigir: gerar IDs únicos (`crypto.randomUUID()` no cliente temporariamente, ou ID emitido pelo backend).

### 12. Sincronização por polling é atrasada e ineficiente
- Arquivo: `mural.js` (~69-73)
- Problema: mesmo no único cenário em que `localStorage` é compartilhado (mesmo navegador/perfil), outras abas só veem mudanças a cada 3 segundos. Isso ainda adiciona trabalho periódico desnecessário.
- Como corrigir: reagir ao evento `storage` para sincronização entre abas e eliminar o polling; em produção, substituir isso por atualização vinda do backend.
