def test_update_states():
    device = {
        "id": "xxx",
        "state": "online",
        "capabilities": [
            {
                "reportable": False,
                "retrievable": False,
                "type": "devices.capabilities.quasar.server_action",
                "state": {"instance": "text_action", "value": "Сделай громче на 0"},
                "parameters": {"instance": "text_action"},
            }
        ],
    }
