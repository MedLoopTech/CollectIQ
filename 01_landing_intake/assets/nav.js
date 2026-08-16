(function () {
  var ICON_MENU = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';
  var ICON_CLOSE = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';

  var btn = document.getElementById("navToggle");
  var links = document.getElementById("navlinks");
  if (!btn || !links) return;

  btn.innerHTML = ICON_MENU;

  function close() {
    links.classList.remove("open");
    btn.setAttribute("aria-expanded", "false");
    btn.innerHTML = ICON_MENU;
  }

  btn.addEventListener("click", function () {
    var isOpen = links.classList.toggle("open");
    btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    btn.innerHTML = isOpen ? ICON_CLOSE : ICON_MENU;
  });

  links.querySelectorAll("a").forEach(function (a) {
    a.addEventListener("click", close);
  });

  document.addEventListener("click", function (e) {
    if (!links.classList.contains("open")) return;
    if (links.contains(e.target) || btn.contains(e.target)) return;
    close();
  });
})();
