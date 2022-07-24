
from odoo import api


def mqtt(topic):
    """
    Decorate a method to be a MQTT message subscriber. The method must accept the
    recordset of the messages to process as first argument. The messages are
    automatically set to `processed`

    :param topic: Specifies the topic the method is subscribing. MQTT wildcards with
                  # and + are allowed to use.
    """

    def decorator(method):
        method._mqtt = topic
        return method

    return decorator


api.mqtt = mqtt
