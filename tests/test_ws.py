from unittest.mock import Mock

import pytest
from zeep.exceptions import Fault

from fiskalhr.enums import FetchScope, ResponseErrorEnum
from fiskalhr.errors import ResponseError
from fiskalhr.invoice import Invoice, InvoiceTip, InvoiceWithDoc
from fiskalhr.oib import OIB
from fiskalhr.ws import FiskalClient

TEST_WSDL = "testdata/ws/wsdl/FiskalizacijaService.wsdl"
EMPTY_WSDL = "testdata/ws/wsdl/EmptyService.wsdl"

SERVICE_FAULT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope
    xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
>
    <soap:Body>
        <tns:ProvjeraOdgovor
            Id="G0x7f17105098f8-4D"
            xsi:schemaLocation="http://www.apis-it.hr/fin/2012/types/f73
            ../schema/FiskalizacijaSchema.xsd "
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xmlns:tns="http://www.apis-it.hr/fin/2012/types/f73"
        >
            <tns:Zaglavlje>
                <tns:IdPoruke>c6ce928f-0ebe-4308-9e8e-fe7732e78f9b</tns:IdPoruke>
                <tns:DatumVrijeme>31.08.2022T00:00:00</tns:DatumVrijeme>
            </tns:Zaglavlje>
            <tns:Greske>
                <tns:Greska>
                    <tns:SifraGreske>s005</tns:SifraGreske>
                    <tns:PorukaGreske>
                        OIB iz poruke zahtjeva nije jednak OIB-u iz certifikata.
                    </tns:PorukaGreske>
                </tns:Greska>
            </tns:Greske>
        </tns:ProvjeraOdgovor>
    </soap:Body>
</soap:Envelope>
"""

SERVICE_FAULT_EMPTY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope
    xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
>
</soap:Envelope>
"""


def test_corrupted_wsdl_load_fails():
    with pytest.raises(Exception):
        FiskalClient("testdata/root_ca.crt", "testdata/root_ca.crt", None, None)


def test_incorrect_wsdl_load_fails():
    with pytest.raises(ValueError):
        FiskalClient("testdata/root_ca.crt", EMPTY_WSDL, None, None)


def test_service_ca_cert_not_found():
    with pytest.raises(ValueError):
        FiskalClient("testdata/nonexistent", TEST_WSDL, None, None)


def test_service_wsdl_not_found():
    with pytest.raises(ValueError):
        FiskalClient("testdata/root_ca.crt", "testdata/nonexistent", None, None)


class TestFiskalClient:
    def setup_method(self):
        self.fc = FiskalClient("testdata/root_ca.crt", TEST_WSDL, None, None)

    def test_wsdl_load_succeeds(self):
        assert "FiskalizacijaService" in self.fc.client.wsdl.services

        operations = set(dict(self.fc.client.service).keys())
        expected_operations = {
            "echo",
            "racuni",
            "provjera",
            "racuniPD",
            "prateciDokumenti",
            "promijeniNacPlac",
            "promijeniPodatkeRacuna",
            "napojnice",
            "prijaviRadnoVrijeme",
            "obrisiRadnoVrijeme",
            "dohvatiRadnoVrijeme",
            "prijaviRadnoVrijemeZaPoslovnice",
        }

        assert operations == expected_operations

    @pytest.mark.parametrize(
        "name,requires_signature",
        [
            ("echo", False),
            ("racuni", True),
            ("provjera", True),
        ],
    )
    def test_operation_requires_signature(self, name, requires_signature):
        operation = Mock()
        operation.name = name
        assert self.fc.requires_signature(operation) == requires_signature

    def test_echo_service_correct_answer(self):
        self.fc.client = Mock()
        self.fc.client.service.echo.return_value = "hello"

        self.fc.test_service("hello")
        self.fc.client.service.echo.assert_called_once_with("hello")

    def test_echo_service_incorrect_answer(self):
        self.fc.client = Mock()
        self.fc.client.service.echo.return_value = "hxello"

        with pytest.raises(ValueError):
            self.fc.test_service("hello")

    def test_create_request_header(self):
        header = self.fc.create_request_header()
        assert isinstance(header, type(self.fc.type_factory.ZaglavljeType()))

    def test_parse_no_xml_response(self):
        service_proxy = Mock()
        service_proxy.side_effect = Fault(
            "error",
            detail="",
        )

        with pytest.raises(ResponseError):
            self.fc._call_service(service_proxy, {})

    def test_parse_empty_fault(self):
        service_proxy = Mock()
        service_proxy.side_effect = Fault(
            "error",
            detail=SERVICE_FAULT_EMPTY_XML.encode("utf-8"),
        )

        with pytest.raises(ResponseError):
            self.fc._call_service(service_proxy, {})

    def test_parse_fault(self):
        service_proxy = Mock()
        service_proxy.side_effect = Fault(
            "error",
            detail=SERVICE_FAULT_XML.encode("utf-8"),
        )

        with pytest.raises(ResponseError) as einfo:
            self.fc._call_service(service_proxy, {})

        err = einfo.value
        assert len(err.details) == 1
        assert err.details[0].code == ResponseErrorEnum.OIB_MISMATCH
        assert str(err) == "Service error: s005"

    def test_check_invoice_fails_in_demo(self):
        self.fc.client = Mock()
        del self.fc.client.service.provjera

        with pytest.raises(RuntimeError):
            self.fc.check_invoice(Mock())

    def test_check_invoice(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.provjera = srv
        invoice = Mock()
        invoice.__class__ = Invoice

        resp = self.fc.check_invoice(invoice)

        invoice.to_ws_object.assert_called_once()
        srv.assert_called_once()
        assert srv.call_args.kwargs["Racun"] == invoice.to_ws_object.return_value
        assert resp == srv.return_value.Racun

    def test_check_invoice_with_doc(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.provjera = srv
        invoice = Mock()
        invoice.__class__ = InvoiceWithDoc

        resp = self.fc.check_invoice(invoice)

        invoice.to_ws_object.assert_called_once()
        srv.assert_called_once()
        assert srv.call_args.kwargs["RacunPD"] == invoice.to_ws_object.return_value
        assert resp == srv.return_value.RacunPD

    def test_submit_invoice(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.racuni = srv
        invoice = Mock()
        invoice.__class__ = Invoice

        resp = self.fc.submit_invoice(invoice)

        invoice.to_ws_object.assert_called_once()
        srv.assert_called_once()
        assert srv.call_args.kwargs["Racun"] == invoice.to_ws_object.return_value
        assert resp == srv.return_value.Jir

    def test_submit_invoice_with_doc(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.racuniPD = srv
        invoice = Mock()
        invoice.__class__ = InvoiceWithDoc

        resp = self.fc.submit_invoice(invoice)

        invoice.to_ws_object.assert_called_once()
        srv.assert_called_once()
        assert srv.call_args.kwargs["Racun"] == invoice.to_ws_object.return_value
        assert resp == srv.return_value.Jir

    def test_change_payment(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.promijeniNacPlac = srv
        invoice = Mock()

        self.fc.change_payment_method(invoice)

        invoice.to_ws_object.assert_called_once()
        srv.assert_called_once()
        assert srv.call_args.kwargs["Racun"] == invoice.to_ws_object.return_value

    def test_change_invoice_data(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.promijeniPodatkeRacuna = srv
        invoice = Mock()

        self.fc.change_invoice_data(invoice)

        invoice.to_ws_object.assert_called_once()
        srv.assert_called_once()
        assert srv.call_args.kwargs["Racun"] == invoice.to_ws_object.return_value

    def test_submit_tip(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.napojnice = srv
        invoice = Mock()
        invoice.__class__ = InvoiceTip

        self.fc.submit_tip(invoice)

        invoice.to_ws_object.assert_called_once()
        srv.assert_called_once()
        assert srv.call_args.kwargs["Racun"] == invoice.to_ws_object.return_value

    def test_submit_document(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.prateciDokumenti = srv
        doc = Mock()

        resp = self.fc.submit_document(doc)

        doc.to_ws_object.assert_called_once()
        srv.assert_called_once()
        assert srv.call_args.kwargs["PrateciDokument"] == doc.to_ws_object.return_value
        assert resp == srv.return_value.Jir

    def test_submit_working_hours(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.prijaviRadnoVrijeme = srv
        premises = Mock()

        self.fc.submit_working_hours(premises)

        premises.to_ws_object.assert_called_once_with(self.fc)
        srv.assert_called_once()
        assert (
            srv.call_args.kwargs["PoslovniProstor"]
            == premises.to_ws_object.return_value
        )
        assert srv.call_args.kwargs["OibOper"] == premises.operator_oib

    def test_delete_working_hours(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.obrisiRadnoVrijeme = srv
        premises = Mock()

        self.fc.delete_working_hours(premises)

        premises.to_delete_ws_object.assert_called_once_with(self.fc)
        srv.assert_called_once()
        assert (
            srv.call_args.kwargs["PoslovniProstor"]
            == premises.to_delete_ws_object.return_value
        )
        assert srv.call_args.kwargs["OibOper"] == premises.operator_oib

    def test_fetch_working_hours(self):
        self.fc.client = Mock()
        srv = Mock()
        self.fc.client.service.dohvatiRadnoVrijeme = srv
        oib = OIB("12312312316")
        operator_oib = OIB("12312312316")

        resp = self.fc.fetch_working_hours(oib, "POS01", FetchScope.ALL, operator_oib)

        srv.assert_called_once()
        assert srv.call_args.kwargs["Oib"] == oib
        assert srv.call_args.kwargs["OznPosPr"] == "POS01"
        assert srv.call_args.kwargs["VrstaRadnogVremena"] == FetchScope.ALL
        assert srv.call_args.kwargs["OibOper"] == operator_oib
        assert resp == srv.return_value

    def test_submit_working_hours_batch(self):
        self.fc.client = Mock()
        self.fc.type_factory = Mock()
        srv = Mock()
        self.fc.client.service.prijaviRadnoVrijemeZaPoslovnice = srv
        oib = OIB("12312312316")
        operator_oib = OIB("12312312316")
        p1 = Mock()
        p2 = Mock()

        resp = self.fc.submit_working_hours_batch(oib, [p1, p2], operator_oib)

        p1.to_batch_ws_object.assert_called_once_with(self.fc)
        p2.to_batch_ws_object.assert_called_once_with(self.fc)
        srv.assert_called_once()
        assert srv.call_args.kwargs["Oib"] == oib
        assert srv.call_args.kwargs["OibOper"] == operator_oib
        assert resp == srv.return_value
