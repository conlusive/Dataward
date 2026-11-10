"""Keyboard shortcuts for the dashboard: a table in Python and a small script generated from it.

The page never prints the shortcuts: they are there for those who look (``?`` opens the list,
``Ctrl K`` / ``⌘ K`` the command palette). Keys are matched by their physical position
(``KeyboardEvent.code``), so they work in the Ukrainian layout too. The script clicks the sidebar
links and the trainer's buttons, so nothing here knows how Streamlit routes pages.
"""

import json
from typing import Final

# (title as in the menu, the key after "g"); the titles must match ``dashboard/app.py``.
PAGES: Final[tuple[tuple[str, str], ...]] = (
    ("Головна", "h"),
    ("Каталог", "c"),
    ("Для мене", "f"),
    ("Збережені", "b"),
    ("Профіль", "u"),
    ("Навчання", "l"),
    ("Практика", "p"),
    ("Ринок", "m"),
    ("Навички", "s"),
    ("Зарплати", "w"),
    ("Стан системи", "d"),
)

# pages the public copy does not have (it shows the market, not a person or other people's listings)
PERSONAL: Final[frozenset[str]] = frozenset(
    {"Каталог", "Для мене", "Збережені", "Профіль", "Навчання", "Практика"}
)

# shortcuts that act on a profile (the trainer, undo): not on the public copy either
PERSONAL_KEYS: Final[frozenset[str]] = frozenset({"Space", "1 · 2 · 3", "Z"})

# (keys, what it does) for the help overlay, after the "g" shortcuts
OTHER: Final[tuple[tuple[str, str], ...]] = (
    ("/", "до пошуку на сторінці"),
    ("Ctrl K", "палітра команд"),
    ("?", "ця довідка"),
    ("Space", "тренажер: показати відповідь"),
    ("1 · 2 · 3", "тренажер: оцінити відповідь"),
    ("Z", "скасувати останню дію (також Ctrl Z)"),
    ("Esc", "закрити вікно або вийти з поля"),
)

_SCRIPT: Final = """
(cfg) => {
  if (window.__dwKeys) window.__dwKeys();
  const doc = document;
  let pending = false, timer = null, swallow = false;
  const links = () => [...doc.querySelectorAll('[data-testid="stSidebarNavLink"]')];
  const go = (title) => {
    // the link text starts with the icon's name ("homeГоловна"), so match the end
    const link = links().find((a) => a.textContent.trim().endsWith(title));
    if (link) link.click();
  };
  const typing = (el) => !!el && (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)
    || el.isContentEditable);
  const click = (selector, index = 0) => {
    const found = doc.querySelectorAll(selector);
    if (found[index]) { found[index].click(); return true; }
    return false;
  };
  const close = () => { const o = doc.getElementById('dw-overlay'); if (o) o.remove(); };
  const el = (tag, cls, text) => {
    const node = doc.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const overlay = (title) => {
    close();
    const root = el('div'); root.id = 'dw-overlay';
    const box = el('div', 'dw-box'); box.appendChild(el('h3', '', title));
    root.appendChild(box);
    root.addEventListener('mousedown', (e) => { if (e.target === root) close(); });
    doc.body.appendChild(root);
    return box;
  };
  const row = (left, right) => {
    const r = el('div', 'dw-row');
    r.appendChild(el('span', '', left)); r.appendChild(el('span', '', right));
    return r;
  };
  const help = () => {
    const box = overlay('Гарячі клавіші');
    cfg.pages.forEach((p) => box.appendChild(row(p.title, 'g ' + p.key)));
    cfg.other.forEach((o) => box.appendChild(row(o.what, o.keys)));
  };
  const palette = () => {
    const box = overlay('Куди перейти');
    const input = el('input'); input.placeholder = 'Почніть вводити назву сторінки';
    const list = el('div'); box.insertBefore(input, box.children[1]); box.appendChild(list);
    let shown = [], at = 0;
    const draw = () => {
      const q = input.value.trim().toLowerCase();
      shown = cfg.pages.filter((p) => p.title.toLowerCase().includes(q) || p.key === q);
      at = Math.min(at, Math.max(shown.length - 1, 0));
      list.textContent = '';
      shown.forEach((p, i) => {
        const r = row(p.title, 'g ' + p.key);
        if (i === at) r.classList.add('on');
        r.addEventListener('mousedown', () => { close(); go(p.title); });
        list.appendChild(r);
      });
    };
    input.addEventListener('input', () => { at = 0; draw(); });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') { at = Math.min(at + 1, shown.length - 1); draw(); }
      else if (e.key === 'ArrowUp') { at = Math.max(at - 1, 0); draw(); }
      else if (e.key === 'Enter' && shown[at]) { const p = shown[at]; close(); go(p.title); }
      else return;
      e.preventDefault();
    });
    draw(); input.focus();
  };
  const onKey = (e) => {
    const open = doc.getElementById('dw-overlay');
    if ((e.ctrlKey || e.metaKey) && e.code === 'KeyK') {
      e.preventDefault(); open ? close() : palette(); return;
    }
    if (e.code === 'Escape' || e.key === 'Escape') {
      if (open) close(); else if (typing(e.target)) e.target.blur();
      return;
    }
    if (!open && !typing(e.target) && e.code === 'KeyZ' && !e.altKey && !e.shiftKey) {
      if (click('.st-key-dw_undo_btn button')) { e.preventDefault(); return; }
    }
    if (open || typing(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
    if (pending) {
      pending = false; clearTimeout(timer);
      const page = cfg.pages.find((p) => 'Key' + p.key.toUpperCase() === e.code);
      if (page) { e.preventDefault(); go(page.title); }
      return;
    }
    if (e.code === 'Slash') {
      e.preventDefault();
      if (e.shiftKey) { help(); return; }
      const field = doc.querySelector('[data-testid="stMain"] [data-testid="stTextInput"] input')
        || doc.querySelector('[data-testid="stMain"] input');
      if (field) field.focus();
    } else if (e.code === 'KeyG' && !e.shiftKey) {
      pending = true; timer = setTimeout(() => { pending = false; }, 1200);
    } else if (e.code === 'Space') {
      if (click('.st-key-iv_reveal button')) { e.preventDefault(); swallow = true; }
    } else if (/^Digit[123]$/.test(e.code)) {
      click('[class*="st-key-iv_rate_"] button', Number(e.code.slice(5)) - 1);
    }
  };
  // a key released over a button that just appeared would click it: eat the release of our Space
  const onUp = (e) => {
    if (swallow && e.code === 'Space') { swallow = false; e.preventDefault(); e.stopPropagation(); }
  };
  doc.addEventListener('keydown', onKey, true);
  doc.addEventListener('keyup', onUp, true);
  window.__dwKeys = () => {
    doc.removeEventListener('keydown', onKey, true);
    doc.removeEventListener('keyup', onUp, true);
    close();
  };
}
"""


def config(*, public: bool = False) -> dict[str, list[dict[str, str]]]:
    """What the script needs: the pages with their keys and the other shortcuts for the help.

    On the public copy the personal pages are left out, so no key or palette entry leads nowhere.
    """
    return {
        "pages": [
            {"title": title, "key": key}
            for title, key in PAGES
            if not (public and title in PERSONAL)
        ],
        "other": [
            {"keys": keys, "what": what}
            for keys, what in OTHER
            if not (public and keys in PERSONAL_KEYS)
        ],
    }


def script(*, public: bool = False) -> str:
    """The code to inject once per page load; running it again replaces the earlier listener."""
    data = json.dumps(config(public=public), ensure_ascii=False).replace("</", "<\\/")
    return f"<script>({_SCRIPT})({data});</script>"
