"""Provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from smart360.ai.schema import SolveRequest, SolveResult

SYSTEM_PROMPT = """Du bist ein Fachlehrer für die deutsche Führerschein-Theorieprüfung (Klasse B, amtlicher \
Fragenkatalog). Du erhältst eine Frage aus einer Lernsoftware: Fragetext, nummerierte Antwortmöglichkeiten \
und ggf. Bildausschnitte (Fragebereich, Situationsbild/Verkehrszeichen, Antwortbereich).

Regeln:
- Bei Auswahlfragen können EINE oder MEHRERE Antworten richtig sein. Gib ALLE richtigen Antworten als \
1-basierte Nummern in der angezeigten Reihenfolge an.
- Bei Zahlenfragen ("Zahl eingeben") gib die Zahl in number_answer an und lasse answers leer.
- Nutze das Situationsbild aktiv (Verkehrszeichen, Vorfahrtsituation, Ampeln, Fahrbahnmarkierungen).
- Der OCR-Text kann kleine Erkennungsfehler enthalten; im Zweifel gilt das Bild.
- reason: höchstens zwei kurze, verständliche Sätze auf Deutsch, die die Regel erklären.
- confidence: deine ehrliche Sicherheit von 0.0 bis 1.0.
- uncertain = true, wenn Frage oder Antworten unvollständig/unleserlich sind oder du unsicher bist.
- Antworte ausschließlich im vorgegebenen JSON-Format."""


def build_user_text(req: SolveRequest) -> str:
    lines = [f"Frage (OCR, Konfidenz {req.ocr_confidence:.2f}):", req.question_text.strip(), ""]
    if req.number_question:
        lines.append("Fragetyp: Zahleneingabe")
    else:
        lines.append("Antwortmöglichkeiten:")
        lines.extend(f"{i}. {a.strip()}" for i, a in enumerate(req.answers, start=1))
    if req.image_png:
        lines.append("\nDas erste Bild ist das Situationsbild der Frage.")
    return "\n".join(lines)


class ProviderError(RuntimeError):
    """Error raised by providers. `retryable` drives the retry policy."""

    def __init__(self, message: str, retryable: bool, kind: str = "error", retry_after: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.kind = kind  # network | timeout | rate_limit | auth | invalid | server | refusal | config
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class ProviderInfo:
    id: str
    display_name: str
    default_model: str
    models: tuple[str, ...]
    key_name: str  # credential name in the secret store / env var
    # USD per 1M tokens (input, output) for local cost estimation only
    pricing: dict[str, tuple[float, float]]


class AIProvider(ABC):
    info: ProviderInfo

    def __init__(self, api_key: str | None, model: str | None = None, timeout_s: float = 30.0):
        self.api_key = api_key
        self.model = model or self.info.default_model
        self.timeout_s = timeout_s

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @abstractmethod
    def solve_question(self, req: SolveRequest) -> SolveResult:
        """Blocking call; runs on a worker thread, never the UI thread."""

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        pin, pout = self.info.pricing.get(self.model, (0.0, 0.0))
        return (input_tokens * pin + output_tokens * pout) / 1_000_000
