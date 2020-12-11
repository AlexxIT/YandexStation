import logging

from .yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)

IOT_TYPES = {
    'on': 'devices.capabilities.on_off',
    'temperature': 'devices.capabilities.range',
    'fan_speed': 'devices.capabilities.mode',
    'thermostat': 'devices.capabilities.mode',
    'volume': 'devices.capabilities.range',
    'pause': 'devices.capabilities.toggle',
    'mute': 'devices.capabilities.toggle',
    'channel': 'devices.capabilities.range',
    'input_source': 'devices.capabilities.mode',
    'brightness': 'devices.capabilities.range',
    'color': 'devices.capabilities.color_setting',
    # don't work
    'hsv': 'devices.capabilities.color_setting',
    'rgb': 'devices.capabilities.color_setting',
    'temperature_k': 'devices.capabilities.color_setting',
}

MASK_EN = '0123456789abcdef-'
MASK_RU = 'оеаинтсрвлкмдпуяы'

URL_USER = 'https://iot.quasar.yandex.ru/m/user'


def encode(uid: str) -> str:
    """Кодируем UID в рус. буквы. Яндекс привередливый."""
    return 'ХА ' + ''.join([MASK_RU[MASK_EN.index(s)] for s in uid])


def decode(uid: str) -> str:
    """Раскодируем UID из рус.букв."""
    return ''.join([MASK_EN[MASK_RU.index(s)] for s in uid[3:]])


class YandexQuasar:
    # all devices
    devices = None

    def __init__(self, session: YandexSession):
        self.session = session

    @property
    def hass_id(self):
        for device in self.devices:
            if device['name'] == "Yandex Intents":
                return device['id']
        return None

    async def init(self):
        """Основная функция. Возвращает список колонок."""
        _LOGGER.debug("Получение списка устройств.")

        r = await self.session.get(f"{URL_USER}/devices")
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        self.devices = [device for room in resp['rooms']
                        for device in room['devices']]
        self.devices += resp['speakers'] + resp['unconfigured_devices']

    @property
    def speakers(self):
        return [
            device for device in self.devices
            if device['type'].startswith('devices.types.smart_speaker') or
               device['type'].endswith('yandex.module')
        ]

    async def load_speakers(self) -> list:
        speakers = self.speakers

        # Яндекс начали добавлять device_id и platform с полным списком
        # устройств
        # for speaker in speakers:
        #     await self.load_speaker_config(speaker)

        scenarios = await self.load_scenarios()
        for speaker in speakers:
            device_id = speaker['id']

            if device_id not in scenarios:
                await self.add_scenario(device_id)
                scenarios = await self.load_scenarios()

            speaker['scenario_id'] = scenarios[device_id]['id']

        return speakers

    async def load_speaker_config(self, device: dict):
        """Загружаем device_id и platform для колонок. Они не приходят с полным
        списком устройств.
        """
        r = await self.session.get(
            f"{URL_USER}/devices/{device['id']}/configuration")
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        # device_id and platform
        device.update(resp['quasar_info'])

    async def load_scenarios(self) -> dict:
        """Получает список сценариев, которые мы ранее создали."""
        r = await self.session.get(f"{URL_USER}/scenarios")
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        return {
            decode(d['name']): d
            for d in resp['scenarios']
            if d['name'].startswith('ХА ')
        }

    async def add_scenario(self, device_id: str):
        """Добавляет сценарий-пустышку."""
        payload = {
            'name': encode(device_id),
            'icon': 'home',
            'trigger_type': 'scenario.trigger.voice',
            'requested_speaker_capabilities': [],
            'devices': [{
                'id': device_id,
                'capabilities': [{
                    'type': 'devices.capabilities.quasar.server_action',
                    'state': {
                        'instance': 'phrase_action',
                        'value': 'пустышка'
                    }
                }]
            }]
        }
        r = await self.session.post(f"{URL_USER}/scenarios", json=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def add_intent(self, name: str, text: str, num: int):
        speaker = [{
            'type': 'devices.capabilities.quasar.server_action',
            'state': {
                'instance': 'phrase_action',
                'value': text
            }
        }] if text else [{
            'type': 'devices.capabilities.quasar.server_action',
            'state': {
                'instance': 'text_action',
                'value': "Yandex Intents громкость 100"
            }
        }]

        payload = {
            'name': name,
            'icon': 'home',
            'trigger_type': 'scenario.trigger.voice',
            'requested_speaker_capabilities': speaker,
            'devices': [{
                'id': self.hass_id,
                'capabilities': [{
                    'type': 'devices.capabilities.range',
                    'state': {
                        'instance': 'volume',
                        'relative': False,
                        'value': num
                    }
                }]
            }]
        }
        r = await self.session.post(f"{URL_USER}/scenarios", json=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def send(self, device: dict, text: str, is_tts: bool = False):
        """Запускает сценарий на выполнение команды или TTS.
        """
        device_id = device['id']
        _LOGGER.debug(f"{device['name']} => cloud | {text}")

        action = 'phrase_action' if is_tts else 'text_action'
        payload = {
            'name': encode(device_id),
            'icon': 'home',
            'trigger_type': 'scenario.trigger.voice',
            'requested_speaker_capabilities': [],
            'devices': [{
                'id': device_id,
                'capabilities': [{
                    'type': 'devices.capabilities.quasar.server_action',
                    'state': {
                        'instance': action,
                        'value': text
                    }
                }]
            }]
        }

        sid = device['scenario_id']

        r = await self.session.put(f"{URL_USER}/scenarios/{sid}", json=payload)
        resp = await r.json()
        assert resp['status'] == 'ok', resp

        r = await self.session.post(f"{URL_USER}/scenarios/{sid}/actions")
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def load_local_speakers(self):
        """Загружает список локальных колонок. Не используется."""
        try:
            r = await self.session.get(
                'https://quasar.yandex.net/glagol/device_list')
            resp = await r.json()
            return [{
                'device_id': d['id'],
                'name': d['name'],
                'platform': d['platform']
            } for d in resp['devices']]

        except:
            _LOGGER.exception("Load local speakers")
            return None

    async def get_device_config(self, device: dict) -> dict:
        payload = {'device_id': device['quasar_info']['device_id'],
                   'platform': device['quasar_info']['platform']}
        r = await self.session.get(
            'https://quasar.yandex.ru/get_device_config', params=payload
        )
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        return resp['config']

    async def set_device_config(self, device: dict, device_config: dict):
        _LOGGER.debug(f"Меняем конфиг станции: {device_config}")

        payload = {'device_id': device['quasar_info']['device_id'],
                   'platform': device['quasar_info']['platform']}
        r = await self.session.post(
            'https://quasar.yandex.ru/set_device_config', params=payload,
            json=device_config
        )
        resp = await r.json()
        assert resp['status'] == 'ok', resp

    async def get_device(self, deviceid: str):
        r = await self.session.get(f"{URL_USER}/devices/{deviceid}")
        resp = await r.json()
        assert resp['status'] == 'ok', resp
        return resp

    async def device_action(self, deviceid: str, **kwargs):
        _LOGGER.debug(f"Device action: {kwargs}")

        actions = []
        for k, v in kwargs.items():
            type_ = (
                'devices.capabilities.custom.button'
                if k.isdecimal() else IOT_TYPES[k]
            )
            state = (
                {'instance': k, 'value': v, 'relative': True}
                if k in ('volume', 'channel')
                else {'instance': k, 'value': v}
            )
            actions.append({'type': type_, 'state': state})

        r = await self.session.post(
            f"{URL_USER}/devices/{deviceid}/actions", json={'actions': actions}
        )
        resp = await r.json()
        assert resp['status'] == 'ok', resp
