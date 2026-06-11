from app.schemas.common import Quality
from app.schemas.raw import RawData
from app.schemas.state import StateData


def test_raw_and_state_schema_validate():
    raw = RawData(source="seat_pressure", device_id="sim", data={"pressure_sum": 1}, quality=Quality(confidence=0.9))
    state = StateData(sedentary_minutes=30, humidity_percent=50)
    assert raw.quality.valid is True
    assert state.comfort_status == "comfortable"
