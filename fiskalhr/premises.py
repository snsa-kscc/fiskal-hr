import re
from datetime import date
from typing import TYPE_CHECKING, Any, List, Optional, Union

from .enums import DayOfWeek, EvenOdd
from .oib import OIB

if TYPE_CHECKING:
    from .ws import FiskalClient


class SingleShiftHours:
    """
    Jednokratno radno vrijeme

    Working hours for a single shift on a given day of the week.
    """

    def __init__(self, day: DayOfWeek, time_from: str, time_to: str):
        self.day = day
        self.time_from = time_from
        self.time_to = time_to

    def to_ws_object(self, type_factory: Any) -> Any:
        return type_factory.JednokratnoRVType(
            DanUTjednu=self.day,
            RadnoVrijemeOd=self.time_from,
            RadnoVrijemeDo=self.time_to,
        )


class DoubleShiftHours:
    """
    Dvokratno radno vrijeme

    Working hours for a split/double shift on a given day.
    shift_part is 1 (first part) or 2 (second part).
    """

    def __init__(self, day: DayOfWeek, shift_part: int, time_from: str, time_to: str):
        if shift_part not in (1, 2):
            raise ValueError("shift_part must be 1 or 2")
        self.day = day
        self.shift_part = shift_part
        self.time_from = time_from
        self.time_to = time_to

    def to_ws_object(self, type_factory: Any) -> Any:
        return type_factory.DvokratnoRVType(
            DanUTjednu=self.day,
            DioDvokratnog=str(self.shift_part),
            RadnoVrijemeOd=self.time_from,
            RadnoVrijemeDo=self.time_to,
        )


class EvenOddHours:
    """
    Parni/neparni radno vrijeme

    Working hours for even or odd days of the week.
    """

    def __init__(self, day: DayOfWeek, even_odd: EvenOdd, time_from: str, time_to: str):
        self.day = day
        self.even_odd = even_odd
        self.time_from = time_from
        self.time_to = time_to

    def to_ws_object(self, type_factory: Any) -> Any:
        return type_factory.ParniNeparniRVType(
            DanUTjednu=self.day,
            ParniNeparniDani=self.even_odd,
            RadnoVrijemeOd=self.time_from,
            RadnoVrijemeDo=self.time_to,
        )


class RegularWorkingHours:
    """
    Redovno radno vrijeme

    Regular working hours starting from a given date.
    Exactly one of: by_arrangement, single_shifts, double_shifts,
    or even_odd_shifts must be set.
    """

    def __init__(
        self,
        date_from: date,
        note: Optional[str] = None,
        by_arrangement: bool = False,
        single_shifts: Optional[List[SingleShiftHours]] = None,
        double_shifts: Optional[List[DoubleShiftHours]] = None,
        even_odd_shifts: Optional[List[EvenOddHours]] = None,
    ):
        self.date_from = date_from
        self.note = note
        self.by_arrangement = by_arrangement
        self.single_shifts = single_shifts
        self.double_shifts = double_shifts
        self.even_odd_shifts = even_odd_shifts

    def to_ws_object(self, type_factory: Any) -> Any:
        kwargs = {
            "DatumOd": self.date_from.strftime("%d.%m.%Y"),
        }

        if self.note:
            kwargs["Napomena"] = self.note

        if self.by_arrangement:
            kwargs["PoDogovoru"] = type_factory.PoDogovoruRVType(RedovnoPoDogovoru="DA")
        elif self.single_shifts:
            kwargs["Jednokratno"] = [
                s.to_ws_object(type_factory) for s in self.single_shifts
            ]
        elif self.double_shifts:
            kwargs["Dvokratno"] = [
                s.to_ws_object(type_factory) for s in self.double_shifts
            ]
        elif self.even_odd_shifts:
            kwargs["ParniNeparni"] = [
                s.to_ws_object(type_factory) for s in self.even_odd_shifts
            ]

        return type_factory.RedovnoRadnoVrijemeType(**kwargs)


class ExceptionSingleShift:
    """
    Jednokratno radno vrijeme za iznimku

    Exception working hours (single shift) -- no day field, just times.
    """

    def __init__(self, time_from: str, time_to: str):
        self.time_from = time_from
        self.time_to = time_to

    def to_ws_object(self, type_factory: Any) -> Any:
        return type_factory.JednokratnoIznimkaType(
            RadnoVrijemeOd=self.time_from,
            RadnoVrijemeDo=self.time_to,
        )


class ExceptionDoubleShift:
    """
    Dvokratno radno vrijeme za iznimku

    Exception working hours (double shift) -- no day field.
    """

    def __init__(self, shift_part: int, time_from: str, time_to: str):
        if shift_part not in (1, 2):
            raise ValueError("shift_part must be 1 or 2")
        self.shift_part = shift_part
        self.time_from = time_from
        self.time_to = time_to

    def to_ws_object(self, type_factory: Any) -> Any:
        return type_factory.DvokratnoIznimkaType(
            DioDvokratnog=str(self.shift_part),
            RadnoVrijemeOd=self.time_from,
            RadnoVrijemeDo=self.time_to,
        )


class WorkingHoursException:
    """
    Iznimka radnog vremena

    An exception to regular working hours on a specific date.
    Must have either a single_shift or double_shifts set.
    """

    def __init__(
        self,
        exception_date: date,
        single_shift: Optional[ExceptionSingleShift] = None,
        double_shifts: Optional[List[ExceptionDoubleShift]] = None,
    ):
        self.exception_date = exception_date
        self.single_shift = single_shift
        self.double_shifts = double_shifts

    def to_ws_object(self, type_factory: Any) -> Any:
        kwargs = {
            "Datum": self.exception_date.strftime("%d.%m.%Y"),
        }

        if self.single_shift:
            kwargs["Jednokratno"] = self.single_shift.to_ws_object(type_factory)
        elif self.double_shifts:
            kwargs["Dvokratno"] = [
                s.to_ws_object(type_factory) for s in self.double_shifts
            ]

        return type_factory.IznimkaRadnogVremenaType(**kwargs)


class BusinessPremises:
    """
    Poslovni prostor - radno vrijeme

    Represents a business premises with its working hours for registration,
    deletion, or fetching via the Fiskalizacija service.
    """

    PREMISES_CODE_PATTERN = re.compile(r"^[0-9a-zA-Z]{1,20}$")

    def __init__(
        self,
        oib: Union[OIB, str],
        premises_code: str,
        operator_oib: Union[OIB, str],
        regular_hours: Optional[List[RegularWorkingHours]] = None,
        exceptions: Optional[List[WorkingHoursException]] = None,
    ):
        self.oib = OIB(oib)
        self.premises_code = premises_code
        self.operator_oib = OIB(operator_oib)
        self.regular_hours = regular_hours or []
        self.exceptions = exceptions or []

    @property
    def premises_code(self) -> str:
        return self._premises_code

    @premises_code.setter
    def premises_code(self, value: str) -> None:
        if not self.PREMISES_CODE_PATTERN.match(value):
            raise ValueError("Premises code must be 1-20 alphanumeric characters")
        self._premises_code = value

    def to_ws_object(self, client: "FiskalClient") -> Any:
        """Build SOAP object for registering working hours"""
        tf = client.type_factory

        rv = tf.RadnoVrijemeType(
            Redovno=[r.to_ws_object(tf) for r in self.regular_hours],
            Iznimke=[e.to_ws_object(tf) for e in self.exceptions],
        )

        return tf.PoslovniProstorRVType(
            Oib=self.oib,
            OznPosPr=self.premises_code,
            RadnoVrijeme=rv,
            OibOper=self.operator_oib,
        )

    def to_delete_ws_object(self, client: "FiskalClient") -> Any:
        """Build SOAP object for deleting working hours"""
        tf = client.type_factory

        redovno = [
            tf.BrisanjeRedovnogType(DatumOd=r.date_from.strftime("%d.%m.%Y"))
            for r in self.regular_hours
        ]

        iznimke = [
            tf.BrisanjeIznimkeType(Datum=e.exception_date.strftime("%d.%m.%Y"))
            for e in self.exceptions
        ]

        brisanje = tf.BrisanjeRadnogVremenaType(
            Redovno=redovno,
            Iznimke=iznimke,
        )

        return tf.PoslovniProstorBrisanjeRVType(
            Oib=self.oib,
            OznPosPr=self.premises_code,
            BrisanjeRadnogVremena=brisanje,
            OibOper=self.operator_oib,
        )

    def to_batch_ws_object(self, client: "FiskalClient") -> Any:
        """Build a single Poslovnica element for batch registration"""
        tf = client.type_factory

        rv = tf.RadnoVrijemeType(
            Redovno=[r.to_ws_object(tf) for r in self.regular_hours],
            Iznimke=[e.to_ws_object(tf) for e in self.exceptions],
        )

        return tf.PoslovnicaRVType(
            OznPosPr=self.premises_code,
            RadnoVrijeme=rv,
        )
