class Invoice:
    _counter = 0

    def __init__(self, invoice_id: str, user_id: int, amount: float, order: str, customer_name: str = "Customer"):
        self.invoice_id = invoice_id       # bill code e.g. FC-20250611-1234
        self.user_id = user_id
        self.amount = amount
        self.order = order                 # raw user prompt
        self.customer_name = customer_name
