from datetime import date, timedelta

from fiskalhr.enums import DayOfWeek, FetchScope
from fiskalhr.oib import OIB
from fiskalhr.premises import (
    BusinessPremises,
    RegularWorkingHours,
    SingleShiftHours,
)
from fiskalhr.signature import Signer, Verifier
from fiskalhr.ws import FiskalClient

DEMO_PEM = "dvasadva-demo.pem"
FINA_BUNDLE = "fina-demo-bundle.pem"
FISKAL_CERT = "fiskalcistest.pem"
WSDL = "testdata/ws/wsdl/FiskalizacijaService.wsdl"
OIB_VAL = "68847910990"

signer = Signer(DEMO_PEM)
verifier = Verifier(FISKAL_CERT, [FINA_BUNDLE])
fc = FiskalClient(FINA_BUNDLE, WSDL, signer, verifier)

print("Testing echo service...")
fc.test_service()
print("Echo OK")

# Register working hours: single shift Mon-Fri, starting tomorrow
start_date = date.today() + timedelta(days=1)

regular = RegularWorkingHours(
    date_from=start_date,
    note="Standardno radno vrijeme",
    single_shifts=[
        SingleShiftHours(DayOfWeek.MONDAY, "08:00", "16:00"),
        SingleShiftHours(DayOfWeek.TUESDAY, "08:00", "16:00"),
        SingleShiftHours(DayOfWeek.WEDNESDAY, "08:00", "16:00"),
        SingleShiftHours(DayOfWeek.THURSDAY, "08:00", "16:00"),
        SingleShiftHours(DayOfWeek.FRIDAY, "08:00", "16:00"),
    ],
)

premises = BusinessPremises(
    oib=OIB_VAL,
    premises_code="TEST",
    operator_oib=OIB_VAL,
    regular_hours=[regular],
)

print(f"Submitting working hours for premises TEST, starting {start_date}...")
fc.submit_working_hours(premises)
print("Working hours registered OK")
