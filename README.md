# fiskal-hr

Python 3 package for integrating with Croatian tax authority
[Fiskalizacija](https://www.porezna-uprava.hr/HR_Fiskalizacija/Stranice/FiskalizacijaNovo.aspx)
service.

Implements the [Fiskalizacija technical specification v2.6](https://www.porezna-uprava.hr/HR_Fiskalizacija/Stranice/Tehni%C4%8Dke-specifikacije.aspx).

## Scope

The package provides full integration with the Fiskalizacija service, including:

### Invoices

* checking invoice details in test (DEMO) mode - `FiskalClient.check_invoice()`
* submitting an invoice - `FiskalClient.submit_invoice()`
* recipient OIB (`OibPrimateljaRacuna`) support for B2B cash/card transactions on `Invoice`

### Payment method and invoice data changes

* changing the payment method (legacy) - `FiskalClient.change_payment_method()` with `InvoicePaymentMethodChange`
* changing payment method and/or recipient OIB (new) - `FiskalClient.change_invoice_data()` with `InvoiceDataChange`

The newer `change_invoice_data()` method (spec section 2.1.6, `promijeniPodatkeRacuna`) supports
changing both the payment method and the recipient OIB on a previously fiscalized invoice. It
is the recommended method going forward; the legacy `change_payment_method()` only supports
changing the payment method.

### Tips (napojnice)

* submitting a tip for a previously fiscalized invoice - `FiskalClient.submit_tip()` with `InvoiceTip`

### Working hours (radno vrijeme poslovnog prostora)

* registering working hours for a business premises - `FiskalClient.submit_working_hours()`
* deleting working hours - `FiskalClient.delete_working_hours()`
* fetching active working hours - `FiskalClient.fetch_working_hours()`
* batch registration of working hours for multiple premises - `FiskalClient.submit_working_hours_batch()`

> **Note:** In the demo environment, before you can test working hours operations, you must
> request that Porezna Uprava opens test business premises on the OIB your DEMO certificate
> is issued to. Submit a request via [Pišite nam](https://pisitenam.porezna-uprava.hr/)
> selecting topic *Fiskalizacija u krajnjoj potrošnji (F1)* and subtopic *Tehnička podrška*.
> Include the OIB from your DEMO certificate and the desired premises codes (oznake
> poslovnih prostora) in the request.

## Requirements

You'll need your client certificate, Fiskalizacija service certificate and FINA root CA
certificates. Read the [integration guide](doc/integration.md) for detailed steps how to
get and prepare the certificates.

You'll also need the `libxmlsec1` library installed on your computer.

## Quickstart

1. Install `fiskal-hr`:

    ```sh
    pip install fiskal-hr
    ```

2. Make sure you have your certificates ready, then initialize the fiskal client package:

    ```python
    from fiskalhr.invoice import Invoice
    from fiskalhr.ws import FiskalClient
    from fiskalhr.signature import Signer, Verifier

    signer = Signer("path/to/your-client-cert.pem")  # if encrypted, you'll need the password as well
    verifier = Verifier("path/to/service-cert.pem", ["path/to/fina-demo-ca-combined.pem"])
    fiskal_client = FiskalClient(
        "path/to/fina-demo-ca-combined.pem",
        "path/to/wsdl/FiskalizacijaService.wsdl",
        signer,
        verifier,
    )
    ```

3. Check communication with the service:

    ```python
    fiskal_client.test_service()
    ```

    This sends a "ping" message to the echo service, to check that basic connectivity is working.
    If there's an error, the `test_service()` method will raise an exception.

4. Create a test invoice and ask the service to do sanity checks on it (this only works in the
   demo mode):

    ```python
    invoice = Invoice(fiskal_client, oib="YOUR-OIB", invoice_number="1/X/1", total=100)

    fiskal_client.check_invoice(invoice)
    ```

    If there are any errors, the `check_invoice()` method will raise `fiskalhr.ResponseError`
    with the error details in the `details` attribute.

    Note that this does only basic sanity checking. For example, it will not check if the
    point of sale location (code `X` in the invoice number in this example) is registered.

## Usage examples

### Submit an invoice with recipient OIB (B2B)

```python
from fiskalhr.enums import PaymentMethod, SequenceScope
from fiskalhr.invoice import Invoice
from fiskalhr.item import TaxItem

invoice = Invoice(
    fiskal_client,
    oib="YOUR-OIB",
    invoice_number="1/STORE1/1",
    total=1250.00,
    vat=[TaxItem(1000.00, 25, 250.00)],
    is_vat_registered=True,
    payment_method=PaymentMethod.CASH,
    sequence_scope=SequenceScope.LOCATION,
    recipient_oib="BUYER-OIB",  # B2B only, cash/card payments
)

jir = fiskal_client.submit_invoice(invoice)
```

### Change payment method and recipient OIB on a fiscalized invoice

```python
from fiskalhr.invoice import InvoiceDataChange

change = InvoiceDataChange(
    fiskal_client,
    # original invoice data:
    oib="YOUR-OIB",
    issued_at=original_invoice.issued_at,
    invoice_number="1/STORE1/1",
    total=1250.00,
    vat=[TaxItem(1000.00, 25, 250.00)],
    is_vat_registered=True,
    payment_method=PaymentMethod.CASH,
    sequence_scope=SequenceScope.LOCATION,
    original_zki=original_zki,
    # changed data:
    new_payment_method=PaymentMethod.CARD,
    new_recipient_oib="BUYER-OIB",
)

fiskal_client.change_invoice_data(change)
```

### Submit a tip (napojnica)

```python
from fiskalhr.invoice import InvoiceTip

tip = InvoiceTip(
    fiskal_client,
    # original invoice data:
    oib="YOUR-OIB",
    issued_at=original_invoice.issued_at,
    invoice_number="1/STORE1/1",
    total=1250.00,
    vat=[TaxItem(1000.00, 25, 250.00)],
    is_vat_registered=True,
    payment_method=PaymentMethod.CASH,
    sequence_scope=SequenceScope.LOCATION,
    # tip data:
    tip_amount=50.00,
    tip_payment_method=PaymentMethod.CASH,
)

fiskal_client.submit_tip(tip)
```

### Register working hours for a business premises

```python
from fiskalhr.enums import DayOfWeek
from fiskalhr.premises import BusinessPremises, SingleShiftHours, WorkingHoursRange

premises = BusinessPremises(
    oib="YOUR-OIB",
    premises_code="STORE1",
    working_hours=[
        WorkingHoursRange(
            DayOfWeek.MONDAY, DayOfWeek.FRIDAY,
            time_from="08:00", time_to="20:00",
        ),
        SingleShiftHours(
            DayOfWeek.SATURDAY,
            time_from="09:00", time_to="14:00",
        ),
    ],
    effective_date=date(2026, 1, 1),
    operator_oib="OPERATOR-OIB",
)

fiskal_client.submit_working_hours(premises)
```

## Testing

This package has 100% unit test coverage. To run the tests:

```
pytest
```

Coverage report is generated automatically. To export it in HTML form, run `coverage html`.

The tests do not contact Fiskalizacija service or any other external service, nor do they
require actual certificates. They are entirely self-contained.

More info about testing and certificates is available in [the testing guide](doc/testing.md).

## Contributing

Found a bug or think something can be improved? All contributions are welcome!

Before changing any code, please open a GitHub issue explaining what you'd like to do.
This will ensure that your planned contribution fits well with the rest of the package
and minimize the chance your pull request will be rejected.

If changing any code, please ensure that after your changes:

* all tests pass and the code coverage is still 100%
* `black`, `flake8` and `isort` find no problems
* the code doesn't depend on any external service

## Copyright and license

Copyright (C) 2022 by Senko Rasic <senko@senko.net>

This package may be used and distributed under the terms of MIT license.
See the [LICENSE](LICENSE) file for details.
