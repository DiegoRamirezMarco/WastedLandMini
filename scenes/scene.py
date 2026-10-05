from settings import SCALE


def canvas_position(window_position: tuple[int, int]) -> tuple[int, int]:
    """Convert a mouse position in the window to a position on the low-resolution canvas."""
    return (window_position[0] // SCALE, window_position[1] // SCALE)


class Scene:
    def handle_event(self, event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def render(self) -> None:
        raise NotImplementedError
