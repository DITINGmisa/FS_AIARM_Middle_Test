import yaml
import json
import threading
import os
from queue import Queue
import re
from plugins.serial_hqyj import *
from plugins.mqtt_hqyj import *

def load_config_yaml(relative_path_cfg: str):
    path_current_directory = os.path.dirname(os.path.realpath(__file__))
    try:
        absolute_path_config = os.path.join(path_current_directory, relative_path_cfg)
        with open(absolute_path_config, 'r') as fd_yaml_cfg:
            object_cfg = yaml.load(fd_yaml_cfg.read(), Loader=yaml.FullLoader)
        assert object_cfg != {}, ("配置文件{}的内容为空!".format(relative_path_cfg))
        """
        if not object_cfg != {}:
            raise AssertionError("配置文件{}的内容为空!".format(relative_path_cfg))
        """
        print("{}:{}".format(relative_path_cfg, object_cfg))
        return object_cfg
    except Exception as e:
        print("load_config_yaml:{}:error:{}".format(relative_path_cfg, str(e)))
        return {}

class FS_AIARM_Gateway:

    def __init__(self, port_name: str, baud_rate: int, check_mode: str,
                 max_size_rcv_data_sp: int, max_size_rcv_msg_sp: int,
                 pth_cfg_sp2mqtt: str, pth_cfg_mqtt2sp: str,
                 ip_broker: str, port_broker: int,
                 time_out_seconds: int, max_size_rcv_msg_mqtt: int):
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.check_mode = check_mode
        self.max_size_rcv_data_sp = max_size_rcv_data_sp
        self.max_size_rcv_msg_sp = max_size_rcv_msg_sp
        self.obj_serial_port = HQYJ_Serial(self.port_name, self.baud_rate, self.check_mode, self.max_size_rcv_data_sp,
                                           self.max_size_rcv_msg_sp)
        if not self.obj_serial_port.open_serial_port():
            print("串口:{}打开失败!".format(self.port_name))
            os._exit(0)
        self.obj_cfg_sp2mqtt = load_config_yaml(pth_cfg_sp2mqtt)
        if self.obj_cfg_sp2mqtt == {}:
            print("obj_cfg_sp2mqtt:获取失败!")
            os._exit(0)
        self.obj_cfg_mqtt2sp = load_config_yaml(pth_cfg_mqtt2sp)
        if self.obj_cfg_mqtt2sp == {}:
            print("obj_cfg_mqtt2sp:获取失败!")
            os._exit(0)
        self.ip_broker = ip_broker
        self.port_broker = port_broker
        self.time_out_seconds = time_out_seconds
        self.max_size_rcv_msg_mqtt = max_size_rcv_msg_mqtt
        self.obj_mqtt_clt = HQYJ_Mqtt_Client(self.ip_broker, self.port_broker,
                                             self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Topic"],
                                             self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Topic"],
                                             self.time_out_seconds, self.max_size_rcv_msg_mqtt)
        self.t_sp_rcv_dt = threading.Thread(target=self.obj_serial_port.receive_data)
        self.t_sp_rcv_dt.start()
        self.t_sp_rcv_msg = threading.Thread(target=self.obj_serial_port.receive_msg)
        self.t_sp_rcv_msg.start()
        self.t_mqtt2sp = threading.Thread(target=self.mqtt2sp)
        self.t_mqtt2sp.start()

    def __del__(self):
        self.obj_serial_port.close_serial_port()

    def mqtt2sp(self):
        while self.obj_serial_port.loop_run:
            if not self.obj_mqtt_clt.queue_rcv_msg.empty():
                obj_mqtt_clt = self.obj_mqtt_clt.queue_rcv_msg.get()
                if type(obj_mqtt_clt) == dict:
                    if obj_mqtt_clt.get("To_XArm"):
                        obj_mqtt_clt_to_xarm = obj_mqtt_clt["To_XArm"]
                        print(obj_mqtt_clt_to_xarm)
                    elif obj_mqtt_clt.get("To_WSN"):
                        obj_mqtt_clt_to_wsn = obj_mqtt_clt["To_WSN"]
                        if type(obj_mqtt_clt_to_wsn) == dict:
                            if obj_mqtt_clt_to_wsn.get("By_WIFI"):
                                obj_mqtt_clt_to_wsn_by_wifi = obj_mqtt_clt_to_wsn["By_WIFI"]
                                if type(obj_mqtt_clt_to_wsn_by_wifi) == dict:
                                    pass
                                else:
                                    print("obj_mqtt_clt_to_wsn_by_wifi格式错误!")
                        else:
                            print("obj_mqtt_clt_to_wsn格式错误!")
                else:
                    print("obj_mqtt_clt格式错误!")
            else:
                pass

    def sp2mqtt(self):
        pass

if __name__ == "__main__":
    obj_fs_aiarm_gtw = FS_AIARM_Gateway("/dev/ttyS4", 115200, "crc-8", 50, 25, "config/cfg_serial2mqtt.yml",
                                        "config/cfg_mqtt2serial.yml", "127.0.0.1", 1883, 30, 25)
    obj_fs_aiarm_gtw.sp2mqtt()
