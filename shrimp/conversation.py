# Conversation state management and messenger bot command dispatch
from dataclasses import dataclass
from datetime import date
import logging
import re
import string
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple
import unicodedata

from shrimp.models import AnalysisNotFound, Dashboard, SegmentationError, TrayResult

logger = logging.getLogger(__name__)

YES_WORDS = {"co", "yes", "ok", "luu", "dong y", "y"}
CANCEL_WORDS = {"huy", "cancel", "thoi"}
STATUS_WORDS = {"tinh hinh", "status", "dashboard", "ket qua"}

HELP_WORDS = {"huong dan", "help", "menu", "tro giup"}
ADD_WORDS = {"chon", "them", "add"}
REMOVE_WORDS = {"bo", "xoa", "remove"}
ALL_WORDS = {"het", "tat ca", "tatca", "all"}
LEFT_OUT_WORDS = {"xem loai", "loai", "con bi loai"}

NO_PENDING_TEXT = 'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.'
HELP_TEXT = (
    "Cách dùng\n"
    "1. Gửi 1 ảnh khay tôm để đo.\n"
    '2. Nhấn "có" để lưu mẫu.\n'
    '3. Gõ "chọn 1 3" để thêm con.\n'
    '4. Gõ "bỏ 1 3" để bớt con.\n'
    "5. Gõ 1 3 5 để chỉ tính các con này.\n"
    '6. Gõ "xem loại" để xem các con bị loại.\n'
    '7. Gõ "hủy" để bỏ kết quả vừa đo.\n'
    '8. Gõ "tình hình" để xem biểu đồ các lần đo.\n'
    '9. Gõ "hướng dẫn" để xem lại trợ giúp.'
)


SORRY_TEXT = "Có lỗi khi xử lý, bạn thử lại giúp mình nhé."


class IncomingLike(Protocol):
    sender_id: str
    mid: str
    text: Optional[str]
    image_urls: List[str]


class TransportLike(Protocol):
    def send_text(
        self,
        recipient_id: str,
        text: str,
        quick_replies: Optional[List[Tuple[str, str]]] = None,
    ) -> None: ...
    def send_image(self, recipient_id: str, jpeg: bytes) -> None: ...
    def download(self, url: str) -> bytes: ...


@dataclass
class PendingAnalysis:
    analysis_id: str
    photo: bytes
    include: Optional[List[int]]
    tray: TrayResult
    updated_at: float


def _normalize(text: str) -> str:
    # Lower-case, map d-stroke to d, remove combining marks, punctuation, extra spaces
    s = text.lower()
    s = s.replace("đ", "d").replace("Đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = "".join(c for c in s if not unicodedata.category(c).startswith("P") and c not in string.punctuation)
    return " ".join(s.split())


def _quick_replies_for_tray(tray: TrayResult) -> Optional[List[Tuple[str, str]]]:
    # Return quick-reply button pairs based on tray result status and left out shrimp
    if tray.status == "ok":
        buttons = [("Lưu mẫu", "có")]
        if tray.n_left_out > 0:
            buttons.append(("Xem con bị loại", "xem loại"))
        buttons.append(("Hủy", "hủy"))
        return buttons
    elif tray.status == "too_few":
        buttons = []
        if tray.n_left_out > 0:
            buttons.append(("Xem con bị loại", "xem loại"))
        buttons.append(("Hủy", "hủy"))
        return buttons
    return None


class Conversation:
    # Manages conversational state and dispatches commands per sender
    def __init__(
        self,
        service: Any,
        transport: TransportLike,
        render: Callable[[bytes, TrayResult], bytes],
        write_reply: Callable[[TrayResult, int, Optional[bool]], str],
        write_status: Callable[[Dashboard], str],
        dashboard_url: Optional[str] = None,
        ttl_seconds: int = 1800,
        clock: Callable[[], float] = time.time,
        render_left_out: Optional[Callable[[bytes, TrayResult], bytes]] = None,
    ):
        self._render_left_out = render_left_out
        self._service = service
        self._transport = transport
        self._render = render
        self._write_reply = write_reply
        self._write_status = write_status
        self.dashboard_url = dashboard_url
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._pending: Dict[str, PendingAnalysis] = {}
        self._sender_locks: Dict[str, threading.Lock] = {}

    def _get_sender_lock(self, sender_id: str) -> threading.Lock:
        with self._lock:
            if sender_id not in self._sender_locks:
                self._sender_locks[sender_id] = threading.Lock()
            return self._sender_locks[sender_id]

    def _get_pending(self, sender_id: str) -> Optional[PendingAnalysis]:
        with self._lock:
            entry = self._pending.get(sender_id)
            if entry is not None:
                if self._clock() - entry.updated_at >= self._ttl_seconds:
                    del self._pending[sender_id]
                    return None
            return entry

    def _set_pending(self, sender_id: str, entry: PendingAnalysis) -> None:
        with self._lock:
            self._pending[sender_id] = entry

    def _drop_pending(self, sender_id: str) -> None:
        with self._lock:
            self._pending.pop(sender_id, None)

    def _safe_send_text(
        self,
        recipient_id: str,
        text: str,
        quick_replies: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        try:
            self._transport.send_text(recipient_id, text, quick_replies=quick_replies)
        except Exception:
            logger.exception("Failed to send text to %s", recipient_id)

    def _safe_send_image(self, recipient_id: str, jpeg: bytes) -> None:
        try:
            self._transport.send_image(recipient_id, jpeg)
        except Exception:
            logger.exception("Failed to send image to %s", recipient_id)

    def handle(self, incoming: IncomingLike) -> None:
        # Handle incoming message without raising exceptions
        try:
            sender_id = incoming.sender_id
            sender_lock = self._get_sender_lock(sender_id)
            with sender_lock:
                self._handle_sender(incoming)
        except Exception:
            logger.exception("Unexpected error in conversation handle")
            # the farmer always gets an answer, never silence
            self._safe_send_text(incoming.sender_id, SORRY_TEXT)

    def _apply_choice(self, sender_id: str, pending: PendingAnalysis, include: List[int]) -> None:
        # Recompute the result for exactly these shrimp, resend photo and text, remember the choice
        try:
            tray = self._service.summary(pending.analysis_id, include)
        except AnalysisNotFound:
            self._drop_pending(sender_id)
            self._safe_send_text(sender_id, "Ảnh này đã hết hạn, bạn gửi lại giúp mình nhé.")
            return

        try:
            jpeg = self._render(pending.photo, tray)
            self._safe_send_image(sender_id, jpeg)
            min_measured = self._service.settings().min_measured
            text = self._write_reply(tray, min_measured, None)
            quick_replies = _quick_replies_for_tray(tray)
            self._safe_send_text(sender_id, text, quick_replies=quick_replies)
        except Exception:
            logger.exception("Render/send failure in choice for sender %s", sender_id)
            return

        pending.include = include
        pending.tray = tray
        pending.updated_at = self._clock()
        self._set_pending(sender_id, pending)

    def _send_left_out_view(self, sender_id: str) -> None:
        # Second photo: only the shrimp that are not counted, numbered, so the farmer can add one
        pending = self._get_pending(sender_id)
        if pending is None:
            self._safe_send_text(sender_id, NO_PENDING_TEXT)
            return
        counted = set(pending.tray.included)
        left_out = [s.index + 1 for s in pending.tray.shrimp if s.index not in counted]
        if not left_out:
            self._safe_send_text(sender_id, "Không có con nào bị loại.")
            return
        if self._render_left_out is None:
            self._safe_send_text(sender_id, SORRY_TEXT)
            return
        jpeg = self._render_left_out(pending.photo, pending.tray)
        self._safe_send_image(sender_id, jpeg)
        example = " ".join(str(n) for n in left_out[:2])
        self._safe_send_text(
            sender_id,
            "Đây là các con đang bị loại (màu cam), kèm độ dài tính bằng cm. "
            f'Gõ "chọn {example}" để thêm con vào kết quả.',
            quick_replies=[("Thêm tất cả", "chọn hết"), ("Hủy", "hủy")],
        )

    def _handle_sender(self, incoming: IncomingLike) -> None:
        sender_id = incoming.sender_id

        # 1. Photo message
        if incoming.image_urls:
            self._drop_pending(sender_id)
            url = incoming.image_urls[0]
            try:
                photo = self._transport.download(url)
            except Exception:
                logger.exception("Download failure for sender %s", sender_id)
                self._safe_send_text(sender_id, "Chưa tải được ảnh. Bạn gửi lại giúp mình nhé.")
                return

            try:
                analysis_id, tray = self._service.analyze(photo)
            except SegmentationError:
                logger.exception("SegmentationError for sender %s", sender_id)
                self._safe_send_text(sender_id, "Chưa xử lý được ảnh này. Bạn chụp lại giúp mình nhé.")
                return
            except Exception:
                logger.exception("Analyze failure for sender %s", sender_id)
                self._safe_send_text(sender_id, "Chưa xử lý được ảnh này. Bạn chụp lại giúp mình nhé.")
                return

            try:
                jpeg = self._render(photo, tray)
                self._safe_send_image(sender_id, jpeg)
                min_measured = self._service.settings().min_measured
                text = self._write_reply(tray, min_measured, None)
                quick_replies = _quick_replies_for_tray(tray)
                self._safe_send_text(sender_id, text, quick_replies=quick_replies)
            except Exception:
                logger.exception("Render/send failure for sender %s", sender_id)
                return

            if tray.status in ("ok", "too_few"):
                entry = PendingAnalysis(
                    analysis_id=analysis_id,
                    photo=photo,
                    include=None,
                    tray=tray,
                    updated_at=self._clock(),
                )
                self._set_pending(sender_id, entry)
            return

        # 2. Text message or empty
        raw = incoming.text
        if raw is None or not raw.strip():
            self._safe_send_text(
                sender_id, HELP_TEXT, quick_replies=[("Tình hình", "tình hình")]
            )
            return

        raw_text = raw.strip()

        # Numbers
        if all(c in "0123456789 ,." for c in raw_text):
            pending = self._get_pending(sender_id)
            if pending is None:
                self._safe_send_text(sender_id, NO_PENDING_TEXT)
                return

            nums = [int(x) for x in re.findall(r"\d+", raw_text)]
            num_shrimp = len(pending.tray.shrimp)
            if not nums or any(n < 1 or n > num_shrimp for n in nums):
                self._safe_send_text(sender_id, f"Số con phải từ 1 đến {num_shrimp}. Ví dụ: 1 3 5.")
                return

            self._apply_choice(sender_id, pending, sorted(set(n - 1 for n in nums)))
            return

        # "chọn 1 3" adds and "bỏ 1 3" removes, on top of what is counted now
        parts = raw_text.split(None, 1)
        command = _normalize(parts[0])
        if command in ADD_WORDS or command in REMOVE_WORDS:
            pending = self._get_pending(sender_id)
            if pending is None:
                self._safe_send_text(sender_id, NO_PENDING_TEXT)
                return
            rest = parts[1] if len(parts) > 1 else ""
            num_shrimp = len(pending.tray.shrimp)
            if _normalize(rest) in ALL_WORDS:
                picked = set(range(num_shrimp))
            else:
                nums = [int(x) for x in re.findall(r"\d+", rest)]
                if not nums or any(n < 1 or n > num_shrimp for n in nums):
                    self._safe_send_text(
                        sender_id,
                        f"Số con phải từ 1 đến {num_shrimp}. Ví dụ: chọn 1 3 hoặc bỏ 2.",
                    )
                    return
                picked = set(n - 1 for n in nums)
            current = set(pending.include if pending.include is not None else pending.tray.included)
            changed = current | picked if command in ADD_WORDS else current - picked
            self._apply_choice(sender_id, pending, sorted(changed))
            return

        # Word commands
        norm = _normalize(raw_text)
        if norm in YES_WORDS:
            pending = self._get_pending(sender_id)
            if pending is None:
                self._safe_send_text(sender_id, NO_PENDING_TEXT)
                return

            try:
                tray = self._service.save(pending.analysis_id, pending.include, date.today())
            except AnalysisNotFound:
                self._drop_pending(sender_id)
                self._safe_send_text(sender_id, "Ảnh này đã hết hạn, bạn gửi lại giúp mình nhé.")
                return

            saved = (tray.status == "ok")
            min_measured = self._service.settings().min_measured
            text = self._write_reply(tray, min_measured, saved)
            if saved:
                self._safe_send_text(
                    sender_id,
                    text,
                    quick_replies=[("Tình hình", "tình hình"), ("Hướng dẫn", "hướng dẫn")],
                )
                self._drop_pending(sender_id)
            else:
                quick_replies = _quick_replies_for_tray(tray)
                self._safe_send_text(sender_id, text, quick_replies=quick_replies)
                pending.tray = tray
                self._set_pending(sender_id, pending)
            return

        if norm in HELP_WORDS:
            self._safe_send_text(
                sender_id, HELP_TEXT, quick_replies=[("Tình hình", "tình hình")]
            )
            return

        if norm in LEFT_OUT_WORDS:
            self._send_left_out_view(sender_id)
            return

        if norm in CANCEL_WORDS:
            self._drop_pending(sender_id)
            self._safe_send_text(sender_id, "Đã bỏ kết quả vừa rồi.")
            return

        if norm in STATUS_WORDS:
            dash = self._service.dashboard()
            status_text = self._write_status(dash)
            if self.dashboard_url:
                status_text = f"{status_text}\nXem biểu đồ: {self.dashboard_url}"
            self._safe_send_text(sender_id, status_text)
            return

        # Anything else
        self._safe_send_text(
            sender_id, HELP_TEXT, quick_replies=[("Tình hình", "tình hình")]
        )
