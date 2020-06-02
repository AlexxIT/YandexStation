# Yandex.Station for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Donate](https://img.shields.io/badge/donate-Yandex-red.svg)](https://money.yandex.ru/to/41001428278477)

Компонент для управления Яндекс.Станцией по локальной сети.

**Новые фичи в версии 2.0:**

- **Поддержка всех колонок** через облачное управление (*не все протестированы!*)
- Одновременное управление колонками по локальной сети и через облако

**Список колонок**

- [Яндекс.Станция](https://station.yandex.ru/#station) (большая) - поддержавается локальное и облачное управление
- [Яндекс.Модуль](https://alice.yandex.ru/modul) - поддержавается локальное и облачное управление
- [Яндекс.Станция Мини](https://yandex.ru/alice/station-mini/index-mobile) - только облачное управление
- [Irbis A](https://yandex.ru/promo/alice/irbis-a-m) - только облачное управление
- [DEXP Smartbox](https://yandex.ru/promo/alice/dexp-smartbox-m) - только облачное управление
- [Elari SmartBeat](https://elari.net/smartbeat/) - не тестировалась
- [LG XBOOM AI ThinQ WK7Y](https://www.lg.com/ru/audio/lg-WK7Y) - не тестировалась
- [Prestigio Smartmate Mayak Edition](https://prestigio.ru/smart-speaker/smartmate) - не тестировалась

Локальное управление **не поддерживаются на стороне Яндекса**. Если на колонку "прилетит" новая прошивка с поддержкой управления - она с высокой вероятностью "подхватится" без доработки компонента.

**Внимание:** у облачного управления нет обратной связи от колонки. Неизвестно играет ли колонка что-то или стоит на паузе и какая у неё актуальная громкость. Так что состояние колонки в Home Assistant может отличаться от актуального состояния колонки, если вы давали ей команды не из компонента.

Возможности локального и облачного управления:

- **управление воспроизведением и громкостью** станции
- **отправка TTS на станцию** из окна медиаплеера и через сервисы (**голосом Алисы!**)
- **отправка любых текстовых команд** на станцию из окна медиаплеера и через сервисы (например, *включи мою музыку*)
- **спецэффекты в TTS** (библиотека звуков и наложение эффектов на голос Алисы)

Дополнительные возможности локального управления:

- **просмотр что играет на станции**, включая обложку (только для музыки)
- **перемотка треков**

![media_player](media_player.png)

#### Карточка Яндекс Мини

<img src="yandex_mini.png" width="455" height="205">

## Настройка

Нужны имя и пароль аккаунта Яндекс, к которому привязаны колонки. Изучите код,
если думаете, что это небезопасно.

Двухфакторная авторизация работает по одноразовому паролю из приложения Яндекс Ключ. Главное успеть за 30 секунд :)

```yaml
yandex_station:
  username: myuser
  password: mypass
```

## Примеры использования

Если у вас в конфиге есть другие TTS, например от Google - [читайте это](#несколько-tts-в-конфиге).

Для шаблонов не забывайте указывать `data_template`, для остальных команд хватит просто `data`.

Поддерживаются команды на несколько станций одновременно (как TTS, так и media_player).

**Внимание:** Для каждой вашей колонки в мобильном приложении Яндекса будет создан **служебный сценарий**. Не трогайте его. Если случайно удалили - перезапустите Home Assistant.

### Обычный способ вызвать TTS

**Работает на всех колонках**

Зависит от настройки "Режим звука" (из окна медиа-плеера). Будет или произносить текст или выполнять команду. Он же вызывается из окна медиа-плеера.

```yaml
script:
  # TTS зависит от настройки "Режим звука"! (произнести или выполнить команду)
  yandex_tts1:
    alias: TTS зависит от настройки "Режим звука"!
    sequence:
    - service: tts.yandex_station_say
      entity_id: media_player.yandex_station
      data_template:
        message: Температура в комнате {{ states("sensor.temperature_hall")|round }} градуса.
```

### Второй способ вызвать TTS

**Работает на всех колонках**

Не зависит от настройки "Режим звука".

Команда всегда отправляется через облако, даже на большой Станции, потому что это единственно известный способ, чтоб станция НЕ продолжала слушать после TTS.

**Внимание:** у Яндекса стоит ограничение на **100 символов для TTS** через облачное управление! Включая спец.символы из раздела "Спецэффекты в TTS".

```yaml
script:
  # TTS не зависит от настройки "Режим звука"! и всегда будет произносить фразу
  yandex_tts2:
    alias: TTS не зависит от настройки "Режим звука"
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station
      data:
        media_content_id: Повторяю вашу фразу
        media_content_type: text
```

### Третий способ вызвать TTS

**Только для локального режима!**

Не зависит от настройки "Режим звука", но продолжает слушать после произнесения текста! Зато нет ограничения на количество символов. Поддерживает спецэффекты.

```yaml
script:
  yandex_tts3:
    alias: TTS только для локального режима
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station
      data:
        media_content_id: <speaker effect="megaphone">Объявление погоды на сегодня...
        media_content_type: dialog
```

### Спецэффекты в TTS

**Работает на всех колонках**

Все колонки поддерживают эффекты, библиотеку звуков и настройка речи:

- [Настройка генерацию речи](https://yandex.ru/dev/dialogs/alice/doc/speech-tuning-docpage/)
   ```yaml
   media_content_id: смелость sil <[500]> город+а берёт
   ```
- [Наложение эффектов на голос](https://yandex.ru/dev/dialogs/alice/doc/speech-effects-docpage/)
   ```yaml
   media_content_id: <speaker effect="megaphone">Ехал Грека через реку <speaker effect="-">видит Грека в реке рак
   ```
- [Библиотека звуков](https://yandex.ru/dev/dialogs/alice/doc/sounds-docpage/)
   ```yaml
   media_content_id: <speaker audio="alice-sounds-game-win-1.opus"> У вас получилось!
   ```

```yaml
script:
  yandex_tts4:  # работает и в локальном и в облачном режиме
    alias: TTS c эффектами
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station
      data:
        media_content_id: <speaker audio="alice-sounds-game-win-1.opus"> sil <[500]> Объявление погоды на сегодня...
        media_content_type: text
```

### Выполнение команд станцией

**Работает на всех колонках**

```yaml
script:
  yandex_command:  # работает и в локальном и в облачном режиме
    alias: Выполнить команду
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station
      data:
        media_content_id: Включи мою любимую музыку вперемешку
        media_content_type: command
```

### Примеры управления станцией

**Работает на всех колонках**

```yaml
script:
  yandex_volume_set:  # в локальном или облачном режиме
    alias: Меняем громкость нескольких станций
    sequence:
    - service: media_player.volume_set
      data:
        entity_id:
        - media_player.yandex_station_12345678901234567890
        - media_player.yandex_station_98765432109876543210
        volume_level: 0.5
```

**Только для локального режима!**

```yaml
script:
  yandex_play_album:  # только в локальном режиме!!!
    alias: Включить Би-2 на Станции
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station
      data:
        media_content_id: 60062    # ID альбома в Яндекс.Музыка
        media_content_type: album  # album, track or playlist
```

## Внешний вид

Красивые [иконки Яндекс устройств](https://github.com/iswitch/ha-yandex-icons) можно установить через HACS.

[![Иконки Яндекс устройств для Home Assistant](https://img.youtube.com/vi/lRD0nnNt5f0/mqdefault.jpg)](https://www.youtube.com/watch?v=lRD0nnNt5f0)

Красивый [медиа плеер](https://github.com/kalkih/mini-media-player) можно установить через HACS.

**Внимание:** правильно указывайте название вашего TTS сервиса. По умолчанию он `yandex_station`. Если вы его не изменили на `alice` по инструкции про [несколько TTS](#несколько-tts-в-конфиге). Тут `_say` на конце не нужно указывать.

Пример как настроить [такую](https://github.com/AlexxIT/YandexStation/blob/master/yandex_mini.png) карточку:

```yaml
entity: media_player.yandex_station_mini
shortcuts:
  attribute: sound_mode
  buttons:
    - icon: 'mdi:voice'
      id: Произнеси текст
      type: sound_mode
    - icon: 'mdi:google-assistant'
      id: Выполни команду
      type: sound_mode
    - icon: 'mdi:playlist-star'
      id: включи мою любимую музыку вперемешку
      type: command
    - icon: 'mdi:playlist-music'
      id: включи плейлист дня
      type: command
    - icon: 'mdi:heart'
      id: лайк
      type: command
    - icon: 'mdi:heart-off'
      id: снять лайк
      type: command
  columns: 6
tts:
  platform: yandex_station
type: 'custom:mini-media-player'
```

## Продвинутое использование команд

**Только для локального режима!**

Компонент создаёт сервис `yandex_station.send_command`, которому необходимо передать команду.

Полезные команды станции можно узнать [тут](https://documenter.getpostman.com/view/525400/SWLfd8et?version=latest).

Самая универсальная - это `sendText`. Станция выполнит посланную фразу, как буд-то услышала команду голосом.

Выбрать станцию можно указав `entity_id` или `device` (для обратной совместимости). В качесте `device` может быть название станции или идентификатор. Можно посмотреть в приложении Яндекс или в [веб](https://quasar.yandex.ru/skills/iot) интерфейсе.

Если станция одна - можно ничего не указывать.

```yaml
script:
  yandex_tts:
    alias: TTS на Яндекс.Станции
    sequence:
    - service: yandex_station.send_command
      data:
        entity_id: media_player.yandex_station_12345678901234567890
        command: sendText
        text: Повтори за мной 'Привет, человек!'
```

## Звук Яндекс.Станции по HDMI

Больше не поддерживается. Яндекс его поломал! :(

## Несколько TTS в конфиге

TTS Яндекса работает только с их колонками и не работает с другими, например 
Google Mini. Так и другие TTS не работают с колонками Яндекса.
 
В этом случае вы можете настроить несколько TTS сервисов. Из окна медиа плеера
всех колонок всегда будет стартовать первый повавшийся сервис (в алфавитном 
порядке). Поэтому название TTS сервиса Яндекса можно переименовать, например, в 
`alice_say` (слово `say` на конце обязательно!).

```yaml
yandex_station:
  username: myuser
  password: mypass
  tts_service_name: alice_say

tts:
- platform: google_translate
  language: ru
```

## Получение команд от станции

**Только для продвинутых пользователей**

Для работы функционала должна быть настроена [интеграция](https://github.com/dmitry-k/yandex_smart_home) Home Assistant с умным домом Яндекса!

1. Настройте список фраз, на которые ваши станции должны реагировать и ответы на них. Если не хотите ответ - просто поставьте точку как в примере. При первом запуске копонент создаёт служебный медиа-плеер `media_player.yandex_intents`.
2. Синхронизируйте ваши устройства в мобильном приложении Яндекса, чтоб этот плеер появился и там. Не нужно его переименовывать и перемещать в комнаты.
3. Перезапустите Home Assistant. В мобильном приложении Яндекса должны появиться ваши сценарии.

В ответ на эти фразы в Home Assistan будет генерироваться событие типа `yandex_intent` с произнесённым текстом. Теперь можете писать свои автоматизации на YAML или Node-RED.

```yaml
yandex_station:
  username: myuser
  password: mypass
  intents:
    Покажи сообщение: ага
    Какая температура в комнате: .
    Какая влажность в комнате: .

automation:
- trigger:
    platform: event
    event_type: yandex_intent
    event_data:
      text: Покажи сообщение
  action:
    service: persistent_notification.create
    data:
      title: Сообщение со станции
      message: Шеф, станция чего-то хочет
```

## Локальное управление по токену

Если есть Oauth-токен с правами на Яндекс.Музыку, можно так. Не спрашивайте как его достать.

Но в этом случае будет работать только локальное управление на тех колонках, кто его поддерживает.

```yaml
yandex_station:
  token: abcdefghijklmnopqrstuvwxyz
```

## Полезные ссылки

- https://github.com/sergejey/majordomo-yadevices
- https://github.com/anVlad11/dd-alicization
