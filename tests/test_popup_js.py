"""
Popup JS Tests
==============

Behavior tests for popup.js DOM updates, executed with Node.js against a
minimal DOM stub. The tests are skipped when Node.js is unavailable.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_POPUP_JS = Path(__file__).parent.parent / 'usage_monitor_for_claude' / 'popup' / 'popup.js'
_NODE = shutil.which('node')

_DOM_STUB = r'''
class StubElement {
    constructor(tag) {
        this.tagName = tag;
        this.className = '';
        this.textContent = '';
        this.title = '';
        this.listeners = {};
        this.disabled = false;
        this.style = {};
        this.dataset = {};
        this.children = [];
        this.parentNode = null;
        const element = this;
        this.classList = {
            add(name) { const classes = element._classSet(); classes.add(name); element.className = [...classes].join(' '); },
            remove(name) { const classes = element._classSet(); classes.delete(name); element.className = [...classes].join(' '); },
            contains(name) { return element._classSet().has(name); },
            toggle(name, force) {
                const classes = element._classSet();
                const on = force === undefined ? !classes.has(name) : !!force;
                if (on) classes.add(name); else classes.delete(name);
                element.className = [...classes].join(' ');
                return on;
            },
        };
    }
    _classSet() { return new Set(this.className.split(/\s+/).filter(Boolean)); }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    setAttribute(name, value) { this[name] = value; }
    click() { if (this.listeners.click) this.listeners.click(); }
    appendChild(node) { node.parentNode = this; this.children.push(node); return node; }
    append(...nodes) { for (const node of nodes) this.appendChild(node); }
    replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
    remove() {
        if (this.parentNode) {
            const index = this.parentNode.children.indexOf(this);
            if (index >= 0) this.parentNode.children.splice(index, 1);
            this.parentNode = null;
        }
    }
    matches(selector) { return selector.startsWith('.') && this._classSet().has(selector.slice(1)); }
    querySelector(selector) {
        for (const child of this.children) {
            if (child.matches(selector)) return child;
            const nested = child.querySelector(selector);
            if (nested) return nested;
        }
        return null;
    }
    querySelectorAll(selector) {
        const found = [];
        for (const child of this.children) {
            if (child.matches(selector)) found.push(child);
            found.push(...child.querySelectorAll(selector));
        }
        return found;
    }
}

globalThis.document = {
    createElement: (tag) => new StubElement(tag),
    body: new StubElement('body'),
};
globalThis.ResizeObserver = class { constructor() {} observe() {} };
globalThis.requestAnimationFrame = (callback) => callback();
'''

_SCENARIO_PRELUDE = r'''
els = { usageBars: document.createElement('div') };

function makeEntry(overrides) {
    return Object.assign({
        key: 'five_hour', label: '5h', pct_text: '0%', fill_pct: 0.0,
        warn: false, dividers: [], marker_rel: null, reset_text: '',
    }, overrides);
}
'''


def _run_scenario(scenario: str) -> dict:
    """Execute popup.js with the DOM stub and return its JSON result."""
    script = _DOM_STUB + _POPUP_JS.read_text(encoding='utf-8') + _SCENARIO_PRELUDE + scenario
    with TemporaryDirectory() as tmp:
        script_path = Path(tmp) / 'scenario.js'
        script_path.write_text(script, encoding='utf-8')
        proc = subprocess.run([_NODE, str(script_path)], capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise AssertionError(f'Node scenario failed:\n{proc.stderr}')
    return json.loads(proc.stdout)


@unittest.skipUnless(_NODE, 'Node.js not available')
class TestUsageBarUpdates(unittest.TestCase):
    """Tests for updateUsageBars and updateBarElement."""

    def test_changed_field_set_with_equal_count_updates_labels(self):
        result = _run_scenario('''
updateUsageBars([
    makeEntry({ key: 'five_hour', label: '5h', pct_text: '10%' }),
    makeEntry({ key: 'seven_day', label: '7d', pct_text: '20%' }),
]);
updateUsageBars([
    makeEntry({ key: 'five_hour', label: '5h', pct_text: '30%' }),
    makeEntry({ key: 'seven_day_opus', label: '7d Opus', pct_text: '99%' }),
]);
console.log(JSON.stringify(els.usageBars.children.map((bar) => ({
    label: bar.children[0].children[0].textContent,
    pct: bar.querySelector('.bar-pct').textContent,
}))));
''')
        self.assertEqual(result, [
            {'label': '5h', 'pct': '30%'},
            {'label': '7d Opus', 'pct': '99%'},
        ])

    def test_marker_and_divider_positions_stable_across_update(self):
        result = _run_scenario('''
const fields = { key: 'five_hour', label: '5h', marker_rel: 0.5, dividers: [0.25] };
updateUsageBars([makeEntry(Object.assign({ pct_text: '10%' }, fields))]);
const container = els.usageBars.children[0].querySelector('.bar-container');
const before = {
    marker: container.querySelector('.bar-marker').style.left,
    divider: container.querySelector('.bar-divider').style.left,
};
updateUsageBars([makeEntry(Object.assign({ pct_text: '11%' }, fields))]);
const after = {
    marker: container.querySelector('.bar-marker').style.left,
    divider: container.querySelector('.bar-divider').style.left,
};
console.log(JSON.stringify({ before, after }));
''')
        self.assertEqual(result['after'], result['before'])

    def test_unchanged_field_set_updates_in_place(self):
        result = _run_scenario('''
updateUsageBars([makeEntry({ key: 'five_hour', label: '5h', pct_text: '10%' })]);
const barBefore = els.usageBars.children[0];
updateUsageBars([makeEntry({ key: 'five_hour', label: '5h', pct_text: '50%', fill_pct: 0.5 })]);
console.log(JSON.stringify({
    sameElement: els.usageBars.children[0] === barBefore,
    pct: els.usageBars.children[0].querySelector('.bar-pct').textContent,
    fillWidth: els.usageBars.children[0].querySelector('.bar-fill').style.width,
}));
''')
        self.assertEqual(result, {'sameElement': True, 'pct': '50%', 'fillWidth': '50%'})


@unittest.skipUnless(_NODE, 'Node.js not available')
class TestManualRefresh(unittest.TestCase):
    """Tests for the popup refresh button's async request state."""

    def test_duplicate_click_suppressed_and_success_updates_immediately(self):
        result = _run_scenario('''
const refreshBtn = document.createElement('button');
document.getElementById = (id) => id === 'refreshBtn' ? refreshBtn : null;
translations = { refresh: 'Refresh' };
let resolveRefresh;
let calls = 0;
let updated = null;
globalThis.pywebview = { api: { refresh: () => {
    calls += 1;
    return new Promise((resolve) => { resolveRefresh = resolve; });
} } };
updateData = (data) => { updated = data; };
setupRefreshButton();
refreshBtn.click();
refreshBtn.click();
const loading = refreshBtn.disabled && refreshBtn.classList.contains('refreshing');
resolveRefresh({ status: { text: 'fresh' } });
setTimeout(() => console.log(JSON.stringify({
    calls, loading, updated, disabled: refreshBtn.disabled,
    refreshing: refreshBtn.classList.contains('refreshing'),
    title: refreshBtn.title, ariaLabel: refreshBtn['aria-label'],
})), 0);
''')
        self.assertEqual(result, {
            'calls': 1,
            'loading': True,
            'updated': {'status': {'text': 'fresh'}},
            'disabled': False,
            'refreshing': False,
            'title': 'Refresh',
            'ariaLabel': 'Refresh',
        })

    def test_rejection_restores_button_without_replacing_data(self):
        result = _run_scenario('''
const refreshBtn = document.createElement('button');
document.getElementById = (id) => id === 'refreshBtn' ? refreshBtn : null;
translations = { refresh: 'Refresh' };
let rejectRefresh;
let updates = 0;
globalThis.pywebview = { api: { refresh: () => new Promise((_resolve, reject) => { rejectRefresh = reject; }) } };
updateData = () => { updates += 1; };
setupRefreshButton();
refreshBtn.click();
const loading = refreshBtn.disabled && refreshBtn.classList.contains('refreshing');
rejectRefresh(new Error('offline'));
setTimeout(() => console.log(JSON.stringify({
    loading, updates, disabled: refreshBtn.disabled,
    refreshing: refreshBtn.classList.contains('refreshing'),
})), 0);
''')
        self.assertEqual(result, {
            'loading': True,
            'updates': 0,
            'disabled': False,
            'refreshing': False,
        })




if __name__ == '__main__':
    unittest.main()
