* Using the Odoo configuration file:

.. code-block:: ini

  [options]
  (...)
  server_wide_modules = web,mqtt

  (...)
  [mqtt]
  # connection parameter for the MQTT broker
  host = ...
  port = 1883
  keepalive = 60
  # authentication if required
  username = ...
  password = ...
  # TLS
  # Path to a directory containing CA files (*.pem)
  ca_certs = ...
  # Path to a certificate and key file (PEM encoded)
  certfile = ...
  keyfile = ...
  # the MQTT will to set on connection
  will_topic = ...
  will_payload = ...
  will_qos = 0
  will_retain = False
  # idle timeout which controls the responsiblity for publishing/subscribing
  idle = 5
