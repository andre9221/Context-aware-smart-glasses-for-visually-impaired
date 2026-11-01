/* Adds a lightweight pointer spotlight to the existing dashboard card components. */
(() => {
  const cardSelector = [
    ".glass-card",
    ".care-card",
    ".care-kpi",
    ".patient-row",
    ".patient-list-item",
    ".appointment-list > article",
    ".visit-list > article",
    ".stat-box",
    ".traffic-stats > div",
    ".patient-notifications",
  ].join(",");

  let activeCard = null;

  function registerCards(root = document) {
    if (root instanceof Element && root.matches(cardSelector)) {
      root.setAttribute("data-spotlight-card", "");
    }
    root.querySelectorAll?.(cardSelector).forEach((card) => {
      card.setAttribute("data-spotlight-card", "");
    });
  }

  function clearActiveCard() {
    activeCard?.setAttribute("data-spotlight-active", "false");
    activeCard = null;
  }

  registerCards();
  new MutationObserver((records) => {
    records.forEach((record) => record.addedNodes.forEach((node) => {
      if (node instanceof Element) registerCards(node);
    }));
  }).observe(document.body, { childList: true, subtree: true });

  document.addEventListener("pointermove", (event) => {
    const card = event.target instanceof Element ? event.target.closest("[data-spotlight-card]") : null;
    if (!card) {
      clearActiveCard();
      return;
    }

    if (activeCard !== card) {
      clearActiveCard();
      activeCard = card;
      card.setAttribute("data-spotlight-active", "true");
    }

    const rect = card.getBoundingClientRect();
    card.style.setProperty("--spotlight-x", `${(event.clientX - rect.left).toFixed(1)}px`);
    card.style.setProperty("--spotlight-y", `${(event.clientY - rect.top).toFixed(1)}px`);
  }, { passive: true });

  document.addEventListener("pointerout", (event) => {
    if (!event.relatedTarget) clearActiveCard();
  }, { passive: true });

  document.addEventListener("focusin", (event) => {
    const card = event.target instanceof Element ? event.target.closest("[data-spotlight-card]") : null;
    if (!card) return;
    clearActiveCard();
    activeCard = card;
    card.setAttribute("data-spotlight-active", "true");
    card.style.setProperty("--spotlight-x", `${card.clientWidth / 2}px`);
    card.style.setProperty("--spotlight-y", `${card.clientHeight / 2}px`);
  });

  document.addEventListener("focusout", (event) => {
    if (activeCard && !activeCard.contains(event.relatedTarget)) clearActiveCard();
  });
})();
