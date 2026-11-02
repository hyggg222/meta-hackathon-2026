# Test fixtures and fake segmenter
from typing import Dict, List, Optional
import numpy as np
import pytest


class FakeSegmenter:
    # Fake segmenter callable for tests
    def __init__(
        self,
        responses: Optional[Dict[str, List[np.ndarray]]] = None,
        exc: Optional[Exception] = None,
    ):
        self.responses = responses or {}
        self.exc = exc

    def __call__(self, photo: bytes, prompt: str) -> List[np.ndarray]:
        # Return mocked masks or raise exception
        if self.exc is not None:
            raise self.exc
        return self.responses.get(prompt, [])


@pytest.fixture
def fake_photo() -> bytes:
    # Sample byte payload for tests
    return b"dummy_photo_bytes"
