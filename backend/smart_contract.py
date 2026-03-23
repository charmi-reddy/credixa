import algopy
from algopy import ARC4Contract, UInt64, String, Account, Txn, gtxn

class InvoiceFinancing(ARC4Contract):
    def __init__(self) -> None:
        self.owner = algopy.Account()
        self.amount = UInt64(0)
        self.status = String("Created")

    @algopy.arc4.abimethod()
    def create_invoice(self, amount: UInt64) -> None:
        self.owner = Txn.sender
        self.amount = amount
        self.status = String("Created")

    @algopy.arc4.abimethod()
    def request_financing(self) -> None:
        assert Txn.sender == self.owner, "Only owner can request financing"
        assert self.status == String("Created"), "Invoice must be in Created state"
        self.status = String("Available")

    @algopy.arc4.abimethod()
    def fund_invoice(self, payment: gtxn.PaymentTransaction) -> None:
        assert self.status == String("Available"), "Invoice not available for funding"
        assert payment.receiver == self.owner, "Payment must be to the current owner"
        assert payment.amount == self.amount, "Payment amount must match invoice amount"
        
        self.owner = Txn.sender
        self.status = String("Funded")

    @algopy.arc4.abimethod()
    def settle_invoice(self, payment: gtxn.PaymentTransaction) -> None:
        assert self.status == String("Funded"), "Invoice must be Funded to be settled"
        assert payment.receiver == self.owner, "Payment must be to the current owner (investor)"
        assert payment.amount == self.amount, "Payment amount must match invoice amount"
        
        self.status = String("Settled")
