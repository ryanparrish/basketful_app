/**
 * Jest tests for category filter functionality
 */

const {
  saveFilterState,
  loadFilterState,
  applyFilterState,
  clearFilter,
  activateFilter
} = require('./filter.js');

describe('Filter State Management', () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = '';
  });

  test('should save filter state to localStorage', () => {
    saveFilterState('fruits');
    expect(localStorage.getItem('activeCategory')).toBe('fruits');
  });

  test('should save empty string when category is null', () => {
    saveFilterState(null);
    expect(localStorage.getItem('activeCategory')).toBe('');
  });

  test('should load filter state from localStorage', () => {
    localStorage.setItem('activeCategory', 'vegetables');
    const state = loadFilterState();
    expect(state).toBe('vegetables');
  });

  test('should return null when no filter state exists', () => {
    // localStorage is empty by default
    const state = loadFilterState();
    expect(state).toBeNull();
  });

  test('should return null for empty string', () => {
    localStorage.setItem('activeCategory', '');
    const state = loadFilterState();
    // loadFilterState returns `|| null` so empty string becomes null
    expect(state).toBeNull();
  });
});

describe('Filter Application', () => {
  beforeEach(() => {
    localStorage.clear();
    // Setup DOM
    document.body.innerHTML = `
      <div>
        <ul>
          <li>
            <a class="category-toggle" data-category="fruits">Fruits</a>
          </li>
          <li>
            <a class="category-toggle" data-category="vegetables">Vegetables</a>
          </li>
        </ul>
        <div class="category-section" data-category="fruits">Fruits content</div>
        <div class="category-section" data-category="vegetables">Vegetables content</div>
      </div>
    `;
  });

  test('should apply filter state to DOM elements', () => {
    localStorage.setItem('activeCategory', 'fruits');
    
    applyFilterState();
    
    const fruitsLink = document.querySelector('[data-category="fruits"]');
    const veggiesLink = document.querySelector('[data-category="vegetables"]');
    
    expect(fruitsLink.classList.contains('active')).toBe(true);
    expect(veggiesLink.classList.contains('active')).toBe(false);
  });

  test('should show only active category section', () => {
    localStorage.setItem('activeCategory', 'fruits');
    
    applyFilterState();
    
    const fruitsSection = document.querySelector('.category-section[data-category="fruits"]');
    const veggiesSection = document.querySelector('.category-section[data-category="vegetables"]');
    
    expect(fruitsSection.style.display).toBe('block');
    expect(veggiesSection.style.display).toBe('none');
  });

  test('should not modify DOM when no filter state exists', () => {
    // localStorage is empty by default
    
    const initialHTML = document.body.innerHTML;
    applyFilterState();
    
    expect(document.body.innerHTML).toBe(initialHTML);
  });
});

describe('Filter Activation', () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = `
      <div>
        <ul>
          <li>
            <a class="category-toggle" data-category="fruits">Fruits</a>
          </li>
          <li>
            <a class="category-toggle" data-category="vegetables">Vegetables</a>
          </li>
        </ul>
        <div class="category-section" data-category="fruits">Fruits content</div>
        <div class="category-section" data-category="vegetables">Vegetables content</div>
      </div>
    `;
  });

  test('should activate specific category filter', () => {
    activateFilter('vegetables');
    
    expect(localStorage.getItem('activeCategory')).toBe('vegetables');
    
    const veggiesLink = document.querySelector('[data-category="vegetables"]');
    expect(veggiesLink.classList.contains('active')).toBe(true);
  });

  test('should show only activated category section', () => {
    activateFilter('fruits');
    
    const fruitsSection = document.querySelector('.category-section[data-category="fruits"]');
    const veggiesSection = document.querySelector('.category-section[data-category="vegetables"]');
    
    expect(fruitsSection.style.display).toBe('block');
    expect(veggiesSection.style.display).toBe('none');
  });
});

describe('Filter Clearing', () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML = `
      <div>
        <ul>
          <li class="active">
            <a class="category-toggle active fw-bold" data-category="fruits">Fruits</a>
          </li>
          <li>
            <a class="category-toggle" data-category="vegetables">Vegetables</a>
          </li>
        </ul>
        <div class="category-section" data-category="fruits" style="display: block;">Fruits</div>
        <div class="category-section" data-category="vegetables" style="display: none;">Vegetables</div>
      </div>
    `;
  });

  test('should clear filter state in localStorage', () => {
    localStorage.setItem('activeCategory', 'fruits');
    clearFilter();
    expect(localStorage.getItem('activeCategory')).toBe('');
  });

  test('should remove active classes from all links', () => {
    clearFilter();
    
    const links = document.querySelectorAll('.category-toggle');
    links.forEach(link => {
      expect(link.classList.contains('active')).toBe(false);
      expect(link.classList.contains('fw-bold')).toBe(false);
    });
  });

  test('should show all category sections', () => {
    clearFilter();
    
    const sections = document.querySelectorAll('.category-section');
    sections.forEach(section => {
      expect(section.style.display).toBe('block');
    });
  });
});
