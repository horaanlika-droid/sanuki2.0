/* ============================================================
   SANUKI WEB — SPA. Механика 1-в-1 с ботом:
   конструктор удона (основа → белок → топпинг → допы),
   корзина, заказы с живыми статусами (SSE), админка.
   ============================================================ */

"use strict";

// ---------- Утилиты ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtPrice = (n) => `${Number(n || 0).toLocaleString("ru-RU")} ₽`;
const fmtDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso.includes("T") ? iso : iso.replace(" ", "T"));
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit" }) +
    " · " + d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
};

function toast(msg, ms = 2200) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._tm);
  t._tm = setTimeout(() => t.classList.remove("show"), ms);
}

// ---------- Картинки (вырезаны из брендового постера) ----------
const IMG = {
  broth: {
    "Говяжий бульон": "assets/img/broth_beef.png",
    "Цую бульон": "assets/img/broth_tsuyu.png",
    "Соус карри": "assets/img/broth_curry.png",
    "Сырный соус": "assets/img/broth_cheese.png",
  },
  protein: {
    "криспи курица": "assets/img/prot_chicken.png",
    "креветки темпура": "assets/img/prot_shrimp.png",
    "томлёная говядина": "assets/img/prot_beef.png",
    "хрустящий бекон": "assets/img/prot_chicken.png",
    "томлёная курица": "assets/img/prot_chicken.png",
  },
  item: {
    "Картошка фри": "assets/img/item_fries.png",
    "Бекон криспи": "assets/img/item_fries.png",
    "Креветка темпура": "assets/img/item_shrimp.png",
    "Креветки темпура": "assets/img/item_shrimp.png",
    "Овощи темпура": "assets/img/item_shrimp.png",
    "Курица криспи": "assets/img/prot_chicken.png",
    "Тофу темпура": "assets/img/prot_tofu.png",
    "Крабовая палка": "assets/img/item_chuka.png",
    "Вешенка темпура": "assets/img/item_edamame.png",
    "Капуста кимчи by Яна": "assets/img/item_edamame.png",
    "Битые огурцы": "assets/img/item_edamame.png",
    "Морковь by Ольга": "assets/img/item_chuka.png",
    "Гёдза с курицей": "assets/img/item_gyoza.png",
    "Эдамамэ": "assets/img/item_edamame.png",
    "Такояки": "assets/img/item_tako.png",
    "Чука-салат": "assets/img/item_chuka.png",
    "Лимонад в ассортименте": "assets/img/item_lemonade.png",
    "Лимонад Козу": "assets/img/item_lemonade.png",
  },
};
const fallbackImg = "assets/img/item_udon_bowl.png";
const imgFor = (kind, name) => (IMG[kind] && IMG[kind][name]) || fallbackImg;

// ---------- Состояние ----------
const State = {
  menu: null,
  settings: {},
  cart: JSON.parse(localStorage.getItem("sanuki.cart") || "[]"),
  udon: JSON.parse(localStorage.getItem("sanuki.udon") || '{"base":null,"protein":null,"topping":null,"extras":[]}'),
  orderType: localStorage.getItem("sanuki.orderType") || "С собой 🥡",
  payMethod: localStorage.getItem("sanuki.payMethod") || "cash",
  profile: JSON.parse(localStorage.getItem("sanuki.profile") || '{"name":"","phone":""}'),
  tgId: null,
  myOrders: JSON.parse(localStorage.getItem("sanuki.myOrders") || "[]"),
  lastOrder: null,
  adminId: localStorage.getItem("sanuki.admin") || "",
  adminTab: "active",
};

const saveState = () => {
  localStorage.setItem("sanuki.cart", JSON.stringify(State.cart));
  localStorage.setItem("sanuki.udon", JSON.stringify(State.udon));
  localStorage.setItem("sanuki.orderType", State.orderType);
  localStorage.setItem("sanuki.payMethod", State.payMethod);
  localStorage.setItem("sanuki.profile", JSON.stringify(State.profile));
  localStorage.setItem("sanuki.myOrders", JSON.stringify(State.myOrders));
};

// ---------- API ----------
async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (State.adminId) headers["X-Admin-Id"] = State.adminId;
  const res = await fetch(path, { ...opts, headers });
  if (!res.ok) {
    let msg = `Ошибка ${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

// ---------- Telegram Mini App ----------
function initTelegram() {
  try {
    const tg = window.Telegram && window.Telegram.WebApp;
    if (!tg) return;
    tg.ready();
    tg.expand();
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
      State.tgId = tg.initDataUnsafe.user.id;
      if (tg.initDataUnsafe.user.first_name && !State.profile.name) {
        State.profile.name = tg.initDataUnsafe.user.first_name;
        saveState();
      }
    }
    if (tg.setHeaderColor) tg.setHeaderColor("#fdf7ec");
  } catch (_) {}
}

// ---------- Загрузка данных ----------
async function loadMenu() {
  const [menu, settings] = await Promise.all([api("/api/menu"), api("/api/settings")]);
  State.menu = menu;
  State.settings = settings;
}

// ============================================================
// Роутер
// ============================================================
const VIEWS = ["home", "menu", "udon", "cart", "success", "orders", "order", "profile", "about", "admin"];
let currentView = "home";

function go(view, param) {
  if (!VIEWS.includes(view)) view = "home";
  currentView = view;
  $$(".view").forEach((v) => v.classList.remove("active"));
  const el = $(`#view-${view}`);
  if (el) el.classList.add("active");
  $$(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.view === view || (view === "udon" && n.dataset.view === "menu")));
  render(view, param);
  window.scrollTo({ top: 0 });
  document.body.classList.toggle("admin", view === "admin");
  hideDockbar();
}

function render(view, param) {
  switch (view) {
    case "home": renderHome(); break;
    case "menu": renderMenu(); break;
    case "udon": renderUdon(); break;
    case "cart": renderCart(); break;
    case "success": renderSuccess(param); break;
    case "orders": renderOrders(); break;
    case "order": renderOrderDetail(param); break;
    case "profile": renderProfile(); break;
    case "about": renderAbout(); break;
    case "admin": renderAdmin(); break;
  }
}

// ============================================================
// Главная
// ============================================================
function renderHome() {
  const el = $("#view-home");
  el.innerHTML = `
    <div class="hero">
      <img class="team" src="assets/img/team.png" alt="Команда SANUKI">
      <h1>Собери свой<br>идеальный удон</h1>
      <p>Свежий, горячий и такой,<br>каким любишь именно ты</p>
      <div style="margin-top:14px">
        <button class="btn block" data-go="udon">🍜 Собрать удон</button>
      </div>
      <img class="hero-bowl" src="assets/img/bowl_hero.png" alt="Удон SANUKI">
      <div class="promo">🎉 Первый заказ — десерт бесплатно!</div>
      <div class="features">
        <div class="feature"><span>🥬</span>Свежие ингредиенты</div>
        <div class="feature"><span>⏱</span>15–20 минут</div>
        <div class="feature"><span>🎛</span>Выбираешь сам</div>
      </div>
    </div>

    <div class="section-title">
      <h2>Популярные удоны</h2>
      <a data-go="menu">Все</a>
    </div>
    <div class="grid2">
      <div class="dish">
        <img src="assets/img/udon_tori.png" alt="Тори Удон">
        <div class="body">
          <div class="name">Тори Удон</div>
          <div class="price">480 ₽</div>
          <div class="row">
            <span style="font-size:11px;color:var(--muted);font-weight:700">курица криспи</span>
            <button class="add-btn" data-popular="Тори Удон|480|криспи курица|Говяжий бульон">+</button>
          </div>
        </div>
      </div>
      <div class="dish">
        <img src="assets/img/udon_curry.png" alt="Карри Удон">
        <div class="body">
          <div class="name">Карри Удон</div>
          <div class="price">520 ₽</div>
          <div class="row">
            <span style="font-size:11px;color:var(--muted);font-weight:700">соус карри</span>
            <button class="add-btn" data-popular="Карри Удон|520|криспи курица|Соус карри">+</button>
          </div>
        </div>
      </div>
    </div>

    <div class="section-title"><h2>Закуски</h2><a data-go="menu">Все</a></div>
    <div class="grid2">
      ${[["Гёдза с курицей", 190], ["Креветка темпура", 240]].map(([n, p]) => `
        <div class="dish">
          <img src="${imgFor("item", n)}" alt="${esc(n)}">
          <div class="body">
            <div class="name">${esc(n)}</div>
            <div class="price">${fmtPrice(p)}</div>
            <div class="row"><span></span><button class="add-btn" data-add="${esc(n)}|${p}">+</button></div>
          </div>
        </div>`).join("")}
    </div>
  `;
}

// ============================================================
// Меню
// ============================================================
let menuTab = "udon";
function renderMenu() {
  const el = $("#view-menu");
  const cats = [
    { id: "udon", title: "Удон" },
    ...(State.menu?.categories || []).map((c) => ({ id: c.id, title: c.title })),
  ];
  el.innerHTML = `
    <div class="tabs">${cats.map((c) => `<button class="tab ${menuTab === c.id ? "active" : ""}" data-tab="${c.id}">${esc(c.title)}</button>`).join("")}</div>
    <div id="menu-body"></div>
  `;
  renderMenuBody();
  $$("[data-tab]", el).forEach((b) => b.addEventListener("click", () => { menuTab = b.dataset.tab; renderMenu(); }));
}

function renderMenuBody() {
  const body = $("#menu-body");
  if (menuTab === "udon") {
    body.innerHTML = `
      <button class="btn block" data-go="udon" style="margin-bottom:14px">🛠 Собрать свой удон</button>
      <div class="grid2">
        ${[["Тори Удон", 480], ["Карри Удон", 520]].map(([n, p]) => `
          <div class="dish">
            <img src="${n === "Тори Удон" ? "assets/img/udon_tori.png" : "assets/img/udon_curry.png"}">
            <div class="body">
              <div class="name">${n}</div>
              <div class="price">${fmtPrice(p)}</div>
              <div class="row"><span></span><button class="add-btn" data-popular="${n}|${p}|криспи курица|Говяжий бульон">+</button></div>
            </div>
          </div>`).join("")}
      </div>`;
  } else {
    const cat = (State.menu?.categories || []).find((c) => c.id === menuTab);
    body.innerHTML = `<div class="grid2">${(cat?.items || []).map((it) => `
      <div class="dish">
        <img src="${imgFor("item", it.name)}" alt="${esc(it.name)}">
        <div class="body">
          <div class="name">${esc(it.name)}</div>
          <div class="price">${fmtPrice(it.price)}</div>
          <div class="row"><span></span><button class="add-btn" data-add="${esc(it.name)}|${it.price}">+</button></div>
        </div>
      </div>`).join("")}</div>`;
  }
}

// ---------- Добавление в корзину ----------
function addToCart(title, price, kind = "item", extra = {}) {
  const found = State.cart.find((l) => l.title === title && l.kind === kind);
  if (found) found.qty += 1;
  else State.cart.push({ kind, title, price, qty: 1, ...extra });
  saveState();
  updateBadges();
  toast(`✅ ${title} — в корзине!`);
}

function popularToCart(spec) {
  const [title, price, protein, base] = spec.split("|");
  State.cart.push({
    kind: "udon", title: `Удон: ${base} + ${protein}`, base, protein,
    topping: null, extras: [], price: Number(price), qty: 1,
  });
  saveState();
  updateBadges();
  toast(`✅ ${title} — в корзине!`);
}

// ============================================================
// Конструктор удона
// ============================================================
const STEP_LABELS = ["Основа", "Белок", "Топпинг", "Допы"];
let udonStep = 0;

function renderUdon() {
  const el = $("#view-udon");
  const u = State.udon;
  const stepsHtml = `
    <div class="steps">
      ${STEP_LABELS.map((label, i) => `
        <div class="step ${i < udonStep ? "done" : i === udonStep ? "current" : ""}">
          <div class="dot">${i < udonStep ? "✓" : i + 1}</div>${label}
        </div>`).join("")}
    </div>`;

  let bodyHtml = "";
  let sum = (State.menu?.udon?.proteins.find((p) => p.name === u.protein)?.price || 0)
          + (State.udon.extras || []).reduce((s, e) => s + (e.price || 0), 0);

  if (udonStep === 0) {
    bodyHtml = `
      <h2 style="font-size:19px;font-weight:900">Выберите бульон</h2>
      <p style="color:var(--muted);font-weight:700;font-size:13px;margin:4px 0 14px">Выбор бульона — первый шаг к твоему идеальному удону</p>
      ${(State.menu?.udon?.bases || []).map((b) => `
        <div class="opt ${u.base === b.name ? "selected" : ""}" data-base="${esc(b.name)}">
          <img src="${IMG.broth[b.name] || fallbackImg}">
          <div class="info">
            <div class="name">${esc(b.name)}</div>
            <div class="sub">${esc(b.description || "")}</div>
          </div>
          <div class="check">✓</div>
        </div>`).join("")}`;
  } else if (udonStep === 1) {
    bodyHtml = `
      <h2 style="font-size:19px;font-weight:900">Выберите белок</h2>
      <p style="color:var(--muted);font-weight:700;font-size:13px;margin:4px 0 14px">Можно выбрать только один вариант</p>
      ${(State.menu?.udon?.proteins || []).map((p) => `
        <div class="opt ${u.protein === p.name ? "selected" : ""}" data-protein="${esc(p.name)}">
          <img src="${IMG.protein[p.name] || fallbackImg}">
          <div class="info">
            <div class="name">${esc(p.name)}</div>
            <div class="price">+ ${fmtPrice(p.price)}</div>
          </div>
          <div class="check">✓</div>
        </div>`).join("")}`;
  } else if (udonStep === 2) {
    bodyHtml = `
      <h2 style="font-size:19px;font-weight:900">Выберите топпинг</h2>
      <p style="color:var(--muted);font-weight:700;font-size:13px;margin:4px 0 14px">Бесплатно — входит в стоимость</p>
      ${(State.menu?.udon?.toppings || []).map((t) => `
        <div class="opt ${u.topping === t.name ? "selected" : ""}" data-topping="${esc(t.name)}">
          <img src="${imgFor("item", t.name)}">
          <div class="info"><div class="name">${esc(t.name)}</div><div class="price" style="color:var(--green)">+ 0 ₽</div></div>
          <div class="check">✓</div>
        </div>`).join("")}
      <div class="opt ${!u.topping ? "selected" : ""}" data-topping="">
        <img src="${fallbackImg}">
        <div class="info"><div class="name">Без топпинга</div></div>
        <div class="check">✓</div>
      </div>`;
  } else {
    const extras = State.menu?.extras || [];
    bodyHtml = `
      <h2 style="font-size:19px;font-weight:900">Дополнительные топпинги</h2>
      <p style="color:var(--muted);font-weight:700;font-size:13px;margin:4px 0 14px">Выбери любые варианты</p>
      ${extras.map((e) => {
        const on = (u.extras || []).some((x) => x.name === e.name);
        return `
        <div class="checkrow ${on ? "on" : ""}" data-extra="${esc(e.name)}|${e.price}">
          <div class="box">✓</div>
          <img src="${imgFor("item", e.name)}" style="width:44px;height:44px;border-radius:10px;object-fit:cover">
          <div class="info"><div class="name">${esc(e.name)}</div></div>
          <div class="price">+ ${fmtPrice(e.price)}</div>
        </div>`;
      }).join("")}`;
  }

  el.innerHTML = stepsHtml + bodyHtml;

  // Нижняя панель: Итого + Далее
  const dock = $("#dockbar");
  dock.innerHTML = `
    <div class="inner">
      <div class="sum">Итого<b>${fmtPrice(sum)}</b></div>
      ${udonStep > 0 ? `<button class="btn ghost" id="udon-back" style="padding:14px 16px">←</button>` : ""}
      <button class="btn" id="udon-next" ${udonStep === 0 && !u.base ? "disabled" : udonStep === 1 && !u.protein ? "disabled" : ""}>
        ${udonStep === 3 ? "Готово" : "Далее"}
      </button>
    </div>`;
  dock.style.display = "block";

  $("#udon-next").addEventListener("click", () => {
    if (udonStep === 3) {
      finalizeUdon();
      return;
    }
    udonStep += 1;
    renderUdon();
    window.scrollTo({ top: 0 });
  });
  const back = $("#udon-back");
  if (back) back.addEventListener("click", () => { udonStep = Math.max(0, udonStep - 1); renderUdon(); });

  // Выборы
  $$("[data-base]", el).forEach((o) => o.addEventListener("click", () => {
    u.base = o.dataset.base; u.protein = null; saveState(); udonStep = 1; renderUdon();
  }));
  $$("[data-protein]", el).forEach((o) => o.addEventListener("click", () => {
    u.protein = o.dataset.protein; saveState(); udonStep = 2; renderUdon();
  }));
  $$("[data-topping]", el).forEach((o) => o.addEventListener("click", () => {
    u.topping = o.dataset.topping || null; saveState(); udonStep = 3; renderUdon();
  }));
  $$("[data-extra]", el).forEach((o) => o.addEventListener("click", () => {
    const [name, price] = o.dataset.extra.split("|");
    u.extras = u.extras || [];
    const has = u.extras.some((x) => x.name === name);
    u.extras = has ? u.extras.filter((x) => x.name !== name) : [...u.extras, { name, price: Number(price) }];
    saveState(); renderUdon();
  }));
}

function finalizeUdon() {
  const u = State.udon;
  const protein = (State.menu?.udon?.proteins || []).find((p) => p.name === u.protein);
  const extraSum = (u.extras || []).reduce((s, e) => s + e.price, 0);
  State.cart.push({
    kind: "udon",
    title: `Удон: ${u.base} + ${u.protein}`,
    base: u.base, protein: u.protein, topping: u.topping,
    extras: (u.extras || []).map((e) => e.name),
    price: (protein?.price || 0) + extraSum,
    qty: 1,
  });
  State.udon = { base: null, protein: null, topping: null, extras: [] };
  udonStep = 0;
  saveState();
  updateBadges();
  toast("🍜 Удон собран! Он в корзине");
  go("cart");
}

// ============================================================
// Корзина
// ============================================================
function cartTotal() {
  return State.cart.reduce((s, l) => s + l.price * l.qty, 0);
}

function renderCart() {
  const el = $("#view-cart");
  if (!State.cart.length) {
    el.innerHTML = `
      <div style="text-align:center;padding:50px 10px;color:var(--muted);font-weight:800">
        <div style="font-size:44px;margin-bottom:10px">🛒</div>
        Корзина пуста<br><span style="font-size:13px">Добавь что-нибудь вкусное!</span>
        <div style="margin-top:18px"><button class="btn" data-go="menu">Открыть меню</button></div>
      </div>`;
    return;
  }

  el.innerHTML = `
    <h2 style="font-size:20px;font-weight:900;margin-bottom:12px">Ваш заказ</h2>
    ${State.cart.map((l, i) => `
      <div class="cart-line">
        <img src="${l.kind === "udon" ? fallbackImg : imgFor("item", l.title)}">
        <div class="info">
          <div class="name">${esc(l.kind === "udon" ? "Удон (конструктор)" : l.title)}</div>
          ${l.kind === "udon" ? `<div class="desc">${esc(l.base)}. ${esc(l.protein)}. ${l.topping ? esc(l.topping) + "." : ""} ${l.extras?.length ? esc(l.extras.join(", ")) + "." : ""}</div>` : ""}
          <div class="sum">${fmtPrice(l.price * l.qty)}</div>
        </div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
          <button class="trash" data-del="${i}">🗑</button>
          <div class="stepper">
            <button data-dec="${i}">−</button><b>${l.qty}</b><button data-inc="${i}">+</button>
          </div>
        </div>
      </div>`).join("")}

    <div class="section-title"><h2>Итого</h2><span style="font-weight:900;font-size:19px">${fmtPrice(cartTotal())}</span></div>

    <div style="font-size:12.5px;font-weight:800;color:var(--muted);margin:2px 4px 8px">Формат заказа</div>
    <div class="formats">
      ${[["В зале 🍽", "В зале", "🍽"], ["С собой 🥡", "С собой", "🥡"], ["Доставка 🛵", "Доставка", "🛵"]].map(([label, short, ico]) => `
        <button class="format ${State.orderType === label ? "active" : ""}" data-otype="${esc(label)}">
          ${short}<br><span style="font-size:16px">${ico}</span>
        </button>`).join("")}
    </div>

    <div class="section-title"><h2>Контактные данные</h2></div>
    <div class="field"><label>Имя</label><input id="ck-name" placeholder="Как к вам обращаться" value="${esc(State.profile.name)}"></div>
    <div class="field"><label>Телефон</label><input id="ck-phone" placeholder="+7 (900) 000-00-00" value="${esc(State.profile.phone)}"></div>

    <div style="font-size:12.5px;font-weight:800;color:var(--muted);margin:2px 4px 8px">Способ оплаты</div>
    <div class="paymethods">
      <button class="paym ${State.payMethod === "cash" ? "active" : ""}" data-pay="cash">💵 Наличными<small>при получении</small></button>
      <button class="paym ${State.payMethod === "yoomoney" ? "active" : ""}" data-pay="yoomoney">💳 Картой<small>ЮMoney</small></button>
    </div>
    <div class="stub-note">⚠️ Оплата ЮMoney пока работает в тестовом режиме — деньги не списываются.</div>

    <button class="btn block" id="checkout">Оформить заказ · ${fmtPrice(cartTotal())}</button>
    <button class="btn ghost block" data-go="menu" style="margin-top:9px">Продолжить покупки</button>
  `;

  $$("[data-inc]", el).forEach((b) => b.addEventListener("click", () => { State.cart[b.dataset.inc].qty++; saveState(); renderCart(); updateBadges(); }));
  $$("[data-dec]", el).forEach((b) => b.addEventListener("click", () => {
    const line = State.cart[b.dataset.dec];
    line.qty--;
    if (line.qty <= 0) State.cart.splice(b.dataset.dec, 1);
    saveState(); renderCart(); updateBadges();
  }));
  $$("[data-del]", el).forEach((b) => b.addEventListener("click", () => { State.cart.splice(b.dataset.del, 1); saveState(); renderCart(); updateBadges(); }));
  $$("[data-otype]", el).forEach((b) => b.addEventListener("click", () => { State.orderType = b.dataset.otype; saveState(); renderCart(); }));
  $$("[data-pay]", el).forEach((b) => b.addEventListener("click", () => { State.payMethod = b.dataset.pay; saveState(); renderCart(); }));

  $("#checkout").addEventListener("click", checkout);
}

async function checkout() {
  const name = $("#ck-name").value.trim();
  const phone = $("#ck-phone").value.trim();
  if (!name) return toast(" Подскажите имя 😊");
  if (!phone) return toast(" Оставьте телефон, чтобы мы связались");

  State.profile.name = name;
  State.profile.phone = phone;
  saveState();

  const btn = $("#checkout");
  btn.disabled = true;
  btn.textContent = "Отправляем…";
  try {
    const order = await api("/api/orders", {
      method: "POST",
      body: JSON.stringify({
        name, phone,
        order_type: State.orderType,
        pay_method: State.payMethod,
        telegram_id: State.tgId,
        items: State.cart,
      }),
    });
    if (State.payMethod === "yoomoney") {
      try { await api(`/api/orders/${order.id}/pay`, { method: "POST", body: "{}" }); } catch (_) {}
    }
    State.cart = [];
    State.myOrders = [order.id, ...State.myOrders].slice(0, 30);
    State.lastOrder = order.id;
    saveState();
    updateBadges();
    go("success", order.id);
  } catch (e) {
    toast("⚠️ " + e.message);
    btn.disabled = false;
    btn.textContent = "Оформить заказ";
  }
}

// ============================================================
// Успех / детали заказа
// ============================================================

function renderSuccess(orderId) {
  const el = $("#view-success");
  el.innerHTML = `<div class="success"><div class="chef">⏳</div><h2>Загружаем заказ…</h2></div>`;
  if (orderId) refreshOrderView(el, orderId, true);
}

async function refreshOrderView(el, orderId, isSuccessView) {
  try {
    const o = await api(`/api/orders/${orderId}`);
    el.innerHTML = `
      <div class="success">
        <img class="chef" src="assets/img/chef_ok.png" alt="Шеф доволен">
        <h2>Заказ принят!</h2>
        <div class="label">Номер заказа</div>
        <div class="num">#${esc(o.public_id)}</div>
        <div class="status-card">
          <div class="row"><span class="k">Статус</span><span class="v"><span class="dot" style="background:${o.status_color}"></span>${esc(o.status_title)}</span></div>
          <div class="row"><span class="k">Ожидаемое время</span><span class="v">15–20 минут</span></div>
          <div class="row"><span class="k">Оплата</span><span class="v">${o.pay_method === "yoomoney" ? "💳 ЮMoney" + (o.payment_stub ? " (тест)" : "") : "💵 при получении"}</span></div>
          <div class="row"><span class="k">Сумма</span><span class="v">${fmtPrice(o.total)}</span></div>
        </div>
        ${o.payment_stub ? `<div class="stub-note" style="text-align:left">💳 Платёж ЮMoney подтверждён в тестовом режиме (заглушка).</div>` : ""}
        <button class="btn block" data-go="home">На главную</button>
        <button class="btn ghost block" data-go="orders" style="margin-top:9px">Мои заказы</button>
      </div>`;
  } catch (e) {
    el.innerHTML = `<div class="success"><h2>⚠️ ${esc(e.message)}</h2></div>`;
  }
}

function renderOrderDetail(orderId) {
  const el = $("#view-order");
  el.dataset.orderId = orderId;
  el.innerHTML = `<p style="text-align:center;color:var(--muted);font-weight:800;padding:30px">Загрузка…</p>`;
  refreshOrderDetail(el, orderId);
}

async function refreshOrderDetail(el, orderId) {
  try {
    const o = await api(`/api/orders/${orderId}`);
    el.innerHTML = `
      <h2 style="font-size:20px;font-weight:900">#${esc(o.public_id)}
        <span class="chip" style="background:${o.status_color}">${esc(o.status_title)}</span></h2>
      <p style="color:var(--muted);font-weight:700;font-size:12.5px;margin-top:3px">${fmtDate(o.created_at)}</p>
      <div class="status-card" style="margin-top:14px">
        ${o.items.map((it) => `
          <div class="row" style="flex-direction:column;align-items:flex-start;gap:2px">
            <span class="v" style="font-size:13.5px">${it.kind === "udon" ? "🍜 " : "• "}${esc(it.title)} × ${it.qty} — ${fmtPrice(it.price * it.qty)}</span>
            ${it.kind === "udon" ? `<span class="k" style="font-size:11.5px">${esc([it.base, it.protein, it.topping, ...(it.extras || [])].filter(Boolean).join(" · "))}</span>` : ""}
          </div>`).join("")}
        <div class="row"><span class="k">Формат</span><span class="v">${esc(o.type)}</span></div>
        <div class="row"><span class="k">Итого</span><span class="v">${fmtPrice(o.total)}</span></div>
      </div>
      <div class="section-title"><h2>История статусов</h2></div>
      <div class="status-card"><div class="timeline">
        ${(o.history || []).map((h) => `
          <div class="tl-row">
            <span class="mark" style="background:${h.color}"></span>
            <span class="t">${esc(h.status)}</span>
            <span class="at">${fmtDate(h.at)}</span>
          </div>`).join("")}
      </div></div>
      <div class="stub-note">${o.payment_stub ? "💳 Оплачен картой ЮMoney (тестовый режим)" : "💵 Оплата при получении"}</div>
      <button class="btn block" data-go="orders">Мои заказы</button>
    `;
  } catch (e) {
    el.innerHTML = `<p style="color:var(--red);font-weight:800;text-align:center;padding:30px">${esc(e.message)}</p>`;
  }
}

// ============================================================
// Мои заказы
// ============================================================
async function renderOrders() {
  const el = $("#view-orders");
  el.innerHTML = `<p style="text-align:center;color:var(--muted);font-weight:800;padding:30px">Загрузка…</p>`;
  let orders = [];
  try {
    if (State.tgId) {
      orders = await api(`/api/my-orders?telegram_id=${State.tgId}`);
    } else {
      const results = await Promise.all(State.myOrders.map((id) => api(`/api/orders/${id}`).catch(() => null)));
      orders = results.filter(Boolean);
    }
  } catch (e) {
    el.innerHTML = `<p style="color:var(--red);font-weight:800;text-align:center;padding:30px">${esc(e.message)}</p>`;
    return;
  }
  if (!orders.length) {
    el.innerHTML = `
      <div style="text-align:center;padding:50px 10px;color:var(--muted);font-weight:800">
        <div style="font-size:44px;margin-bottom:10px">📋</div>
        Пока здесь пусто…<br><span style="font-size:13px">Сделайте свой первый заказ в SANUKI!</span>
        <div style="margin-top:18px"><button class="btn" data-go="menu">Открыть меню</button></div>
      </div>`;
    return;
  }
  el.innerHTML = `
    <h2 style="font-size:20px;font-weight:900;margin-bottom:12px">Мои заказы</h2>
    ${orders.map((o) => `
      <div class="order-card" data-order="${o.id}">
        <div class="top">
          <div><div class="num">#${esc(o.public_id)}</div><div class="date">${fmtDate(o.created_at)}</div></div>
          <span class="chip" style="background:${o.status_color}">${esc(o.status_title)}</span>
        </div>
        <div class="bot"><span style="color:var(--muted);font-size:12px;font-weight:700">${esc(o.type)}</span><span class="total">${fmtPrice(o.total)}</span></div>
      </div>`).join("")}
    <p style="text-align:center;color:var(--muted);font-size:11.5px;font-weight:700;margin-top:10px">Статусы обновляются автоматически — как в боте 🔄</p>
  `;
  $$("[data-order]", el).forEach((c) => c.addEventListener("click", () => go("order", c.dataset.order)));
}

// ============================================================
// Профиль
// ============================================================
function renderProfile() {
  const el = $("#view-profile");
  const s = State.settings;
  el.innerHTML = `
    <div class="profile-head">
      <div class="avatar">${esc((State.profile.name || "Г")[0].toUpperCase())}</div>
      <div>
        <div class="name">${esc(State.profile.name || "Гость")}</div>
        <div class="phone">${esc(State.profile.phone || "телефон не указан")}</div>
      </div>
    </div>
    ${State.tgId ? `<div class="stub-note" style="margin-top:10px">✅ Открыто через Telegram — заказы также появятся в боте.</div>` : ""}

    <div class="section-title"><h2>Связаться с нами</h2></div>
    <div class="contact-card"><div class="ico">📞</div><div><div class="k">Телефон</div><div class="v"><a href="tel:${esc(s.phone)}">${esc(s.phone)}</a></div></div></div>
    <div class="contact-card"><div class="ico">✈️</div><div><div class="k">Telegram-бот</div><div class="v">заказы и статусы дублируются в бот</div></div></div>
    <div class="contact-card"><div class="ico">📍</div><div><div class="k">Адрес</div><div class="v">${esc(s.address)}</div></div></div>
    <div class="contact-card"><div class="ico">🕒</div><div><div class="k">Часы работы</div><div class="v">${esc(s.work_hours)}</div></div></div>

    <div class="section-title"><h2>Ваши данные</h2></div>
    <div class="field"><label>Имя</label><input id="pf-name" value="${esc(State.profile.name)}" placeholder="Ваше имя"></div>
    <div class="field"><label>Телефон</label><input id="pf-phone" value="${esc(State.profile.phone)}" placeholder="+7 (900) 000-00-00"></div>
    <button class="btn block" id="pf-save">Сохранить</button>
    <p style="text-align:center;color:var(--muted);font-size:11px;font-weight:700;margin-top:12px">SANUKI UDON SHOP · версия 2.0</p>
  `;
  $("#pf-save").addEventListener("click", () => {
    State.profile.name = $("#pf-name").value.trim();
    State.profile.phone = $("#pf-phone").value.trim();
    saveState();
    toast("✅ Сохранено!");
    renderProfile();
  });
}

// ============================================================
// О SANUKI
// ============================================================
function renderAbout() {
  const el = $("#view-about");
  el.innerHTML = `
    <img class="about-art" src="assets/img/art_team.jpg" alt="Команда SANUKI">
    <div class="about-text">
      <b>SANUKI UDON SHOP</b> — футуристичный вкус Японии в сердце Петербурга.<br><br>
      Мы готовим удон в стиле сётя-аниме: свежие ингредиенты, хрустящие темпуры
      и бульоны, которые варятся с утра. Собери свой идеальный удон —
      основа, белок, топпинг и допы выбираешь ты сам.<br><br>
      📍 ${esc(State.settings.address)}<br>
      🕒 ${esc(State.settings.work_hours)}<br>
      📞 ${esc(State.settings.phone)}
    </div>
    <img class="about-art" src="assets/img/art_battle.jpg" alt="Битва ингредиентов" style="margin-top:14px">
    <button class="btn block" data-go="udon" style="margin-top:14px">🍜 Собрать удон</button>
  `;
}

// ============================================================
// АДМИНКА (тёмная тема)
// ============================================================
let adminCache = [];

async function renderAdmin() {
  const el = $("#view-admin");
  if (!State.adminId) {
    el.innerHTML = `
      <div class="login">
        <div style="font-size:36px">🔐</div>
        <h3 style="margin-top:8px">Админ-панель</h3>
        <input id="adm-id" type="password" inputmode="numeric" placeholder="Ваш Telegram ID">
        <button class="btn block" id="adm-enter">Войти</button>
        <div class="hint">ID администратора задаётся в переменной ADMIN_ID на сервере</div>
      </div>`;
    $("#adm-enter").addEventListener("click", () => {
      State.adminId = $("#adm-id").value.replace(/\D/g, "");
      localStorage.setItem("sanuki.admin", State.adminId);
      renderAdmin();
    });
    return;
  }

  el.innerHTML = `
    <div class="section-title" style="margin-top:2px">
      <h2 style="color:#fff">Заказы</h2>
      <a id="adm-logout" style="color:#8b93a1">Выйти</a>
    </div>
    <div class="stat-grid" id="adm-stats"></div>
    <div class="tabs">
      <button class="tab ${State.adminTab === "active" ? "active" : ""}" data-atab="active">Активные</button>
      <button class="tab ${State.adminTab === "all" ? "active" : ""}" data-atab="all">Все</button>
    </div>
    <div id="adm-list"><p style="text-align:center;color:#8b93a1;font-weight:800;padding:30px">Загрузка…</p></div>
    <div class="modal-bg" id="adm-modal"><div class="modal" id="adm-modal-body"></div></div>
  `;

  $("#adm-logout").addEventListener("click", () => {
    State.adminId = ""; localStorage.removeItem("sanuki.admin"); renderAdmin();
  });
  $$("[data-atab]", el).forEach((b) => b.addEventListener("click", () => { State.adminTab = b.dataset.atab; renderAdmin(); }));
  $("#adm-modal").addEventListener("click", (e) => { if (e.target.id === "adm-modal") e.currentTarget.classList.remove("open"); });

  try {
    const [orders, st] = await Promise.all([
      api(`/api/admin/orders?scope=${State.adminTab}`),
      api("/api/admin/stats"),
    ]);
    adminCache = orders;
    $("#adm-stats").innerHTML = `
      <div class="stat"><div class="k">Заказов сегодня</div><div class="v">${st.today}</div></div>
      <div class="stat"><div class="k">Выручка</div><div class="v">${st.today_sum.toLocaleString("ru-RU")} <small>₽</small></div></div>
      <div class="stat"><div class="k">Активные</div><div class="v">${st.active}</div></div>
      <div class="stat"><div class="k">Пользователей</div><div class="v">${st.users}</div></div>`;
    const list = $("#adm-list");
    if (!orders.length) {
      list.innerHTML = `<div class="empty">📭 Активных заказов нет<br>Все заказы выполнены. Отдыхайте!</div>`;
    } else {
      list.innerHTML = orders.map((o) => `
        <div class="a-order" data-aorder="${o.id}">
          <div class="top">
            <div class="num">#${esc(o.public_id)}</div>
            <span class="chip" style="background:${o.status_color}">${esc(o.status_title)}</span>
          </div>
          <div class="meta">${esc(o.name)} · ${esc(o.phone || "—")} · ${fmtDate(o.created_at)}</div>
          <div class="sumrow">
            <span class="src">${o.source === "web" ? "🌐 сайт" : "🤖 бот"}${o.pay_method === "yoomoney" ? " · 💳" : ""}</span>
            <span class="sum">${fmtPrice(o.total)}</span>
          </div>
        </div>`).join("");
      $$("[data-aorder]", list).forEach((c) => c.addEventListener("click", () => openAdminOrder(Number(c.dataset.aorder))));
    }
  } catch (e) {
    if (String(e.message).includes("403")) {
      State.adminId = ""; localStorage.removeItem("sanuki.admin");
      toast("⛔ Неверный ID администратора");
      renderAdmin();
    } else {
      $("#adm-list").innerHTML = `<div class="empty">⚠️ ${esc(e.message)}</div>`;
    }
  }
}

function openAdminOrder(orderId) {
  const o = adminCache.find((x) => x.id === orderId);
  if (!o) return;
  const modal = $("#adm-modal");
  const body = $("#adm-modal-body");
  const statuses = State.menu?.statuses || [];
  const editable = ["new", "accepted", "cooking", "ready"].includes(o.status) || o.status === "cancelled";
  body.innerHTML = `
    <h3>Заказ #${esc(o.public_id)} <button class="close" id="adm-close">✕</button></h3>
    <div style="margin-top:10px">
      <div class="m-row"><span class="k">Статус</span><span class="v"><span class="chip" style="background:${o.status_color}">${esc(o.status_title)}</span></span></div>
      <div class="m-row"><span class="k">Клиент</span><span class="v">${esc(o.name)}</span></div>
      <div class="m-row"><span class="k">Телефон</span><span class="v">${esc(o.phone || "—")}</span></div>
      <div class="m-row"><span class="k">Формат</span><span class="v">${esc(o.type)}</span></div>
      <div class="m-row"><span class="k">Оплата</span><span class="v">${o.pay_method === "yoomoney" ? "💳 ЮMoney" + (o.payment_stub ? " (тест)" : "") : "💵 при получении"}</span></div>
      <div class="m-row"><span class="k">Источник</span><span class="v">${o.source === "web" ? "🌐 сайт" : "🤖 бот"}</span></div>
      <div class="m-row"><span class="k">Создан</span><span class="v">${fmtDate(o.created_at)}</span></div>
    </div>
    <div style="background:#1d2127;border-radius:13px;padding:12px;margin-top:12px;font-size:13px;font-weight:700;line-height:1.7">
      ${esc(o.items_text).replace(/\n/g, "<br>")}
    </div>
    <div class="stgrid">
      ${statuses.filter((s) => s.id !== "new").map((s) => `
        <button class="stbtn" style="background:${s.color}" data-setst="${s.id}" ${(!editable || o.status === s.id) ? "disabled style='opacity:.4;background:#3a414c'" : ""}>
          ${esc(s.title)}
        </button>`).join("")}
    </div>`;
  modal.classList.add("open");
  $("#adm-close").addEventListener("click", () => modal.classList.remove("open"));
  $$("[data-setst]", body).forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    try {
      await api(`/api/admin/orders/${o.id}/status`, { method: "POST", body: JSON.stringify({ status: b.dataset.setst }) });
      toast("✅ Статус обновлён — уведомления отправлены");
      modal.classList.remove("open");
      renderAdmin();
    } catch (e) {
      toast("⚠️ " + e.message);
      b.disabled = false;
    }
  }));
}

// ============================================================
// SSE: живые статусы (как в боте)
// ============================================================
function connectEvents() {
  const es = new EventSource("/api/events");
  es.onmessage = (m) => {
    try {
      const ev = JSON.parse(m.data);
      const stNames = { accepted: "Принят", cooking: "Готовится", ready: "Готов! 🍜", issued: "Выдан", cancelled: "Отменён" };
      if (ev.type === "order_status" || ev.type === "order_new") {
        // экран конкретного заказа
        const odEl = $("#view-order");
        if (currentView === "order" && ev.type === "order_status" && Number(odEl.dataset.orderId) === ev.order_id) {
          renderOrderDetail(ev.order_id);
        }
        // список «Мои заказы»
        if (currentView === "orders" && (State.tgId || State.myOrders.includes(ev.order_id))) renderOrders();
        // экран «Заказ принят»
        if (currentView === "success" && ev.order_id === State.lastOrder && ev.type === "order_status") {
          renderSuccess(ev.order_id);
        }
        // админка
        if (currentView === "admin" && State.adminId && !$("#adm-modal").classList.contains("open")) {
          renderAdmin();
        }
        // тост клиенту
        if (ev.type === "order_status" && State.myOrders.includes(ev.order_id)) {
          const st = stNames[ev.status] || ev.status;
          toast(`🔔 Заказ #${String(ev.public_id || ev.order_id).padStart(4, "0")}: ${st}`, 3200);
        }
      }
      if (ev.type === "payment_stub_confirmed" && currentView === "success") {
        renderSuccess(ev.order_id);
      }
    } catch (_) {}
  };
  es.onerror = () => { /* EventSource переподключится сам */ };
}

// ============================================================
// Навигация / бейджи / докбар
// ============================================================
function updateBadges() {
  const count = State.cart.reduce((s, l) => s + l.qty, 0);
  $("#cart-badge").textContent = count;
  $("#cart-badge").style.display = count ? "grid" : "none";
  const navBadge = $("#nav-cart-badge");
  navBadge.textContent = count;
  navBadge.style.display = count ? "grid" : "none";
}

function hideDockbar() {
  $("#dockbar").style.display = "none";
}

function bindGlobal() {
  // Делегирование: data-go и data-add
  document.addEventListener("click", (e) => {
    const goEl = e.target.closest("[data-go]");
    if (goEl) { go(goEl.dataset.go); return; }
    const addEl = e.target.closest("[data-add]");
    if (addEl) {
      const [name, price] = addEl.dataset.add.split("|");
      addToCart(name, Number(price));
      return;
    }
    const popEl = e.target.closest("[data-popular]");
    if (popEl) { popularToCart(popEl.dataset.popular); }
  });
  $$(".nav-item").forEach((n) => n.addEventListener("click", () => go(n.dataset.view)));
  $("#cart-btn").addEventListener("click", () => go("cart"));
}

// ============================================================
// Инициализация
// ============================================================
(async function init() {
  initTelegram();
  bindGlobal();
  try {
    await loadMenu();
  } catch (e) {
    document.body.innerHTML = `<div style="margin:auto;text-align:center;font-weight:800;color:#9a8d79">⚠️ Сервер недоступен. Обновите страницу.</div>`;
    return;
  }
  updateBadges();
  connectEvents();
  go("home");
})();
