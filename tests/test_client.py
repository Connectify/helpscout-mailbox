"""Tests for the HelpScout client."""

import json
import os
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
import responses

from helpscout_mailbox import HelpScoutClient, HelpScoutError, parse_created_at


def test_parse_created_at() -> None:
    """parse_created_at extracts UTC date from conversation createdAt field."""
    conversation = {"createdAt": "2026-06-15T14:30:00Z"}
    assert parse_created_at(conversation) == date(2026, 6, 15)


def test_parse_created_at_with_offset() -> None:
    """parse_created_at normalizes non-UTC timestamps to UTC date."""
    conversation = {"createdAt": "2026-06-15T20:30:00-05:00"}
    # 20:30 -05:00 = 01:30 UTC next day
    assert parse_created_at(conversation) == date(2026, 6, 16)


@responses.activate
def test_client_fetches_token_on_init() -> None:
    """HelpScoutClient requests OAuth2 token on initialization."""
    responses.add(
        responses.POST,
        "https://api.helpscout.net/v2/oauth2/token",
        json={"access_token": "test_token", "expires_in": 3600},
        status=200,
    )
    with patch.dict(os.environ, {"HELPSCOUT_APP_ID": "test_id", "HELPSCOUT_APP_SECRET": "test_secret"}):
        client = HelpScoutClient()
    assert client._session.headers["Authorization"] == "Bearer test_token"


@responses.activate
def test_client_raises_on_token_failure() -> None:
    """HelpScoutClient raises HelpScoutError if token request fails."""
    responses.add(
        responses.POST,
        "https://api.helpscout.net/v2/oauth2/token",
        json={"error": "invalid_client"},
        status=401,
    )
    with patch.dict(os.environ, {"HELPSCOUT_APP_ID": "bad_id", "HELPSCOUT_APP_SECRET": "bad_secret"}):
        with pytest.raises(HelpScoutError, match="OAuth2 token request failed"):
            HelpScoutClient()


def test_client_requires_app_id() -> None:
    """HelpScoutClient raises RuntimeError if HELPSCOUT_APP_ID is not set."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="HELPSCOUT_APP_ID"):
            HelpScoutClient()


def test_client_requires_app_secret() -> None:
    """HelpScoutClient raises RuntimeError if HELPSCOUT_APP_SECRET is not set."""
    with patch.dict(os.environ, {"HELPSCOUT_APP_ID": "test_id"}):
        with pytest.raises(RuntimeError, match="HELPSCOUT_APP_SECRET"):
            HelpScoutClient()


@responses.activate
def test_snooze_conversation_issues_put() -> None:
    """snooze_conversation PUTs the snooze with a UTC timestamp and clears the cache."""
    responses.add(
        responses.POST,
        "https://api.helpscout.net/v2/oauth2/token",
        json={"access_token": "test_token", "expires_in": 3600},
        status=200,
    )
    responses.add(
        responses.PUT,
        "https://api.helpscout.net/v2/conversations/7/snooze",
        status=204,
    )
    with patch.dict(os.environ, {"HELPSCOUT_APP_ID": "test_id", "HELPSCOUT_APP_SECRET": "test_secret"}):
        client = HelpScoutClient()
    client._thread_cache[7] = [{"id": 1}]
    until = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    client.snooze_conversation(7, until)
    # Verify cache was cleared
    assert 7 not in client._thread_cache
    # Verify request was made
    assert len(responses.calls) == 2  # token + snooze
    snooze_call = responses.calls[1]
    assert snooze_call.request.url == "https://api.helpscout.net/v2/conversations/7/snooze"
    assert snooze_call.request.method == "PUT"


@responses.activate
def test_close_conversation_issues_patch() -> None:
    """close_conversation PATCHes the status to closed and clears the cache."""
    responses.add(
        responses.POST,
        "https://api.helpscout.net/v2/oauth2/token",
        json={"access_token": "test_token", "expires_in": 3600},
        status=200,
    )
    responses.add(
        responses.PATCH,
        "https://api.helpscout.net/v2/conversations/7",
        status=204,
    )
    with patch.dict(os.environ, {"HELPSCOUT_APP_ID": "test_id", "HELPSCOUT_APP_SECRET": "test_secret"}):
        client = HelpScoutClient()
    client._thread_cache[7] = [{"id": 1}]
    client.close_conversation(7)
    # Verify cache was cleared
    assert 7 not in client._thread_cache
    # Verify request was made
    assert len(responses.calls) == 2  # token + close
    close_call = responses.calls[1]
    assert close_call.request.url == "https://api.helpscout.net/v2/conversations/7"
    assert close_call.request.method == "PATCH"
    assert json.loads(close_call.request.body) == {"op": "replace", "path": "/status", "value": "closed"}


@responses.activate
def test_rate_limit_retry() -> None:
    """Client retries on 429 rate limit with backoff."""
    responses.add(
        responses.POST,
        "https://api.helpscout.net/v2/oauth2/token",
        json={"access_token": "test_token", "expires_in": 3600},
        status=200,
    )
    # First request hits rate limit, second succeeds
    responses.add(
        responses.GET,
        "https://api.helpscout.net/v2/conversations/123",
        status=429,
        headers={"Retry-After": "1"},
    )
    responses.add(
        responses.GET,
        "https://api.helpscout.net/v2/conversations/123",
        json={"id": 123, "subject": "Test"},
        status=200,
    )
    with patch.dict(os.environ, {"HELPSCOUT_APP_ID": "test_id", "HELPSCOUT_APP_SECRET": "test_secret"}):
        client = HelpScoutClient()
    result = client.get_conversation(123)
    assert result["id"] == 123
    assert len(responses.calls) == 3  # token + 429 + retry success


@responses.activate
def test_token_refresh_retries_transport_error() -> None:
    """A transport-level failure during the OAuth2 token POST is retried, not fatal."""
    import requests

    responses.add(
        responses.POST, "https://api.helpscout.net/v2/oauth2/token", body=requests.exceptions.ConnectionError("boom")
    )
    responses.add(
        responses.POST,
        "https://api.helpscout.net/v2/oauth2/token",
        json={"access_token": "tok", "expires_in": 3600},
        status=200,
    )
    with (
        patch.dict(os.environ, {"HELPSCOUT_APP_ID": "id", "HELPSCOUT_APP_SECRET": "secret"}),
        patch("helpscout_mailbox.client.time.sleep"),
    ):
        client = HelpScoutClient()
    assert client._session.headers["Authorization"] == "Bearer tok"
    assert len(responses.calls) == 2  # first attempt raised, retried once


def _token_stub() -> None:
    """Register the OAuth2 token response every client init performs."""
    responses.add(
        responses.POST,
        "https://api.helpscout.net/v2/oauth2/token",
        json={"access_token": "test_token", "expires_in": 3600},
        status=200,
    )


def _client() -> HelpScoutClient:
    with patch.dict(os.environ, {"HELPSCOUT_APP_ID": "test_id", "HELPSCOUT_APP_SECRET": "test_secret"}):
        return HelpScoutClient()


@responses.activate
def test_create_conversation_posts_reply_thread() -> None:
    """create_conversation POSTs an email conversation with a reply thread and returns its id."""
    _token_stub()
    responses.add(
        responses.POST,
        "https://api.helpscout.net/v2/conversations",
        status=201,
        headers={"Resource-ID": "4242"},
    )
    client = _client()
    conv_id = client.create_conversation(24584, "Subject here", "user@example.com", "Body here")

    assert conv_id == 4242
    sent = json.loads(responses.calls[1].request.body)
    assert sent["type"] == "email"
    assert sent["mailboxId"] == 24584
    assert sent["subject"] == "Subject here"
    assert sent["customer"] == {"email": "user@example.com"}
    assert sent["status"] == "active"
    assert sent["threads"] == [{"type": "reply", "customer": {"email": "user@example.com"}, "text": "Body here"}]
    assert "tags" not in sent


@responses.activate
def test_create_conversation_draft_marks_thread_not_status() -> None:
    """draft=True flags the reply thread; it must not become a conversation status.

    HelpScout rejects `status: "draft"` (the enum is active/closed/open/pending/spam) and also
    rejects a conversation made only of note threads. Drafting is a property of the reply.
    """
    _token_stub()
    responses.add(
        responses.POST,
        "https://api.helpscout.net/v2/conversations",
        status=201,
        headers={"Resource-ID": "7"},
    )
    client = _client()
    client.create_conversation(1, "s", "user@example.com", "b", draft=True)

    sent = json.loads(responses.calls[1].request.body)
    assert sent["threads"][0]["draft"] is True
    assert sent["threads"][0]["type"] == "reply"
    assert sent["status"] == "active"


@responses.activate
def test_create_conversation_passes_tags_and_status() -> None:
    """Tags are forwarded when given, and a non-default status is honoured."""
    _token_stub()
    responses.add(
        responses.POST,
        "https://api.helpscout.net/v2/conversations",
        status=201,
        headers={"Resource-ID": "9"},
    )
    client = _client()
    client.create_conversation(1, "s", "user@example.com", "b", tags=["alpha", "beta"], status="pending")

    sent = json.loads(responses.calls[1].request.body)
    assert sent["tags"] == ["alpha", "beta"]
    assert sent["status"] == "pending"


@responses.activate
def test_create_conversation_without_resource_id_raises() -> None:
    """A creation response with no Resource-ID header is an error, not a silent 0."""
    _token_stub()
    responses.add(responses.POST, "https://api.helpscout.net/v2/conversations", status=201)
    client = _client()
    with pytest.raises(HelpScoutError, match="Resource-ID"):
        client.create_conversation(1, "s", "user@example.com", "b")
