(() => {
  'use strict';
  const root = document.querySelector('[data-mpw-catalog]');
  if (!root) return;
  const message = (text) => { root.replaceChildren(); const p = document.createElement('p'); p.className = 'mpw-catalog-message'; p.textContent = text; root.append(p); };
  const card = (product) => {
    const article = document.createElement('article'); article.className = 'mpw-catalog-card';
    const kind = document.createElement('small'); kind.textContent = product.type || 'DIGITAL PRODUCT';
    const title = document.createElement('h3'); title.textContent = product.title;
    const price = document.createElement('p'); price.textContent = product.price && Number(product.price) > 0 ? product.price + ' ' + product.currency : 'View details for availability';
    const link = document.createElement('a'); link.textContent = 'View product →'; link.href = '/store/product/' + encodeURIComponent(product.id) + '/';
    article.append(kind, title, price, link); return article;
  };
  fetch(root.dataset.endpoint, {headers:{Accept:'application/json'}, credentials:'same-origin'})
    .then((r) => { if (!r.ok) throw new Error('Unavailable'); return r.json(); })
    .then((data) => { if (!Array.isArray(data.products)) throw new Error('Invalid response'); root.replaceChildren(); if (!data.products.length) { message('No public products are available yet. Browse our development categories below.'); return; } data.products.forEach((p) => root.append(card(p))); })
    .catch(() => message('The live catalog is temporarily unavailable. Please browse the store instead.'));
})();
