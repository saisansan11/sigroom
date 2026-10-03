(() => {
  function syncDays() {
    const form = document.querySelector('.online-quick-filter');
    const selected = form?.querySelector('input[name="day"]:checked')?.value;
    form?.querySelectorAll('input[name="day"]').forEach(input => {
      input.nextElementSibling.classList.toggle('is-on', input.value === selected);
    });
  }
  document.addEventListener('change', syncDays);
  document.addEventListener('htmx:afterSwap', syncDays);
  syncDays();
})();
