# Review do Mural de Recados

Escopo: `index.html` e `mural.js`.

## Crítico

| Arquivo | Linha aprox. | Problema | Como corrigir |
| --- | --- | --- | --- |
| `mural.js` | 4 | Há um token/API key hardcoded no JavaScript do cliente. Qualquer pessoa que abrir a página consegue extrair esse segredo; se ele for real, isso permite abuso direto da conta/serviço e exposição de credenciais. | Remover o segredo do frontend, mover o acesso sensível para o backend/variáveis de ambiente e rotacionar a chave comprometida. |
| `mural.js` | 39-42 | `innerHTML` recebe `autor`, `mensagem` e `quando` sem escaping. Isso abre XSS no contexto da página, porque conteúdo inserido pelo usuário ou vindo do `localStorage` pode virar HTML executável. | Renderizar com `textContent`/nós DOM ou sanitizar o conteúdo antes de inserir. Nunca concatenar input de usuário em `innerHTML`. |

## Médio

| Arquivo | Linha aprox. | Problema | Como corrigir |
| --- | --- | --- | --- |
| `mural.js` | 24-29, 69-73 | Há corrida entre `salvarNoServidor()` e o `setInterval()`: o estado é salvo de forma assíncrona, mas o poll recarrega `localStorage` e pode sobrescrever `recados` com uma versão antiga. O resultado é perda silenciosa de recados em produção, especialmente com mais de uma aba ou com latência simulada. | Serializar as escritas, evitar recarregar estado enquanto há save pendente e usar backend com controle de concorrência/versionamento ou merge explícito. |
| `mural.js` | 2, 17, 69 | O “backend” é só `localStorage`, então o mural não é realmente compartilhado entre usuários/dispositivos. O texto da UI promete que o recado aparece para todo mundo, mas cada navegador vê apenas a própria cópia. | Trocar `localStorage` por persistência real no servidor e sincronizar via API/websocket conforme a necessidade de compartilhamento. |
| `mural.js` | 35-44 | O loop de renderização usa `i > 0`, então o item `0` nunca é exibido. Com um único recado, o mural fica vazio; com vários, o mais antigo some sempre. | Trocar a condição para incluir `0` e validar o comportamento com listas vazias e listas de 1 item. |

## Baixo

| Arquivo | Linha aprox. | Problema | Como corrigir |
| --- | --- | --- | --- |
| `mural.js` | 47-49 | `getMonth()` é base 0, então janeiro aparece como `0`. A data também sai sem formatação consistente. | Somar `1` ao mês e formatar dia/mês com zero à esquerda se isso for requisito da interface. |
| `mural.js` | 75-81 | `ehSpam()` nunca é chamada. A lógica de moderação é código morto e o comentário sugere uma proteção que não existe. | Integrar a checagem no fluxo de submissão ou remover a função/comentário se a regra não for usar. |
| `mural.js` | 16-21 | Erros de `JSON.parse` em `carregarDoServidor()` são engolidos silenciosamente. Se o storage corromper, o app fica com estado indefinido e sem diagnóstico. | Exibir erro, limpar/reconstruir o estado e registrar a falha em vez de ignorá-la. |
