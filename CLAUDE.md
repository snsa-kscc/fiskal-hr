# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run tests (coverage report auto-generated)
pytest

# Run a single test file
pytest tests/test_invoice.py

# Run a single test
pytest tests/test_invoice.py::test_function_name

# Export HTML coverage report
coverage html

# Format code
black .

# Check formatting without changing files
black --check --diff --color .

# Lint
flake8 fiskalhr tests

# Check import order
isort --check --diff fiskalhr tests
```

The system package `libxmlsec1-dev` must be installed for the `xmlsec` dependency.

## Architecture

This is a Python library for Croatian [Fiskalizacija](https://www.porezna-uprava.hr/HR_Fiskalizacija/Stranice/FiskalizacijaNovo.aspx) — a government tax service requiring all cash-register invoices to be digitally signed and submitted in real-time via SOAP.

### Request flow

1. The caller builds an `Invoice` (or related document) from `fiskalhr/invoice.py`
2. `FiskalClient` (`fiskalhr/ws.py`) serializes it to a SOAP request via `zeep`
3. `EnvelopedSignaturePlugin` (`fiskalhr/signature.py`) intercepts the outgoing request and signs the XML using the merchant's private key via `xmlsec`
4. The response is verified against the Fiskalizacija service certificate by the same plugin
5. On success the JIR (server-assigned unique invoice ID) is returned; on failure a `ResponseError` is raised

### Key modules

- **`ws.py`** — `FiskalClient`: the main entry point. Wraps a `zeep` SOAP client. The WSDL and service cert/CA paths are passed at construction time. Provides `test_service()`, `check_invoice()`, `submit_invoice()`, `change_payment_method()`, `change_invoice_data()`, `submit_tip()`, `submit_document()`, `submit_working_hours()`, `delete_working_hours()`, `fetch_working_hours()`, `submit_working_hours_batch()`.

- **`invoice.py`** — `Invoice`, `Document`, `InvoiceWithDoc`, `InvoicePaymentMethodChange`, `InvoiceDataChange`, `InvoiceTip`, `BaseDocument`: property-based models. Setting attributes (e.g. `invoice.vat`, `invoice.fees`) validates and stores data. `Invoice` auto-calculates `ZKI` (the local control code) from `zki.py` whenever relevant properties change. `Invoice` supports optional `recipient_oib` for B2B cash/card transactions. `InvoiceDataChange` supports changing both payment method and recipient OIB on a fiscalized invoice (spec section 2.1.6). `InvoiceTip` supports submitting tips for fiscalized invoices.

- **`premises.py`** — `BusinessPremises`, `SingleShiftHours`, `WorkingHoursRange`, `SeasonalHours`: models for business premises working hours registration. Supports single shifts, ranges (Mon-Fri), seasonal hours, and even/odd week schedules.

- **`signature.py`** — `Signer` (signs outgoing requests with merchant key), `Verifier` (verifies responses against service cert), `EnvelopedSignaturePlugin` (zeep plugin wiring the two together). XML signing uses `xmldsig` with RSA-SHA1.

- **`item.py`** — `TaxItem` (VAT/consumption tax: base, rate, amount) and `Fee` (named monetary fee). Used as list values on `Invoice`.

- **`oib.py`** — `OIB`: validates the 11-digit Croatian personal/company ID including its checksum.

- **`zki.py`** — `ZKI`: calculates the 32-char hex invoice control code (RSA-SHA1 signature of invoice fields → MD5).

- **`enums.py`** — `PaymentMethod`, `SequenceScope`, `ResponseErrorEnum` (40+ Croatian service error codes), `DayOfWeek`, `EvenOdd`, `FetchScope` (working hours enums).

- **`errors.py`** — `ResponseError` / `ResponseErrorDetail`: raised when the service returns a fault.

### Testing

Tests are entirely self-contained — no network calls, no real certificates required. Test certificates live in `testdata/`. `freezegun` is used to freeze time in tests. 100% coverage is a hard requirement; `pytest` is configured in `pyproject.toml` to always run with `--cov=fiskalhr`.
