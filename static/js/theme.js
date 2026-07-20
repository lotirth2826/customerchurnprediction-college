(() => {
  const key = "churn-theme";
  const root = document.documentElement;
  const body = document.body;
  const button = document.getElementById("themeToggle");
  const saved = localStorage.getItem(key) || "light";

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    body.setAttribute("data-theme", theme);
    localStorage.setItem(key, theme);
    window.dispatchEvent(new CustomEvent("themechange", { detail: { theme } }));
  }

  apply(saved);
  if (button) {
    button.addEventListener("click", () => {
      const next = body.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(next);
    });
  }

  document.querySelectorAll("[data-count-to]").forEach((node) => {
    const target = Number(node.getAttribute("data-count-to"));
    const suffix = node.getAttribute("data-count-suffix") || "";
    const duration = Number(node.getAttribute("data-count-duration") || 900);
    const start = performance.now();

    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const value = Math.round(target * (0.25 + 0.75 * progress));
      node.textContent = `${value}${suffix}`;
      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        node.textContent = `${target}${suffix}`;
      }
    };

    requestAnimationFrame(tick);
  });
})();
