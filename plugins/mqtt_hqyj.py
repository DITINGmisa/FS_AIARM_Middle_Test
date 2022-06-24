import paho.mqtt.client as ph_mqtt_clt
from paho.mqtt.client import *
from queue import Queue
import os
import json

class HQYJ_Mqtt_Client():

    def __init__(self, ip_broker: str, port_broker: int,
                 topic_subscribe: str, topic_publish: str,
                 time_out_seconds: int, max_size_rcv_msg: int):
        self.hqyj_mqtt_clt = ph_mqtt_clt.Client()
        self.hqyj_mqtt_clt.on_message = self.on_message # 0.设置接收回调
        self.topic_subscribe = topic_subscribe
        self.topic_publish = topic_publish
        self.queue_rcv_msg = Queue(max_size_rcv_msg)
        try:
            self.hqyj_mqtt_clt.connect(ip_broker, port_broker, time_out_seconds)    # 1.连接Mqtt Broker
            self.hqyj_mqtt_clt.subscribe(self.topic_subscribe, qos=0)   # 2. 订阅相关的topic
            self.hqyj_mqtt_clt.loop_start() # 3.开启接收循环
        except Exception as e:
            print("HQYJ_Mqtt_Client init failed!error:", str(e))
            os._exit(0)

    def __del__(self):
        self.queue_rcv_msg.queue.clear()
        self.hqyj_mqtt_clt.loop_stop()
        self.hqyj_mqtt_clt.disconnect()

    def on_message(self, client, userdata, message):
        msg = json.loads(message.payload.decode())
        if not self.queue_rcv_msg.full():
            self.queue_rcv_msg.put(msg)
        else:
            print("mqtt_hqyj:queue_rcv_msg full!")
            self.queue_rcv_msg.queue.clear()

    def send_json_data(self, msg: str) -> bool:
        msg_inf: MQTTMessageInfo = self.hqyj_mqtt_clt.publish(self.topic_publish, payload="{}".format(msg))
        return msg_inf.rc == MQTT_ERR_SUCCESS

    def upload_mcu_json_data(self, obj_upload) -> bool:
        return self.send_json_data(json.dumps(obj_upload))
