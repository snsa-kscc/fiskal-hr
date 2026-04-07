"""
End-to-end tests for working hours API against CIS test server.

Requires:
  - Network access to cistest.apis-it.hr:8449
  - Valid demo certificates (dvasadva-demo.pem, fina-demo-bundle.pem, fiskalcistest.pem)
  - Registered business premises: TEST, POS01, POS02, POS03, POS04

Run with: pytest --e2e tests/e2e/
"""

from datetime import date, timedelta

import pytest

from fiskalhr.enums import DayOfWeek, FetchScope
from fiskalhr.premises import (
    BusinessPremises,
    DoubleShiftHours,
    ExceptionDoubleShift,
    ExceptionSingleShift,
    RegularWorkingHours,
    SingleShiftHours,
    WorkingHoursException,
)
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


@pytest.fixture(scope="module")
def start_date():
    return date.today() + timedelta(days=1)


@pytest.fixture(scope="module")
def exception_date():
    return date.today() + timedelta(days=3)


class TestEcho:
    def test_echo(self, fc):
        fc.test_service()


class TestFetchWorkingHours:
    def test_fetch_regular(self, fc):
        resp = fc.fetch_working_hours(OIB_VAL, "TEST", FetchScope.REGULAR, OIB_VAL)
        pp = resp.PoslovniProstor
        assert pp is not None
        assert pp.RadnoVrijeme is not None

    def test_fetch_exceptions(self, fc):
        resp = fc.fetch_working_hours(OIB_VAL, "TEST", FetchScope.EXCEPTIONS, OIB_VAL)
        assert resp is not None

    def test_fetch_all(self, fc):
        resp = fc.fetch_working_hours(OIB_VAL, "TEST", FetchScope.ALL, OIB_VAL)
        pp = resp.PoslovniProstor
        assert pp is not None
        assert pp.RadnoVrijeme is not None
        assert pp.RadnoVrijeme.Redovno is not None


class TestSubmitRegularHours:
    def test_single_shift(self, fc, start_date):
        regular = RegularWorkingHours(
            date_from=start_date,
            note="E2E test: single shift",
            single_shifts=[
                SingleShiftHours(DayOfWeek.MONDAY, "07:00", "17:00"),
                SingleShiftHours(DayOfWeek.TUESDAY, "07:00", "17:00"),
                SingleShiftHours(DayOfWeek.WEDNESDAY, "07:00", "17:00"),
                SingleShiftHours(DayOfWeek.THURSDAY, "07:00", "17:00"),
                SingleShiftHours(DayOfWeek.FRIDAY, "07:00", "17:00"),
                SingleShiftHours(DayOfWeek.SATURDAY, "08:00", "14:00"),
            ],
        )
        premises = BusinessPremises(
            oib=OIB_VAL,
            premises_code="TEST",
            operator_oib=OIB_VAL,
            regular_hours=[regular],
        )
        fc.submit_working_hours(premises)

        resp = fc.fetch_working_hours(OIB_VAL, "TEST", FetchScope.REGULAR, OIB_VAL)
        rv = resp.PoslovniProstor.RadnoVrijeme
        latest = rv.Redovno[-1]
        assert latest.Napomena == "E2E test: single shift"
        assert len(latest.Jednokratno) == 6

    def test_double_shift(self, fc, start_date):
        regular = RegularWorkingHours(
            date_from=start_date,
            note="E2E test: double shift",
            double_shifts=[
                DoubleShiftHours(DayOfWeek.MONDAY, 1, "08:00", "12:00"),
                DoubleShiftHours(DayOfWeek.MONDAY, 2, "16:00", "20:00"),
                DoubleShiftHours(DayOfWeek.TUESDAY, 1, "08:00", "12:00"),
                DoubleShiftHours(DayOfWeek.TUESDAY, 2, "16:00", "20:00"),
            ],
        )
        premises = BusinessPremises(
            oib=OIB_VAL,
            premises_code="POS01",
            operator_oib=OIB_VAL,
            regular_hours=[regular],
        )
        fc.submit_working_hours(premises)

        resp = fc.fetch_working_hours(OIB_VAL, "POS01", FetchScope.REGULAR, OIB_VAL)
        rv = resp.PoslovniProstor.RadnoVrijeme
        latest = rv.Redovno[-1]
        assert latest.Dvokratno is not None
        assert len(latest.Dvokratno) == 4

    def test_by_arrangement(self, fc, start_date):
        regular = RegularWorkingHours(
            date_from=start_date,
            note="E2E test: by arrangement",
            by_arrangement=True,
        )
        premises = BusinessPremises(
            oib=OIB_VAL,
            premises_code="POS02",
            operator_oib=OIB_VAL,
            regular_hours=[regular],
        )
        fc.submit_working_hours(premises)

        resp = fc.fetch_working_hours(OIB_VAL, "POS02", FetchScope.REGULAR, OIB_VAL)
        rv = resp.PoslovniProstor.RadnoVrijeme
        latest = rv.Redovno[-1]
        assert latest.PoDogovoru is not None
        assert latest.PoDogovoru.RedovnoPoDogovoru == "DA"


class TestSubmitExceptions:
    def test_single_shift_exception(self, fc, exception_date):
        exc = WorkingHoursException(
            exception_date=exception_date,
            single_shift=ExceptionSingleShift("09:00", "13:00"),
        )
        premises = BusinessPremises(
            oib=OIB_VAL,
            premises_code="TEST",
            operator_oib=OIB_VAL,
            exceptions=[exc],
        )
        fc.submit_working_hours(premises)

        resp = fc.fetch_working_hours(OIB_VAL, "TEST", FetchScope.EXCEPTIONS, OIB_VAL)
        rv = resp.PoslovniProstor.RadnoVrijeme
        assert len(rv.Iznimke) >= 1
        found = [
            e for e in rv.Iznimke if e.Datum == exception_date.strftime("%d.%m.%Y")
        ]
        assert len(found) == 1
        assert found[0].Jednokratno.RadnoVrijemeOd == "09:00"
        assert found[0].Jednokratno.RadnoVrijemeDo == "13:00"

    def test_double_shift_exception(self, fc, exception_date):
        exc = WorkingHoursException(
            exception_date=exception_date,
            double_shifts=[
                ExceptionDoubleShift(1, "08:00", "11:00"),
                ExceptionDoubleShift(2, "17:00", "20:00"),
            ],
        )
        premises = BusinessPremises(
            oib=OIB_VAL,
            premises_code="POS01",
            operator_oib=OIB_VAL,
            exceptions=[exc],
        )
        fc.submit_working_hours(premises)

        resp = fc.fetch_working_hours(OIB_VAL, "POS01", FetchScope.EXCEPTIONS, OIB_VAL)
        rv = resp.PoslovniProstor.RadnoVrijeme
        found = [
            e for e in rv.Iznimke if e.Datum == exception_date.strftime("%d.%m.%Y")
        ]
        assert len(found) == 1
        assert found[0].Dvokratno is not None
        assert len(found[0].Dvokratno) == 2


class TestDeleteWorkingHours:
    def test_delete_exception(self, fc, exception_date):
        premises = BusinessPremises(
            oib=OIB_VAL,
            premises_code="TEST",
            operator_oib=OIB_VAL,
            exceptions=[WorkingHoursException(exception_date=exception_date)],
        )
        fc.delete_working_hours(premises)

        resp = fc.fetch_working_hours(OIB_VAL, "TEST", FetchScope.EXCEPTIONS, OIB_VAL)
        rv = resp.PoslovniProstor.RadnoVrijeme
        if rv is None:
            return  # no working hours at all means exception is gone
        found = [
            e
            for e in (rv.Iznimke or [])
            if e.Datum == exception_date.strftime("%d.%m.%Y")
        ]
        assert len(found) == 0

    def test_delete_regular_and_exception(self, fc, start_date, exception_date):
        premises = BusinessPremises(
            oib=OIB_VAL,
            premises_code="POS01",
            operator_oib=OIB_VAL,
            regular_hours=[RegularWorkingHours(date_from=start_date)],
            exceptions=[WorkingHoursException(exception_date=exception_date)],
        )
        fc.delete_working_hours(premises)

        resp = fc.fetch_working_hours(OIB_VAL, "POS01", FetchScope.ALL, OIB_VAL)
        rv = resp.PoslovniProstor.RadnoVrijeme
        new_regular = [
            r
            for r in (rv.Redovno or [])
            if r.DatumOd == start_date.strftime("%d.%m.%Y")
        ]
        assert len(new_regular) == 0
        new_exc = [
            e
            for e in (rv.Iznimke or [])
            if e.Datum == exception_date.strftime("%d.%m.%Y")
        ]
        assert len(new_exc) == 0


class TestBatchSubmit:
    def test_batch_submit(self, fc, start_date):
        # Clean up first in case of previous run
        for code in ["POS03", "POS04"]:
            try:
                fc.delete_working_hours(
                    BusinessPremises(
                        oib=OIB_VAL,
                        premises_code=code,
                        operator_oib=OIB_VAL,
                        regular_hours=[RegularWorkingHours(date_from=start_date)],
                    )
                )
            except Exception:
                pass

        regular = RegularWorkingHours(
            date_from=start_date,
            note="E2E test: batch",
            single_shifts=[
                SingleShiftHours(DayOfWeek.MONDAY, "09:00", "17:00"),
                SingleShiftHours(DayOfWeek.TUESDAY, "09:00", "17:00"),
                SingleShiftHours(DayOfWeek.WEDNESDAY, "09:00", "17:00"),
                SingleShiftHours(DayOfWeek.THURSDAY, "09:00", "17:00"),
                SingleShiftHours(DayOfWeek.FRIDAY, "09:00", "17:00"),
            ],
        )
        batch = [
            BusinessPremises(
                oib=OIB_VAL,
                premises_code="POS03",
                operator_oib=OIB_VAL,
                regular_hours=[regular],
            ),
            BusinessPremises(
                oib=OIB_VAL,
                premises_code="POS04",
                operator_oib=OIB_VAL,
                regular_hours=[regular],
            ),
        ]

        resp = fc.submit_working_hours_batch(OIB_VAL, batch, OIB_VAL)
        assert resp.PoslovniProstoriOdgovor is not None
        answers = resp.PoslovniProstoriOdgovor.PoslovnicaOdgovor
        assert len(answers) == 2
        for a in answers:
            assert a.OznPosPr in ("POS03", "POS04")
            assert a.PorukaOdgovora is not None


class TestCleanup:
    """Restore baseline state after tests."""

    def test_cleanup_test(self, fc, start_date):
        fc.delete_working_hours(
            BusinessPremises(
                oib=OIB_VAL,
                premises_code="TEST",
                operator_oib=OIB_VAL,
                regular_hours=[RegularWorkingHours(date_from=start_date)],
            )
        )

    def test_cleanup_pos02(self, fc, start_date):
        fc.delete_working_hours(
            BusinessPremises(
                oib=OIB_VAL,
                premises_code="POS02",
                operator_oib=OIB_VAL,
                regular_hours=[RegularWorkingHours(date_from=start_date)],
            )
        )

    def test_cleanup_pos03_pos04(self, fc, start_date):
        for code in ["POS03", "POS04"]:
            fc.delete_working_hours(
                BusinessPremises(
                    oib=OIB_VAL,
                    premises_code=code,
                    operator_oib=OIB_VAL,
                    regular_hours=[RegularWorkingHours(date_from=start_date)],
                )
            )
