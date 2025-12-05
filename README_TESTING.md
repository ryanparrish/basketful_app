# JavaScript Testing with Jest

## Setup

1. **Install Node.js** (if not already installed):
   ```bash
   # macOS with Homebrew
   brew install node
   
   # Or download from https://nodejs.org/
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

## Running Tests

### Run all tests:
```bash
npm test
```

### Run tests in watch mode (auto-rerun on file changes):
```bash
npm run test:watch
```

### Run tests with coverage report:
```bash
npm run test:coverage
```

### Run specific test file:
```bash
npm test -- apps/pantry/static/js/cart.test.js
```

## Test Structure

```
lyn_project/
├── apps/
│   └── pantry/
│       └── static/
│           └── js/
│               ├── cart.js                    # Cart logic extracted
│               ├── cart.test.js               # Cart tests (13 tests)
│               ├── cart-submission.test.js    # Cart validation tests (17 tests)
│               ├── filter.js                  # Filter logic extracted
│               └── filter.test.js             # Filter tests (13 tests)
├── jest.config.js                    # Jest configuration
├── jest.setup.js                     # Test setup (mocks, etc)
├── package.json                      # NPM dependencies
└── README_TESTING.md                 # This file
```

### Test Coverage

**Total: 43 tests across 3 test suites**

1. **cart.test.js** - 13 tests
   - Cart initialization
   - Add/remove/update items
   - Cart calculations
   - Session vs localStorage priority

2. **filter.test.js** - 13 tests
   - Filter state management
   - DOM manipulation
   - Filter activation/clearing

3. **cart-submission.test.js** - 17 tests
   - Cart-to-server data validation
   - Cart clearing after submission
   - Data integrity and error handling

## Writing Tests

Example test structure:

```javascript
describe('Feature Name', () => {
  beforeEach(() => {
    // Setup code runs before each test
    localStorage.clear();
  });

  test('should do something specific', () => {
    // Arrange
    const input = 'test';
    
    // Act
    const result = functionToTest(input);
    
    // Assert
    expect(result).toBe('expected output');
  });
});
```

## Available Matchers

Jest provides many matchers:
- `expect(value).toBe(expected)` - strict equality
- `expect(value).toEqual(expected)` - deep equality
- `expect(value).toBeTruthy()` - truthy value
- `expect(value).toBeFalsy()` - falsy value
- `expect(array).toContain(item)` - array contains item
- `expect(fn).toHaveBeenCalled()` - mock function called
- `expect(fn).toHaveBeenCalledWith(arg)` - called with specific arg

See more: https://jestjs.io/docs/expect

## Mocking

LocalStorage is automatically mocked in `jest.setup.js`:

```javascript
test('should save to localStorage', () => {
  saveData('key', 'value');
  expect(localStorage.setItem).toHaveBeenCalledWith('key', 'value');
});
```

## Testing DOM Manipulation

Jest uses jsdom to simulate browser environment:

```javascript
test('should add class to element', () => {
  document.body.innerHTML = '<div id="test"></div>';
  const el = document.getElementById('test');
  el.classList.add('active');
  expect(el.classList.contains('active')).toBe(true);
});
```

## Coverage Reports

After running `npm run test:coverage`, open:
```bash
open coverage/lcov-report/index.html
```

This shows:
- Line coverage
- Branch coverage
- Function coverage
- Statement coverage

## Debugging Tests

Add `debugger;` statement in your test:

```javascript
test('debug this test', () => {
  const value = someFunction();
  debugger; // Execution will pause here
  expect(value).toBe('expected');
});
```

Run with Node debugger:
```bash
node --inspect-brk node_modules/.bin/jest --runInBand
```

## Continuous Integration

Add to your CI pipeline (GitHub Actions, etc):

```yaml
- name: Install Node.js
  uses: actions/setup-node@v3
  with:
    node-version: '18'
    
- name: Install dependencies
  run: npm ci
  
- name: Run tests
  run: npm test
```

## Standalone Test File

For quick browser testing without Django, open:
```bash
open test_cart_javascript.html
```

This file contains:
- Real cart and filter JavaScript
- Test products and UI
- Debug panel showing state
- Console logging
