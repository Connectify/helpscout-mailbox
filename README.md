# helpscout-mailbox

[![PyPI](https://img.shields.io/pypi/v/helpscout-mailbox.svg)](https://pypi.org/project/helpscout-mailbox/)
[![Python Versions](https://img.shields.io/pypi/pyversions/helpscout-mailbox.svg)](https://pypi.org/project/helpscout-mailbox/)
[![License](https://img.shields.io/pypi/l/helpscout-mailbox.svg)](https://github.com/Connectify/helpscout-mailbox/blob/main/LICENSE)
[![Tests](https://github.com/Connectify/helpscout-mailbox/actions/workflows/test.yml/badge.svg)](https://github.com/Connectify/helpscout-mailbox/actions/workflows/test.yml)

A Python client for the [HelpScout Mailbox API v2](https://developer.helpscout.com/mailbox-api/).

## Features

- **OAuth2 client-credentials authentication** with automatic token refresh
- **Retry logic** for rate limiting (429), server errors (5xx), and transient failures
- **Conversation management**: search, read, snooze, tag
- **Thread operations**: notes, replies, drafts, attachments
- **Clean API** with type hints and comprehensive docstrings

## Installation

```bash
pip install helpscout-mailbox
```

## Quick Start

```python
import os
from datetime import date, datetime, timedelta, timezone
from helpscout_mailbox import HelpScoutClient

# Set credentials (create app at HelpScout → Your Profile → My Apps)
os.environ["HELPSCOUT_APP_ID"] = "your-app-id"
os.environ["HELPSCOUT_APP_SECRET"] = "your-app-secret"

# Initialize client (fetches OAuth2 token automatically)
client = HelpScoutClient()

# Search conversations
for conv in client.search_conversations('subject:"Invoice"', since=date(2026, 6, 1)):
    print(f"#{conv['number']}: {conv['subject']}")

# Get conversation details
conversation = client.get_conversation(12345)
print(conversation["subject"])

# Add a note
client.add_note(12345, "Processed invoice #INV-001")

# Snooze until tomorrow
tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
client.snooze_conversation(12345, tomorrow)

# Add tags
client.add_tags(12345, ["billing", "processed"])
```

## API Coverage

### Conversations
- `search_conversations(query, since)` - Search with client-side date filtering
- `get_conversation(conversation_id)` - Fetch conversation details
- `snooze_conversation(conversation_id, snoozed_until)` - Snooze conversation
- `add_tags(conversation_id, tags)` - Add tags (preserves existing)

### Threads
- `conversation_threads(conversation_id)` - List threads (cached)
- `conversation_body(conversation_id)` - Concatenated HTML body
- `add_note(conversation_id, text)` - Create note thread
- `update_thread_text(conversation_id, thread_id, text)` - Update thread body
- `create_reply(conversation_id, customer_id, text, draft)` - Create reply
- `send_draft(conversation_id, thread_id)` - Send draft reply

### Attachments
- `attachment_data(conversation_id, attachment_id)` - Download attachment bytes

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HELPSCOUT_APP_ID` | Yes | OAuth2 app ID (from My Apps) |
| `HELPSCOUT_APP_SECRET` | Yes | OAuth2 app secret (from My Apps) |

## Authentication

The client uses OAuth2 client-credentials flow. Create an app at **HelpScout → Your Profile → My Apps**:

1. Click "Create My App"
2. Give it a name (e.g., "Invoice Processor")
3. Copy the **App ID** and **App Secret**
4. Set them as environment variables

The client automatically:
- Fetches access tokens on initialization
- Refreshes tokens before expiry
- Retries on 401 with fresh token

## Error Handling

All API errors raise `HelpScoutError`:

```python
from helpscout_mailbox import HelpScoutClient, HelpScoutError

try:
    client = HelpScoutClient()
    client.get_conversation(99999)
except HelpScoutError as e:
    print(f"API error: {e}")
```

The client automatically retries:
- **429 rate limits** (respects `Retry-After` header)
- **5xx server errors** (exponential backoff)
- **Transport failures** (connection resets, timeouts)

## Documentation

Full API documentation: [https://connectify.github.io/helpscout-mailbox/](https://connectify.github.io/helpscout-mailbox/)

HelpScout API reference: [https://developer.helpscout.com/mailbox-api/](https://developer.helpscout.com/mailbox-api/)

## Development

```bash
# Clone repository
git clone https://github.com/Connectify/helpscout-mailbox.git
cd helpscout-mailbox

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linters
pre-commit run --all-files

# Build documentation
pip install -e ".[docs]"
pdoc -o docs/ helpscout_mailbox
```

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

GPL-3.0-or-later. See [COPYING](COPYING) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/Connectify/helpscout-mailbox/issues)
- **HelpScout API Docs**: [developer.helpscout.com](https://developer.helpscout.com/mailbox-api/)
