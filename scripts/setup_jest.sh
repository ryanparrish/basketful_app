#!/bin/bash

# Setup script for Jest testing environment

echo "Setting up JavaScript testing with Jest..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Node.js is not installed. Please install it first:"
    echo ""
    echo "macOS (with Homebrew):"
    echo "  brew install node"
    echo ""
    echo "Or download from: https://nodejs.org/"
    exit 1
fi

echo "✓ Node.js version: $(node --version)"
echo "✓ NPM version: $(npm --version)"

# Install dependencies
echo ""
echo "Installing Jest and testing dependencies..."
npm install

# Run tests
echo ""
echo "Running tests..."
npm test

echo ""
echo "Setup complete! You can now run:"
echo "  npm test              # Run all tests"
echo "  npm run test:watch    # Run tests in watch mode"
echo "  npm run test:coverage # Run with coverage report"
