This module connects Odoo to a MQTT broker to exchange and process messages allowing
Odoo to indirectly connecting to additional systems with a single interface. This
can be used to synchronize records between multiple systems.

Features:

* Publishing messages on the MQTT bus using the MQTT events. A list of fields or
  Python snippets can be used to fill the payload of the messages
* Predefined MQTT event types to generate messages if records are created, written,
  or deleted for almost all Odoo models
* Subscribing to topics and receiving MQTT messages to process by model functions
  or Python snippets of MQTT processors
* Support for further development by providing a simple decorator to subscribe functions
  to topics and generating MQTT messages

Example:

.. code-block:: python

  from odoo import api, models

  class MyModel(models.Model):
      _name = "my.model"

      @api.mqtt("odoo/#")
      def my_method(self, messages):
          _logger.info("New messages %s arrived for the topic odoo/#", messages)

      def button_do_stuff(self):
          self.mqtt_publish("odoo/topic", payload={"status": "ok"})
