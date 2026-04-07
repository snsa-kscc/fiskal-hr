"""
End-to-end test for napojnica (tip) API against CIS test server.

Requires:
  - Network access to cistest.apis-it.hr:8449
  - Valid demo certificates (dvasadva-demo.pem, fina-demo-bundle.pem, fiskalcistest.pem)

Run with: pytest --e2e tests/e2e/test_napojnica.py
"""

from datetime import datetime
from decimal import Decimal

import pytest

from fiskalhr.enums import PaymentMethod, SequenceScope
from fiskalhr.invoice import Invoice, InvoiceTip
from fiskalhr.signature import Signer, Verifier
from fiskalhr.ws import FiskalClient

pytestmark = pytest.mark.e2e

DEMO_PEM = "dvasadva-demo.pem"
FINA_BUNDLE = "fina-demo-bundle.pem"
FISKAL_CERT = "fiskalcistest.pem"
WSDL = "testdata/ws/wsdl/FiskalizacijaService.wsdl"
OIB_VAL = "68847910990"


@pytest.fixture(scope="module")
def fc():
    signer = Signer(DEMO_PEM)
    verifier = Verifier(FISKAL_CERT, [FINA_BUNDLE])
    return FiskalClient(FINA_BUNDLE, WSDL, signer, verifier)


INVOICE_PARAMS = dict(
    oib=OIB_VAL,
    issued_at=datetime.now(),
    invoice_number="1/TEST/1",
    total=Decimal("100.00"),
    is_vat_registered=True,
    payment_method=PaymentMethod.CASH,
    sequence_scope=SequenceScope.LOCATION,
)


class TestNapojnica:
    def test_submit_tip(self, fc):
        # First submit an invoice to get a JIR
        invoice = Invoice(fc, **INVOICE_PARAMS)
        jir = fc.submit_invoice(invoice)
        assert jir is not None

        # Now submit a tip for that invoice
        tip = InvoiceTip(
            fc,
            **INVOICE_PARAMS,
            tip_amount=Decimal("10.00"),
            tip_payment_method=PaymentMethod.CASH,
        )
        fc.submit_tip(tip)
