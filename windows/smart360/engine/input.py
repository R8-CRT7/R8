"""Input drivers used by the executor (only ever after an approved question)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from smart360.capture.simulator import PracticeSimulator
from smart360.platform import win32


class InputDriver(ABC):
    name = "input"

    @abstractmethod
    def click(self, x: int, y: int, expected_window: int | None = None) -> None: ...

    @abstractmethod
    def type_text(self, text: str) -> None: ...


class Win32InputDriver(InputDriver):
    name = "win32"

    def click(self, x: int, y: int, expected_window: int | None = None) -> None:
        win32.click(x, y, expected_hwnd=expected_window)

    def type_text(self, text: str) -> None:
        win32.type_text(text)


class SimulatorInputDriver(InputDriver):
    name = "simulator"

    def __init__(self, sim: PracticeSimulator):
        self.sim = sim
        self.fail_next = 0
        self.log: list[tuple[str, object]] = []

    def click(self, x: int, y: int, expected_window: int | None = None) -> None:
        self.log.append(("click", (x, y)))
        if self.fail_next > 0:
            self.fail_next -= 1
            return  # click "lost" (e.g. swallowed by another window)
        self.sim.click(x, y)

    def type_text(self, text: str) -> None:
        self.log.append(("type", text))
        self.sim.type_text(text)
