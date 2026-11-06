# nldate

Parse natural-language date strings into `datetime.date` objects.

## Usage

```python
from datetime import date
from nldate import parse

parse("5 days before December 1st, 2025")
parse("next Tuesday", today=date(2025, 11, 6))
parse("1 year and 2 months after yesterday", today=date(2025, 11, 6))
```

## Development

```bash
uv sync
uv run pytest
uv run mypy src/
uv run ruff check
uv run ruff format --check
```
