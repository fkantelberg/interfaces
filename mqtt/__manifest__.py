# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "MQTT Framework",
    "summary": "MQTT Client and Framework",
    "license": "AGPL-3",
    "version": "15.0.1.0.0",
    "website": "https://github.com/fkantelberg/iot",
    "author": "initOS GmbH",
    "depends": ["base_setup"],
    "data": [
        "data/ir_cron.xml",
        "data/mqtt_event_type.xml",
        "data/res_config.xml",
        "security/ir.model.access.csv",
        "views/menuitems.xml",
        "views/mqtt_event_views.xml",
        "views/mqtt_message_views.xml",
        "views/mqtt_subscription_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "external_dependencies": {
        "python": [
            "paho.mqtt",
        ],
    },
}
