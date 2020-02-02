# YandexStation for Home Assistant

Компонент для управления Яндекс.Станцией по локальной сети.

На конец января 2020 поддерживается:

- Яндекс.Станция (большая)

Не поддерживается:

- Яндекс.Станция Мини
- Irbis
- Dexp

Остальные колонки не тестировались.

![media_player](media_player.png)

## Настройка

Нужны имя и пароль аккаунта Яндекс, к которому привязаны колонки. Изучите код,
если думаете, что это небезопасно.

Токен сохраняется в директории конфигов и больше не запрашивается.

```yaml
yandex_station:
  username: myuser
  password: mypass
```

Если знаете свой Oauth-токен, можно так:

```yaml
yandex_station:
  token: abcdefghijklmnopqrstuvwxyz
```

## Пример использования

```yaml
script:
  yandex_tts:
    alias: TTS на Яндекс.Станции
    sequence:
      - service: tts.yandex_station_say
        data_template:
          entity_id: media_player.yandex_station_12345678901234567890

  yandex_play_album:
    alias: Включить Би-2 на Станции
    sequence:
    - service: media_player.play_media
      data:
        entity_id: media_player.yandex_station_12345678901234567890
        media_content_id: 60062    # ID альбома в Яндекс.Музыка
        media_content_type: album  # album, track or playlist
```

Для шаблонов не забывайте указывать `data_template`, для остальных команд 
хватит просто `data`.

## Продвинутое использование

Компонент создаёт сервис `yandex_station.send_command`, которому необходимо 
передать команду.

Полезные команды станции можно узнать [тут](https://documenter.getpostman.com/view/525400/SWLfd8et?version=latest).

Самая универсальная - это `sendText`. Станция выполнит посланную фразу, как 
буд-то услышала команду голосом.

Если у аккаунта больше одной станции - команда выполнится на первой из 
поддерживаемых. Если поддерживаемых станций несколько - нужно дополнительно 
передать `device` равный `id` или названию станции. Можно посмотреть в 
приложении Яндекс или в [веб](https://quasar.yandex.ru/skills/iot) интерфейсе.

```yaml
script:
  yandex_tts:
    alias: TTS на Яндекс.Станции
    sequence:
    - service: yandex_station.send_command
      data_template:
        command: sendText
        text: Повтори за мной 'Привет, человек!'
        device: Яндекс Станция
```

## Полезные ссылки

[CHANGELOG](CHANGELOG.md)

- https://github.com/sergejey/majordomo-yadevices
- https://github.com/anVlad11/dd-alicization