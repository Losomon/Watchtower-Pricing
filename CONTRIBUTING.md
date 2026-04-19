# Contributing to Watchtower Pricing

Thank you for your interest in contributing!

## How to Contribute

### Reporting Bugs

1. Check if the bug already exists in [issues](https://github.com/Losomon/Watchtower-Pricing/issues)
2. If not, open a new issue with:
   - Clear title describing the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, Python version, etc.)

### Suggesting Features

1. Search existing proposals first
2. Open a new issue with:
   - Clear title: "Feature: [your idea]"
   - Use case and rationale
   - Proposed implementation (if any)

### Pull Requests

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add tests if applicable
5. Ensure tests pass: `python -m pytest backend/tests/`
6. Commit with clear messages
7. Push and open a PR

### Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints where possible
- Keep functions under 100 lines
- Document public APIs

### Development Setup

```bash
git clone https://github.com/Losomon/Watchtower-Pricing
cd Watchtower-Pricing
pip install -r backend/requirements.txt
```

### Running Tests

```bash
python -m pytest backend/tests/ -v
```

## Questions?

Open an issue or start a discussion.