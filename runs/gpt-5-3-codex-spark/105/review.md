# Revisão de código — Mural de Recados

## Crítico

1. Segredo sensível exposto no cliente
- Arquivo/linha aproximada: `mural.js:4`
- Problema: `API_TOKEN` com valor de API key `sk_live_*` está embutido no JavaScript enviado ao navegador. Qualquer usuário pode inspecionar o código e usar esse token fora do controle da aplicação.
- Correção: remover a chave do frontend. Guardar segredo em backend (variável de ambiente/server-side), proxificar chamadas sensíveis e não versionar nem expor tokens no código do cliente.

2. XSS armazenado por `innerHTML` com dado do usuário
- Arquivo/linha aproximada: `mural.js:39-42`
- Problema: `autor`, `quando` e `mensagem` são inseridos com `el.innerHTML = ...` sem escape. Um recado contendo HTML/JS malicioso pode executar script no navegador de todos que carregarem o mural.
- Correção: renderizar com `textContent` em nós de texto (`createElement` + `textContent`) ou sanitizar HTML explicitamente antes de inserir no DOM.

3. Corrida/condição de perda de dados ao “sincronizar” via `localStorage`
- Arquivo/linha aproximada: `mural.js:24-30` e `mural.js:70-73`
- Problema: o fluxo `recados.push(...)` + `setTimeout(... localStorage.setItem(...))` e `setInterval` de reloads lê/escreve o estado inteiro sem resolução de conflitos. Em múltiplas abas/usuários no mesmo `origin`, recados podem ser sobrescritos e perdidos (last-write-wins sobre versão antiga).
- Correção: não usar `localStorage` como backend; usar API real com persistência transacional e timestamps/ETag/locking, ou no mínimo merge por operação (append idempotente) em vez de sobrescrever array inteiro.

## Médio

1. Loop de render com limite incorreto (item zero nunca aparece)
- Arquivo/linha aproximada: `mural.js:35`
- Problema: `for (var i = recados.length - 1; i > 0; i--)` ignora `i === 0`. O recado mais antigo (ou único) pode não ser exibido.
- Correção: usar `i >= 0`.

2. Código morto/incompleto de moderação
- Arquivo/linha aproximada: `mural.js:75-81`
- Problema: função `ehSpam` existe, mas nunca é chamada no fluxo de publicação. Comentário/constantes sugerem moderação, mas ela não é aplicada.
- Correção: integrar `ehSpam(novo)` no `submit` antes de `recados.push(...)` e definir ação (bloquear/publicar com aviso/revisão).

3. Erro de parsing tratado silenciosamente
- Arquivo/linha aproximada: `mural.js:19-21`
- Problema: falha de `JSON.parse` é engolida, deixando estado possivelmente inconsistente sem notificação nem recuperação.
- Correção: registrar erro e reinicializar estado seguro (`recados = []`), além de limpar `localStorage` corrompido.

4. Data com mês incorreto
- Arquivo/linha aproximada: `mural.js:49`
- Problema: `getMonth()` retorna 0–11; janeiro vira 0, fevereiro 1 etc.
- Correção: ajustar para `d.getMonth() + 1` e considerar zero padding/locale.

## Baixo

1. Nome/limite do recado não é sanitizado/normalizado
- Arquivo/linha aproximada: `mural.js:54-58`
- Problema: aceita texto com só espaços, sem `trim`, e sem limite de tamanho.
- Correção: aplicar `trim()`, limites de comprimento e regras de validação no cliente e no backend.

2. Geração de `id` frágil
- Arquivo/linha aproximada: `mural.js:55`
- Problema: `id: recados.length + 1` pode repetir em cenários de reload/manual clear e colidir com concorrência.
- Correção: usar identificador único (UUID/ULID) gerado no backend.

3. Falha de fluxo ao iniciar/salvar com erro de armazenamento
- Arquivo/linha aproximada: `mural.js:24-30`
- Problema: não há tratamento de exceção para `localStorage.setItem` (`QuotaExceededError`, bloqueios de privacidade), e o status exibido volta para “Publicado!” sem confirmar persistência real.
- Correção: envolver em `try/catch`, tratar falha e mostrar erro de publicação com botão de reenvio.
