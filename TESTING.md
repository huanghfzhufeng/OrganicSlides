# Testing Framework

This document describes the test framework and how to run tests for the OrganicSlides project.

## Architecture

### Backend Testing (Python/pytest)

- **Unit Tests**: `tests/unit/`
  - `test_style_data.py` - Validates style JSON structure and data integrity
- **Integration Tests**: `tests/integration/`
  - `test_styles_api.py` - Tests API endpoints and style data integration
- **E2E Tests**: `tests/e2e/` (reserved for future)
- **Configuration**: `pytest.ini` and `tests/conftest.py`

### Frontend Testing (React/Vitest)

- **Component Tests**: `frontend/src/__tests__/`
  - `StyleSelector.test.tsx` - Tests StyleSelector component
- **Configuration**: `frontend/vitest.config.ts`
- **Setup**: `frontend/src/__tests__/setup.ts`

## Running Tests

### Backend Tests

Install test dependencies:
```bash
pip3 install --break-system-packages -r tests/requirements-test.txt
pip3 install --break-system-packages -r backend/requirements.txt
```

Run all tests:
```bash
pytest tests/ -v
```

Run only unit tests:
```bash
pytest tests/unit/ -v
```

Run with coverage:
```bash
pytest tests/ --cov=backend --cov-report=html
```

### Frontend Tests

Install dependencies:
```bash
cd frontend
npm install
```

Run tests:
```bash
npm test
```

Run tests with UI:
```bash
npm run test:ui
```

Run with coverage:
```bash
npm run test:coverage
```

## Test Coverage Goals

- **Unit Tests**: 80%+ coverage of style data validation
- **Integration Tests**: API endpoint coverage (requires services)
- **E2E Tests**: Critical user flows (future phase)

## Notes

### Backend API Tests

Integration tests for API endpoints require:
- Redis server running (default localhost:6379)
- PostgreSQL database configured
- Environment variables properly set

When these services are not available, tests will attempt to gracefully handle errors.

### Frontend Tests

Vitest is configured with:
- jsdom environment for DOM testing
- React Testing Library for component testing
- Mock implementations for browser APIs

## Test Files Structure

```
tests/
├── __init__.py
├── conftest.py                 # Shared fixtures
├── requirements-test.txt       # Test dependencies
├── unit/
│   ├── __init__.py
│   └── test_style_data.py     # Style JSON validation
├── integration/
│   ├── __init__.py
│   └── test_styles_api.py     # API and data integration
└── e2e/
    └── __init__.py

frontend/
├── vitest.config.ts           # Vitest configuration
└── src/
    └── __tests__/
        ├── setup.ts           # Test setup/mocks
        └── StyleSelector.test.tsx
```

## Test Categories

### Style Data Validation (Unit)

Tests verify:
- All JSON files are valid
- Required fields present in each style
- Color values are valid hex codes
- Tier values are within valid range
- Use cases are non-empty arrays
- Sample images exist (when available)

### API Integration (Integration)

Tests verify:
- Health check endpoint works
- Project creation accepts valid payloads
- Session IDs are valid UUIDs
- Outline retrieval works for valid sessions
- Proper 404 responses for invalid sessions

### Component Testing (Frontend)

Tests verify:
- Component renders correctly
- Style options are displayed
- Default style selection works
- Style switching functionality
- Feature tags are present
- Button click handlers are called

## Best Practices

1. **Write tests first** - Follow TDD approach
2. **Test at system boundaries** - Validate input/output
3. **Mock external services** - Don't rely on actual databases/APIs in unit tests
4. **Use fixtures** - Share common test data via conftest.py
5. **Keep tests focused** - One assertion per test where possible
6. **Clear test names** - Names should describe what is being tested
