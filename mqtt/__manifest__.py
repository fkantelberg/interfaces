
{
    "name": "MQTT Framework",
    "summary": "MQTT Client and Framework",
    "license": "AGPL-3",
    "version": "15.0.1.0.0",
    "website": "...",
    "author": "...",
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
