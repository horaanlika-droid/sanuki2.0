/* SANUKI UDON SHOP — интерфейс приложения */
(function () {
  'use strict';

  const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
  const view = document.getElementById('view');
  const header = document.getElementById('app-header');
  const headerSub = document.getElementById('header-sub');
  const tabbar = document.getElementById('tabbar');
  const btnBack = document.getElementById('btn-back');

  let pollers = [];
  let booted = false;

  /* ------------------------------------------------------------------ *
   * Telegram Web App
   * ------------------------------------------------------------------ */
  function initTelegram() {
    if (!tg) return;
    try {
      tg.ready();
      tg.expand();
      if (tg.setHeaderColor) tg.setHeaderColor('#F76D10');
      if (tg.setBackgroundColor) tg.setBackgroundColor('#FDF9F1');
      if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
    } catch (e) { /* ignore */ }
  }

  function syncBackButton(route) {
    const isRoot = ['#/', '#/menu', '#/cart', '#/orders', '#/profile', ''].indexOf(route) >= 0;
    if (tg && tg.BackButton) {
      try {
        if (isRoot) { tg.BackButton.hide(); tg.BackButton.offClick(onTgBack); }
        else { tg.BackButton.show(); tg.BackButton.onClick(onTgBack); }
      } catch (e) { /* ignore */ }
    }
    btnBack.classList.toggle('hidden', isRoot);
  }

  function onTgBack() {
    if (history.length > 1) history.back();
    else location.hash = '#/';
  }

  btnBack.addEventListener('click', onTgBack);

  /* ------------------------------------------------------------------ *
   * Роутер
   * ------------------------------------------------------------------ */
  const routes = [
    { re: /^#?\/?$/, fn: screenHome, title: 'Главная' },
    { re: /^#\/menu$/, fn: screenMenu, title: 'Меню' },
    { re: /^#\/constructor$/, fn: screenConstructor, title: 'Конструктор удона' },
    { re: /^#\/cart$/, fn: screenCart, title: 'Корзина' },
    { re: /^#\/checkout$/, fn: screenCheckout, title: 'Оформление' },
    { re: /^#\/pay\/(.+)$/, fn: screenPay, title: 'Оплата' },
    { re: /^#\/orders$/, fn: screenOrders, title: 'Мои заказы' },
    { re: /^#\/order\/(.+)$/, fn: screenOrder, title: 'Заказ' },
    { re: /^#\/profile$/, fn: screenProfile, title: 'Профиль' },
    { re: /^#\/admin$/, fn: screenAdmin, title: 'Админ-панель' },
    { re: /^#\/about$/, fn: screenAbout, title: 'О SANUKI' },
  ];

  function currentRoute() {
    return location.hash || '#/';
  }

  async function route(silent) {
    stopPollers();
    const hash = currentRoute();
    for (const r of routes) {
      const m = hash.match(r.re);
      if (m) {
        headerSub.textContent = r.title;
        syncBackButton(hash);
        markTab(hash);
        if (!silent) view.innerHTML = '<div class="empty">…</div>';
        try {
          const html = await r.fn(m[1]);
          if (currentRoute() !== hash) return;   // успели перейти на другой экран
          view.innerHTML = html;
          afterRender(hash);
        } catch (err) {
          console.error(err);
          view.innerHTML = '<div class="empty"><span class="emoji">😵</span>' +
            UI.esc(err.message || 'Ошибка загрузки') + '</div>';
        }
        if (!silent) window.scrollTo(0, 0);
        return;
      }
    }
    location.hash = '#/';
  }

  function markTab(hash) {
    const base = '#' + (hash.split('/').slice(0, 2).join('/') || '/');
    document.querySelectorAll('.tab').forEach(t => {
      t.classList.toggle('active', t.dataset.route === base);
    });
    updateCartDot();
  }

  function updateCartDot() {
    const tab = document.querySelector('.tab[data-route="#/cart"]');
    if (!tab) return;
    const count = API.cartCount();
    let dot = tab.querySelector('.dot');
    if (count > 0) {
      if (!dot) {
        dot = document.createElement('span');
        dot.className = 'dot';
        tab.appendChild(dot);
      }
      dot.textContent = count;
    } else if (dot) {
      dot.remove();
    }
  }

  function afterRender(hash) {
    updateCartDot();
    if (hash.indexOf('#/orders') === 0 || hash.indexOf('#/order/') === 0 || hash === '#/admin') {
      startPolling(route, 6000);
    }
    // Навигация по табам
    document.querySelectorAll('.tab').forEach(tab => {
      tab.onclick = () => { location.hash = tab.dataset.route; };
    });
  }

  function startPolling(fn, ms) {
    const id = setInterval(() => {
      if (document.hidden) return;
      fn(true);
    }, ms);
    pollers.push(id);
  }

  function stopPollers() {
    pollers.forEach(clearInterval);
    pollers = [];
  }

  /* ------------------------------------------------------------------ *
   * Экран: Главная
   * ------------------------------------------------------------------ */
  async function screenHome() {
    const catalog = await API.menu();
    const settings = catalog.settings || {};
    const presets = buildPresets(catalog);

    const presetCards = presets.map(p => `
      <div class="card tight" style="margin-bottom:10px">
        <div class="between">
          <div>
            <div style="font-weight:800">${UI.esc(p.name)}</div>
            <div class="small muted">${UI.esc(p.base)} · ${UI.esc(p.protein)}</div>
          </div>
          <button class="btn sm primary" data-preset='${UI.esc(JSON.stringify(p))}'>Собрать · ${UI.money(p.price)}</button>
        </div>
      </div>`).join('');

    const cats = (catalog.categories || [])
      .filter(c => c.kind === 'items' && c.items && c.items.length)
      .map(c => `<button class="chip" data-cat="${UI.esc(c.name)}">${c.emoji} ${UI.esc(c.name)}</button>`)
      .join('');

    return `
      <div class="hero">
        <img src="/static/img/hero.jpg" alt="SANUKI">
        <div class="hero-body">
          <span class="hero-badge">UDON SHOP</span>
          <h1>Собери свой идеальный удон</h1>
          <p>Четыре шага: бульон, белок, топпинг и допы. Готовим при вас.</p>
          <button class="btn primary" data-go="#/constructor">🍜 Собрать удон</button>
        </div>
      </div>

      <div class="usp">
        <div class="usp-item"><b>15–20</b>минут</div>
        <div class="usp-item"><b>Свежие</b>ингредиенты</div>
        <div class="usp-item"><b>Сами</b>собираем удон</div>
      </div>

      <div class="section">
        <div class="section-head"><h2>Хиты SANUKI</h2></div>
        ${presetCards}
      </div>

      <div class="section">
        <div class="section-head"><h2>Категории</h2>
          <a class="link" href="#/menu">всё меню ›</a></div>
        <div class="row wrap" style="gap:8px">${cats}</div>
      </div>

      <div class="card dark">
        <h3>🎌 SANUKI UDON SHOP</h3>
        <div class="info-grid" style="margin-top:8px">
          <div class="info-row"><b>Адрес</b><span>${UI.esc(settings.address || '')}</span></div>
          <div class="info-row"><b>Время</b><span>${UI.esc(settings.work_hours || '')}</span></div>
          <div class="info-row"><b>Телефон</b><span>${UI.esc(settings.phone || '')}</span></div>
        </div>
        <div class="row" style="margin-top:12px;gap:8px">
          <button class="btn sm ghost" data-go="#/about" style="color:#fff;border-color:rgba(255,255,255,.3)">О нас</button>
          <button class="btn sm" data-go="#/profile">Позвать сотрудника</button>
        </div>
      </div>
    `;
  }

  function buildPresets(catalog) {
    const udon = catalog.udon || {};
    const bases = (udon.bases || []).filter(b => b.available !== false);
    const proteins = (udon.proteins || []).filter(p => p.available !== false);
    const byName = (arr, name) => arr.find(x => x.name === name);
    const wanted = [
      { name: 'Тори удон', base: 'Цую бульон', protein: 'томлёная курица' },
      { name: 'Карри удон', base: 'Соус карри', protein: 'криспи курица' },
      { name: 'Говяжий удон', base: 'Говяжий бульон', protein: 'томлёная говядина' },
    ];
    const result = [];
    wanted.forEach(w => {
      const b = byName(bases, w.base);
      const p = byName(proteins, w.protein);
      if (b && p) result.push(Object.assign({}, w, { price: p.price }));
    });
    if (!result.length && bases.length && proteins.length) {
      result.push({
        name: 'Классический удон', base: bases[0].name,
        protein: proteins[0].name, price: proteins[0].price,
      });
    }
    return result;
  }

  /* ------------------------------------------------------------------ *
   * Экран: Меню
   * ------------------------------------------------------------------ */
  let menuCategory = null;

  async function screenMenu() {
    const catalog = await API.menu();
    const cats = (catalog.categories || []).filter(c => c.kind === 'items' && c.items);
    if (!menuCategory || !cats.find(c => c.name === menuCategory)) {
      menuCategory = cats.length ? cats[0].name : '';
    }
    const category = cats.find(c => c.name === menuCategory) || { items: [] };

    const chips = cats.map(c =>
      `<button class="chip ${c.name === menuCategory ? 'active' : ''}" data-cat="${UI.esc(c.name)}">` +
      `${c.emoji} ${UI.esc(c.name)}</button>`).join('');

    const items = category.items.map(item => {
      const inCart = API.state.cart.findIndex(i => i.name === item.name);
      const control = item.available === false
        ? '<span class="small muted">нет сегодня</span>'
        : (inCart >= 0
          ? `<div class="qty"><button data-qty-minus="${inCart}">−</button>` +
            `<span>${API.state.cart[inCart].qty}</span>` +
            `<button data-qty-plus="${inCart}">+</button></div>`
          : `<button class="add-btn" data-add="${UI.esc(item.name)}">+</button>`);
      return `
        <div class="dish ${item.available === false ? 'out' : ''}">
          <div class="dish-emoji">${item.emoji || '•'}</div>
          <div class="dish-body">
            <div class="dish-name">${UI.esc(item.name)}</div>
            ${item.description ? `<div class="dish-desc">${UI.esc(item.description)}</div>` : ''}
            <div class="dish-price">${UI.money(item.price)}</div>
          </div>
          ${control}
        </div>`;
    }).join('');

    const footer = API.cartCount()
      ? `<div class="footer-bar">
           <div class="grow total">В корзине ${API.cartCount()} шт.<b>${UI.money(API.cartTotal())}</b></div>
           <button class="btn primary" data-go="#/cart">К корзине</button>
         </div>`
      : '';

    return `
      <div class="card tight">
        <div class="between">
          <div>
            <h3 style="margin:0">🍜 Конструктор удона</h3>
            <div class="small muted">Основа, белок, топпинг и допы</div>
          </div>
          <button class="btn sm primary" data-go="#/constructor">Собрать</button>
        </div>
      </div>

      <div class="pill-row">${chips}</div>

      <div class="card">
        <h3 style="margin-bottom:4px">${category.emoji || ''} ${UI.esc(category.name || '')}</h3>
        ${items || UI.empty('В этой категории пока пусто')}
      </div>
      ${footer}
    `;
  }

  /* ------------------------------------------------------------------ *
   * Экран: Конструктор
   * ------------------------------------------------------------------ */
  function draft() {
    if (!API.state.draft) {
      API.state.draft = { step: 1, base: null, protein: null, topping: null, extras: [] };
    }
    return API.state.draft;
  }

  async function screenConstructor() {
    const catalog = await API.menu();
    const udon = catalog.udon || { bases: [], proteins: [], toppings: [] };
    const d = draft();
    if (d.step < 1 || d.step > 4) d.step = 1;

    const extrasCat = (catalog.categories || [])
      .find(c => c.name === 'Дополнительные топпинги');
    const extrasList = (extrasCat && extrasCat.items) || [];

    const steps = [1, 2, 3, 4].map(n =>
      `<div class="step-dot ${d.step >= n ? 'done' : ''}"></div>`).join('');

    let body = '';

    if (d.step === 1) {
      body = udon.bases.map(b => `
        <button class="option ${d.base === b.name ? 'selected' : ''}" data-base="${UI.esc(b.name)}">
          <span class="opt-emoji">${b.emoji || '🍜'}</span>
          <span class="opt-body">
            <span class="opt-name">${UI.esc(b.name)}</span>
            <span class="opt-desc">${UI.esc(b.description || '')}</span>
          </span>
          <span class="check">${d.base === b.name ? '✓' : ''}</span>
        </button>`).join('') || UI.empty('Нет доступных основ', '🥣');
    }

    if (d.step === 2) {
      body = udon.proteins.map(p => `
        <button class="option ${d.protein === p.name ? 'selected' : ''}" data-protein="${UI.esc(p.name)}">
          <span class="opt-emoji">${p.emoji || '🍖'}</span>
          <span class="opt-body">
            <span class="opt-name">${UI.esc(p.name)}</span>
          </span>
          <span class="opt-price">${p.price} ₽</span>
        </button>`).join('') || UI.empty('Нет доступных белков', '🍗');
    }

    if (d.step === 3) {
      body = udon.toppings.map(t => `
        <button class="option ${d.topping === t.name ? 'selected' : ''}" data-topping="${UI.esc(t.name)}">
          <span class="opt-emoji">${t.emoji || '🌿'}</span>
          <span class="opt-body"><span class="opt-name">${UI.esc(t.name)}</span>
            <span class="opt-desc">бесплатно</span></span>
          <span class="check">${d.topping === t.name ? '✓' : ''}</span>
        </button>`).join('') + `
        <button class="option" data-topping-skip="1">
          <span class="opt-emoji">⏭</span>
          <span class="opt-body"><span class="opt-name">Пропустить</span>
            <span class="opt-desc">удон без топпинга</span></span>
        </button>`;
    }

    if (d.step === 4) {
      const chosen = d.extras.map(e => {
        const info = extrasList.find(x => x.name === e) || { price: 0, emoji: '➕' };
        return { name: e, price: info.price, emoji: info.emoji };
      });
      body = `
        <div class="card tight" style="background:#FFF6EE;border-color:rgba(247,109,16,.25)">
          <div class="small muted">Ваш удон</div>
          <div style="font-weight:800">${UI.esc(d.base)} + ${UI.esc(d.protein)}</div>
          <div class="small muted">🌿 ${UI.esc(d.topping || 'Без топпинга')}</div>
          ${chosen.length ? '<div class="divider"></div>' + chosen.map(c =>
            `<div class="between small"><span>${c.emoji} ${UI.esc(c.name)}</span>` +
            `<span>+${c.price} ₽</span></div>`).join('') : ''}
        </div>
        <h3 style="margin:14px 0 8px">Дополнительные топпинги</h3>
        ` + extrasList.map(e => {
        const on = d.extras.indexOf(e.name) >= 0;
        return `
          <button class="option ${on ? 'selected' : ''}" data-extra="${UI.esc(e.name)}">
            <span class="opt-emoji">${e.emoji || '➕'}</span>
            <span class="opt-body"><span class="opt-name">${UI.esc(e.name)}</span></span>
            <span class="opt-price">+${e.price} ₽</span>
            <span class="check">${on ? '✓' : ''}</span>
          </button>`;
      }).join('') || UI.empty('Допов пока нет');
    }

    const titles = [
      'Шаг 1 из 4 — выберите бульон',
      'Шаг 2 из 4 — главный ингредиент',
      'Шаг 3 из 4 — топпинг бесплатно',
      'Шаг 4 из 4 — дополните вкус',
    ];

    const proteinPrice = (udon.proteins.find(p => p.name === d.protein) || {}).price || 0;
    const extrasTotal = d.extras.reduce((s, name) => {
      const info = extrasList.find(x => x.name === name);
      return s + (info ? info.price : 0);
    }, 0);
    const total = proteinPrice + extrasTotal;

    const footer = `
      <div class="footer-bar">
        <div class="grow total">${titles[d.step - 1]}<b>${UI.money(total)}</b></div>
        ${d.step > 1 ? '<button class="btn sm ghost" data-step-back="1">Назад</button>' : ''}
        ${d.step < 4
          ? `<button class="btn primary" data-step-next="1" ${stepReady(d) ? '' : 'disabled'}>Далее</button>`
          : '<button class="btn primary" data-add-udon="1">В корзину</button>'}
      </div>`;

    return `<div class="steps">${steps}</div>
      <h2>${UI.esc(titles[d.step - 1])}</h2>
      <div style="margin-top:12px">${body}</div>
      ${footer}`;
  }

  function stepReady(d) {
    if (d.step === 1) return !!d.base;
    if (d.step === 2) return !!d.protein;
    if (d.step === 3) return !!d.topping;
    return true;
  }

  /* ------------------------------------------------------------------ *
   * Экран: Корзина
   * ------------------------------------------------------------------ */
  async function screenCart() {
    const cart = API.state.cart;
    if (!cart.length) {
      return UI.empty('Корзина пуста. Соберите удон или выберите закуски!', '🛒') +
        `<button class="btn primary block" data-go="#/constructor">🍜 Собрать удон</button>`;
    }

    const lines = cart.map((item, idx) => `
      <div class="cart-line">
        <div class="body">
          <div class="name">${UI.esc(item.title || item.name)}</div>
          ${item.kind === 'udon'
            ? `<div class="meta">${UI.esc(item.topping || '')}${
                (item.extras || []).length ? ' · ' + item.extras.map(e => e.name).join(', ') : ''}</div>`
            : ''}
          <div class="meta">${UI.money(item.price)} × ${item.qty}</div>
        </div>
        <div class="price">${UI.money(item.price * item.qty)}</div>
        <div class="qty">
          <button data-qty-minus="${idx}">−</button>
          <span>${item.qty}</span>
          <button data-qty-plus="${idx}">+</button>
        </div>
        <button class="del" data-qty-del="${idx}" aria-label="Удалить">✕</button>
      </div>`).join('');

    return `
      <div class="card">
        <h3 style="margin-bottom:6px">🛒 Ваш заказ</h3>
        ${lines}
        <div class="divider"></div>
        <div class="between">
          <b>Итого</b>
          <span class="price-lg">${UI.money(API.cartTotal())}</span>
        </div>
      </div>
      <button class="btn ghost block" data-go="#/menu" style="margin-bottom:10px">➕ Добавить ещё</button>
      <button class="btn primary block" data-go="#/checkout">✅ Оформить заказ</button>
      <button class="btn ghost block" data-clear-cart="1" style="margin-top:10px;color:#D8433A">🗑 Очистить корзину</button>
    `;
  }

  /* ------------------------------------------------------------------ *
   * Экран: Оформление
   * ------------------------------------------------------------------ */
  let checkoutForm = {
    order_type: 'dine_in', name: '', phone: '', address: '', comment: '',
    payment_method: 'cash',
  };

  async function screenCheckout() {
    if (!API.state.cart.length) {
      location.hash = '#/cart';
      return '<div class="empty">Корзина пуста</div>';
    }
    const catalog = await API.menu();
    const pay = await API.paymentMethods();
    const user = API.state.user || {};
    if (!checkoutForm.name) checkoutForm.name = user.name || '';
    if (!checkoutForm.phone) checkoutForm.phone = user.phone || '';

    const types = (catalog.order_types || []).map(t =>
      `<button class="chip ${checkoutForm.order_type === t.code ? 'active' : ''}"
        data-order-type="${t.code}">${UI.esc(t.title)}</button>`).join('');

    const methods = (pay.methods || []).map(m =>
      `<button class="chip ${checkoutForm.payment_method === m.code ? 'active' : ''}"
        data-pay-method="${m.code}">${UI.esc(m.title)}</button>`).join('');

    const isDelivery = checkoutForm.order_type === 'delivery';

    return `
      <h2>Оформление заказа</h2>
      <div class="card">
        <div class="small muted" style="margin-bottom:6px">Формат заказа</div>
        <div class="row wrap" style="gap:8px">${types}</div>
      </div>

      <div class="card">
        <div class="field">
          <label>Имя</label>
          <input id="f-name" value="${UI.esc(checkoutForm.name)}" placeholder="Как к вам обращаться">
        </div>
        <div class="field">
          <label>Телефон</label>
          <input id="f-phone" value="${UI.esc(checkoutForm.phone)}" placeholder="+7 999 000-00-00">
        </div>
        ${isDelivery ? `
        <div class="field">
          <label>Адрес доставки</label>
          <input id="f-address" value="${UI.esc(checkoutForm.address)}" placeholder="Улица, дом, квартира">
        </div>` : ''}
        ${!isDelivery ? `
        <div class="field">
          <label>Стол или комментарий</label>
          <input id="f-comment" value="${UI.esc(checkoutForm.comment)}" placeholder="Например: стол 5, без лука">
        </div>` : `
        <div class="field">
          <label>Комментарий к заказу</label>
          <input id="f-comment" value="${UI.esc(checkoutForm.comment)}" placeholder="Пожелания">
        </div>`}
      </div>

      <div class="card">
        <div class="small muted" style="margin-bottom:6px">Способ оплаты</div>
        <div class="row wrap" style="gap:8px">${methods}</div>
        ${pay.stub && checkoutForm.payment_method === 'yoomoney'
          ? '<div class="stub-note" style="margin-top:12px"><b>ЮMoney — заглушка.</b> ' +
            'Реального списания не происходит: оплата подтверждается одной кнопкой, ' +
            'статус заказа меняется как при настоящей оплате.</div>'
          : ''}
      </div>

      <div class="card">
        ${API.state.cart.map(i =>
          `<div class="between small"><span>${UI.esc(i.title || i.name)} × ${i.qty}</span>
           <span>${UI.money(i.price * i.qty)}</span></div>`).join('')}
        <div class="divider"></div>
        <div class="between"><b>Итого</b><span class="price-lg">${UI.money(API.cartTotal())}</span></div>
      </div>

      <div class="footer-bar">
        <div class="grow total">К оплате<b>${UI.money(API.cartTotal())}</b></div>
        <button class="btn primary" id="submit-order">✅ Подтвердить</button>
      </div>
    `;
  }

  /* ------------------------------------------------------------------ *
   * Экран: Оплата (заглушка ЮMoney)
   * ------------------------------------------------------------------ */
  async function screenPay(code) {
    const data = await API.order(code);
    const order = data.order;
    if (order.payment_status === 'paid') {
      return `
        <div class="card center">
          <div style="font-size:44px">💜</div>
          <h2>Оплачено</h2>
          <p class="muted">Заказ №${UI.esc(order.code)} на ${UI.money(order.total)}</p>
          <button class="btn primary block" data-go="#/order/${UI.esc(order.code)}">К заказу</button>
        </div>`;
    }
    return `
      <h2>Оплата заказа №${UI.esc(order.code)}</h2>
      <div class="stub-note">
        <b>Режим заглушки (YOOMONEY_MODE=stub).</b>
        Интерфейс и статусы работают как с настоящей кассой, но деньги не списываются.
        После подключения боевого токена ЮMoney здесь будет редирект на форму оплаты.
      </div>
      <div class="card">
        <div class="center">
          <div class="small muted">Сумма к оплате</div>
          <div class="price-lg" style="font-size:34px">${UI.money(order.total)}</div>
          <div class="small muted" style="margin-top:6px">ЮMoney · ${UI.esc(order.payment_id || '')}</div>
        </div>
      </div>
      <button class="btn primary block" id="pay-stub">💜 Оплатить ${UI.money(order.total)}</button>
      <button class="btn ghost block" style="margin-top:10px" data-go="#/order/${UI.esc(order.code)}">
        Отложить оплату
      </button>
    `;
  }

  /* ------------------------------------------------------------------ *
   * Экран: Мои заказы
   * ------------------------------------------------------------------ */
  async function screenOrders() {
    const statuses = await API.statuses();
    const data = await API.orders();
    const orders = data.orders || [];
    if (!orders.length) {
      return UI.empty('Пока нет заказов. Соберите свой удон!', '📋') +
        '<button class="btn primary block" data-go="#/constructor">🍜 Собрать удон</button>';
    }
    const cards = orders.map(o => `
      <div class="card order-card" data-go="#/order/${UI.esc(o.code)}">
        <div class="between">
          <div>
            <div style="font-weight:800">№${UI.esc(o.code)} · ${UI.dateTime(o.created_at)}</div>
            <div class="small muted">${UI.esc(o.order_type_title)} · ${UI.esc(o.guest_name)}</div>
          </div>
          ${UI.badge(statuses, o.status)}
        </div>
        <div class="divider"></div>
        <div class="small muted" style="white-space:pre-line">${UI.esc(o.items_text)}</div>
        <div class="between" style="margin-top:10px">
          <b>${UI.money(o.total)}</b>
          ${o.payment_method === 'yoomoney' ? UI.paymentBadge(o.payment_status) : ''}
        </div>
      </div>`).join('');
    return `<h2>Мои заказы</h2>
      <p class="small muted">Статусы обновляются автоматически и совпадают с ботом.</p>
      ${cards}`;
  }

  /* ------------------------------------------------------------------ *
   * Экран: Заказ
   * ------------------------------------------------------------------ */
  async function screenOrder(code) {
    const statuses = await API.statuses();
    const data = await API.order(code);
    const order = data.order;
    const history = data.history || [];
    const timeline = data.timeline || [];

    const doneSet = {};
    history.forEach(h => { doneSet[h.status] = h; });
    const cancelled = order.status === 'cancelled';
    const chain = cancelled ? ['cancelled'] : timeline;

    const steps = chain.map((code2, idx) => {
      const meta = UI.statusMeta(statuses, code2);
      const entry = doneSet[code2];
      const isDone = !!entry;
      const isCurrent = order.status === code2;
      const cls = isDone ? (isCurrent ? 'done current' : 'done') : 'pending';
      return `<li class="${cls}">
          <div class="t-name">${meta.emoji} ${UI.esc(meta.title)}</div>
          <div class="t-time">${entry ? UI.dateTime(entry.created_at) : 'ожидается'}</div>
        </li>`;
    }).join('');

    const passed = chain.indexOf(order.status);
    const percent = cancelled ? 100 : Math.round(((passed + 1) / chain.length) * 100);

    return `
      <div class="card">
        <div class="between">
          <div>
            <h2 style="margin:0">Заказ №${UI.esc(order.code)}</h2>
            <div class="small muted">${UI.dateTime(order.created_at)} · ${UI.esc(order.order_type_title)}</div>
          </div>
          ${UI.badge(statuses, order.status)}
        </div>
        <div class="progress-track" style="margin-top:12px">
          <div style="width:${percent}%"></div>
        </div>
      </div>

      <div class="card">
        <h3>Состав</h3>
        <div class="small" style="white-space:pre-line">${UI.esc(order.items_text)}</div>
        <div class="divider"></div>
        <div class="between"><b>Итого</b><span class="price-lg">${UI.money(order.total)}</span></div>
        ${order.address ? `<div class="small muted" style="margin-top:6px">🏠 ${UI.esc(order.address)}</div>` : ''}
        ${order.payment_method === 'yoomoney'
          ? `<div class="row" style="margin-top:10px"><span class="small muted">Оплата:</span>
             ${UI.paymentBadge(order.payment_status)}</div>
             ${order.payment_status === 'pending'
               ? `<button class="btn primary block" style="margin-top:10px"
                   data-go="#/pay/${UI.esc(order.code)}">💜 Оплатить</button>` : ''}`
          : `<div class="small muted" style="margin-top:8px">💵 Оплата при получении</div>`}
      </div>

      <div class="card">
        <h3>История статусов</h3>
        <ul class="timeline">${steps}</ul>
      </div>

      ${order.can_cancel
        ? '<button class="btn danger block" id="cancel-order">❌ Отменить заказ</button>'
        : ''}
      <p class="small muted center" style="margin-top:12px">
        Этот статус виден и в боте, и в приложении — они всегда одинаковые.
      </p>
    `;
  }

  /* ------------------------------------------------------------------ *
   * Экран: Профиль
   * ------------------------------------------------------------------ */
  async function screenProfile() {
    const user = API.state.user || {};
    return `
      <h2>Профиль</h2>
      <div class="card">
        <div class="field">
          <label>Имя</label>
          <input id="p-name" value="${UI.esc(user.name || '')}" placeholder="Ваше имя">
        </div>
        <div class="field">
          <label>Телефон</label>
          <input id="p-phone" value="${UI.esc(user.phone || '')}" placeholder="+7 999 000-00-00">
        </div>
        <div class="small muted">Telegram ID: ${user.telegram_id || '—'}</div>
        <button class="btn primary block" id="save-profile" style="margin-top:12px">Сохранить</button>
      </div>

      <div class="card">
        <h3>Позвать сотрудника</h3>
        <div class="staff-grid">
          <button class="staff-btn" data-staff="help"><span>🆘</span>Нужна помощь</button>
          <button class="staff-btn" data-staff="bill"><span>🧾</span>Попросить счёт</button>
        </div>
      </div>

      ${user.is_admin
        ? '<button class="btn dark block" data-go="#/admin" style="margin-bottom:12px">👨‍🍳 Админ-панель</button>'
        : ''}
      <button class="btn ghost block" data-go="#/about">🎌 О SANUKI</button>
      ${tg ? '' : '<button class="btn ghost block" id="logout" style="margin-top:10px">Выйти (демо)</button>'}
    `;
  }

  /* ------------------------------------------------------------------ *
   * Экран: О SANUKI
   * ------------------------------------------------------------------ */
  async function screenAbout() {
    const catalog = await API.menu();
    const s = catalog.settings || {};
    return `
      <div class="card" style="padding:0;overflow:hidden">
        <img src="/static/img/udon.jpg" alt="SANUKI" class="img-round">
      </div>
      <div class="card">
        <h3>🎌 SANUKI UDON SHOP</h3>
        <p class="small muted">Мы создаём настоящий удон по японским рецептам,
        добавляя футуристичный акцент в каждое блюдо. Традиции,
        переосмысленные через призму современности.</p>
        <div class="info-grid">
          <div class="info-row"><b>Адрес</b><span>${UI.esc(s.address || '')}</span></div>
          <div class="info-row"><b>Время</b><span>${UI.esc(s.work_hours || '')}</span></div>
          <div class="info-row"><b>Телефон</b><span>${UI.esc(s.phone || '')}</span></div>
        </div>
      </div>
      <img src="/static/img/poster.jpg" alt="Меню SANUKI" class="img-round">
    `;
  }

  /* ------------------------------------------------------------------ *
   * Экран: Админ-панель
   * ------------------------------------------------------------------ */
  let adminFilter = 'active';

  async function screenAdmin() {
    const statuses = await API.statuses();
    const [statsData, ordersData, stopData] = await Promise.all([
      API.adminStats(),
      API.adminOrders(adminFilter === 'all' ? {} : { active: true }),
      API.stopList(),
    ]);
    const stats = statsData;
    const orders = ordersData.orders || [];

    const boxes = [
      ['Выручка', UI.money(stats.revenue)],
      ['Заказов', stats.total_orders],
      ['Средний чек', UI.money(stats.avg_total)],
      ['Отменено', stats.cancelled],
    ].map(b => `<div class="stat-box"><div class="v">${b[1]}</div><div class="k">${b[0]}</div></div>`).join('');

    const byStatus = (stats.by_status || [])
      .filter(s => s.count > 0)
      .map(s => `<div class="between small"><span>${s.emoji} ${UI.esc(s.title)}</span><b>${s.count}</b></div>`)
      .join('');

    const pills = ['active', 'all'].map(f =>
      `<button class="chip ${adminFilter === f ? 'active' : ''}" data-admin-filter="${f}">` +
      `${f === 'active' ? 'Активные' : 'Все'}</button>`).join('');

    const list = orders.length ? orders.map(o => {
      const next = (o.next_statuses || []).map(code => {
        const meta = UI.statusMeta(statuses, code);
        const cls = code === 'cancelled' ? 'btn sm danger' : 'btn sm primary';
        return `<button class="${cls}" data-admin-status="${o.id}" data-status="${code}">` +
          `${meta.emoji} ${UI.esc(meta.title)}</button>`;
      }).join('');
      return `
        <div class="card admin-order status-${UI.esc(o.status)}">
          <div class="between">
            <div>
              <b>№${UI.esc(o.code)}</b> <span class="small muted">· ${UI.esc(o.source)} · ${UI.time(o.created_at)}</span>
              <div class="small muted">${UI.esc(o.guest_name)} · ${UI.esc(o.order_type_title)}</div>
            </div>
            <div class="right">
              ${UI.badge(statuses, o.status)}
              <div class="small" style="margin-top:4px">${UI.money(o.total)}</div>
            </div>
          </div>
          <div class="small muted" style="white-space:pre-line;margin-top:8px">${UI.esc(o.items_text)}</div>
          ${o.address ? `<div class="small muted">🏠 ${UI.esc(o.address)}</div>` : ''}
          <div class="admin-actions">${next}</div>
        </div>`;
    }).join('') : UI.empty('Нет заказов по фильтру', '📭');

    const stopItems = (stopData.items || []).map(i =>
      `<div class="between" style="padding:6px 0;border-bottom:1px solid var(--line)">
         <span>${UI.esc(i.name)} <span class="small muted">${UI.esc(i.reason || '')}</span></span>
         <button class="btn sm ghost" data-stop-del="${UI.esc(i.name)}">Убрать</button>
       </div>`).join('') || '<div class="small muted">Стоп-лист пуст</div>';

    return `
      <h2>Админ-панель</h2>
      <div class="stat-grid">${boxes}</div>

      <div class="card" style="margin-top:12px">
        <h3>Статусы</h3>
        ${byStatus || '<div class="small muted">Пока нет данных</div>'}
      </div>

      <div class="pill-row" style="margin-top:14px">${pills}</div>
      ${list}

      <div class="card">
        <h3>Стоп-лист</h3>
        ${stopItems}
        <div class="row" style="margin-top:10px">
          <input id="stop-name" placeholder="Позиция" class="grow"
                 style="border:1.5px solid var(--line-strong);border-radius:14px;padding:10px 12px">
          <button class="btn sm dark" id="stop-add">Добавить</button>
        </div>
      </div>
      <p class="small muted center">Статусы здесь и в боте — одни и те же, меняются синхронно.</p>
    `;
  }

  /* ------------------------------------------------------------------ *
   * Обработчики событий (делегирование)
   * ------------------------------------------------------------------ */
  document.addEventListener('click', async (e) => {
    const t = e.target.closest('button, [data-go], .card[data-go]');
    if (!t) return;

    if (t.dataset.go) { location.hash = t.dataset.go; return; }

    if (t.dataset.cat) { menuCategory = t.dataset.cat; return route(); }

    if (t.dataset.add) {
      const item = findMenuItem(t.dataset.add);
      if (item) {
        API.cartAdd({ kind: 'item', name: item.name, title: item.name, price: item.price });
        UI.haptic('light');
        UI.toast(item.name + ' — в корзине');
        route();
      }
      return;
    }

    if (t.dataset.qtyMinus !== undefined) {
      const i = +t.dataset.qtyMinus;
      const item = API.state.cart[i];
      if (item) API.cartSetQty(i, (item.qty || 1) - 1);
      return route();
    }
    if (t.dataset.qtyPlus !== undefined) {
      const i = +t.dataset.qtyPlus;
      const item = API.state.cart[i];
      if (item) API.cartSetQty(i, (item.qty || 1) + 1);
      return route();
    }
    if (t.dataset.qtyDel !== undefined) {
      API.cartRemove(+t.dataset.qtyDel);
      return route();
    }
    if (t.dataset.clearCart) { API.cartClear(); return route(); }

    /* --- конструктор --- */
    const d = draft();
    if (t.dataset.preset) {
      const p = JSON.parse(t.dataset.preset);
      API.state.draft = { step: 3, base: p.base, protein: p.protein, topping: null, extras: [] };
      UI.haptic('medium');
      return (location.hash = '#/constructor');
    }
    if (t.dataset.base) { d.base = t.dataset.base; d.step = 2; return route(); }
    if (t.dataset.protein) { d.protein = t.dataset.protein; d.step = 3; return route(); }
    if (t.dataset.topping) { d.topping = t.dataset.topping; d.step = 4; return route(); }
    if (t.dataset.toppingSkip) { d.topping = 'Без топпинга'; d.step = 4; return route(); }
    if (t.dataset.extra) {
      const i = d.extras.indexOf(t.dataset.extra);
      if (i >= 0) d.extras.splice(i, 1); else d.extras.push(t.dataset.extra);
      return route();
    }
    if (t.dataset.stepBack) { d.step = Math.max(1, d.step - 1); return route(); }
    if (t.dataset.stepNext) { d.step = Math.min(4, d.step + 1); return route(); }
    if (t.dataset.addUdon) {
      const catalog = await API.menu();
      const extrasCat = (catalog.categories || []).find(c => c.name === 'Дополнительные топпинги');
      const extrasList = (extrasCat && extrasCat.items) || [];
      const protein = (catalog.udon.proteins || []).find(p => p.name === d.protein) || { price: 0 };
      const extras = d.extras.map(name => {
        const info = extrasList.find(x => x.name === name) || { price: 0 };
        return { name, price: info.price };
      });
      const price = protein.price + extras.reduce((s, e) => s + e.price, 0);
      API.cartAdd({
        kind: 'udon',
        base: d.base, protein: d.protein, topping: d.topping || 'Без топпинга',
        extras, price, title: 'Удон «' + d.base + '» с ' + d.protein,
      });
      API.state.draft = null;
      UI.haptic('success');
      UI.toast('Удон добавлен в корзину');
      location.hash = '#/cart';
      return;
    }

    /* --- оформление --- */
    if (t.dataset.orderType) {
      syncCheckoutInputs();
      checkoutForm.order_type = t.dataset.orderType;
      return route();
    }
    if (t.dataset.payMethod) {
      syncCheckoutInputs();
      checkoutForm.payment_method = t.dataset.payMethod;
      return route();
    }

    if (t.id === 'submit-order') return submitOrder();
    if (t.id === 'pay-stub') {
      const code = decodeURIComponent(location.hash.split('/')[2] || '');
      await API.confirmStub(code);
      UI.toast('Оплата подтверждена (заглушка)');
      return route();
    }
    if (t.id === 'cancel-order') {
      const code = decodeURIComponent(currentRoute().split('/')[2] || '');
      if (!confirm('Отменить заказ?')) return;
      await API.cancelOrder(code);
      UI.toast('Заказ отменён');
      return route();
    }
    if (t.id === 'save-profile') return saveProfile();
    if (t.id === 'logout') { API.clearAuth(); return location.reload(); }

    if (t.dataset.staff) {
      await API.staffCall({ kind: t.dataset.staff });
      UI.haptic('success');
      UI.toast('Сотрудник уже в пути!');
      return;
    }

    /* --- админка --- */
    if (t.dataset.adminFilter) { adminFilter = t.dataset.adminFilter; return route(); }
    if (t.dataset.adminStatus) {
      await API.adminStatus(+t.dataset.adminStatus, t.dataset.status);
      UI.haptic('success');
      UI.toast('Статус обновлён');
      return route();
    }
    if (t.id === 'stop-add') {
      const input = document.getElementById('stop-name');
      if (input && input.value.trim()) {
        await API.stopAdd(input.value.trim());
        input.value = '';
        return route();
      }
    }
    if (t.dataset.stopDel) {
      await API.stopRemove(t.dataset.stopDel);
      return route();
    }
  });

  function findMenuItem(name) {
    const catalog = API.state.catalog || {};
    for (const c of (catalog.categories || [])) {
      for (const i of (c.items || [])) if (i.name === name) return i;
    }
    return null;
  }

  function syncCheckoutInputs() {
    const name = (document.getElementById('f-name') || {}).value;
    const phone = (document.getElementById('f-phone') || {}).value;
    const address = (document.getElementById('f-address') || {}).value;
    const comment = (document.getElementById('f-comment') || {}).value;
    if (name !== undefined) checkoutForm.name = name.trim();
    if (phone !== undefined) checkoutForm.phone = phone.trim();
    if (address !== undefined) checkoutForm.address = address.trim();
    if (comment !== undefined) checkoutForm.comment = comment.trim();
  }

  async function submitOrder() {
    const name = (document.getElementById('f-name') || {}).value || '';
    const phone = (document.getElementById('f-phone') || {}).value || '';
    const addressEl = document.getElementById('f-address');
    const commentEl = document.getElementById('f-comment');
    checkoutForm.name = name.trim();
    checkoutForm.phone = phone.trim();
    if (addressEl) checkoutForm.address = addressEl.value.trim();
    if (commentEl) checkoutForm.comment = commentEl.value.trim();

    if (!checkoutForm.name) { UI.toast('Укажите имя'); return; }
    if (checkoutForm.order_type === 'delivery' && !checkoutForm.address) {
      UI.toast('Укажите адрес доставки'); return;
    }

    try {
      const res = await API.createOrder({
        items: API.state.cart.map(i => ({
          kind: i.kind, name: i.name, base: i.base, protein: i.protein,
          topping: i.topping, extras: i.extras, qty: i.qty,
        })),
        order_type: checkoutForm.order_type,
        guest_name: checkoutForm.name,
        phone: checkoutForm.phone,
        address: checkoutForm.address,
        comment: checkoutForm.comment,
        payment_method: checkoutForm.payment_method,
      });
      API.cartClear();
      checkoutForm = {
        order_type: 'dine_in', name: checkoutForm.name, phone: checkoutForm.phone,
        address: '', comment: '', payment_method: 'cash',
      };
      UI.haptic('success');
      const order = res.order;
      if (res.payment && res.payment.payment_url && order.payment_method === 'yoomoney') {
        location.hash = '#/pay/' + order.code;
      } else {
        location.hash = '#/order/' + order.code;
      }
    } catch (err) {
      UI.toast(err.message || 'Не удалось оформить заказ');
    }
  }

  async function saveProfile() {
    const name = (document.getElementById('p-name') || {}).value || '';
    const phone = (document.getElementById('p-phone') || {}).value || '';
    const user = await API.saveProfile({ name: name.trim(), phone: phone.trim() });
    API.state.user = Object.assign({}, API.state.user, user);
    UI.toast('Профиль сохранён');
  }

  /* ------------------------------------------------------------------ *
   * Запуск
   * ------------------------------------------------------------------ */
  async function boot() {
    initTelegram();
    document.getElementById('login-screen').classList.remove('hidden');

    const hint = document.getElementById('login-hint');

    if (tg && tg.initData) {
      try {
        const session = await API.loginTelegram(tg.initData);
        API.setToken(session.token, session);
        return start();
      } catch (err) {
        hint.textContent = 'Не удалось подтвердить данные Telegram: ' + err.message;
      }
    }

    // Telegram недоступен — пробуем демо-вход (только при DEV_LOGIN=1)
    try {
      const probe = await API.get('/api/health');
      if (!probe.debug) {
        hint.textContent = 'Откройте приложение внутри Telegram — ' +
          'кнопка «Открыть SANUKI» в меню бота.';
        return;
      }
    } catch (e) { /* ignore */ }

    hint.textContent = 'Telegram не найден — демо-режим';
    document.getElementById('login-dev').classList.remove('hidden');
    document.getElementById('dev-login').onclick = async () => {
      const id = parseInt((document.getElementById('dev-id').value || '0'), 10);
      try {
        const s = await API.loginDev(id, 'Гость SANUKI');
        API.setToken(s.token, s);
        start();
      } catch (err) {
        const el = document.getElementById('dev-error');
        el.textContent = err.message;
        el.classList.remove('hidden');
      }
    };
    document.getElementById('dev-guest').onclick = async () => {
      const id = 700000000 + Math.floor(Math.random() * 200000000);
      try {
        const s = await API.loginDev(id, 'Гость ' + id.toString().slice(-4));
        API.setToken(s.token, s);
        start();
      } catch (err) {
        const el = document.getElementById('dev-error');
        el.textContent = err.message;
        el.classList.remove('hidden');
      }
    };
  }

  async function start() {
    if (booted) return;
    booted = true;
    document.getElementById('login-screen').classList.add('hidden');
    header.classList.remove('hidden');
    tabbar.classList.remove('hidden');
    try {
      API.state.user = await API.me();
      await API.menu();
      await API.statuses();
    } catch (e) {
      console.warn(e);
    }
    window.addEventListener('hashchange', route);
    document.addEventListener('cart:changed', updateCartDot);
    if (!location.hash) location.hash = '#/';
    route();
  }

  document.addEventListener('auth:expired', () => location.reload());

  boot();
})();
