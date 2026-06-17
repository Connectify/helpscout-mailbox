# Contributing to helpscout-mailbox

Thank you for your interest in contributing to helpscout-mailbox!

## Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Issues

- Check existing [issues](https://github.com/Connectify/helpscout-mailbox/issues) first
- Provide reproduction steps, expected vs actual behavior
- Include Python version, library version, and environment details

### Submitting Pull Requests

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes**:
   - Follow existing code style (Black, isort, flake8)
   - Add tests for new functionality
   - Update docstrings (NumPy style)
   - Run `pre-commit run --all-files` before committing
4. **Commit**: Use clear, descriptive commit messages
5. **Push**: `git push origin feature/your-feature-name`
6. **Open a Pull Request** with:
   - Description of what changed and why
   - Link to related issues
   - Test results

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/helpscout-mailbox.git
cd helpscout-mailbox

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run all linters
pre-commit run --all-files
```

### Testing

- Add tests for all new features and bug fixes
- Maintain or improve code coverage
- Use `responses` library to mock HTTP calls
- Run `pytest` to verify tests pass

```bash
# Run tests with coverage
pytest --cov=helpscout_mailbox --cov-report=term-missing

# Run specific test
pytest tests/test_client.py::test_parse_created_at
```

### Code Style

This project uses:
- **Black** (line length 120) for formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking (strict mode)
- **bandit** for security checks

Pre-commit hooks enforce these automatically.

### Docstring Style

Use NumPy-style docstrings:

```python
def example_function(param1: str, param2: int) -> bool:
    """
    Brief description of what the function does.

    Longer description if needed, explaining behavior,
    edge cases, or important details.

    Parameters
    ----------
    param1 : str
        Description of param1.
    param2 : int
        Description of param2.

    Returns
    -------
    bool
        Description of return value.

    Raises
    ------
    ValueError
        When param2 is negative.
    """
    pass
```

### Documentation

- Update README.md for user-facing changes
- Docstrings generate API docs automatically via pdoc
- Build docs locally: `pdoc -o docs/ helpscout_mailbox`

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0-or-later license.

No Contributor License Agreement (CLA) is required.

## Questions?

Open an issue or start a discussion in [GitHub Issues](https://github.com/Connectify/helpscout-mailbox/issues).
