// Minhas Notas — app simples de notas com persistência em localStorage.
const form = document.getElementById('form-nota');
const campoTitulo = document.getElementById('campo-titulo');
const campoCorpo = document.getElementById('campo-corpo');
const lista = document.getElementById('lista-notas');
const STORAGE_KEY = 'minhas-notas';
const LEGACY_STORAGE_KEY = 'minhasnotas';

let notas = [];

function carregar() {
  try {
    const bruto = localStorage.getItem(STORAGE_KEY) ?? localStorage.getItem(LEGACY_STORAGE_KEY);
    notas = bruto ? JSON.parse(bruto) : [];
    if (!localStorage.getItem(STORAGE_KEY) && localStorage.getItem(LEGACY_STORAGE_KEY)) {
      salvar();
      localStorage.removeItem(LEGACY_STORAGE_KEY);
    }
  } catch (e) {
    notas = [];
  }
  render();
}

function salvar() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(notas));
}

function render() {
  lista.innerHTML = '';
  if (!notas.length) {
    lista.innerHTML = '<p class="vazio">Nenhuma nota ainda.</p>';
    return;
  }
  for (const nota of notas) {
    const el = document.createElement('article');
    el.className = 'nota';
    const apagar = document.createElement('button');
    apagar.className = 'apagar';
    apagar.textContent = 'apagar';
    apagar.addEventListener('click', () => {
      notas = notas.filter(n => n.id !== nota.id);
      salvar();
      render();
    });
    const h3 = document.createElement('h3');
    h3.textContent = nota.titulo;
    const p = document.createElement('p');
    p.textContent = nota.corpo;
    el.append(apagar, h3, p);
    lista.appendChild(el);
  }
}

form.addEventListener('submit', (ev) => {
  ev.preventDefault();
  notas.push({
    id: Date.now(),
    titulo: campoTitulo.value.trim(),
    corpo: campoCorpo.value.trim(),
  });
  salvar();
  render();
  form.reset();
  campoTitulo.focus();
});

carregar();
