All models within Odoo can use the `mqtt_publish` method to generate custom MQTT messages which are automatically flagged as to publish.

MQTT events can be used to publish MQTT messages on specific type of events. Pre-defined are creation of a record, write of specific fields of a record, or the deletion of a record.

MQTT processors can be used to define actions which are used to process incoming MQTT messages. This is one of the options to process incoming messages.

The decorator `odoo.api.mqtt(topic)` can be used to subscribe model functions to specific MQTT topics. The function has to take the messages as first arguments. A message can be processed by multiple subscribers.
