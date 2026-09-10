/* SANUKI — слой общения с API */
(function (global) {
  'use strict';

  const TOKEN_KEY = 'sanuki.token';
  const CART_KEY = 'sanuki.cart';
  const USER_KEY = 'sanuki.user';

  const state = {
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: null,
    catalog: null,
    statuses: null,
    settings: null,
    cart: readCart(),
    draft: null,          // черновик конструктора удона
    pollers: [],
  };

  function readCart() {
    try {
      const raw = JSON.parse(localStorage.getItem(CART_KEY) || '[]');
      return Array.isArray(raw) ? raw : [];
    } catch (e) {
      return [];
    }
  }

  function saveCart() {
    localStorage.setItem(CART_KEY, JSON.stringify(state.cart));
    document.dispatchEvent(new CustomEvent('cart:changed'));
  }

  function setToken(token, user) {
    state.token = token || '';
    if (token) localStorage.setItem(TOKEN_KEY, token);
    if (user) {
      state.user = user;
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
  }

  function clearAuth() {
    state.token = '';
    state.user = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  async function request(path, options) {
    const opts = Object.assign({ method: 'GET' }, options || {});
    const headers = Object.assign({}, opts.headers || {});
    if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
    if (opts.body && !(opts.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, Object.assign({}, opts, { headers }));
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : {}; } catch (e) { data = { detail: text }; }

    if (res.status === 401) {
      clearAuth();
      document.dispatchEvent(new CustomEvent('auth:expired'));
      throw new Error('Требуется авторизация');
    }
    if (!res.ok) {
      const msg = (data && (data.detail || data.message)) || ('Ошибка ' + res.status);
      throw new Error(Array.isArray(msg) ? msg.map(m => m.msg || m).join(', ') : msg);
    }
    return data;
  }

  const api = {
    state, setToken, clearAuth, saveCart,

    get: (p) => request(p),
    post: (p, body) => request(p, { method: 'POST', body: body || {} }),
    del: (p) => request(p, { method: 'DELETE' }),

    /* --- авторизация --- */
    loginTelegram(initData) { return api.post('/api/auth/telegram', { init_data: initData }); },
    loginDev(telegramId, name) {
      return api.post('/api/auth/dev', { telegram_id: telegramId, name: name });
    },
    me() { return api.get('/api/me'); },
    saveProfile(payload) { return api.post('/api/me', payload); },

    /* --- данные --- */
    async menu(force) {
      if (!state.catalog || force) state.catalog = await api.get('/api/menu');
      return state.catalog;
    },
    async statuses() {
      if (!state.statuses) state.statuses = await api.get('/api/statuses');
      return state.statuses;
    },
    settings() { return api.get('/api/settings'); },
    paymentMethods() { return api.get('/api/payment-methods'); },

    /* --- заказы --- */
    createOrder(payload) { return api.post('/api/orders', payload); },
    orders() { return api.get('/api/orders'); },
    order(key) { return api.get('/api/orders/' + encodeURIComponent(key)); },
    cancelOrder(key) { return api.post('/api/orders/' + encodeURIComponent(key) + '/cancel'); },
    payOrder(key) { return api.post('/api/orders/' + encodeURIComponent(key) + '/pay'); },
    confirmStub(code) { return api.post('/api/payments/stub/' + encodeURIComponent(code)); },
    staffCall(payload) { return api.post('/api/staff-call', payload); },

    /* --- админка --- */
    adminOrders(params) {
      const q = new URLSearchParams(params || {}).toString();
      return api.get('/api/admin/orders' + (q ? '?' + q : ''));
    },
    adminStatus(id, status) {
      return api.post('/api/admin/orders/' + id + '/status', { status });
    },
    adminStats() { return api.get('/api/admin/stats'); },
    stopList() { return api.get('/api/admin/stop-list'); },
    stopAdd(name, reason) { return api.post('/api/admin/stop-list', { name, reason }); },
    stopRemove(name) { return api.del('/api/admin/stop-list/' + encodeURIComponent(name)); },

    /* --- корзина --- */
    cartAdd(item) {
      const key = cartKey(item);
      const found = state.cart.find(i => cartKey(i) === key);
      if (found) found.qty = (found.qty || 1) + 1;
      else state.cart.push(Object.assign({ qty: 1 }, item));
      saveCart();
    },
    cartSetQty(index, qty) {
      if (!state.cart[index]) return;
      if (qty <= 0) state.cart.splice(index, 1);
      else state.cart[index].qty = qty;
      saveCart();
    },
    cartRemove(index) { state.cart.splice(index, 1); saveCart(); },
    cartClear() { state.cart = []; saveCart(); },
    cartTotal() {
      return state.cart.reduce((s, i) => s + (i.price || 0) * (i.qty || 1), 0);
    },
    cartCount() {
      return state.cart.reduce((s, i) => s + (i.qty || 1), 0);
    },
  };

  function cartKey(item) {
    if (item.kind === 'udon') {
      return 'udon|' + item.base + '|' + item.protein + '|' + item.topping + '|' +
        (item.extras || []).map(e => e.name).sort().join('+');
    }
    return 'item|' + (item.name || item.title);
  }

  global.API = api;
})(window);
