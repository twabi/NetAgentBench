"""Feedback arms for the property-guidance closed-loop experiment."""

from enum import Enum

CHECK_PROPERTIES_CAP = 20


class FeedbackArm(str, Enum):
    """How intent properties are exposed to the agent during the episode."""

    BLIND = "blind"
    DECLARED = "declared"
    FEEDBACK = "feedback"
    PLACEBO = "placebo"

    @classmethod
    def from_str(cls, value: str | None) -> "FeedbackArm":
        if value is None:
            return cls.BLIND
        normalized = value.strip().lower()
        return cls(normalized)
