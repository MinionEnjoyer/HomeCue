import pytest

from homecue.const import EFFECT_BREATHING, EFFECT_COLOR_CYCLE, EFFECT_RAINBOW, EFFECT_STATIC
from homecue.effects.engine import EffectsEngine, _ActiveEffect


def active(name: str, brightness: int = 255) -> _ActiveEffect:
    return _ActiveEffect(name, 120, 60, 30, brightness, 0)


def test_static_effect_sets_scaled_color_once() -> None:
    calls: list[tuple[str, int, int, int]] = []
    engine = EffectsEngine(lambda *args: calls.append(args), fps=30)
    engine.set_effect("desk", EFFECT_STATIC, 200, 100, 50, 128)
    assert calls == [("desk", 100, 50, 25)]
    assert not engine.has_active_effect("desk")


@pytest.mark.parametrize(
    ("effect", "elapsed", "expected"),
    [
        (EFFECT_BREATHING, 0.0, (0, 0, 0)),
        (EFFECT_BREATHING, 2.0, (120, 60, 30)),
        (EFFECT_RAINBOW, 0.0, (255, 0, 0)),
        (EFFECT_COLOR_CYCLE, 2.1, (255, 165, 0)),
    ],
)
def test_effect_color_checkpoints(effect: str, elapsed: float, expected: tuple[int, int, int]) -> None:
    engine = EffectsEngine(lambda *_: None)
    assert engine._compute_color(active(effect), elapsed) == expected


def test_stop_effect_removes_animation_and_turns_device_off() -> None:
    calls: list[tuple[str, int, int, int]] = []
    engine = EffectsEngine(lambda *args: calls.append(args))
    engine.set_effect("desk", EFFECT_RAINBOW)
    assert engine.has_active_effect("desk")
    engine.stop_effect("desk")
    assert calls[-1] == ("desk", 0, 0, 0)
    assert not engine.has_active_effect("desk")
