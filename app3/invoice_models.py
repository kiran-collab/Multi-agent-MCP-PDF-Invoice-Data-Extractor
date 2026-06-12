"""
Shared data models used across all three stages.

These describe the structured data we extract from an invoice and the
per-client report we generate from a set of invoices.
"""

from dataclasses import dataclass, field, asdict
from typing import List
import json


@dataclass
class LineItem:
    """A single purchased product / line on an invoice."""
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0
    amount: float = 0.0


@dataclass
class Invoice:
    """Structured representation of a single invoice."""
    invoice_id: str = ""
    client_name: str = ""
    invoice_date: str = ""
    currency: str = "USD"
    total_amount: float = 0.0
    line_items: List[LineItem] = field(default_factory=list)
    source_file: str = ""

    @classmethod
    def from_dict(cls, data: dict, source_file: str = "") -> "Invoice":
        """Build an Invoice from a parsed JSON dict (e.g. LLM output)."""
        items = [LineItem(**li) for li in data.get("line_items", [])]
        return cls(
            invoice_id=data.get("invoice_id", ""),
            client_name=data.get("client_name", ""),
            invoice_date=data.get("invoice_date", ""),
            currency=data.get("currency", "USD"),
            total_amount=float(data.get("total_amount", 0) or 0),
            line_items=items,
            source_file=source_file,
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ClientReport:
    """An aggregated report for a single client across many invoices."""
    client_name: str
    invoice_count: int
    total_spend: float
    currency: str
    products: List[str] = field(default_factory=list)
    invoices: List[Invoice] = field(default_factory=list)

    def render(self) -> str:
        """Render a human-readable text report."""
        lines = [
            f"Client Report: {self.client_name}",
            "=" * 40,
            f"Invoices processed : {self.invoice_count}",
            f"Total spend        : {self.total_spend:.2f} {self.currency}",
            "",
            "Products purchased:",
        ]
        lines += [f"  - {p}" for p in sorted(set(self.products))] or ["  (none)"]
        lines.append("")
        lines.append("Invoice breakdown:")
        for inv in self.invoices:
            lines.append(
                f"  - {inv.invoice_id or '(no id)'} "
                f"({inv.invoice_date or 'n/a'}): "
                f"{inv.total_amount:.2f} {inv.currency}"
            )
        return "\n".join(lines)


def build_client_reports(invoices: List[Invoice]) -> List[ClientReport]:
    """Group invoices by client and aggregate them into reports."""
    by_client: dict[str, List[Invoice]] = {}
    for inv in invoices:
        by_client.setdefault(inv.client_name or "Unknown", []).append(inv)

    reports = []
    for client, invs in by_client.items():
        products = [li.description for inv in invs for li in inv.line_items]
        reports.append(
            ClientReport(
                client_name=client,
                invoice_count=len(invs),
                total_spend=sum(i.total_amount for i in invs),
                currency=invs[0].currency if invs else "USD",
                products=products,
                invoices=invs,
            )
        )
    return reports
