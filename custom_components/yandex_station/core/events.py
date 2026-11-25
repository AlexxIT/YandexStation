"""Distinguish activations from cached event-property states."""

from datetime import datetime, timezone


class YandexEventTracker:
    def __init__(self):
        self._seen: dict[tuple[str, str], tuple[datetime | None, set[str]]] = {}

    def update(self, device: dict, *, live: bool = False) -> list[dict]:
        events = []
        for prop in device.get("properties", []):
            if prop.get("type") != "devices.properties.event":
                continue
            instance = prop.get("parameters", {}).get("instance")
            state = prop.get("state") or {}
            instance = instance or state.get("instance")
            if not instance:
                continue

            key = (device["id"], instance)
            known = key in self._seen
            previous, values = self._seen.get(key, (None, set()))
            activated = prop.get("last_activated")
            try:
                timestamp = datetime.fromisoformat(activated.replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    continue
                timestamp = timestamp.astimezone(timezone.utc)
            except (AttributeError, TypeError, ValueError):
                # last_updated can also change on a refresh. It is not proof
                # that an event happened, so do not use it as a fallback.
                self._seen.setdefault(key, (None, set()))
                continue

            value = state.get("value")
            if not isinstance(value, str):
                continue
            if previous is not None and (
                timestamp < previous or (timestamp == previous and value in values)
            ):
                continue
            values = values | {value} if timestamp == previous else {value}
            self._seen[key] = (timestamp, values)

            # Initial/reconnect snapshots establish a baseline, never events.
            # An unknown property in a live message needs a baseline too.
            if live and known and device.get("state") != "offline":
                events.append(
                    {
                        "device_id": device["id"],
                        "instance": instance,
                        "value": value,
                        "last_activated": activated,
                    }
                )
        return events
