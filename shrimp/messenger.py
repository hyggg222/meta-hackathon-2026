# Messenger webhook router and Graph API transport
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import hmac
import json
import logging
import threading
from typing import Any, Callable, FrozenSet, List, Optional
import urllib.parse
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Incoming:
    sender_id: str
    mid: str
    text: Optional[str]
    image_urls: List[str]


@dataclass(frozen=True)
class MessengerConfig:
    verify_token: str
    app_secret: str
    allowed_ids: FrozenSet[str]


class TransportError(Exception):
    # Exception raised on Graph API or transport failures
    pass


class _MidCache:
    # Thread-safe bounded cache tracking seen message ids
    def __init__(self, capacity: int = 1000) -> None:
        self._capacity = capacity
        self._items = OrderedDict()
        self._lock = threading.Lock()

    def add(self, mid: str) -> bool:
        # Record mid returning True if new or False if duplicate
        with self._lock:
            if mid in self._items:
                return False
            self._items[mid] = True
            if len(self._items) > self._capacity:
                self._items.popitem(last=False)
            return True


def _split_text(text: str, limit: int = 1900) -> List[str]:
    # Split text into chunks bounded by limit, breaking at newlines
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    current_lines: List[str] = []
    current_len = 0
    for line in text.split("\n"):
        line_len = len(line)
        needed = line_len if not current_lines else line_len + 1
        if current_lines and current_len + needed > limit:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_len = 0
        if line_len > limit:
            for start in range(0, line_len, limit):
                chunks.append(line[start : start + limit])
        else:
            current_lines.append(line)
            current_len += line_len if len(current_lines) == 1 else line_len + 1
    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks


class GraphTransport:
    # Graph API transport for sending messages and downloading attachments
    def __init__(
        self,
        page_token: str,
        session: Any = None,
        version: str = "v21.0",
    ) -> None:
        # Initialise transport with page token, session and API version
        self.page_token = page_token
        self.session = session if session is not None else requests.Session()
        self.version = version

    def _strip_token(self, msg: str) -> str:
        # Remove page token from error message text
        if self.page_token:
            if self.page_token in msg:
                msg = msg.replace(self.page_token, "[REDACTED]")
            quoted = urllib.parse.quote(self.page_token)
            if quoted in msg:
                msg = msg.replace(quoted, "[REDACTED]")
        return msg

    def _url(self, path: str) -> str:
        # Construct Graph API URL
        return f"https://graph.facebook.com/{self.version}/{path}"

    def send_text(self, recipient_id: str, text: str) -> None:
        # Send text to recipient splitting messages longer than 1900 chars
        url = self._url("me/messages")
        params = {"access_token": self.page_token}
        chunks = _split_text(text, 1900)
        for chunk in chunks:
            payload = {
                "recipient": {"id": recipient_id},
                "messaging_type": "RESPONSE",
                "message": {"text": chunk},
            }
            try:
                resp = self.session.post(
                    url,
                    params=params,
                    json=payload,
                )
            except Exception as exc:
                msg = self._strip_token(f"Failed to send text: {exc}")
                raise TransportError(msg) from exc

            if resp.status_code < 200 or resp.status_code >= 300:
                msg = self._strip_token(
                    f"Send text failed with status {resp.status_code}: {resp.text}"
                )
                raise TransportError(msg)

    def send_image(self, recipient_id: str, jpeg: bytes) -> None:
        # Send JPEG image via multipart form upload to Graph API
        url = self._url("me/messages")
        params = {"access_token": self.page_token}
        data = {
            "recipient": json.dumps({"id": recipient_id}),
            "message": json.dumps(
                {"attachment": {"type": "image", "payload": {"is_reusable": False}}}
            ),
        }
        files = {
            "filedata": ("reply.jpg", jpeg, "image/jpeg"),
        }
        try:
            resp = self.session.post(
                url,
                params=params,
                data=data,
                files=files,
            )
        except Exception as exc:
            msg = self._strip_token(f"Failed to send image: {exc}")
            raise TransportError(msg) from exc

        if resp.status_code < 200 or resp.status_code >= 300:
            msg = self._strip_token(
                f"Send image failed with status {resp.status_code}: {resp.text}"
            )
            raise TransportError(msg)

    def download(self, url: str) -> bytes:
        # Download attachment refusing non-http/https and payloads over 15 MB
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise TransportError(f"Unsupported URL scheme: {parsed.scheme}")

        max_bytes = 15 * 1024 * 1024
        resp = None
        try:
            resp = self.session.get(url, stream=True, timeout=20)
            if resp.status_code < 200 or resp.status_code >= 300:
                msg = self._strip_token(
                    f"Download failed with status {resp.status_code}: {resp.text}"
                )
                raise TransportError(msg)

            content_length = resp.headers.get("Content-Length")
            if content_length is not None:
                try:
                    if int(content_length) > max_bytes:
                        raise TransportError("File exceeds 15 MB limit")
                except ValueError:
                    pass

            chunks: List[bytes] = []
            total = 0
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise TransportError("File exceeds 15 MB limit")
                chunks.append(chunk)
            return b"".join(chunks)
        except TransportError:
            raise
        except Exception as exc:
            msg = self._strip_token(f"Failed to download {url}: {exc}")
            raise TransportError(msg) from exc
        finally:
            if resp is not None:
                resp.close()


async def _raw_body(request: Request) -> bytes:
    # Read raw request body from request stream
    return await request.body()


def create_messenger_router(
    config: MessengerConfig,
    handler: Callable[[Incoming], None],
    executor: Optional[Any] = None,
) -> APIRouter:
    # Build FastAPI router for Messenger webhook verification and events
    router = APIRouter()
    pool = executor if executor is not None else ThreadPoolExecutor(max_workers=4)
    mid_cache = _MidCache(1000)

    @router.get("/webhook/messenger")
    def get_webhook(request: Request) -> Response:
        # Handle Facebook webhook verification challenge
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if (
            mode == "subscribe"
            and token is not None
            and hmac.compare_digest(token, config.verify_token)
        ):
            return PlainTextResponse(challenge or "", status_code=200)
        return PlainTextResponse("Forbidden", status_code=403)

    @router.post("/webhook/messenger")
    def post_webhook(
        request: Request,
        body: bytes = Depends(_raw_body),
    ) -> Response:
        # Validate webhook signature and dispatch messaging events
        sig_header = request.headers.get("x-hub-signature-256")
        if not sig_header or not sig_header.startswith("sha256="):
            return PlainTextResponse("Forbidden", status_code=403)

        expected = "sha256=" + hmac.new(
            config.app_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(sig_header, expected):
            return PlainTextResponse("Forbidden", status_code=403)

        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            return JSONResponse(status_code=200, content={"status": "ok"})

        if not isinstance(data, dict) or data.get("object") != "page":
            return JSONResponse(status_code=200, content={"status": "ok"})

        entries = data.get("entry")
        if not isinstance(entries, list):
            return JSONResponse(status_code=200, content={"status": "ok"})

        def _safe_dispatch(item: Incoming) -> None:
            # Execute message handler catching and logging exceptions
            try:
                handler(item)
            except Exception:
                logger.exception("Error handling messenger message %s", item.mid)

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            messaging = entry.get("messaging")
            if not isinstance(messaging, list):
                continue
            for item in messaging:
                if not isinstance(item, dict):
                    continue
                sender = item.get("sender")
                if not isinstance(sender, dict):
                    continue
                sender_id = sender.get("id")
                if not isinstance(sender_id, str) or sender_id not in config.allowed_ids:
                    continue

                msg = item.get("message")
                if not isinstance(msg, dict):
                    continue
                if msg.get("is_echo") is True:
                    continue
                mid = msg.get("mid")
                if not isinstance(mid, str) or not mid:
                    continue

                if not mid_cache.add(mid):
                    continue

                text = msg.get("text")
                if text is not None and not isinstance(text, str):
                    text = None

                image_urls: List[str] = []
                attachments = msg.get("attachments")
                if isinstance(attachments, list):
                    for att in attachments:
                        if isinstance(att, dict) and att.get("type") == "image":
                            payload = att.get("payload")
                            if isinstance(payload, dict):
                                url = payload.get("url")
                                if isinstance(url, str):
                                    image_urls.append(url)

                incoming = Incoming(
                    sender_id=sender_id,
                    mid=mid,
                    text=text,
                    image_urls=image_urls,
                )
                pool.submit(_safe_dispatch, incoming)

        return JSONResponse(status_code=200, content={"status": "ok"})

    return router
