# © 2022 Florian Kantelberg - initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import time
from contextlib import contextmanager
from datetime import datetime

import odoo
from odoo import api, fields
from odoo.tools import config

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None


_logger = logging.getLogger(__name__)

DEFAULT_IDLE = 5


def _connection_info_for(db_name):
    return odoo.sql_db.connection_info_for(db_name)[1]


def to_bool(x):
    if isinstance(x, str):
        return x.lower() in ("true", "yes", "1", "t", "y", "on")
    return bool(x)


class MQTTRunner:
    """Runner which runs in a separate thread/process and connects to the MQTT
    broker. It directly connects to the Odoo database to handle subscriptions
    and messages"""

    def __init__(self):
        self.has_mqtt = self._has_mqtt()
        self.subscriptions = {}
        self.client = None
        self.connect()
        self.running = True

    def run(self):
        if not self.has_mqtt:
            _logger.warning("mqtt isn't installed. The client can't start")
            return

        idle = config.misc.get("mqtt", {}).get("idle", DEFAULT_IDLE)
        self.client.loop_start()
        while self.running:
            self.subscribe()
            self.publish()

            time.sleep(idle)

    def stop(self):
        self.client.loop_stop()

    def _connect_callback(self, *_args, **_kwargs):
        _logger.info("Connected to MQTT broker")
        self.subscriptions = {}

    def _disconnect_callback(self, *_args, **_kwargs):
        _logger.info("Disconnected from MQTT broker")
        self.subscriptions = {}

    def _message_callback(self, _client, _userdata, message):
        with self.env() as env:
            env["mqtt.message"].create(
                {
                    "direction": "incoming",
                    "state": "enqueued",
                    "enqueue_date": datetime.now(),
                    "topic": message.topic,
                    "payload": message.payload,
                    "qos": str(message.qos),
                    "retain": message.retain,
                }
            )

    def connect(self):
        """Connect to the MQTT broker"""
        cfg = config.misc.get("mqtt", {})
        if "host" not in cfg:
            _logger.error("Missing host configuration for the MQTT broker")
            return False

        with self.cursor() as cr:
            cr.execute("SELECT value FROM ir_config_parameter WHERE key = 'mqtt.uuid'")
            row = cr.fetchone()

        self.client_id = row[0] if row else None
        _logger.info(f"MQTT Client ID: {self.client_id}")
        self.client = mqtt.Client(client_id=self.client_id, clean_session=False)

        self.client.on_message = self._message_callback
        self.client.on_connect = self._connect_callback
        self.client.on_disconnect = self._disconnect_callback

        if cfg.get("username"):
            self.client.username_pw_set(cfg["username"], password=cfg.get("password"))

        if cfg.get("will_topic"):
            self.client.will_set(
                cfg["will_topic"],
                payload=cfg.get("will_payload", None),
                qos=int(cfg.get("will_qos", 0)),
                retain=to_bool(cfg.get("will_retain", False)),
            )

        if any(map(cfg.get, ("ca_certs", "certfile", "keyfile"))):
            self.client.tls_set(
                ca_certs=cfg.get("ca_certs"),
                certfile=cfg.get("certfile"),
                keyfile=cfg.get("keyfile"),
            )

        self.client.connect_async(
            cfg["host"],
            port=cfg.get("port", 1883),
            keepalive=int(cfg.get("keepalive", 60)),
        )
        return True

    def publish(self):
        """Publish new messages on the bus"""
        with self.cursor() as cr:
            cr.execute(
                """
                SELECT id, topic, payload, qos, retain FROM mqtt_message
                WHERE state = 'enqueued' AND direction = 'outgoing'
                """
            )
            messages = list(cr.fetchall())

        published = []
        for mid, topic, payload, qos, retain in messages:
            qos = int(qos or 0)

            result = self.client.publish(topic, payload=payload, qos=qos, retain=retain)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                published.append(mid)

        if not published:
            return

        now = datetime.now()
        with self.cursor() as cr:
            cr.execute(
                """
                UPDATE mqtt_message
                SET state = 'processed', process_date = %s
                WHERE id IN %s
                """,
                (fields.Datetime.to_string(now), tuple(published)),
            )

    def subscribe(self):
        """Handle the subscription for new topics and unsubscribe old ones"""
        with self.cursor() as cr:
            cr.execute("SELECT topic, qos FROM mqtt_subscription WHERE active = true")
            subs = dict(cr.fetchall())

        # Unsubscribe topics
        topics = [
            topic for topic, qos in self.subscriptions.items() if subs.get(topic) != qos
        ]
        if topics:
            result, _ = self.client.unsubscribe(topics)
            if result == mqtt.MQTT_ERR_SUCCESS:
                _logger.info(f"Unsubscribed from {','.join(sorted(topics))}")
                for topic in topics:
                    self.subscriptions.pop(topic, None)

        # Subscribe new topics
        topics = [
            (topic, int(qos or 0))
            for topic, qos in subs.items()
            if topic not in self.subscriptions
        ]
        if topics:
            result, _ = self.client.subscribe(topics)
            if result == mqtt.MQTT_ERR_SUCCESS:
                topics = ",".join(sorted(topic for topic, qos in topics))
                _logger.info(f"Subscribed to {topics}")
                self.subscriptions.update(subs)

    @contextmanager
    def cursor(self):
        with odoo.registry(config["db_name"]).cursor() as cr:
            yield cr

    @contextmanager
    def env(self):
        with self.cursor() as cr:
            yield api.Environment(cr, odoo.SUPERUSER_ID, {})

    def _has_mqtt(self):
        """Check if the module is installed in the database"""
        with self.cursor() as cr:
            cr.execute(
                "SELECT 1 FROM pg_tables WHERE tablename=%s", ("ir_module_module",)
            )
            if not cr.fetchone():
                return False

            cr.execute(
                "SELECT 1 FROM ir_module_module WHERE name=%s AND state=%s",
                ("mqtt", "installed"),
            )
            if not cr.fetchone():
                return False

        return True
