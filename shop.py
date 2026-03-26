from collections import OrderedDict
from invoice import Invoice


class Shop:
    def __init__(self, shop_id: int, name: str, X: float, Y: float):
        self.shop_id = shop_id
        self.name = name
        self.X = X
        self.Y = Y
        # OrderedDict guarantees insertion order → FIFO
        self.Invoices: OrderedDict[str, Invoice] = OrderedDict()

    def add_invoice(self, invoice: Invoice):
        self.Invoices[invoice.invoice_id] = invoice

    def serve(self) -> Invoice:
        """Return (not remove) the first invoice — the one currently being served."""
        if not self.Invoices:
            raise IndexError("No invoices in queue")
        first_key = next(iter(self.Invoices))
        return self.Invoices[first_key]

    def remove_invoice(self, invoice_id: str):
        if invoice_id in self.Invoices:
            del self.Invoices[invoice_id]

    def is_empty(self) -> bool:
        return len(self.Invoices) == 0

    def queue_snapshot(self) -> list:
        """List of invoice_ids in FIFO order."""
        return list(self.Invoices.keys())
