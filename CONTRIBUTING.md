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
1. **Create a feature branch**: `git checkout -b feature/your-feature-name`
1. **Make your changes**:
   - Follow existing code style (Black, isort, flake8)
   - Add tests for new functionality
   - Update docstrings (NumPy style)
   - Run `pre-commit run --all-files` before committing
1. **Commit**: Use clear, descriptive commit messages
1. **Push**: `git push origin feature/your-feature-name`
1. **Open a Pull Request** with:
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

### Where New Methods Go

`HelpScoutClient` is organised into groups, each marked by a comment banner, and the generated API docs list methods in **source order**. A method appended to the end of the class therefore lands at the end of the documentation, away from everything it belongs with — which is how the listing got scrambled in the first place.

So put a new method inside the group it belongs to:

| Group | Covers |
| --- | --- |
| `# ---- internals ----` | auth, transport, request helpers — anything underscore-prefixed |
| `# ---- conversations: create and read ----` | opening a conversation, fetching or searching for one |
| `# ---- threads: read ----` | reading threads, bodies, attachments |
| `# ---- threads: write ----` | adding notes and replies, editing and sending them |
| `# ---- conversation state ----` | status, snoozing, tags |

If a method genuinely does not fit any of them, add a new group with its own banner rather than appending to the end, and say so in the pull request — a new group is a signal the client has grown a new area of responsibility.

The grouping is also listed in the `HelpScoutClient` class docstring, which renders above the members on the docs page. Update it when you add or move a method.

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
- Build docs locally: `pdoc -t templates/ -o docs/ helpscout_mailbox`

The `-t templates/` is not optional — `templates/module.html.jinja2` overrides pdoc's `nav_members` macro to group the sidebar under labelled headings. Building without it produces a flat list and will not match what CI publishes.

#### Adding a method to the sidebar groups

pdoc hands Jinja the names, kinds and docstrings of members, but **not** source comments, so the group banners in `client.py` are invisible to the template. Group membership is therefore declared separately, in `NAV_GROUPS` at the top of `templates/module.html.jinja2`:

```jinja
{% set NAV_GROUPS = [
    ("Conversations", ["create_conversation", "get_conversation", "search_conversations"]),
    ...
] %}
```

When you add a public method, add its name to the matching list. If you forget, the method still appears — under an **Other** heading in a different colour, at the bottom of the class. That is deliberate: a missing entry should be visible on the page rather than silently dropped or attached to the wrong group. If you see "Other" on the published docs, something needs adding to `NAV_GROUPS`.

Private methods (underscore-prefixed) are hidden by pdoc and need no entry.

So a new public method takes three edits: the method in its group in `client.py`, its name in the class docstring's group list, and its name in `NAV_GROUPS`.

## License

By contributing, you agree that your contributions will be licensed under the BSD-3-Clause license.

No Contributor License Agreement (CLA) is required.

## Questions?

Open an issue or start a discussion in [GitHub Issues](https://github.com/Connectify/helpscout-mailbox/issues).
