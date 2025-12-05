/**
 * Category Filter Management Module
 * Extracted from create_order.html for testing
 */

/**
 * Save active category filter to localStorage
 */
function saveFilterState(activeCategory) {
  localStorage.setItem('activeCategory', activeCategory || '');
}

/**
 * Load active category filter from localStorage
 */
function loadFilterState() {
  return localStorage.getItem('activeCategory') || null;
}

/**
 * Apply saved filter state to DOM
 */
function applyFilterState() {
  const activeCategory = loadFilterState();
  if (!activeCategory) return;

  // Highlight the active category in sidebar
  document.querySelectorAll('.category-toggle').forEach(link => {
    const cat = link.dataset.category;
    if (cat === activeCategory) {
      link.classList.add('active', 'fw-bold');
      link.parentElement.classList.add('active');
    } else {
      link.classList.remove('active', 'fw-bold');
      link.parentElement.classList.remove('active');
    }
  });

  // Show only the active category section
  document.querySelectorAll('.category-section').forEach(section => {
    if (section.dataset.category === activeCategory) {
      section.style.display = 'block';
    } else {
      section.style.display = 'none';
    }
  });
}

/**
 * Clear all filters and show all categories
 */
function clearFilter() {
  saveFilterState(null);
  
  // Remove active state from all filters
  document.querySelectorAll('.category-toggle').forEach(link => {
    link.classList.remove('active', 'fw-bold');
    link.parentElement.classList.remove('active');
  });
  
  // Show all categories
  document.querySelectorAll('.category-section').forEach(section => {
    section.style.display = 'block';
  });
}

/**
 * Activate a specific category filter
 */
function activateFilter(category) {
  saveFilterState(category);
  
  // Update UI - highlight active filter
  document.querySelectorAll('.category-toggle').forEach(link => {
    const cat = link.dataset.category;
    if (cat === category) {
      link.classList.add('active', 'fw-bold');
      link.parentElement.classList.add('active');
    } else {
      link.classList.remove('active', 'fw-bold');
      link.parentElement.classList.remove('active');
    }
  });

  // Show only selected category
  document.querySelectorAll('.category-section').forEach(section => {
    if (section.dataset.category === category) {
      section.style.display = 'block';
      section.classList.remove('d-none');
    } else {
      section.style.display = 'none';
    }
  });
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    saveFilterState,
    loadFilterState,
    applyFilterState,
    clearFilter,
    activateFilter
  };
}
