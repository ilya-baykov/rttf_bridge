from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FetchResult:
    url: str
    html: str | None = None
    status_code: int | None = None
    final_url: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.html is not None and self.error_type is None
