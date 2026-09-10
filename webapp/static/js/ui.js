/* SANUKI — мелкие помощники разметки */
(function (global) {
  'use strict';

  function esc(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function money(n) {
    return Number(n || 0).toLocaleString('ru-RU') + ' ₽';
  }

  function time(ts) {
    if (!ts) return '';
    const s = String(ts);
    return s.length >= 16 ? s.slice(11, 16) : s;
  }

  function dateTime(ts) {
    if (!ts) return '';
    const s = String(ts);
    // 'YYYY-MM-DD HH:MM:SS'
    const d = s.slice(8, 10) + '.' + s.slice(5, 7);
    return d + ' ' + s.slice(11, 16);
  }

  let toastTimer = null;
  function toast(message) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = message;
    el.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add('hidden'), 2200);
  }

  function haptic(type) {
    try {
      global.Telegram && global.Telegram.WebApp &&
        global.Telegram.WebApp.HapticFeedback &&
        global.Telegram.WebApp.HapticFeedback.impactOccurred(type || 'light');
    } catch (e) { /* нет Telegram — тихо */ }
  }

  function statusMeta(statuses, code) {
    const list = (statuses && statuses.statuses) || [];
    return list.find(s => s.code === code) || { code, title: code, emoji: '📦', description: '' };
  }

  function badge(statuses, code, extraClass) {
    const s = statusMeta(statuses, code);
    return '<span class="badge ' + esc(code) + ' ' + (extraClass || '') + '">' +
      s.emoji + ' ' + esc(s.title) + '</span>';
  }

  function paymentBadge(status) {
    const map = {
      unpaid: ['unpaid', '💵 Не оплачен'],
      pending: ['pending', '⏳ Ожидает оплаты'],
      paid: ['paid', '💜 Оплачен'],
      failed: ['cancelled', '❌ Оплата не прошла'],
      refunded: ['unpaid', '↩️ Возврат'],
    };
    const v = map[status] || ['unpaid', status];
    return '<span class="badge ' + v[0] + '">' + v[1] + '</span>';
  }

  function itemsText(items) {
    return (items || []).map(itemText).join('\n');
  }

  function itemText(item) {
    if (item.kind === 'udon') {
      let s = '🍜 ' + item.base + ' + ' + item.protein;
      if (item.topping && item.topping !== 'Без топпинга') s += '\n   🌿 ' + item.topping;
      (item.extras || []).forEach(e => { s += '\n   ➕ ' + e.name + ' (+' + e.price + ' ₽)'; });
      if ((item.qty || 1) > 1) s += '\n   × ' + item.qty;
      return s;
    }
    const qty = item.qty || 1;
    return '• ' + (item.name || item.title) + (qty > 1 ? ' × ' + qty : '');
  }

  function empty(text, emoji) {
    return '<div class="empty"><span class="emoji">' + (emoji || '🍜') + '</span>' +
      esc(text) + '</div>';
  }

  function on(selector, event, handler) {
    document.querySelectorAll(selector).forEach(el => el.addEventListener(event, handler));
  }

  global.UI = {
    esc, money, time, dateTime, toast, haptic,
    statusMeta, badge, paymentBadge, itemText, itemsText, empty, on,
  };
})(window);
