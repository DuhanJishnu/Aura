# Contributing to Shopper

Thank you for contributing to Shopper!

## Development Setup

1. **Backend**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # or source .venv/bin/activate on Unix
   pip install -r requirements-dev.txt
   python -m data.seed
   ```

2. **Frontend**:
   ```bash
   cd web
   npm install
   ```

## Running Verification

Before opening a pull request, ensure all tests and linter checks pass:

- **Backend**:
  ```bash
  ruff check .
  pytest -q
  ```

- **Frontend**:
  ```bash
  cd web
  npm run typecheck
  npm test
  npm run build
  ```

## Code Guidelines
- Keep decisions in Python and wording in the LLM.
- Grounding: Never display unvalidated model outputs for prices, specs, or catalog products.
- Maintain existing test suites and add tests for any new rules or category behaviors.
