from datetime import date
from unittest.mock import Mock

import pytest

from fiskalhr.enums import DayOfWeek, EvenOdd, FetchScope
from fiskalhr.oib import OIB
from fiskalhr.premises import (
    BusinessPremises,
    DoubleShiftHours,
    EvenOddHours,
    ExceptionDoubleShift,
    ExceptionSingleShift,
    RegularWorkingHours,
    SingleShiftHours,
    WorkingHoursException,
)


class TestSingleShiftHours:
    def test_create(self):
        s = SingleShiftHours(DayOfWeek.MONDAY, "08:00", "16:00")
        assert s.day == DayOfWeek.MONDAY
        assert s.time_from == "08:00"
        assert s.time_to == "16:00"

    def test_to_ws_object(self):
        s = SingleShiftHours(DayOfWeek.FRIDAY, "09:00", "17:00")
        tf = Mock()
        result = s.to_ws_object(tf)
        tf.JednokratnoType.assert_called_once_with(
            DanUTjednu=DayOfWeek.FRIDAY,
            RadnoVrijemeOd="09:00",
            RadnoVrijemeDo="17:00",
        )
        assert result == tf.JednokratnoType.return_value


class TestDoubleShiftHours:
    def test_create(self):
        d = DoubleShiftHours(DayOfWeek.TUESDAY, 1, "07:00", "11:00")
        assert d.day == DayOfWeek.TUESDAY
        assert d.shift_part == 1
        assert d.time_from == "07:00"
        assert d.time_to == "11:00"

    def test_invalid_shift_part(self):
        with pytest.raises(ValueError, match="shift_part must be 1 or 2"):
            DoubleShiftHours(DayOfWeek.MONDAY, 3, "07:00", "11:00")

    def test_to_ws_object(self):
        d = DoubleShiftHours(DayOfWeek.WEDNESDAY, 2, "16:00", "20:00")
        tf = Mock()
        result = d.to_ws_object(tf)
        tf.DvokratnoType.assert_called_once_with(
            DanUTjednu=DayOfWeek.WEDNESDAY,
            DioDvokratnog="2",
            RadnoVrijemeOd="16:00",
            RadnoVrijemeDo="20:00",
        )
        assert result == tf.DvokratnoType.return_value


class TestEvenOddHours:
    def test_create(self):
        e = EvenOddHours(DayOfWeek.SATURDAY, EvenOdd.EVEN, "10:00", "14:00")
        assert e.day == DayOfWeek.SATURDAY
        assert e.even_odd == EvenOdd.EVEN
        assert e.time_from == "10:00"
        assert e.time_to == "14:00"

    def test_to_ws_object(self):
        e = EvenOddHours(DayOfWeek.HOLIDAY, EvenOdd.ODD, "08:00", "12:00")
        tf = Mock()
        result = e.to_ws_object(tf)
        tf.ParniNeparniType.assert_called_once_with(
            DanUTjednu=DayOfWeek.HOLIDAY,
            ParNepar=EvenOdd.ODD,
            RadnoVrijemeOd="08:00",
            RadnoVrijemeDo="12:00",
        )
        assert result == tf.ParniNeparniType.return_value


class TestRegularWorkingHours:
    def test_by_arrangement(self):
        r = RegularWorkingHours(date_from=date(2025, 6, 1), by_arrangement=True)
        tf = Mock()
        result = r.to_ws_object(tf)
        tf.RedovnoType.assert_called_once()
        kwargs = tf.RedovnoType.call_args.kwargs
        assert kwargs["DatumOd"] == "01.06.2025"
        assert "PoDogovoru" in kwargs
        assert result == tf.RedovnoType.return_value

    def test_with_note(self):
        r = RegularWorkingHours(
            date_from=date(2025, 6, 1),
            note="Test note",
            by_arrangement=True,
        )
        tf = Mock()
        r.to_ws_object(tf)
        kwargs = tf.RedovnoType.call_args.kwargs
        assert kwargs["Napomena"] == "Test note"

    def test_single_shifts(self):
        shifts = [
            SingleShiftHours(DayOfWeek.MONDAY, "08:00", "16:00"),
            SingleShiftHours(DayOfWeek.TUESDAY, "08:00", "16:00"),
        ]
        r = RegularWorkingHours(date_from=date(2025, 6, 1), single_shifts=shifts)
        tf = Mock()
        r.to_ws_object(tf)
        kwargs = tf.RedovnoType.call_args.kwargs
        assert "Jednokratno" in kwargs
        assert len(kwargs["Jednokratno"]) == 2

    def test_double_shifts(self):
        shifts = [
            DoubleShiftHours(DayOfWeek.MONDAY, 1, "07:00", "11:00"),
            DoubleShiftHours(DayOfWeek.MONDAY, 2, "16:00", "20:00"),
        ]
        r = RegularWorkingHours(date_from=date(2025, 6, 1), double_shifts=shifts)
        tf = Mock()
        r.to_ws_object(tf)
        kwargs = tf.RedovnoType.call_args.kwargs
        assert "Dvokratno" in kwargs
        assert len(kwargs["Dvokratno"]) == 2

    def test_even_odd_shifts(self):
        shifts = [
            EvenOddHours(DayOfWeek.MONDAY, EvenOdd.EVEN, "08:00", "16:00"),
        ]
        r = RegularWorkingHours(date_from=date(2025, 6, 1), even_odd_shifts=shifts)
        tf = Mock()
        r.to_ws_object(tf)
        kwargs = tf.RedovnoType.call_args.kwargs
        assert "ParniNeparni" in kwargs
        assert len(kwargs["ParniNeparni"]) == 1


class TestExceptionSingleShift:
    def test_create(self):
        s = ExceptionSingleShift("10:00", "14:00")
        assert s.time_from == "10:00"
        assert s.time_to == "14:00"

    def test_to_ws_object(self):
        s = ExceptionSingleShift("10:00", "14:00")
        tf = Mock()
        result = s.to_ws_object(tf)
        tf.JednokratnoIznimkeType.assert_called_once_with(
            RadnoVrijemeOd="10:00",
            RadnoVrijemeDo="14:00",
        )
        assert result == tf.JednokratnoIznimkeType.return_value


class TestExceptionDoubleShift:
    def test_create(self):
        d = ExceptionDoubleShift(1, "07:00", "11:00")
        assert d.shift_part == 1
        assert d.time_from == "07:00"
        assert d.time_to == "11:00"

    def test_invalid_shift_part(self):
        with pytest.raises(ValueError, match="shift_part must be 1 or 2"):
            ExceptionDoubleShift(0, "07:00", "11:00")

    def test_to_ws_object(self):
        d = ExceptionDoubleShift(2, "16:00", "20:00")
        tf = Mock()
        result = d.to_ws_object(tf)
        tf.DvokratnoIznimkeType.assert_called_once_with(
            DioDvokratnog="2",
            RadnoVrijemeOd="16:00",
            RadnoVrijemeDo="20:00",
        )
        assert result == tf.DvokratnoIznimkeType.return_value


class TestWorkingHoursException:
    def test_with_single_shift(self):
        shift = ExceptionSingleShift("10:00", "14:00")
        exc = WorkingHoursException(
            exception_date=date(2025, 12, 25), single_shift=shift
        )
        assert exc.exception_date == date(2025, 12, 25)
        assert exc.single_shift == shift

    def test_to_ws_object_single(self):
        shift = ExceptionSingleShift("10:00", "14:00")
        exc = WorkingHoursException(
            exception_date=date(2025, 12, 25), single_shift=shift
        )
        tf = Mock()
        result = exc.to_ws_object(tf)
        tf.IznimkeType.assert_called_once()
        kwargs = tf.IznimkeType.call_args.kwargs
        assert kwargs["Datum"] == "25.12.2025"
        assert "Jednokratno" in kwargs
        assert result == tf.IznimkeType.return_value

    def test_to_ws_object_double(self):
        shifts = [
            ExceptionDoubleShift(1, "07:00", "11:00"),
            ExceptionDoubleShift(2, "16:00", "20:00"),
        ]
        exc = WorkingHoursException(
            exception_date=date(2025, 10, 3), double_shifts=shifts
        )
        tf = Mock()
        exc.to_ws_object(tf)
        kwargs = tf.IznimkeType.call_args.kwargs
        assert "Dvokratno" in kwargs
        assert len(kwargs["Dvokratno"]) == 2


class TestBusinessPremises:
    def test_create(self):
        bp = BusinessPremises(
            oib="12312312316",
            premises_code="POS01",
            operator_oib="12312312316",
        )
        assert bp.oib == OIB("12312312316")
        assert bp.premises_code == "POS01"
        assert bp.operator_oib == OIB("12312312316")
        assert bp.regular_hours == []
        assert bp.exceptions == []

    def test_invalid_premises_code_empty(self):
        with pytest.raises(ValueError, match="1-20 alphanumeric"):
            BusinessPremises(
                oib="12312312316",
                premises_code="",
                operator_oib="12312312316",
            )

    def test_invalid_premises_code_special_chars(self):
        with pytest.raises(ValueError, match="1-20 alphanumeric"):
            BusinessPremises(
                oib="12312312316",
                premises_code="POS-01",
                operator_oib="12312312316",
            )

    def test_invalid_premises_code_too_long(self):
        with pytest.raises(ValueError, match="1-20 alphanumeric"):
            BusinessPremises(
                oib="12312312316",
                premises_code="A" * 21,
                operator_oib="12312312316",
            )

    def test_to_ws_object(self):
        regular = RegularWorkingHours(date_from=date(2025, 6, 1), by_arrangement=True)
        exception = WorkingHoursException(
            exception_date=date(2025, 12, 25),
            single_shift=ExceptionSingleShift("10:00", "14:00"),
        )
        bp = BusinessPremises(
            oib="12312312316",
            premises_code="POS01",
            operator_oib="12312312316",
            regular_hours=[regular],
            exceptions=[exception],
        )
        client = Mock()
        tf = client.type_factory

        result = bp.to_ws_object(client)

        tf.RadnoVrijemeType.assert_called_once()
        tf.PoslovniProstorType.assert_called_once()
        call_kwargs = tf.PoslovniProstorType.call_args.kwargs
        assert str(call_kwargs["Oib"]) == "12312312316"
        assert call_kwargs["OznPosPr"] == "POS01"
        assert "OibOper" not in call_kwargs
        assert result == tf.PoslovniProstorType.return_value

    def test_to_delete_ws_object(self):
        regular = RegularWorkingHours(date_from=date(2025, 6, 1))
        exception = WorkingHoursException(exception_date=date(2025, 12, 25))
        bp = BusinessPremises(
            oib="12312312316",
            premises_code="POS01",
            operator_oib="12312312316",
            regular_hours=[regular],
            exceptions=[exception],
        )
        client = Mock()
        tf = client.type_factory

        result = bp.to_delete_ws_object(client)

        tf.RadnoVrijemeBrisanjeType.assert_called_once()
        brisanje_kwargs = tf.RadnoVrijemeBrisanjeType.call_args.kwargs
        assert brisanje_kwargs["Redovno"] == [{"DatumOd": "01.06.2025"}]
        assert brisanje_kwargs["Iznimke"] == [{"Datum": "25.12.2025"}]
        tf.PoslovniProstorType.assert_called_once()
        call_kwargs = tf.PoslovniProstorType.call_args.kwargs
        assert "OibOper" not in call_kwargs
        assert "BrisanjeRadnogVremena" in call_kwargs
        assert result == tf.PoslovniProstorType.return_value

    def test_to_batch_ws_object_regular(self):
        regular = RegularWorkingHours(date_from=date(2025, 6, 1), by_arrangement=True)
        bp = BusinessPremises(
            oib="12312312316",
            premises_code="POS02",
            operator_oib="12312312316",
            regular_hours=[regular],
        )
        client = Mock()
        tf = client.type_factory

        result = bp.to_batch_ws_object(client)

        tf.PoslovnicaType.assert_called_once()
        call_kwargs = tf.PoslovnicaType.call_args.kwargs
        assert call_kwargs["OznPosPr"] == "POS02"
        assert "Redovno" in call_kwargs
        assert result == tf.PoslovnicaType.return_value

    def test_to_batch_ws_object_exception(self):
        exception = WorkingHoursException(
            exception_date=date(2025, 12, 25),
            single_shift=ExceptionSingleShift("10:00", "14:00"),
        )
        bp = BusinessPremises(
            oib="12312312316",
            premises_code="POS03",
            operator_oib="12312312316",
            exceptions=[exception],
        )
        client = Mock()
        tf = client.type_factory

        result = bp.to_batch_ws_object(client)

        tf.PoslovnicaType.assert_called_once()
        call_kwargs = tf.PoslovnicaType.call_args.kwargs
        assert call_kwargs["OznPosPr"] == "POS03"
        assert "Iznimka" in call_kwargs
        assert result == tf.PoslovnicaType.return_value

    def test_to_batch_ws_object_empty_raises(self):
        bp = BusinessPremises(
            oib="12312312316",
            premises_code="POS04",
            operator_oib="12312312316",
        )
        client = Mock()
        with pytest.raises(ValueError, match="regular_hours or exceptions"):
            bp.to_batch_ws_object(client)


class TestEnums:
    def test_day_of_week_str(self):
        assert str(DayOfWeek.MONDAY) == "1"
        assert str(DayOfWeek.HOLIDAY) == "8"

    def test_even_odd_str(self):
        assert str(EvenOdd.EVEN) == "P"
        assert str(EvenOdd.ODD) == "N"

    def test_fetch_scope_str(self):
        assert str(FetchScope.ALL) == "SVE"
        assert str(FetchScope.REGULAR) == "REDOVNO"
        assert str(FetchScope.EXCEPTIONS) == "IZNIMKE"
