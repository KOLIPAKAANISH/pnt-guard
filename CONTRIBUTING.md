# Contributing to PNT-Guard

Thank you for your interest in contributing to PNT-Guard! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

Please be respectful and constructive in all interactions. We are committed to providing a welcoming and inclusive experience for everyone.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/pnt-guard.git
   cd pnt-guard
   ```
3. **Add the upstream remote**:
   ```bash
   git remote add upstream https://github.com/KOLIPAKAANISH/pnt-guard.git
   ```
4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### Installation

1. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   venv\Scripts\activate  # Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install flake8 pip-audit  # Development tools
   ```

3. **Verify installation** by running tests:
   ```bash
   python -m unittest test_unit -v
   python test_api.py
   ```

### Running the Application

```bash
# Start the server
python app.py

# In another terminal, start the simulator
python signal_simulator.py

# Open http://localhost:5000/dashboard
```

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **Bug fixes** — Fix issues in existing functionality
- **New features** — Add new capabilities (see [Ideas for Contributions](#ideas-for-contributions))
- **Documentation** — Improve docs, add examples, fix typos
- **Tests** — Add or improve test coverage
- **Performance** — Optimize code for speed or memory usage
- **Refactoring** — Improve code structure without changing behavior

### Ideas for Contributions

Based on the project's known limitations and future goals:

1. **ML-based anomaly detection** — Add a machine learning module for detecting sophisticated spoofing patterns
2. **Weighted fusion** — Implement weighted averaging based on source accuracy/reliability
3. **Database backend** — Add PostgreSQL or other database support
4. **Authentication** — Add API authentication and authorization
5. **Real hardware integration** — Add NMEA sentence parsing for real GPS receivers
6. **Docker support** — Containerize the application
7. **API documentation** — Add OpenAPI/Swagger documentation
8. **Monitoring** — Add metrics and alerting capabilities

## Pull Request Process

### Before Submitting

1. **Sync your fork** with upstream:
   ```bash
   git fetch upstream
   git checkout master
   git merge upstream/master
   ```

2. **Run all tests** to ensure nothing is broken:
   ```bash
   python -m unittest test_unit -v
   python test_api.py
   python test_frontend.py
   ```

3. **Check code style**:
   ```bash
   flake8 . --max-line-length=127
   ```

### Submitting Your PR

1. **Commit your changes** with a clear message:
   ```bash
   git commit -m "Add feature: description of what you changed"
   ```
   
   Commit message format:
   - Use present tense ("Add feature" not "Added feature")
   - Use imperative mood ("Fix bug" not "Fixes bug")
   - Keep first line under 72 characters
   - Reference issues when applicable (e.g., "Fixes #42")

2. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create a Pull Request** on GitHub:
   - Use a descriptive title
   - Fill out the PR template
   - Link any related issues
   - Add screenshots for UI changes

### PR Requirements

All PRs must meet these requirements before merging:

- ✅ All CI checks pass (tests on Python 3.10, 3.11, 3.12 + linting)
- ✅ At least 1 approving review
- ✅ No merge conflicts with master
- ✅ New features include tests
- ✅ Documentation is updated (if applicable)

## Coding Standards

### Python Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide
- Maximum line length: 127 characters
- Use meaningful variable and function names
- Add docstrings to all public functions and classes

### Code Organization

- **Separation of concerns** — Keep logic in appropriate modules:
  - `ingestion.py` — Data input validation
  - `detection.py` — Anomaly detection logic
  - `fusion.py` — Position fusion algorithms
  - `models.py` — Database operations
  - `app.py` — API endpoints only

- **Configuration** — Use `config.py` for all tunable settings
- **Environment variables** — Support env vars for all configuration

### Comments

- Explain *why*, not *what* (the code shows what)
- Keep comments up-to-date with code changes
- Use comments to clarify complex algorithms

Example:
```python
# Use median instead of mean because it's resistant to outliers.
# A single spoofed reading shouldn't pull the fused position toward it.
median_lat = statistics.median(latitudes)
```

## Testing

### Running Tests

```bash
# Unit tests (fast, no database needed)
python -m unittest test_unit -v

# API tests (uses test database)
python test_api.py

# Frontend tests (checks HTML/JS structure)
python test_frontend.py
```

### Writing Tests

- Add tests for new features in the appropriate test file
- Use meaningful test names that describe what's being tested
- Test both happy paths and edge cases
- Keep tests independent (no shared state between tests)

Example:
```python
def test_fusion_excludes_anomalous_sources(self):
    """Fused position should only use healthy sources."""
    # ... test code here
```

### Test Structure

- `test_unit.py` — Pure function tests (detection, fusion logic)
- `test_api.py` — API endpoint tests
- `test_frontend.py` — Dashboard and static file tests

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Description** — Clear description of the problem
2. **Steps to reproduce** — Exact steps to trigger the bug
3. **Expected behavior** — What you expected to happen
4. **Actual behavior** — What actually happened
5. **Environment** — Python version, OS, browser (for UI issues)
6. **Screenshots** — If applicable

### Feature Requests

For feature requests, please include:

1. **Problem statement** — What problem does this solve?
2. **Proposed solution** — How should it work?
3. **Alternatives considered** — Other approaches you thought about
4. **Use cases** — Real scenarios where this would be useful

## Questions?

If you have questions about contributing:

- Open a [Discussion](https://github.com/KOLIPAKAANISH/pnt-guard/discussions) on GitHub
- Check existing issues and discussions for answers

Thank you for contributing to PNT-Guard! 🚀
