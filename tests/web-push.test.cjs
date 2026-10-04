const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');

const source = readFileSync('static/js/web_push.js', 'utf8');
const workerSource = readFileSync('static/js/web_push_sw.js', 'utf8');

function element() {
  const listeners = {};
  return {
    listeners,
    dataset: {},
    disabled: false,
    hidden: false,
    textContent: '',
    value: '',
    attrs: {},
    addEventListener(name, fn) { listeners[name] = fn; },
    setAttribute(name, value) { this.attrs[name] = value; },
  };
}

function jsonResponse(data, ok=true) {
  return {ok, async json() { return data; }};
}

async function flush() {
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
}

function setup({subscription=null, owned=false, unsubscribeResult=true}={}) {
  const events = [];
  const requests = [];
  const button = element();
  const status = element();
  const token = element(); token.value = 'csrf-qa-token';
  const install = element();
  let activeSubscription = subscription;
  if (activeSubscription) {
    activeSubscription.unsubscribe = async () => { events.push('unsubscribe-browser'); return unsubscribeResult; };
  }
  const newSubscription = {
    endpoint: 'https://fcm.googleapis.com/fcm/send/new-device',
    toJSON() { return {endpoint: this.endpoint, keys: {p256dh: 'pub', auth: 'auth'}}; },
    async unsubscribe() { events.push('unsubscribe-new'); return true; },
  };
  const registration = {
    pushManager: {
      async getSubscription() { return activeSubscription; },
      async subscribe() { events.push('subscribe-browser'); activeSubscription = newSubscription; return newSubscription; },
    },
  };
  const panel = element();
  Object.assign(panel.dataset, {
    publicKey: 'AQIDBA',
    workerUrl: '/sw.js',
    statusUrl: '/notifications/push/status/',
    subscribeUrl: '/notifications/push/subscribe/',
    unsubscribeUrl: '/notifications/push/unsubscribe/',
  });
  panel.querySelector = selector => ({
    '[data-webpush-toggle]': button,
    '[data-webpush-status]': status,
    '[name="csrfmiddlewaretoken"]': token,
    '[data-webpush-install]': install,
  })[selector];

  const serviceWorker = {
    async getRegistration() { return subscription ? registration : null; },
    async register(url, options) { events.push(`register:${url}:${options.scope}`); return registration; },
    ready: Promise.resolve(registration),
  };
  const Notification = {
    permission: 'default',
    async requestPermission() { events.push('permission'); Notification.permission = 'granted'; return 'granted'; },
  };
  async function fetch(url, options={}) {
    requests.push({url, options});
    if (url === panel.dataset.statusUrl) {
      return jsonResponse({endpoints: owned && subscription ? [subscription.endpoint] : []});
    }
    if (url === panel.dataset.subscribeUrl) return jsonResponse({enabled: true});
    if (url === panel.dataset.unsubscribeUrl) return jsonResponse({enabled: false});
    throw new Error(`unexpected fetch ${url}`);
  }

  const context = {
    window: {isSecureContext: true, matchMedia: () => ({matches: false}), Notification, atob},
    navigator: {userAgent: 'Desktop Browser', platform: 'Win32', maxTouchPoints: 0, serviceWorker},
    Notification,
    PushManager: function PushManager() {},
    fetch,
    atob,
    Uint8Array,
    Error,
    Promise,
    document: {querySelectorAll: () => [panel], addEventListener() {}},
    setImmediate,
  };
  context.window.PushManager = context.PushManager;
  context.window.navigator = context.navigator;
  vm.runInNewContext(source, context);
  return {button, status, panel, requests, events, registration, newSubscription};
}

test('owned browser subscription is recognized using no-store same-origin status request', async () => {
  const sub = {endpoint: 'https://fcm.googleapis.com/fcm/send/owned'};
  const qa = setup({subscription: sub, owned: true});
  await flush();
  assert.equal(qa.button.attrs['aria-pressed'], 'true');
  assert.equal(qa.requests.length, 1);
  assert.equal(qa.requests[0].url, '/notifications/push/status/');
  assert.equal(qa.requests[0].options.credentials, 'same-origin');
  assert.equal(qa.requests[0].options.cache, 'no-store');
});

test('subscription from another account is removed from browser during initialization', async () => {
  const sub = {endpoint: 'https://fcm.googleapis.com/fcm/send/old-account'};
  const qa = setup({subscription: sub, owned: false});
  await flush();
  assert.deepEqual(qa.events, ['unsubscribe-browser']);
  assert.equal(qa.button.attrs['aria-pressed'], 'false');
  assert.match(qa.status.textContent, /บัญชีเดิม/);
});

test('failed browser unsubscribe keeps server subscription enabled and does not call unsubscribe endpoint', async () => {
  const sub = {endpoint: 'https://fcm.googleapis.com/fcm/send/owned'};
  const qa = setup({subscription: sub, owned: true, unsubscribeResult: false});
  await flush();
  await qa.button.listeners.click();
  assert.equal(qa.button.attrs['aria-pressed'], 'true');
  assert.match(qa.status.textContent, /ยังรับแจ้งเตือนอยู่/);
  assert.equal(qa.requests.filter(item => item.url === '/notifications/push/unsubscribe/').length, 0);
});

test('enable action requests permission before registration and posts subscription with CSRF', async () => {
  const qa = setup();
  await flush();
  await qa.button.listeners.click();
  assert.deepEqual(qa.events.slice(0, 3), ['permission', 'register:/sw.js:/', 'subscribe-browser']);
  const request = qa.requests.find(item => item.url === '/notifications/push/subscribe/');
  assert.ok(request);
  assert.equal(request.options.method, 'POST');
  assert.equal(request.options.credentials, 'same-origin');
  assert.equal(request.options.headers['X-CSRFToken'], 'csrf-qa-token');
  assert.equal(request.options.headers['Content-Type'], 'application/json');
  assert.equal(qa.button.attrs['aria-pressed'], 'true');
});

test('service worker internalPath rejects external, query, fragment and encoded scheme-relative URLs', () => {
  const listeners = {};
  const context = {
    URL,
    self: {
      location: {origin: 'https://sigroom.web.app'},
      addEventListener(name, fn) { listeners[name] = fn; },
      registration: {showNotification() {}},
      clients: {matchAll: async () => [], openWindow: async () => {}},
    },
  };
  vm.runInNewContext(workerSource, context);
  assert.equal(context.internalPath('/bookings/abc/pass/'), '/bookings/abc/pass/');
  for (const value of ['https://evil.example/x', '//evil.example/x', '/x?token=secret', '/x#frag', '/%2f%2fevil.example/x']) {
    assert.equal(context.internalPath(value), '/notifications/');
  }
  assert.ok(listeners.push);
  assert.ok(listeners.notificationclick);
});
