# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "MQTT - Login Event",
    "summary": "Event for the Users model which publishes MQTT messages if a "
    "user logs in",
    "license": "AGPL-3",
    "version": "15.0.1.0.0",
    "website": "https://github.com/fkantelberg/iot",
    "author": "initOS GmbH",
    "depends": ["mqtt"],
    "data": [
        "data/mqtt_event_type.xml",
    ],
}
