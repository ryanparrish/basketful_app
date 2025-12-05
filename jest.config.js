module.exports = {
  testEnvironment: 'jsdom',
  testMatch: [
    '**/apps/**/static/**/*.test.js',
    '**/tests/js/**/*.test.js'
  ],
  collectCoverageFrom: [
    'apps/**/static/**/*.js',
    '!apps/**/static/**/*.test.js',
    '!apps/**/static/**/vendor/**'
  ],
  coverageDirectory: 'coverage',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  moduleFileExtensions: ['js', 'json'],
  testPathIgnorePatterns: [
    '/node_modules/',
    '/venv/',
    '/.venv/',
    '/staticfiles/'
  ],
  verbose: true
};
