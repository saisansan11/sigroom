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

    async function removeBrowserSubscription(message) {
      if (!subscription) return true;
      const removed = await subscription.unsubscribe();
      if (!removed) {
        display(enabled, message || 'เบราว์เซอร์ยังยกเลิกการแจ้งเตือนไม่สำเร็จ กรุณาลองอีกครั้ง');
        return false;
      }
      subscription = null;
      return true;
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
          const endpoint = subscription.endpoint;
          if (!await removeBrowserSubscription('ปิดแจ้งเตือนไม่สำเร็จ เครื่องนี้ยังรับแจ้งเตือนอยู่')) return;
          try {
            await request(panel.dataset.unsubscribeUrl, {endpoint: endpoint});
            display(false);
          } catch (_) {
            // ฝั่ง browser ปิดแล้ว จึงไม่แสดงว่าเปิดอยู่ แม้ทะเบียน server จะรอล้างเมื่อ push service ตอบ 404/410
            display(false, 'ปิดบนเครื่องนี้แล้ว แต่ล้างทะเบียนบนระบบไม่สำเร็จ ระบบจะล้างให้อัตโนมัติเมื่อส่งครั้งถัดไป');
          }
          return;
        }
        if (subscription && !enabled) {
          // subscription ที่ browser ถืออยู่แต่ไม่ใช่ของบัญชีปัจจุบัน ต้องเอาออกก่อนเพื่อกันรับ push ของบัญชีเดิม
          if (!await removeBrowserSubscription('พบการแจ้งเตือนของบัญชีเดิม แต่เบราว์เซอร์ยังยกเลิกไม่สำเร็จ กรุณาลองอีกครั้ง')) return;
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
          try { await subscription.unsubscribe(); } catch (_) { /* server ไม่บันทึก subscription ใหม่ จึงไม่มีการส่งจากบัญชีนี้ */ }
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
          if (result.endpoints.includes(subscription.endpoint)) {
            display(true);
          } else if (await removeBrowserSubscription('พบการแจ้งเตือนของบัญชีเดิม แต่เบราว์เซอร์ยังยกเลิกไม่สำเร็จ กรุณากดปุ่มเพื่อลองอีกครั้ง')) {
            display(false, 'ล้างการแจ้งเตือนที่ผูกกับบัญชีเดิมจากเครื่องนี้แล้ว');
          }
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
