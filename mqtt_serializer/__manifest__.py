# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "MQTT Serializer",
    "summary": "Make the serializer usable for MQTT",
    "license": "AGPL-3",
    "version": "16.0.1.0.0",
    "website": "https://github.com/OCA/...",
    "author": "initOS GmbH",
    "depends": ["mqtt", "base_serializer"],
    "data": [
        "views/mqtt_processor_views.xml",
        "views/mqtt_event_views.xml",
    ],
    "demo": [
        "demo/demo_users.xml",
    ],
}
