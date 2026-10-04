(function () {
  'use strict';

  function publicKey(value) {
    const decoded = window.atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4));
    return Uint8Array.from(decoded, function (character) { return character.charCodeAt(0); });
  }

  function init(panel) {
    if (panel.dataset.webpushReady) return;
    panel.dataset.webpushReady = 'true';
    const button = panel.querySelector('[data-webpush-toggle]');
    const status = panel.querySelector('[data-webpush-status]');
    const token = panel.querySelector('[name="csrfmiddlewaretoken"]');
    const install = panel.querySelector('[data-webpush-install]');
    let subscription = null;
    let enabled = false;
    const appleMobile = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const standalone = navigator.standalone || window.matchMedia('(display-mode: standalone)').matches;
    if (install) install.hidden = !(appleMobile && !standalone);

    function display(open, message) {
      enabled = open;
      status.textContent = message || (open ? 'เปิดแล้ว · เครื่องนี้จะรับแจ้งเตือนก่อนสอน' : 'ปิด · กดปุ่มเพื่อรับแจ้งเตือนบนเครื่องนี้');
      button.textContent = open ? 'ปิดแจ้งเตือนบนเครื่องนี้' : 'เปิดแจ้งเตือนบนเครื่องนี้';
      button.disabled = false;
      button.setAttribute('aria-pressed', String(open));
    }

    async function request(url, data) {
      const options = {credentials: 'same-origin', cache: 'no-store'};
      if (data) {
        options.method = 'POST';
        options.headers = {'Content-Type': 'application/json', 'X-CSRFToken': token.value};
        options.body = JSON.stringify(data);
      }
      const response = await fetch(url, options);
      let result;
      try { result = await response.json(); } catch (_) { throw new Error('กรุณาเข้าสู่ระบบใหม่แล้วลองอีกครั้ง'); }
      if (!response.ok) throw new Error(result.error || 'บันทึกการแจ้งเตือนไม่สำเร็จ กรุณาลองอีกครั้ง');
      return result;
    }

    if (!window.isSecureContext || !('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window) || (appleMobile && !standalone)) {
      status.textContent = appleMobile && !standalone ? 'ต้องเปิดจากไอคอน SIGROOM บนหน้าจอโฮมก่อน' : 'เบราว์เซอร์นี้ไม่รองรับแจ้งเตือนบนเครื่อง กระดิ่งในเว็บยังใช้งานได้';
      button.textContent = 'เบราว์เซอร์ไม่รองรับ';
      button.disabled = true;
      return;
    }

    button.addEventListener('click', async function () {
      button.disabled = true;
      let created = false;
      try {
        if (enabled && subscription) {
          await request(panel.dataset.unsubscribeUrl, {endpoint: subscription.endpoint});
          await subscription.unsubscribe();
          subscription = null;
          display(false);
          return;
        }
        // เรียกก่อน await แรก เพื่อคง user activation บน iPhone
        const permission = window.Notification.permission === 'granted' ? 'granted' : await window.Notification.requestPermission();
        if (permission !== 'granted') {
          display(false, 'ยังไม่ได้อนุญาตแจ้งเตือน หากเคยปฏิเสธให้เปิดสิทธิ์ในตั้งค่าเบราว์เซอร์');
          return;
        }
        await navigator.serviceWorker.register(panel.dataset.workerUrl, {scope: '/'});
        const registration = await navigator.serviceWorker.ready;
        subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
          subscription = await registration.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: publicKey(panel.dataset.publicKey)});
          created = true;
        }
        await request(panel.dataset.subscribeUrl, subscription.toJSON());
        display(true);
      } catch (error) {
        if (created && subscription) {
          try { await subscription.unsubscribe(); } catch (_) { /* ไม่บันทึกฝั่ง server จึงไม่มีการส่ง */ }
          subscription = null;
        }
        display(enabled, error.message || 'เปิดแจ้งเตือนไม่สำเร็จ กรุณาลองอีกครั้ง');
      }
    });

    (async function () {
      try {
        const registration = await navigator.serviceWorker.getRegistration('/');
        subscription = registration ? await registration.pushManager.getSubscription() : null;
        if (subscription) {
          const result = await request(panel.dataset.statusUrl);
          display(result.endpoints.includes(subscription.endpoint));
        } else display(false);
      } catch (_) {
        display(false, 'ตรวจสถานะไม่สำเร็จ กดเปิดแจ้งเตือนเพื่อลองอีกครั้ง');
      }
    })();
  }

  function initialize() { document.querySelectorAll('[data-webpush-panel]').forEach(init); }
  initialize();
  document.addEventListener('htmx:afterSwap', initialize);
})();
