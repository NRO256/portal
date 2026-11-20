(() => {
  "use strict";

  const filterButtons = Array.from(document.querySelectorAll(".filter-btn[data-category]"));
  const cards = Array.from(document.querySelectorAll(".app-card[data-category]"));
  const searchInput = document.getElementById("app-search");
  const clearButton = document.getElementById("search-clear");
  const resetButton = document.getElementById("filter-reset");
  const statusElement = document.getElementById("catalog-status");
  const emptyStateElement = document.getElementById("empty-state");

  if (!cards.length || !statusElement || !emptyStateElement) {
    return;
  }

  let activeCategory = "all";

  /**
   * Normalize user query or search index text with NFKC and lowercase.
   * @param {string} value
   * @returns {string}
   */
  function normalizeText(value) {
    return value.normalize("NFKC").toLowerCase().trim();
  }

  const cardRecords = cards.map((card) => ({
    element: card,
    category: card.dataset.category || "",
    searchText: normalizeText(card.dataset.search || ""),
  }));

  function updateFilterButtons() {
    for (const button of filterButtons) {
      const isSelected = button.dataset.category === activeCategory;
      button.setAttribute("aria-pressed", isSelected ? "true" : "false");
    }
  }

  function applyFilters() {
    const rawQuery = searchInput ? searchInput.value : "";
    const normalizedQuery = normalizeText(rawQuery);
    const tokens = normalizedQuery ? normalizedQuery.split(/\s+/) : [];

    if (clearButton) {
      clearButton.disabled = rawQuery.length === 0;
    }

    let visibleCount = 0;

    for (const record of cardRecords) {
      const matchesCategory = activeCategory === "all" || record.category === activeCategory;
      const matchesQuery =
        tokens.length === 0 || tokens.every((token) => record.searchText.includes(token));
      const isVisible = matchesCategory && matchesQuery;

      record.element.hidden = !isVisible;
      if (isVisible) {
        visibleCount += 1;
      }
    }

    emptyStateElement.hidden = visibleCount > 0;
    statusElement.textContent = `全 ${cardRecords.length} 件中 ${visibleCount} 件を表示しています`;
  }

  for (const button of filterButtons) {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.category || "all";
      updateFilterButtons();
      applyFilters();
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", applyFilters);
    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && searchInput.value.length > 0) {
        event.preventDefault();
        searchInput.value = "";
        applyFilters();
      }
    });
  }

  if (clearButton && searchInput) {
    clearButton.addEventListener("click", () => {
      searchInput.value = "";
      applyFilters();
      searchInput.focus();
    });
  }

  if (resetButton) {
    resetButton.addEventListener("click", () => {
      activeCategory = "all";
      if (searchInput) {
        searchInput.value = "";
      }
      updateFilterButtons();
      applyFilters();
    });
  }

  updateFilterButtons();
  applyFilters();
})();
