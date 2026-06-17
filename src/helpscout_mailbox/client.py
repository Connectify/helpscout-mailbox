"""Minimal HelpScout Mailbox API v2 client (client-credentials OAuth2)."""

import base64
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator

import requests

BASE_URL = "https://api.helpscout.net/v2"
TOKEN_URL = f"{BASE_URL}/oauth2/token"  # nosec B105 - URL, not a password
TIMEOUT = 30
APP_ID_ENVVAR = "HELPSCOUT_APP_ID"
APP_SECRET_ENVVAR = "HELPSCOUT_APP_SECRET"  # nosec B105 - env var name, not a password

logger = logging.getLogger(__name__)


class HelpScoutError(Exception):
    """Raised when the HelpScout API returns an error."""


def _getenv_or_fail(envvar: str) -> str:
    """
    Get a value from an environment variable or raise an error.

    Parameters
    ----------
    envvar : str
        The name of the environment variable to retrieve.

    Returns
    -------
    str
        The value of the environment variable.

    Raises
    ------
    RuntimeError
        If the environment variable is not set.
    """
    value = os.getenv(envvar)
    if value is None:
        raise RuntimeError(f"Set the {envvar} environment variable (HelpScout 'My Apps' OAuth2 credentials).")
    return value


def parse_created_at(conversation: dict[str, Any]) -> date:
    """
    Extract the creation date of a HelpScout conversation.

    Parameters
    ----------
    conversation : dict[str, Any]
        A conversation object from the v2 API.

    Returns
    -------
    date
        The UTC date the conversation was created.
    """
    created = datetime.fromisoformat(conversation["createdAt"].replace("Z", "+00:00"))
    return created.astimezone(timezone.utc).date()


class HelpScoutClient:
    """
    Client for the HelpScout Mailbox API v2.

    Authenticates with the OAuth2 client-credentials flow using the app id and
    secret from the ``HELPSCOUT_APP_ID`` / ``HELPSCOUT_APP_SECRET`` environment
    variables (create the app under HelpScout → Your Profile → My Apps).
    """

    def __init__(self) -> None:
        self._app_id = _getenv_or_fail(APP_ID_ENVVAR)
        self._app_secret = _getenv_or_fail(APP_SECRET_ENVVAR)
        self._session = requests.Session()
        self._token_expires_at = 0.0
        self._thread_cache: dict[int, list[dict[str, Any]]] = {}
        self._refresh_token()

    def _refresh_token(self) -> None:
        """
        Fetch a fresh access token and store it on the session.

        Raises
        ------
        HelpScoutError
            If the token request fails.
        """
        response = self._session.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials", "client_id": self._app_id, "client_secret": self._app_secret},
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            raise HelpScoutError(f"OAuth2 token request failed ({response.status_code}): {response.text}")
        payload = response.json()
        self._session.headers["Authorization"] = f"Bearer {payload['access_token']}"
        self._token_expires_at = time.time() + payload.get("expires_in", 3600) - 60

    def _send(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> requests.Response:
        """
        Issue an authenticated request, handling 401 refresh and 429 backoff.

        Parameters
        ----------
        method : str
            HTTP method, e.g. ``get`` or ``post``.
        path : str
            Path under the v2 base URL, e.g. ``/conversations``.
        params : dict[str, Any] | None
            Query string parameters.
        body : dict[str, Any] | None
            JSON request body.

        Returns
        -------
        requests.Response
            The successful (2xx) response.

        Raises
        ------
        HelpScoutError
            If the API returns a non-2xx response after retries.
        """
        if time.time() >= self._token_expires_at:
            self._refresh_token()
        last_exc: requests.exceptions.RequestException | None = None
        for attempt in range(5):
            # Transport-level failures (RemoteDisconnected, timeouts, reset
            # connections) raise instead of returning a response, so they must
            # be caught here or they escape the status-code retries below and
            # abort the run. They are transient, so retry with backoff (#5715).
            try:
                response = self._session.request(method, f"{BASE_URL}{path}", params=params, json=body, timeout=TIMEOUT)
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                wait = 5 * (attempt + 1)
                logger.warning(
                    f"HelpScout request error on {path}: {exc}; retrying in {wait}s (attempt {attempt + 1}/5)"
                )
                time.sleep(wait)
                continue
            if response.status_code == 429:
                wait = int(response.headers.get("Retry-After", "10"))
                logger.warning(f"HelpScout rate limit hit; sleeping {wait}s (attempt {attempt + 1}/5)")
                time.sleep(wait)
                continue
            if response.status_code == 401:
                self._refresh_token()
                continue
            if response.status_code >= 500:
                wait = 5 * (attempt + 1)
                logger.warning(
                    f"HelpScout {response.status_code} on {path}; retrying in {wait}s (attempt {attempt + 1}/5)"
                )
                time.sleep(wait)
                continue
            if response.status_code >= 400:
                raise HelpScoutError(f"{method.upper()} {path} failed ({response.status_code}): {response.text}")
            return response
        raise HelpScoutError(
            f"{method.upper()} {path} still failing (429/5xx/transport) after 5 attempts"
        ) from last_exc

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Issue an authenticated GET request and decode the JSON response.

        Parameters
        ----------
        path : str
            Path under the v2 base URL, e.g. ``/conversations``.
        params : dict[str, Any] | None
            Query string parameters.

        Returns
        -------
        dict[str, Any]
            The decoded JSON response.

        Raises
        ------
        HelpScoutError
            If the API returns a non-2xx response after retries.
        """
        payload: dict[str, Any] = self._send("get", path, params=params).json()
        return payload

    def search_conversations(self, query: str, since: date) -> Iterator[dict[str, Any]]:
        """
        Iterate conversations matching a search query, newest first.

        Pages are harvested until a full page is older than ``since`` (the
        ``after:`` search operator is unreliable, so we filter client-side).

        Parameters
        ----------
        query : str
            HelpScout search query, e.g. ``subject:"Customer Invoice"``.
        since : date
            Only yield conversations created on/after this date.

        Yields
        ------
        dict[str, Any]
            Conversation objects (id, number, subject, primaryCustomer, ...).
        """
        page = 1
        while True:
            payload = self._get(
                "/conversations",
                params={
                    "query": f"({query})",
                    "status": "all",
                    "sortField": "createdAt",
                    "sortOrder": "desc",
                    "page": page,
                },
            )
            conversations = payload.get("_embedded", {}).get("conversations", [])
            if not conversations:
                return
            any_recent = False
            for conversation in conversations:
                if parse_created_at(conversation) >= since:
                    any_recent = True
                    yield conversation
            total_pages = payload.get("page", {}).get("totalPages", page)
            if not any_recent or page >= total_pages:
                return
            page += 1

    def conversation_threads(self, conversation_id: int) -> list[dict[str, Any]]:
        """
        Fetch (and cache) the threads of a conversation.

        Parameters
        ----------
        conversation_id : int
            The HelpScout conversation id.

        Returns
        -------
        list[dict[str, Any]]
            Thread objects, including embedded attachment metadata.
        """
        if conversation_id not in self._thread_cache:
            payload = self._get(f"/conversations/{conversation_id}/threads")
            self._thread_cache[conversation_id] = payload.get("_embedded", {}).get("threads", [])
        return self._thread_cache[conversation_id]

    def conversation_body(self, conversation_id: int) -> str:
        """
        Fetch the concatenated thread bodies (HTML) of a conversation.

        Parameters
        ----------
        conversation_id : int
            The HelpScout conversation id.

        Returns
        -------
        str
            All thread bodies joined by newlines (customer email HTML included).
        """
        threads = self.conversation_threads(conversation_id)
        return "\n".join(thread.get("body", "") for thread in threads if thread.get("body"))

    def attachment_data(self, conversation_id: int, attachment_id: int) -> bytes:
        """
        Download an attachment's raw bytes.

        Parameters
        ----------
        conversation_id : int
            The HelpScout conversation id.
        attachment_id : int
            The attachment id (from a thread's embedded attachment metadata).

        Returns
        -------
        bytes
            The decoded attachment content.
        """
        payload = self._get(f"/conversations/{conversation_id}/attachments/{attachment_id}/data")
        return base64.b64decode(payload["data"])

    def get_conversation(self, conversation_id: int) -> dict[str, Any]:
        """
        Fetch a conversation object.

        Parameters
        ----------
        conversation_id : int
            The HelpScout conversation id.

        Returns
        -------
        dict[str, Any]
            The conversation (id, number, subject, primaryCustomer, tags, ...).
        """
        return self._get(f"/conversations/{conversation_id}")

    def _created_resource_id(self, response: requests.Response, action: str) -> int:
        """
        Extract the ``Resource-ID`` header of a creation response.

        Parameters
        ----------
        response : requests.Response
            The 201 response of a create request.
        action : str
            Description of the request, for the error message.

        Returns
        -------
        int
            The id of the created resource.

        Raises
        ------
        HelpScoutError
            If the response carries no ``Resource-ID`` header.
        """
        resource_id = response.headers.get("Resource-ID")
        if resource_id is None:
            raise HelpScoutError(f"{action} returned no Resource-ID header")
        return int(resource_id)

    def add_note(self, conversation_id: int, text: str) -> int:
        """
        Create a note thread on a conversation.

        Parameters
        ----------
        conversation_id : int
            The HelpScout conversation id.
        text : str
            The note body (HTML allowed).

        Returns
        -------
        int
            The id of the created note thread.
        """
        response = self._send("post", f"/conversations/{conversation_id}/notes", body={"text": text})
        self._thread_cache.pop(conversation_id, None)
        return self._created_resource_id(response, f"Note on conversation {conversation_id}")

    def update_thread_text(self, conversation_id: int, thread_id: int, text: str) -> None:
        """
        Replace the body of an existing thread (e.g. a note).

        Parameters
        ----------
        conversation_id : int
            The HelpScout conversation id.
        thread_id : int
            The id of the thread to update.
        text : str
            The new thread body (HTML allowed).
        """
        self._send(
            "patch",
            f"/conversations/{conversation_id}/threads/{thread_id}",
            body={"op": "replace", "path": "/text", "value": text},
        )
        self._thread_cache.pop(conversation_id, None)

    def create_reply(self, conversation_id: int, customer_id: int, text: str, draft: bool = False) -> int:
        """
        Create a reply thread addressed to a customer.

        Parameters
        ----------
        conversation_id : int
            The HelpScout conversation id.
        customer_id : int
            The HelpScout customer id the reply is addressed to.
        text : str
            The reply body (HTML allowed).
        draft : bool
            When ``True``, save the reply as a draft instead of sending it.

        Returns
        -------
        int
            The id of the created reply thread.
        """
        response = self._send(
            "post",
            f"/conversations/{conversation_id}/reply",
            body={"customer": {"id": customer_id}, "text": text, "draft": draft},
        )
        self._thread_cache.pop(conversation_id, None)
        return self._created_resource_id(response, f"Reply on conversation {conversation_id}")

    def send_draft(self, conversation_id: int, thread_id: int) -> None:
        """
        Send a previously created draft reply.

        The Mailbox API cannot publish a draft directly: a draft is sent by
        scheduling it (the "Send Later" feature) and then publishing that
        schedule immediately. Publishing turns the draft into a real reply and
        delivers it to the customer, preserving any edits made to the draft in
        HelpScout. The schedule time is a couple of minutes out only to satisfy
        the "future" requirement; the publish sends it right away.

        Parameters
        ----------
        conversation_id : int
            The HelpScout conversation id.
        thread_id : int
            The id of the draft thread to send.
        """
        scheduled_for = (datetime.now(timezone.utc) + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._send(
            "put",
            f"/conversations/{conversation_id}/threads/{thread_id}/schedule",
            body={"scheduledFor": scheduled_for, "unscheduleOnCustomerReply": False},
        )
        self._send(
            "patch",
            f"/conversations/{conversation_id}/threads/{thread_id}/schedule",
            body={"op": "replace", "path": "/state", "value": "published"},
        )
        self._thread_cache.pop(conversation_id, None)

    def snooze_conversation(
        self, conversation_id: int, snoozed_until: datetime, unsnooze_on_customer_reply: bool = True
    ) -> None:
        """
        Snooze a conversation until a future time.

        Hides the conversation from the active queue until ``snoozed_until``,
        when HelpScout resurfaces it. The API requires a future timestamp.

        Parameters
        ----------
        conversation_id : int
            The HelpScout conversation id.
        snoozed_until : datetime
            When the conversation should wake up (must be in the future); sent
            as an ISO-8601 UTC instant.
        unsnooze_on_customer_reply : bool
            When ``True``, an incoming customer reply wakes the conversation
            early (e.g. a provider following up about a failed charge).
        """
        self._send(
            "put",
            f"/conversations/{conversation_id}/snooze",
            body={
                "snoozedUntil": snoozed_until.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "unsnoozeOnCustomerReply": unsnooze_on_customer_reply,
            },
        )
        self._thread_cache.pop(conversation_id, None)

    def add_tags(self, conversation_id: int, tags: list[str]) -> None:
        """
        Add tags to a conversation, preserving its existing tags.

        The tags endpoint replaces the full tag set, so the current tags are
        fetched first and the new ones appended.

        Parameters
        ----------
        conversation_id : int
            The HelpScout conversation id.
        tags : list[str]
            Tag names to add; already-present tags are not duplicated.
        """
        conversation = self.get_conversation(conversation_id)
        current = [tag["tag"] if isinstance(tag, dict) else str(tag) for tag in conversation.get("tags", [])]
        merged = current + [tag for tag in tags if tag not in current]
        self._send("put", f"/conversations/{conversation_id}/tags", body={"tags": merged})
