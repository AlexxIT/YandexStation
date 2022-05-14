# Яндекс.Станция для Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Donate](https://img.shields.io/badge/donate-Yandex-red.svg)](https://money.yandex.ru/to/41001428278477)

Компонент для управления [Яндекс.Станцией](https://yandex.ru/alice/station) и другими колонками с [Алисой](https://yandex.ru/alice) из [Home Assistant](https://www.home-assistant.io/).

<img src="yandex_station.png" width="491">

**Внимание**. В тексте часто используются термины локальная колонка, локальный режим и локальное управление (они несут одинаковый смысл). Внимательно изучите, какие колонки его поддерживают. Функции и возможности локального управления сильно превосходят облачное управление. Облачное управление поддерживается на всех колонках, но не поддерживается на модулях. Локальный режим включается автоматически на поддерживаемых колонках.

**Список устройств с локальным управлением**

- [Яндекс.Станция](https://station.yandex.ru/#station) (большая)
- [Яндекс.Станция Макс](https://yandex.ru/alice/station-max/)
- [Яндекс.Станция Мини](https://yandex.ru/alice/station-mini)
- [Яндекс.Станция Лайт](https://yandex.ru/alice/station-lite)
- [Яндекс.Станция Мини 2](https://yandex.ru/alice/station-mini-new) (с часами и без)

**Поддержка локального управления не гарантирована**

- [JBL Link Music](https://yandex.ru/alice/jbl)
- [JBL Link Portable](https://yandex.ru/alice/jbl)

**Список устройств с облачным управлением**

- [DEXP Smartbox](https://yandex.ru/promo/alice/dexp-smartbox-m)
- [Elari SmartBeat](https://elari.net/smartbeat/)
- [Irbis A](https://yandex.ru/promo/alice/irbis-a-m)
- [LG XBOOM AI ThinQ WK7Y](https://www.lg.com/ru/audio/lg-WK7Y)
- [Prestigio Smartmate Mayak Edition](https://prestigio.ru/smart-speaker/smartmate)

**Список устройств с только локальным управлением**

- [Яндекс.Модуль](https://ru.wikipedia.org/wiki/%D0%AF%D0%BD%D0%B4%D0%B5%D0%BA%D1%81.%D0%9C%D0%BE%D0%B4%D1%83%D0%BB%D1%8C) (первый, устарел, поддержка ограничена)
- [Яндекс.Модуль 2](https://plus.yandex.ru/module)

**Внимание:** у облачного управления нет обратной связи от колонки. Неизвестно, играет ли колонка что-то или стоит на паузе, и какая у неё актуальная громкость. Так что состояние колонки в Home Assistant может отличаться от актуального состояния колонки, если вы давали ей команды не из компонента.

Возможности локального и облачного управления:

- **управление воспроизведением и громкостью** станции
- **отправка TTS на станцию** из окна медиаплеера и через сервисы (**голосом Алисы!**)
- **отправка любых текстовых команд** на станцию из окна медиаплеера и через сервисы (например, *включи мою музыку*)
- **спецэффекты в TTS** (библиотека звуков и наложение эффектов на голос Алисы)

Дополнительные возможности локального управления:

- **просмотр что играет на станции**, включая обложку (только для музыки)
- **перемотка треков**

# Оглавление

- [Полезные компоненты](#полезные-компоненты)
- [Установка](#установка)
- [Настройка](#настройка)

**[Возможности всех колонок](#возможности-всех-колонок)**

- [Первый способ вызвать TTS](#первый-способ-вызвать-tts)
- [Спецэффекты в TTS](#спецэффекты-в-tts)
- [Медиа браузер](#медиа-браузер)
- [Внешний вид](#внешний-вид)
- [Выполнение команд станцией](#выполнение-команд-станцией)
- [Примеры управления станцией](#примеры-управления-станцией)
- [Получение команд от станции](#получение-команд-от-станции)
- [Интеграция с Яндекс.Диалогами](#интеграция-с-яндексдиалогами)
  - [Второй способ вызвать TTS](#второй-способ-вызвать-tts)
  - [Диалог с колонкой](#диалог-с-колонкой)
- [Уведомления и предупреждения](#уведомления-и-предупреждения) 

**[Возможности локальных колонок](#возможности-локальных-колонок)**

- [Третий способ вызвать TTS](#третий-способ-вызвать-tts)
- [Громкость TTS](#громкость-tts)
- [Стриминг музыки](#стриминг-музыки)
- [Проигрывание медиа по ссылкам](#проигрывание-медиа-по-ссылкам)
- [Яндекс Алиса в Telegram](#яндекс-алиса-в-telegram)
- [Яндекс Алиса в Lovelace](#яндекс-алиса-в-lovelace)
- [Список покупок](#список-покупок)
- [Статический IP для колонки](#статический-ip-для-колонки)

**[Прочие функции](#прочие-функции)**

- [Управление умным домом Яндекса](#управление-умным-домом-яндекса)
- [Изменение настроек Алисы](#изменение-настроек-алисы)
- [Несколько TTS в конфиге](#несколько-tts-в-конфиге)
- [Звук Яндекс.Станции по HDMI](#звук-яндексстанции-по-hdmi)
- [Управление яркостью экрана станции Макс](#управление-яркостью-станции-макс)
- [Поиск и устранение проблем](#troubleshooting)
- [Полезные автоматизации](#полезные-автоматизации)
- [Полезные ссылки](#полезные-ссылки)

# Полезные компоненты

**Не все из этих компонентов за моим авторством!**

- [Yandex.Station](https://github.com/AlexxIT/YandexStation) - позволяет управлять вашими колонками с Алисой из Home Assistant, отправлять на них голосовые уведомления и много чего ещё
- [Yandex Smart Home](https://github.com/dmitry-k/yandex_smart_home) - позволяет добавить ваши умные устройства из Home Assistant в умный дом Яндекса и управлять ими с любого устройства с Алисой, в том числе с колонок
- [Браузер Яндекс.Музыки](https://github.com/alryaz/hass-yandex-music-browser) - позволяет выбирать и включать треки Яндекс.Музыки из Home Assistant
- [YandexDialogs](https://github.com/AlexxIT/YandexDialogs) - позволяет получать команды от устройств с Алисой в Home Assistant через платформу Яндекс.Диалоги
- [Yandex.Station Intents](https://github.com/dext0r/ha-yandex-station-intents) - позволяет получать команды от устройств с Алисой в Home Assistant через сценарии Яндекса
- [HassWP](https://github.com/AlexxIT/HassWP) - позволяет быстро и легко "попробовать" Home Assistant на компьютере Windows
- [Dataplicity](https://github.com/AlexxIT/Dataplicity) - позволяет легко огранизовать публичный HTTPS-доступ к вашему серверу Home Assistant
- [Morph Numbers](https://github.com/AlexxIT/MorphNumbers) - позволяет правильно склонять числительные для отправки в TTS или Telegram
- [VacuumZones](https://github.com/AlexxIT/VacuumZones) - позволяет легко управлять зональной уборкой на пылесосах Xiaomi с помощью голосовых команд

# Установка

**Способ 1.** [HACS](https://hacs.xyz/) > Интеграции > Добавить > Yandex.Station > Установить

**Способ 2.** Вручную скопируйте папку `yandex_station` из [latest release](https://github.com/AlexxIT/YandexStation/releases/latest) в директорию `/config/custom_components`.

# Настройка

**Внимание:** Для каждой вашей колонки в мобильном приложении Яндекса будет создан *служебный сценарий*. Не трогайте его. Если случайно удалили - перезапустите Home Assistant.

**Способ 1.** GUI (рекомендуется)

> Настройки > Интеграции > Добавить интеграцию > **Yandex Station**

Если интеграции нет в списке - очистите кэш браузера.

Поддерживается несколько способов авторизации:

- **QR-код** - рекомендуется, самый удобный способ
- **Пароль** - при обычной авторизации
- **Одноразовый пароль** - из приложения Яндекс.Ключ, при включенной двухфакторной авторизации
- **Ссылка на E-mail** - поддерживается не на всех аккаунтах
- **Cookies** - компонент подскажет, что нужно сделать
- **Токен** - можно скопировать ТОЛЬКО из другого сервера Home Assistant, где уже была пройдена авторизация

В итоге компонент получит токен Яндекса и сохранит именно его, ваш пароль нигде не сохраняется.

**Способ 2.** YAML (устаревший) 

```yaml
yandex_station:
  username: myuser
  password: mypass
```

# Возможности всех колонок

В тексте часто приводятся разные примеры [скриптов](https://www.home-assistant.io/integrations/script/) и [автоматизаций](https://www.home-assistant.io/docs/automation/). Их можно использовать:

- вручную вызывая [сервисы](https://my.home-assistant.io/redirect/developer_services/) из интерфейса
- создавая [скрипты](https://my.home-assistant.io/redirect/scripts/) и [автоматизации](https://my.home-assistant.io/redirect/automations/) в интерфейсе
- добавляя примеры в [configuration.yaml](https://www.home-assistant.io/docs/configuration/)

Полное состояние и доступные атрибуты ваших колонок можно посмотреть [тут](https://my.home-assistant.io/redirect/developer_states/).

В некоторых примерах используются события (`event_type`). За их срабатыванием можно следить [тут](https://my.home-assistant.io/redirect/developer_events/).

В случае возникновения ошибок, их список и описание можно посмотреть [тут](https://my.home-assistant.io/redirect/logs/).

*Данная документация не призвана научить вас основам работы с Home Assistant.*

## Первый способ вызвать TTS

**Работает на всех колонках**

**Внимание**. Команда всегда отправляется через облако, даже на локальный колонках, чтоб станция НЕ продолжала слушать после TTS.

В облачном режиме есть два ограничения:

- Команда Алисе может содержать только кириллицу, латиницу, цифры и спецсимволы: "-,!.:=?".
- Команда Алисе должна быть не длиннее 100 символов

Компонент автоматически удалит из текста запрещенные символы и ограничит длину текста до допустимой.

```yaml
script:
  yandex_tts1:
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station  # замените на вашу колонку
      data:
        media_content_id: 'Температура в комнате {{ states("sensor.temperature_hall")|round }} градуса'
        media_content_type: text
```

## Спецэффекты в TTS

Поддерживается:

- только в локальном режиме, используя [третий способ вызвать TTS](#третий-способ-вызвать-tts)
- на любой колонке, используя интеграцию с [Яндекс.Диалогами](#интеграция-с-яндексдиалогами)

Доступны следующие эффекты, библиотека звуков, настройка речи и голоса:

- [Настройка генерацию речи](https://yandex.ru/dev/dialogs/alice/doc/speech-tuning-docpage/)

  ```yaml
  media_content_id: смелость sil <[500]> город+а берёт
  ```

- [Наложение эффектов на голос](https://yandex.ru/dev/dialogs/alice/doc/speech-effects-docpage/)

  ```yaml
  media_content_id: <speaker effect="megaphone">Ехал Грека через реку <speaker effect="-">видит Грека в реке рак
  ```

- Шёпот

  ```yaml
  media_content_id: <speaker is_whisper="true">Хозяин, уже утро, пора вставать!
  ```

- [Библиотека звуков](https://yandex.ru/dev/dialogs/alice/doc/sounds-docpage/)

  ```yaml
  media_content_id: <speaker audio="alice-sounds-game-win-1.opus"> У вас получилось!
  ```

- [Собственное аудио](https://yandex.ru/dev/dialogs/alice/doc/resource-sounds-upload.html) Можно загрузить свои аудио файлы до ***120 секунд***. Для воспроизведение загруженного
аудиофайла нет необходимости использовать [Яндекс.Диалог](https://dialogs.yandex.ru/developer), в контекст которого загружен файл.

  ```yaml
  media_content_id: <speaker audio="dialogs-upload/5d77ecc4-b781-4baa-abdd-bd0127553b97/081b7f9e-e708-499c-a907-264e33f28ecd.opus">
  ```

- Разные голоса можно посмотреть [тут](https://cloud.yandex.ru/services/speechkit). Работают не все голоса. Если указать неправильный голос - колонка заглючит. Тогда на неё нужно отправить команду **стоп** или перезагрузить.

  ```yaml
  media_content_id: <speaker voice="zahar">Всем привет. Меня зовут Захар...
  ```

```yaml
script:
  yandex_tts:
    alias: TTS c эффектами
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station  # замените на вашу колонку
      data:
        media_content_id: <speaker audio="alice-sounds-game-win-1.opus"> sil <[500]> Объявление погоды на сегодня...
        media_content_type: dialog  # работает только на локальной колонке
```

## Медиа браузер

Фразы на колоки с Алисой можно отправлять, как из автоматизации, так и из интерфеса Home Assistant. Начиная с версии v2022.3 меню TTS перенесено в раздел **Медиа**, до этого оно находилось в окне Медиа плеера.

При желании вы можете настроить этот раздел через YAML:
 
- произносить фразы в разных режимах
- использовать спецэффекты и шаблоны
- отправлять команды на колоку
- задать перечень "быстрых команд"

Если в команде присутствует `media_content_id` или в `template` нет слова `message` - окно ввода сообщения будет пропущено.

Вот несколько примеров:

```yaml
yandex_station:
  media_source:
    - title: Произнеси текст  # обязательное поле
      media_content_type: text  # обязательное поле
      thumbnail: https://brands.home-assistant.io/_/tts/icon.png
    - title: Выполни команду
      media_content_type: command
      thumbnail: https://brands.home-assistant.io/_/automation/icon.png
    - title: Включи любимое
      media_content_id: Включи моё любимое вперемешку
      media_content_type: command
    - title: Произнеси шепотом 
      template: '<speaker is_whisper="true">{{ message }}'
      media_content_type: dialog
      extra:
        volume_level: 0.2
    - title: Статус эквалайзера
      template: 'Эквалайзер установлен на {{ states("select.yandex_station_equalizer") }}'
      media_content_type: text
```

## Внешний вид

<img src="yandex_mini.png" width="455">

[Пример карточки плеера](https://github.com/AlexxIT/YandexStation/wiki/MiniMediaPlayer). **Внимание**: Этой карточки нет в Home Assistant по умолчанию. Она [легко ставится](https://github.com/kalkih/mini-media-player) через [HACS](https://hacs.xyz/). Если у вас сложности с установкой - просто используйте стандартную карточку. Она тоже работает.

Красивые [иконки Яндекс устройств](https://github.com/iswitch/ha-yandex-icons) так же можно установить через [HACS](https://hacs.xyz/).

## Выполнение команд станцией

**Работает на всех колонках**

```yaml
script:
  yandex_command:  # работает и в локальном и в облачном режиме
    alias: Выполнить команду
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station  # замените на вашу колонку
      data:
        media_content_id: Включи мою любимую музыку вперемешку
        media_content_type: command
```

## Примеры управления станцией

Поддерживаются команды на несколько станций одновременно (как TTS, так и media_player).

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
      entity_id: media_player.yandex_station  # замените на вашу колонку
      data:
        media_content_id: 60062    # ID альбома в Яндекс.Музыка
        media_content_type: album  # album, track or playlist
```

## Получение команд от станции

**Работает на всех колонках**

1. Создайте новый Сценарий в [интерфейсе Яндекса](https://yandex.ru/quasar/iot).
2. Укажите нужные фразы активации в разделе **Если**
3. Выберите "Любая умная колонка" в разделе **То**

Если хотите, чтоб Алиса сразу же что-то сделала или сказала - выберите **Выполнить команду** или **Прочитать текст**. Если хотите, чтоб команда бесшумно ушла в ХА - укажите выполнить команду `Сделай громче на 0`. Такие команды колонка выполняет бесшумно и по факту громкость не меняется.

Когда колонка выполнит такой сценарий, в ХА появится событие `yandex_speaker`, с параметрами:

```yaml
instance: text_action      # text_action при "выполнить команду", phrase_action при "прочитать текст"
value: Сделай громче на 0  # фраза колонке из раздела То
name: Яндекс Мини          # имя колонки в ХА
entity_id: media_player.yandex_station_mini  # ID колонки в ХА
```

По этому событию вы можете создавать автоматизации:

```yaml
automation:
- alias: Расскажи шутку
  trigger:
  - platform: event
    event_type: yandex_speaker
    event_data:
      value: Сделай громче на 0  # фраза из Сценария Яндекса (раздел То) 
  action:
  - service: media_player.play_media
    target:
      entity_id: '{{ trigger.event.data.entity_id }}'  # ответить той же колонкой
    data:
      media_content_type: text
      media_content_id: '{{ ["На связи", "Смольный слушает", "Тут я"]|random }}'
  mode: single
```

К сожалению, нельзя узнать фразу, которую сказали колонке. Можно узнать только фразу, которую колонка выполнила или произнесла.

Для создания нескольких сценариев с "бешумным выполнением", используйте знаки пунктуации `-,!.:=?` и их комбинации `Сделай громче на 0???!!!`. Эффект не изменится, а в ХА вы сможете различать, на какую фразу произошла реакция.

В разделе `trigger:` > `event_data:` вы можете фильтровать колонки, чтоб выполнять разные автоматизации для разных комнат на одну и ту же фразу.

**Внимание!** Вызов TTS из ХА так же активирует эти события.

Для отладки событий перейдите в панель разработчика вашего ХА по адресу `http://192.168.1.123:8123/developer-tools/event`, в разделе "подписаться на событие" укажите `yandex_speaker` и нажмите "подписаться".

PS. Так же есть [cтарый способ](https://github.com/AlexxIT/YandexStation/wiki/YandexIntents) получения команд только для продвинутых пользователей!

## Интеграция с Яндекс.Диалогами

Компонент поддерживает интеграцию с другим моим компонентом - [YandexDialogs](https://github.com/AlexxIT/YandexDialogs). При его наличии вам доступны функции:

### Второй способ вызвать TTS

**Работает на всех колонках**

Поддерживает спецэффекты TTS. Нет ограничения на 100 символов. Послее TTS колонка НЕ слушает пользователя.

В `media_content_type` вы должны указать имя своего Яндекс.Диалога через двоеточие без пробелов. Регистр неважен.

```yaml
script:
  yandex_tts3:
    sequence:
      - service: media_player.play_media
        entity_id: media_player.yandex_station_irbis
        data:
          media_content_id: <speaker is_whisper="true">Хозяин, пора бы спать
          media_content_type: text:умный дом
```

### Диалог с колонкой

**Работает на всех колонках**

Вы можете начать диалог с пользователем, получить на него ответ и выполнить нужные вам действия, в зависимости от ответа пользователя.

В `media_content_type` вы должны указать имя своего Яндекс.Диалога через двоеточие без пробелов. Регистр неважен. И через второе двоеточие некий "тег" диалога, чтоб потом в автоматизации понять, на какой вопрос вам пришёл ответ.

```yaml
script:
  yandex_dialog:
    sequence:
      - service: media_player.play_media
        entity_id: media_player.yandex_station_mini
        data:
          media_content_id: <speaker is_whisper="true">Хозяин, уже утро, пора вставать!
          media_content_type: dialog:умный дом:утро
```

Пример реакции на ответ пользователя можно посмотреть [тут](https://github.com/AlexxIT/YandexStation/wiki/YandexDialogs). Этим подходом легко пользоваться как в автоматизациях Home Assistant, так и в Node-RED.

## Уведомления и предупреждения

Компонент поддерживает [уведомления](https://www.home-assistant.io/integrations/notify/) и [предупреждения](https://www.home-assistant.io/integrations/alert/).

Уведомления это альтернативный способ вызвать TTS. Уведомления настраиваются в `configuration.yaml`. Минимально, вы должны указать имя нового уведомления и перечень колонок, где оно должно звучать. Для каждого уведомления будет создан отдельный сервис. Далее необходимо вызывать этот сервис с параметром `message`.

Опционально уведомления поддерживают параметр `title`. Для его поддержки вы можете использовать шаблон из примера ниже.

При настройке уведомлений параметры `media_content_id` и `media_content_type` необязательные.

Уведомления можно использовать в предупреждениях. Например, если вы забыли закрыть выходную дверь - предупреждение будет отправлять вам уведомление с заданным интервалом, до тех пор, пока проблема не будет решена.

```yaml
notify:
  - name: alice_alert  # любое название
    platform: yandex_station
    data:
      entity_id: media_player.yandex_station_mini  # замените на вашу колонку
      media_content_id: >-
        {% if title is defined %}<speaker effect="megaphone">{{ title }}<speaker effect="-"> sil <[200]>{% endif %}{{ message }}
      media_content_type: dialog

input_boolean: # просто для примера
  garage_door:
    name: Дверь гаража

alert:
  garage_door:
    name: Гараж открыт
    done_message: Гараж закрыт
    entity_id: input_boolean.garage_door
    state: "on"  # опционально, потому что "on" это значение по умолчанию
    repeat: 5  # как часто повторять, в минутах
    can_acknowledge: true  # разрешить выключить уведомления вручную
    skip_first: true  # пропустить первое (мгновенное) уведомление
    notifiers:
      - alice_alert  # название, которые указали выше
```

# Возможности локальных колонок

## Третий способ вызвать TTS

**Только для локального режима!**

Продолжает слушать после произнесения текста! Зато нет ограничения на количество символов. Поддерживает спецэффекты.

```yaml
script:
  yandex_tts4:
    alias: TTS только для локального режима
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station  # замените на вашу колонку
      data:
        media_content_id: <speaker effect="megaphone">Объявление погоды на сегодня...
        media_content_type: dialog
```

## Громкость TTS

**Только для локального режима!**

Колонка произнесёт текст с заданной громкостью и вернёт громкость на прежний уровень.

```yaml
script:
  alice_custom_volume1:
    sequence:
    - service: tts.yandex_station_say
      entity_id: media_player.yandex_station  # замените на вашу колонку
      data:
        message: Внимание! Важное сообщение...
        options:
          volume_level: 0.8
```

Или так

```yaml
script:
  alice_custom_volume2:
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station  # замените на вашу колонку
      data:
        media_content_id: Внимание! Важное сообщение...
        media_content_type: text  # поддерживается text и dialog
        extra:
          volume_level: 0.8
```

## Стриминг музыки

**Только для локального режима!**

Поддерживается стриминг (трансляция) музыки с колонки Яндекса на умные колонки других производителей. Условия такие:

- Нужна Яндекс колонка с поддержкой локального управления. Яндекс Модули функцию НЕ поддерживают.
- Нужна подписка Яндекса на музыку.
- Сторонняя колонка должна иметь интеграцию в Home Assistant с поддержкой потокового воспроизведения музыки. Если она умеет функцию "воспроизвести текст" из окна медиа-плеера, то поддержка скорее всего есть.
- Синхронизовать колонки разных производителей в идеальный мультирум нереально, поэтому звук на колонке Яндекса во время трансляции приглушается. Но при общении с Алисой звук временно возвращается.
- Громкость колонки Яндекса также синхронизируется с внешней акустикой.

Протестирована поддержка интеграций:

- [Chromecast](https://www.home-assistant.io/integrations/cast/):
   - колонки с Google Assistant
   - медиаплееры/телевизоры/проекторы на Android TV
- [DLNA](https://www.home-assistant.io/integrations/dlna_dmr/):
   - саундбар Samsung HW-MS6500
   - саундбар Yamaha YAS-306
   - телевизор Philips 2011 года
   - телевизоры Samsung Tizen 2016+ год
- [Kodi](https://www.home-assistant.io/integrations/kodi/) 
- [MPD](https://www.home-assistant.io/integrations/mpd/)
   - [MPD](https://www.musicpd.org/) for Windows
   - [Xiaomi Gateway EU](https://openlumi.github.io/)
- [SamsungTV](https://github.com/ollo69/ha-samsungtv-smart)
   - телевизоры Samsung Tizen 2016+ год
   - важно указать в конфиге `media_content_type: url`
- [Sonos](https://www.home-assistant.io/integrations/sonos/)
- [Yamaha MusicCast](https://www.home-assistant.io/integrations/yamaha_musiccast/)

**Внимание.** Для корректной работы некоторых интеграций, ваш сервер ХА должен быть доступен в локальной сети по протоколу HTTP и IP-адресу:

> Настройки > Общие > URL-адрес для домашней сети > http://192.168.1.123:8123/

Стоит понимать, что при правильной настройке внешнего доступа [через различные аддоны](https://sprut.ai/client/blog/2431), вы можете пользоваться ХА по адресу вида `https://myhome.duckdns.org/`. И при правильной настройке такая ссылка будет работать как во внешней, так и в локальной сети. А ссылка вида HTTP/IP будет использоваться только локальными медиа-плеерами.

Компонент автоматически найдёт все теоретически подходящие `media_player` и добавит их в список `source_list` у колонки. При желании вы можете вручную указать список колонок в `configuration.yaml`:

```yaml
yandex_station:
  media_players:
    - entity_id: media_player.yas_306
      name: Yamaha
    - entity_id: media_player.mpd
      name: MPD
    - entity_id: media_player.yas_306
      name: Yamaha (no sync)
      sync_volume: False  # опциональное отключение синхронизации громкости звука
    - entity_id: media_player.samsung
      name: SamsungTV
      media_content_type: url  # важно для интеграции SamsungTV из HACS
```

Вы можете переключать трансляцию через:

- Переключатель `source` в карточке [Mini Media Player](#внешний-вид)
- Переключатель `source` в стандартном окне медиа-плеера колонки
- Сервис [media_player.select_source](https://www.home-assistant.io/integrations/media_player/#service-media_playerselect_source)
- [Получение команд от станции](#получение-команд-от-станции), например на фразу "Алиса, включи трансляцию на Ямаху"
- Интеграцию колонок в [умный дом Яндекса](https://github.com/dmitry-k/yandex_smart_home), единственное ограничение - вместо нормальных названий источников там будет "один", "два", "три"...
- Интеграцию колонок в [HomeKit](https://www.home-assistant.io/integrations/homekit/)

## Проигрывание медиа по ссылкам

**Только для локального режима!**

Поддерживаются только ссылки, которые умеют устройства Яндекса!

- Песня на Яндекс.Музыке - [пример](https://music.yandex.ru/album/2150009/track/19174962)
- Альбом на Яндекс.Музыке - [пример](https://music.yandex.ru/album/2150009)
- Исполнитель на Яндекс.Музыке - [пример](https://music.yandex.ru/artist/41114)
- Плейлист на Яндекс.Музыке - [пример](https://music.yandex.ru/users/music.partners/playlists/2050)

Только на устройствах с экраном (большая Станция или Модуль)

- YouTube - [пример](https://www.youtube.com/watch?v=Rqf3J4ZOPCw)
- Кинопоиск - [пример](https://www.kinopoisk.ru/film/819101/)
- Кинопоиск HD - [пример](https://hd.kinopoisk.ru/film/4fabed06d035b5e1b87b75607927c8e5/)

Это работает в том числе из GUI, если вставить ссылку в поле "воспроизвести текст".

```yaml
script:
  yandex_play_url:
    alias: Проигрывание медиа по ссылке
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station  # замените на вашу колонку
      data:
        media_content_id: https://music.yandex.ru/album/2150009/track/19174962
        media_content_type: xxx  # тип не важен, но должен быть!
```

## Яндекс Алиса в Telegram

**Только для локального режима!**

Вы можете общаться со своей Алисой через Telegram. И она вам будет отвечать в Telegram! Можете спросить погоду, вызвать такси, включить песню, поиграть в города или управлять вашим умным домом (если настроили интеграцию с умным домом Яндекса). Никаких слеш-команд Telegram, общайтесь с Алисой обычным текстом.

При этом Home Assistant не обязательно "прокидывать" в Интернет. Telegram в режиме `polling` может работать без внешнего доступа.

При этом [проигрывание медиа по ссылкам](#проигрывание-медиа-по-ссылкам) тоже будет работать. Просто поделитесь со своим Telegram ботом ссылкой на фильм Кинопоиска, ролик YouTube или песню/альбом/плейлист на Яндекс Музыке - и они запустятся на вашей колонке!

```yaml
telegram_bot:
- platform: polling
  api_key: TELEGRAM_BOT_API_KEY  # создайте своего Телеграм бота
  allowed_chat_ids:
  - TELEGRAM_USER1_ID  # укажите ID своего аккаунта
  - TELEGRAM_USER2_ID  # при желании, поддерживается несколько аккаунтов

automation:
- trigger:
    platform: event
    event_type: telegram_text
  action:
    service: media_player.play_media
    entity_id: media_player.yandex_station_mini  # замените на вашу станцию
    data:
      media_content_id: "{{ trigger.event.data.text }}"
      media_content_type: "question:{{ trigger.event.data.chat_id }}"
- trigger:
    platform: event
    event_type: yandex_station_response
  action:
    service: telegram_bot.send_message
    data:
      target: "{{ trigger.event.data.request_id }}"
      message: "{{ trigger.event.data.text }}"
```

Для отправки Telegram сообщений разным станциям [@ProstoMaksks](https://t.me/ProstoMaksks) предложил [такое решение](https://gist.github.com/AlexxIT/dc42882c44e298d41631720f146e701d).

## Яндекс Алиса в Lovelace

**Только для локального режима!**

<img src="conversation.png" width="500">

Вы можете общаться со своей Алисой через GUI Home Assistant ([lovelace](https://www.home-assistant.io/lovelace/)). Это работает в любом браузере на любой платформе, включая смартфоны и официальные мобильные приложения.

При включении компонента [Conversation](https://www.home-assistant.io/integrations/conversation/) в правом верхнем углу интерфейса Home Assistant появляется микрофон. Сам компонент позволяет общаться в режиме диалога.

Работает аналогично добавлению Алисы в Телеграм. Вы фактически общаетесь в текстовом режиме с одной из ваших колонок. Отправка ссылок на медиа тоже работает!

```yaml
conversation:
  intents:
    # менять нужно entity_id до двоеточия, после двоеточия ничего менять не надо!
    media_player.yandex_station_mini: [.+]  # замените на вашу станцию
```

Компонент поддерживает не только текстовый, но и голосовой ввод при следующих условиях:

- *Home Assistant открыт в браузере Google Chrome на Windows, macOS, Linux, Android или в мобильном приложении Android* - потому что для распознования голоса используются API Google
- *Home Assistant открыт по HTTPS-ссылке или localhost-ссылке* - потому что микрофон в браузере Google Chrome доступен только в этом случае

По умолчанию в Home Assistant включен голосовой ввод только на английском языке. Чтоб это исправить - добавьте в конфиг такую настройку. Если у вас голосовой ввод не работает или он вам не нужен - настройку добавлять не надо! Общаться текстом с Алисой вы можете и без неё. После изменения вероятно потребуется сбросить кэш браузера (включая cookies and other site data).

```yaml
yandex_station:
  recognition_lang: ru-RU
```

Текстовый ввод работает в любом браузере на любой платформе, включая мобильные приложения.

## Список покупок

**Только для локального режима!**

Поддерживается двухсторонняя синхронизация списка покупок Алисы и стандартного компонента [Shopping List](https://www.home-assistant.io/integrations/shopping_list/). Можно добавлять и удалять элементы списка как из ХА, так и голосом с колонки.

<img src="shopping_list.png" width="800">

Предварительно необходимо добавить стандартный компонент, через GUI или YAML.

Для синхронизации списков необходимо вызвать следующий сервис. При желании, вызов этого сервиса можно выполнять голосом с колонки, через [получение команд от станции](#получение-команд-от-станции). 

```yaml
script:
  update_shopping_list:
    alias: Обновить список покупок
    sequence:
      - service: media_player.play_media
        entity_id: media_player.yandex_station_mini  # замените на вашу колонку
        data:
          media_content_id: update
          media_content_type: shopping_list
```

После синхронизации вы можете удалять элементы голосом на колонке. Такие элементы будут удалены из ХА при следующей синхронизации, даже если на них не стоит галка.

Или вы можете отмечать элементы как завершенные в интерфейсе ХА. Такие элементы будут удалены из Яндекса при следующей синхронизации. Только не очищайте вручную список завершенных элементов в ХА до синхронизации! Иначе синхронизация нарушится.

Синхронизация происходит по следующим правилам:
1. Завершенные (отмеченные) элементы списка ХА - удаляются из Яндекса (если они там были)
2. Новые элементы, созданные именно из ХА - добавляются в Яндекс (если их там не было)
3. Список ХА полностью заменяется тем, что получилось в Яндексе после 1 и 2
4. Список завершенных элементов ХА очищается

Нужно учитывать, что некоторые названия Яндекс не может добавить в свой список. Поэтому они могут бесследно пропасть.

## Статический IP для колонки

**Только для локального режима!**

Проще всего проверить работу локального режима - запустить на колонке песню и посмотреть, отображается ли обложка в Home Assistant.

Локальные устройства ищутся автоматически по протоколу mDNS ([zeroconf](https://www.home-assistant.io/integrations/zeroconf/)). Он не будет работать, если вы открыли только один порт для Home Assistant. Например, установка в Docker (в Hass.io всё хорошо) без настройки `network=host` или виртуальная машина с NAT.

Если у вас есть с этим какие-то проблемы - можно указать для колонок статический IP-адрес на роутере и в конфиге Home Assistant. `device_id` вашей колонки можно посмотреть в мобильном приложении Яндекса.

```yaml
yandex_station:
  devices:
    12345678901234567890:  # device_id вашей колонки
      host: 192.168.1.123
      name: Яндекс Станция  # имя можно задать и тут
```

# Прочие функции

## Управление умным домом Яндекса

На данный момент поддерживаются:

- **Кондиционеры** - добавленные как через ИК-пульт, так и напрямую (например LG с Wi-Fi)
- **Телевизоры** - добавленные как через ИК-пульт, так и напрямую
- **Обученные вручную ИК-команды** - обученные вручную команды ИК-пульта (Пульт => Добавить устройство => Настроить вручную)
- **Розетки** - включая энергопотребление
- **Лампочки** - включая настройку яркости и цвета
- **Обогреватели**
- **Пылесосы**
- **Чайники**

В качестве ИК-пультов можно использовать Яндекс Пульт или более [дешевую версию от Tuya](https://www.aliexpress.com/item/32984694264.html) (добавляется напрямую как родной пульт Яндекса).

В конфиге нужно перечислить имена ваших устройств:

```yaml
yandex_station:
  include:
  - Кондиционер  # имя вашего кондиционера
  - Приставка  # имя не ИК-пульта, а устройства, настроенного вручную
```

Кондиционер будет добавлен как термостат:

<img src="climate.png" width="448">

Настроенное вручную ИК-устройство будет добавлено как [Remote](https://www.home-assistant.io/integrations/#remote). Команды отправляются через сервис `remote.send_command`. Можно отправить несколько команд за раз, настроить задержку и количество повторов. [Пример вызова](https://github.com/AlexxIT/YandexStation/wiki/RemoteSendCommand).

## Изменение настроек Алисы

```yaml
script:
  change_settings:
    alias: Изменение настроек Алисы
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station  # замените на любую вашу колонку
      data:
        media_content_id: 'без лишних слов: да'  # пробел после двоеточия
        media_content_type: settings
```

Поддерживаемые значения:

- `без лишних слов: да/нет`
- `ответить шепотом: да/нет`
- `звук активации: да/нет`
- `одним устройством: да/нет`
- `понимать детей: да/нет`
- `рассказывать о навыках: да/нет`
- `взрослый голос: умеренный/семейный/безопасный/без ограничений`
- `детский голос: безопасный/семейный`
- `имя: алиса/яндекс`

## Несколько TTS в конфиге

Если в Home Assistant подключены несколько TTS-сервисов - из карточки медиа-плеера будет вызываться самый первый из них (сортировка по имени). Например, `tts.google_translate_say` будет приоритетнее `tts.yandex_station_say`. А `tts.yandex_station_say` будет приоритетнее `tts.yandextts_say`.

Компонент Яндекс.Станции умеет поддерживать другие TTS, а вот другие колонки могут не поддерживать TTS `yandex_station_say`. При необходимости вы можете:

- отключить ненужные TTS в конфиге ХА
- использовать [mini-media-player](https://github.com/kalkih/mini-media-player), где можно указать имя TTS-сервиса для каждой колонки
- изменить название TTS-сервиса:

```yaml
yandex_station:
  tts_service_name: alice_say
```

## Звук Яндекс.Станции по HDMI

**Только для станций с HDMI**

Функция переключения выхода звука находится у Яндекса в бете. На телевизор выводится только звук видео (например YouTube). Звук музыки и голос Алисы остаются на Станции.

Раньше функция включалась в конфиге. Теперь включена по умолчанию для всех владельцев больших Станций.

```yaml
script:
  yandex_hdmi_sound:
    alias: Звук Станции на HDMI
    sequence:
    - service: media_player.select_source
      entity_id: media_player.yandex_station  # поменяйте на вашу станцию
      data:
        source: HDMI
```

## Управление яркостью экрана станции Макс

**Только для Яндекс.Станции Макс**

```yaml
script:
  yandex_brightness:
    sequence:
    - service: media_player.play_media
      entity_id: media_player.yandex_station_max
      data:
        media_content_id: 0.5  # допустимые значения от 0 до 1, или -1 для включения авто режима
        media_content_type: brightness
``````

## Troubleshooting

**Поиск и устранение проблем**

1. Посмотрите [лог Home Assistant](https://my.home-assistant.io/redirect/logs/) на наличие ошибок интеграции **Yandex.Station**.
2. Если в логе есть ошибка, постарайтесь прочитать её. Среди непонятных букв может быть прямой ответ на проблему на русском или английском языке.
3. Поищите похожую ошибку на [GitHub проекта](https://github.com/AlexxIT/YandexStation/issues) (включая закрые issue) или в чатах Telegram: [1](https://t.me/SprutAI_HomeAssistant), [2](https://t.me/homassistant), [3](https://t.me/+DyCa63l98wlmOGZi).
4. Если ошибки нет, можно включить отладочные логи интеграции и посмотреть, что проиходит там.
   ```
   logger:
     default: info
     logs: { custom_components.yandex_station: debug }
   ```
5. Если самостоятельно не справились - переходите по ссылкам в пункте 3 и подробно опишите проблему. Обязательно приложите ошибку из лога, если она есть. При наличии чего-то полезного в пункте 4, приложите и этот лог.

## Полезные автоматизации

[![Отображаем статус Яндекс Станции с помощью умных ламп](https://img.youtube.com/vi/XLoGvy4RLrg/mqdefault.jpg)](https://www.youtube.com/watch?v=XLoGvy4RLrg)

- [Отображаем статус Яндекс Станции с помощью умных ламп](https://gist.github.com/AlexxIT/c275ee512bef01ed4d3b0aebc12caef4), так же эту автоматизацию можно переделать в "Приглушаем звук телевизора, когда Алиса слушает", **Только для локального режима!**
- [Звонок на колонку с Алисой](https://gist.github.com/AlexxIT/5dd25dbe3306d673ad013f05617a8056)
- [Перехват фраз с локальных колонок](https://gist.github.com/AlexxIT/d4995839aedde2bbcf822831a71a52c5), **Только для локального режима!**
- [Отвечать на intents с последней активной колонки](https://gist.github.com/AlexxIT/6a3a1a5ba4c4ebe1fabbec639542d446), **Только для локального режима!**
- [Управление разными станциями из Telegram](https://gist.github.com/AlexxIT/dc42882c44e298d41631720f146e701d), **Только для локального режима!**
- [Действие по таймеру в Яндекс Алисе](https://gist.github.com/AlexxIT/5fb8fd32378cdc16c729f15d7a1bab28)
- [Список радиостанций для колонок Яндекса](https://gist.github.com/AlexxIT/b2a435adb30b9bf91022fccc95267b9b)

## Полезные ссылки

- https://github.com/sergejey/majordomo-yadevices
- https://github.com/anVlad11/dd-alicization
