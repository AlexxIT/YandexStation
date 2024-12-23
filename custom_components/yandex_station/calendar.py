import logging
from datetime import datetime, timedelta

from dateutil.rrule import rrulestr
from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .core.const import DOMAIN
from .core.yandex_quasar import YandexQuasar

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    quasar: YandexQuasar = hass.data[DOMAIN][entry.unique_id]
    # can't use update_before_add because it works for disabled entities
    async_add_entities([YandexCalendar(quasar, sp) for sp in quasar.speakers])


class YandexCalendar(CalendarEntity):
    _attr_entity_registry_enabled_default = False
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT
        | CalendarEntityFeature.UPDATE_EVENT
        | CalendarEntityFeature.DELETE_EVENT
    )

    def __init__(self, quasar: YandexQuasar, device: dict):
        self.quasar = quasar
        self.device = device

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["quasar_info"]["device_id"])},
            name=self.device["name"],
        )
        self._attr_name = device["name"] + " Будильники"
        self._attr_unique_id = device["quasar_info"]["device_id"] + f"_calendar"

        self.entity_id = f"calendar.yandex_station_{self._attr_unique_id.lower()}"

        self.events: list[CalendarEvent] = []
        self.next_event: CalendarEvent | None = None

    @property
    def event(self) -> CalendarEvent | None:
        return self.next_event

    async def async_update(self):
        try:
            alarms = await self.quasar.get_alarms(self.device)
            self.events = [alarm_to_event(i) for i in alarms]
            dt = datetime.now().astimezone()
            for event in sorted(self.events, key=lambda x: x.start):
                if event.start >= dt:
                    self.next_event = event
                    break
            else:
                self.next_event = None
        except:
            pass

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [i for i in self.events if start_date <= i.start and i.end <= end_date]

    async def async_create_event(self, **kwargs) -> None:
        if await self.quasar.create_alarm(self.device, event_to_alarm(kwargs)):
            await self.async_update_ha_state(force_refresh=True)

    async def async_delete_event(self, uid: str, **kwargs) -> None:
        if await self.quasar.cancel_alarms(self.device, uid):
            await self.async_update_ha_state(force_refresh=True)

    async def async_update_event(self, uid: str, event: dict, **kwargs) -> None:
        if await self.quasar.change_alarm(self.device, event_to_alarm(event, uid)):
            await self.async_update_ha_state(force_refresh=True)


DAYS_ALARM = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
DAYS_EVENT = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
DURATION = timedelta(minutes=1)


def alarm_to_event(alarm: dict) -> CalendarEvent:
    if r := alarm.get("recurring"):
        days = [DAYS_EVENT[DAYS_ALARM.index(i)] for i in r["days_of_week"]]
        r = "FREQ=WEEKLY;BYDAY=" + ",".join(days)
        dt = datetime.strptime(alarm["time"], "%H:%M")
        rule = rrulestr(r).replace(dtstart=dt)
        dt = datetime.now()
        dt = rule.after(dt) if alarm["enabled"] else rule.before(dt)
    else:
        dt = datetime.strptime(f'{alarm["date"]}T{alarm["time"]}', "%Y-%m-%dT%H:%M")

    dt = dt.astimezone()  # add current timezone
    summary = "Будильник" if alarm["enabled"] else "Выключен"
    return CalendarEvent(dt, dt + DURATION, summary, "", uid=alarm["alarm_id"], rrule=r)


def event_to_alarm(event: dict, uid: str = "") -> dict:
    alarm = {
        "alarm_id": uid,
        "enabled": event["summary"] != "Выключен",
        "time": event["dtstart"].strftime("%H:%M"),
    }

    if "rrule" in event:
        r: dict[str, str] = dict(s.split("=", 1) for s in event["rrule"].split(";"))
        days = [DAYS_ALARM[DAYS_EVENT.index(i)] for i in r["BYDAY"].split(",")]
        alarm["recurring"] = {"days_of_week": days}
    else:
        alarm["date"] = event["dtstart"].strftime("%Y-%m-%d")

    return alarm
