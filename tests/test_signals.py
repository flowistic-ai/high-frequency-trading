import pytest
from crypto_hft_tool.signals import RollingZScore

def test_rolling_zscore_constant():
    rz = RollingZScore(window_size=5)
    for v in [1, 1, 1, 1, 1]:
        z = rz.add(v)
    # All values are identical ⇒ std=0 ⇒ z should be 0
    assert z == 0.0

def test_rolling_zscore_variance():
    rz = RollingZScore(window_size=3)
    values = [1, 2, 3]
    zs = [rz.add(v) for v in values]
    # For the third point: values=[1,2,3] ⇒ mean=2, std≈0.816 ⇒ z≈(3−2)/0.816≈1.225
    assert pytest.approx(zs[-1], rel=1e-2) == 1.2247
