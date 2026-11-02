# Tests for SAM mask reconstruction
import base64
import numpy as np

from shrimp.sam import masks_from_records


def test_masks_from_records():
    # Rebuild full-size boolean masks from bounds and base64 raster
    ras = np.array([
        [1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0],
        [1, 1, 0, 0, 1],
        [0, 0, 1, 1, 0],
    ], dtype=np.uint8)
    b64 = base64.b64encode(ras.tobytes()).decode("ascii")
    records = [{"id": 1, "bounds": {"top": 10, "bottom": 14, "left": 20, "right": 25}, "b64": b64}]
    masks = masks_from_records(records, 100, 100)
    assert len(masks) == 1
    assert masks[0].shape == (100, 100)
    assert masks[0].dtype == bool
    assert np.array_equal(masks[0][10:14, 20:25], ras > 0)
    assert masks[0][:10, :].sum() == 0
    assert masks[0][14:, :].sum() == 0
    assert masks[0][:, :20].sum() == 0
    assert masks[0][:, 25:].sum() == 0


def test_masks_empty():
    # Return empty list when records are empty
    masks = masks_from_records([], 50, 50)
    assert masks == []
