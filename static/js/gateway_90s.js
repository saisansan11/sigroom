(function () {
  "use strict";

  var pager = document.querySelector(".gateway-pager");
  if (!pager) return;
  var messages = Array.prototype.slice.call(pager.querySelectorAll("[data-pager-message]"));
  if (messages.length < 2) return;

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduceMotion.matches) return;

  var index = 0;
  var timer = 0;

  function showNext() {
    messages[index].hidden = true;
    index = (index + 1) % messages.length;
    messages[index].hidden = false;
  }

  function start() {
    if (document.hidden || reduceMotion.matches || timer) return;
    timer = window.setInterval(showNext, 3500);
  }

  function stop() {
    if (!timer) return;
    window.clearInterval(timer);
    timer = 0;
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) stop();
    else start();
  });
  if (reduceMotion.addEventListener) {
    reduceMotion.addEventListener("change", function (event) {
      if (event.matches) stop();
      else start();
    });
  }
  start();
})();
