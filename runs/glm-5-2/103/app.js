// Meus Gastos — CRUD de gastos com persistência local e filtro por categoria.
// Convenções deste projeto:
//   - estado único em `gastos`, persistido por salvar()/carregar()
//   - todo filtro é uma função pura filtroXxx(gasto) combinada em aplicaFiltros()
//   - render() é a única função que toca o DOM da tabela
const CHAVE = 'meus-gastos-v1';

const form = document.getElementById('form-gasto');
const campoDescricao = document.getElementById('campo-descricao');
const campoValor = document.getElementById('campo-valor');
const campoCategoria = document.getElementById('campo-categoria');
const campoData = document.getElementById('campo-data');
const filtroCategoria = document.getElementById('filtro-categoria');
const filtroDataDe = document.getElementById('filtro-data-de');
const filtroDataAte = document.getElementById('filtro-data-ate');
const corpoTabela = document.querySelector('#tabela-gastos tbody');
const celulaTotal = document.getElementById('total');

let gastos = [];

function carregar() {
  try {
    gastos = JSON.parse(localStorage.getItem(CHAVE)) || [];
  } catch (e) {
    gastos = [];
  }
}

function salvar() {
  localStorage.setItem(CHAVE, JSON.stringify(gastos));
}

function formataMoeda(valor) {
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function formataData(iso) {
  const [ano, mes, dia] = iso.split('-');
  return `${dia}/${mes}/${ano}`;
}

// --- filtros: cada um é função pura (gasto) => boolean -----------------
function filtroPorCategoria(gasto) {
  const escolhida = filtroCategoria.value;
  return !escolhida || gasto.categoria === escolhida;
}

function filtroPorPeriodo(gasto) {
  const de = filtroDataDe.value;
  const ate = filtroDataAte.value;
  // datas estão em ISO (YYYY-MM-DD), então a comparação lexicográfica é correta
  if (de && gasto.data < de) return false;
  if (ate && gasto.data > ate) return false;
  return true;
}

function aplicaFiltros(lista) {
  return lista.filter((g) => filtroPorCategoria(g) && filtroPorPeriodo(g));
}
// -----------------------------------------------------------------------

function render() {
  const visiveis = aplicaFiltros(gastos)
    .slice()
    .sort((a, b) => (a.data < b.data ? 1 : -1));

  corpoTabela.innerHTML = '';
  for (const gasto of visiveis) {
    const tr = document.createElement('tr');

    const tdData = document.createElement('td');
    tdData.textContent = formataData(gasto.data);
    const tdDesc = document.createElement('td');
    tdDesc.textContent = gasto.descricao;
    const tdCat = document.createElement('td');
    tdCat.textContent = gasto.categoria;
    const tdValor = document.createElement('td');
    tdValor.className = 'num';
    tdValor.textContent = formataMoeda(gasto.valor);

    const tdAcao = document.createElement('td');
    const remover = document.createElement('button');
    remover.className = 'remover';
    remover.textContent = 'remover';
    remover.addEventListener('click', () => {
      gastos = gastos.filter((g) => g.id !== gasto.id);
      salvar();
      render();
    });
    tdAcao.appendChild(remover);

    tr.append(tdData, tdDesc, tdCat, tdValor, tdAcao);
    corpoTabela.appendChild(tr);
  }

  const total = visiveis.reduce((soma, g) => soma + g.valor, 0);
  celulaTotal.textContent = formataMoeda(total);
}

form.addEventListener('submit', (ev) => {
  ev.preventDefault();
  gastos.push({
    id: crypto.randomUUID(),
    descricao: campoDescricao.value.trim(),
    valor: Number(campoValor.value),
    categoria: campoCategoria.value,
    data: campoData.value,
  });
  salvar();
  render();
  form.reset();
  campoDescricao.focus();
});

filtroCategoria.addEventListener('change', render);
filtroDataDe.addEventListener('change', render);
filtroDataAte.addEventListener('change', render);

// dados de exemplo na primeira visita, pra tabela não nascer vazia
carregar();
if (!gastos.length) {
  gastos = [
    { id: 'a1', descricao: 'Mercado da semana', valor: 312.4, categoria: 'Alimentação', data: '2026-07-01' },
    { id: 'a2', descricao: 'Uber centro', valor: 24.9, categoria: 'Transporte', data: '2026-07-02' },
    { id: 'a3', descricao: 'Cinema', valor: 58.0, categoria: 'Lazer', data: '2026-07-04' },
    { id: 'a4', descricao: 'Conta de luz', valor: 187.35, categoria: 'Moradia', data: '2026-07-05' },
    { id: 'a5', descricao: 'Padaria', valor: 18.5, categoria: 'Alimentação', data: '2026-07-08' },
  ];
  salvar();
}
render();
