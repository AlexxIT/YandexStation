# YandexStation for Home Assistant

Компонент для управления Яндекс.Станцией по локальной сети. Написан за пару 
часов со всеми вытекающими.

На конец января 2020 поддерживается:

- Яндекс.Станция (большая)

Не поддерживается:

- Яндекс.Станция Мини
- Irbis
- Dexp

Остальные колонки не тестировались.

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

Компонент создаёт сервис `yandex_station.send_command`, которому необходимо 
передать команду.

Если станций у аккаунта больше одной - нужно дополнительно передать `device` 
равный `id` или названию станции (из приложения Яндекс).

```yaml
script:
  yandex_tts:
    alias: TTS на Яндекс.Станции
    sequence:
    - service: yandex_station.send_command
      data_template:
        command: sendText
        text: Повтори за мной 'Температура в комнате {{ states("sensor.temperature_hall")|round }} градуса.'
  
  yandex_volume:
    alias: Громкость Cтанции на 20%
    sequence:
    - service: yandex_station.send_command
      data:
        command: setVolume
        volume: 0.2
  
  yandex_play_album:
    alias: Включить Би-2 на Станции
    sequence:
    - service: yandex_station.send_command
      data:
        command: playMusic
        id: "60062"
        type: "album"
```

Для шаблонов не забывайте указывать `data_template`, для остальных команд 
хватит просто `data`.

Полезные команды станции можно узнать [тут](https://documenter.getpostman.com/view/525400/SWLfd8et?version=latest).

Самая универсальная - это `sendText`. Станция выполнит посланную фразу, как 
буд-то услышала команду голосом. Например, можно:
- включить музыку
- управлять умным домом 
- просить станцию что-то произнести (TTS голосом Алисы!)

IP-адрес станции определяется автоматически через mDNS. Если с этим какие-то 
проблемы - опционально можно передать в сервис параметр `host` с значением 
IP-адреса вашей Станции.

## Полезные ссылки

[CHANGELOG](CHANGELOG.md)

- https://github.com/sergejey/majordomo-yadevices
- https://github.com/anVlad11/dd-alicization