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
                # 先看是不是字典
                if type(obj_mqtt_clt) == dict:
                    if obj_mqtt_clt.get("To_XArm"):
                        obj_mqtt_clt_to_xarm = obj_mqtt_clt["To_XArm"]
                        if type(obj_mqtt_clt_to_xarm)==str:
                            if obj_mqtt_clt_to_xarm in ["Request_6servos_Pose","Control_XArm_Position"]:
                                # print(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_XArm"][obj_mqtt_clt_to_xarm])
                                if not self.obj_serial_port.send_str_data(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_XArm"][obj_mqtt_clt_to_xarm]):
                                    print(f"串口发送{obj_mqtt_clt_to_xarm}失败！")
                            else:
                                print("obj_mqtt_clt_to_xarm为无效字符串！")
                        elif type(obj_mqtt_clt_to_xarm)==dict:
                            if obj_mqtt_clt_to_xarm.get("Control_XArm_Action"):
                                obj_mqtt_clt_to_xarm_action=obj_mqtt_clt_to_xarm["Control_XArm_Action"]
                                if type(obj_mqtt_clt_to_xarm_action)==str:
                                    if obj_mqtt_clt_to_xarm_action in list(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_XArm"]["Control_XArm_Action"].keys()):
                                        if not self.obj_serial_port.send_str_data(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_XArm"]["Control_XArm_Action"][obj_mqtt_clt_to_xarm_action]):
                                            print(f"串口发送{obj_mqtt_clt_to_xarm_action}失败！")
                                    else:
                                        print("obj_mqtt_clt_to_xarm_action为无效字符串！")
                                else:
                                    print("obj_mqtt_clt_to_xarm_action为无效的数据类型！")
                            elif obj_mqtt_clt_to_xarm.get("Control_XArm_Grab"):
                                obj_mqtt_clt_to_xram_grab=obj_mqtt_clt_to_xarm["Control_XArm_Grab"]
                                if type(obj_mqtt_clt_to_xram_grab)==dict:
                                    try:
                                        start= obj_mqtt_clt_to_xram_grab["start"]
                                        end  = obj_mqtt_clt_to_xram_grab["end"]
                                    except:
                                        print("obj_mqtt_clt_to_xram_grab未包含起止点信息！")
                                    if not int(start) < 5 and int(start) > 0:
                                        print("start超限！")
                                    if not int(end) < 5 and int(end) > 0:
                                        print("end超限！")
                                    str_xram_grab=self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_XArm"]["Control_XArm_Grab"]
                                    str_xram_grab=list(str_xram_grab)
                                    str_xram_grab[-3],str_xram_grab[-1]=str(start),str(end)
                                    if not self.obj_serial_port.send_str_data(''.join(str_xram_grab)):
                                        print("串口发送str_xram_grab失败！")
                                else:
                                    print("obj_mqtt_clt_to_xarm_grab为无效的数据类型！")
                            elif obj_mqtt_clt_to_xarm.get("Control_Servo_Pose"):
                                obj_mqtt_clt_to_xram_spose=obj_mqtt_clt_to_xarm["Control_Servo_Pose"]
                                if type(obj_mqtt_clt_to_xram_spose)==dict:
                                    try:
                                        ServoId= obj_mqtt_clt_to_xram_spose["ServoId"]
                                        Pose   = obj_mqtt_clt_to_xram_spose["Pose"]
                                    except:
                                        print("obj_mqtt_clt_to_xram_spose未包含舵机或角度信息！")
                                    if not int(ServoId) < 7 and int(ServoId) > 0:
                                        print("ServoId超限！")
                                    if not int(Pose) < 251 and int(Pose) >= 0:
                                        print("Pose超限！")
                                    str_xram_spose=self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_XArm"]["Control_Servo_Pose"]
                                    str_xram_spose=list(str_xram_spose)
                                    str_xram_spose[-3],str_xram_spose[-2],str_xram_spose[-1]=str(ServoId),str(hex(int(Pose)))[-2],str(hex(int(Pose)))[-1]
                                    if not self.obj_serial_port.send_str_data(''.join(str_xram_spose)):
                                        print("串口发送str_xram_spose失败！")
                                else:
                                    print("obj_mqtt_clt_to_xram_spose为无效的数据类型！")          
                        else:
                            print("obj_mqtt_clt_to_xarm为无效的数据类型！")
                    elif obj_mqtt_clt.get("To_WSN"):
                        obj_mqtt_clt_to_wsn = obj_mqtt_clt["To_WSN"]
                        if type(obj_mqtt_clt_to_wsn) == dict:
                            if obj_mqtt_clt_to_wsn.get("By_WIFI"):
                                obj_mqtt_clt_to_wsn_by_wifi = obj_mqtt_clt_to_wsn["By_WIFI"]
                                if type(obj_mqtt_clt_to_wsn_by_wifi) == dict:
                                    if obj_mqtt_clt_to_wsn_by_wifi.get("Control_Fan"):
                                        obj_mqtt_clt_to_wsn_by_wifi_control_fan = obj_mqtt_clt_to_wsn_by_wifi["Control_Fan"]
                                        if type(obj_mqtt_clt_to_wsn_by_wifi_control_fan) == str:
                                            if obj_mqtt_clt_to_wsn_by_wifi_control_fan in ["On", "Off"]:
                                                # obj_mqtt_clt_to_wsn_by_wifi_control_fan = '"' + obj_mqtt_clt_to_wsn_by_wifi_control_fan + '"'
                                                print(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_WSN"]["By_WIFI"]["Control_Fan"][obj_mqtt_clt_to_wsn_by_wifi_control_fan])
                                                if not self.obj_serial_port.send_str_data(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_WSN"]["By_WIFI"]["Control_Fan"][obj_mqtt_clt_to_wsn_by_wifi_control_fan]):
                                                    print(f"串口发送{obj_mqtt_clt_to_wsn_by_wifi_control_fan}失败！")
                                            else:
                                                print("obj_mqtt_clt_to_wsn_by_wifi_control_fan为无效字符串！")
                                        else:
                                            print("obj_mqtt_clt_to_wsn_by_wifi_control_fan为无效的数据类型！")

                                    elif obj_mqtt_clt_to_wsn_by_wifi.get("Control_Relay"):
                                        obj_mqtt_clt_to_wsn_by_wifi_control_relay = obj_mqtt_clt_to_wsn_by_wifi["Control_Relay"]
                                        if type(obj_mqtt_clt_to_wsn_by_wifi_control_relay) == str:
                                             if obj_mqtt_clt_to_wsn_by_wifi_control_relay in ["Break", "Close"]: 
                                                if not self.obj_serial_port.send_str_data(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_WSN"]["By_WIFI"]["Control_Relay"][obj_mqtt_clt_to_wsn_by_wifi_control_relay]):
                                                    print(f"串口发送{obj_mqtt_clt_to_wsn_by_wifi_control_relay}失败！")
                                             else:
                                                print("obj_mqtt_clt_to_wsn_by_wifi_control_relay为无效字符串！")
                                        else:
                                            print("obj_mqtt_clt_to_wsn_by_wifi_control_relay为无效的数据类型！")
                                    else:
                                        print("obj_mqtt_clt_to_wsn_by_wifi键值错误！")
                                else:
                                    print("obj_mqtt_clt_to_wsn_by_wifi格式错误!")
                            if obj_mqtt_clt_to_wsn.get("By_Zigbee"):
                                obj_mqtt_clt_to_wsn_by_zigbee = obj_mqtt_clt_to_wsn["By_Zigbee"]
                                if type(obj_mqtt_clt_to_wsn_by_zigbee) == dict:
                                    if obj_mqtt_clt_to_wsn_by_zigbee.get("Control_Fan"):
                                        obj_mqtt_clt_to_wsn_by_zigbee_control_fan=obj_mqtt_clt_to_wsn_by_zigbee["Control_Fan"]
                                        if type(obj_mqtt_clt_to_wsn_by_zigbee_control_fan)==str:
                                            if obj_mqtt_clt_to_wsn_by_zigbee_control_fan in list(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_WSN"]["By_Zigbee"]["Control_Fan"].keys()):
                                                # obj_mqtt_clt_to_wsn_by_zigbee_control_fan='"'+obj_mqtt_clt_to_wsn_by_zigbee_control_fan+'"'
                                                if not self.obj_serial_port.send_str_data(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_WSN"]["By_Zigbee"]["Control_Fan"][obj_mqtt_clt_to_wsn_by_zigbee_control_fan]):
                                                    print(f"串口发送{obj_mqtt_clt_to_wsn_by_zigbee_control_fan}失败！")
                                            else: print("obj_mqtt_clt_to_wsn_by_zigbee_control_fan为无效字符串！")
                                        else: print("obj_mqtt_clt_to_wsn_by_zigbee_control_fan为无效的数据类型！")

                                    elif obj_mqtt_clt_to_wsn_by_zigbee.get("Control_Relay"):
                                        obj_mqtt_clt_to_wsn_by_zigbee_control_relay = obj_mqtt_clt_to_wsn_by_zigbee["Control_Relay"]
                                        if type(obj_mqtt_clt_to_wsn_by_zigbee_control_relay) == str:
                                            if obj_mqtt_clt_to_wsn_by_zigbee_control_relay in list(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_WSN"]["By_Zigbee"]["Control_Relay"].keys()):
                                                # obj_mqtt_clt_to_wsn_by_zigbee_control_relay='"'+obj_mqtt_clt_to_wsn_by_zigbee_control_relay+'"'
                                                if not self.obj_serial_port.send_str_data(self.obj_cfg_mqtt2sp["Gateway_HQYJ_MPU2MCU"]["Dictionaries"]["To_WSN"]["By_Zigbee"]["Control_Relay"][obj_mqtt_clt_to_wsn_by_zigbee_control_relay]):
                                                    print(f"串口发送{obj_mqtt_clt_to_wsn_by_zigbee_control_relay}失败！")
                                            else:
                                                print("obj_mqtt_clt_to_wsn_by_zigbee_control_relay为无效字符串！")
                                        else:
                                            print("obj_mqtt_clt_to_wsn_by_zigbee_control_relay为无效的数据类型！")
                                else:
                                    print("obj_mqtt_clt_to_wsn_by_zigbee为无效的数据类型！")
                        else:
                            print("obj_mqtt_clt_to_wsn格式错误!")
                    else:
                        print("obj_mqtt_clt键错误!")
                else:
                    print("obj_mqtt_clt格式错误!")
            else:
                pass

    def sp2mqtt(self):
        while self.obj_serial_port.loop_run:
            if not self.obj_serial_port.queue_rcv_msg.empty():
                str_sp_rcv = self.obj_serial_port.queue_rcv_msg.get()
                str_sp_rcv_excpt_crc = str_sp_rcv[:-2]
                # 长度校验
                if (int(str_sp_rcv_excpt_crc[2: 4], 16) + int(str_sp_rcv_excpt_crc[4: 6], 16)) * 2 == len(str_sp_rcv_excpt_crc):
                    if str_sp_rcv_excpt_crc[0: 2] == "30":
                        if not str_sp_rcv_excpt_crc.find("3006070055A192"):
                            obj_mqtt_pblsh = {"Protocol30": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol30"]["3006070055A192"]}
                            list_6servos_pose = [int(str_sp_rcv_excpt_crc[i: (i + 2)], 16) * 4 for i in range(14, len(str_sp_rcv_excpt_crc), 2)]
                            b_size_check_pass = True
                            for pose in list_6servos_pose:
                                if not 0 <= pose <= 1000:
                                    b_size_check_pass = False
                            if b_size_check_pass:
                                obj_mqtt_pblsh["Protocol30"]["6servos_Pose_Upload"] = list_6servos_pose
                                if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                    print("obj_mqtt_pblsh:针对30协议:上传6个舵机的数据失败!")
                            else:
                                print("所上传的6个舵机角度规格有误!")
                        elif not str_sp_rcv_excpt_crc.find("3001070055A12131"):
                            obj_mqtt_pblsh = {"Protocol30": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol30"]["3001070055A12131"]}
                            if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                print("obj_mqtt_pblsh:针对30协议:上传到达仓库1信号失败!")
                        elif not str_sp_rcv_excpt_crc.find("3001070055A14131"):
                            obj_mqtt_pblsh = {"Protocol30": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol30"]["3001070055A14131"]}
                            if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                print("obj_mqtt_pblsh:针对30协议:上传抓取完毕信号失败!")
                        elif not str_sp_rcv_excpt_crc.find("3004070255A1D2"):
                            obj_mqtt_pblsh = {"Protocol30": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol30"]["3004070255A1D2"]}
                            list_rfid_data = [int(str_sp_rcv_excpt_crc[i: (i + 2)], 16) for i in range(14, len(str_sp_rcv_excpt_crc), 2)]
                            obj_mqtt_pblsh["Protocol30"]["RFID_Data_Upload"] = list_rfid_data
                            if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                print("obj_mqtt_pblsh:针对30协议:上传RFID数据失败!")
                        else:
                            print("str_sp_rcv_excpt_crc:针对30协议数据有误!")
                    elif str_sp_rcv_excpt_crc[0: 2] == "21":
                        if str_sp_rcv_excpt_crc[8: 10] == "57":
                            if not str_sp_rcv_excpt_crc.find("2101090057"):
                                if str_sp_rcv_excpt_crc[14: 16] == "66":
                                    if str_sp_rcv_excpt_crc[18: 20] == "30":
                                        obj_mqtt_pblsh = {"Protocol21": {"By_WIFI": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_WIFI"]["2101090057XXXX66YY30"]}}
                                        if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                            print("obj_mqtt_pblsh:针对21协议:Wifi模块:上传风扇状态失败!")
                                    elif str_sp_rcv_excpt_crc[18: 20] == "31":
                                        obj_mqtt_pblsh = {"Protocol21": {"By_WIFI": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_WIFI"]["2101090057XXXX66YY31"]}}
                                        if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                            print("obj_mqtt_pblsh:针对21协议:Wifi模块:上传风扇状态失败!")
                                    else:
                                        print("str_sp_rcv_excpt_crc:针对21协议:Wifi模块:风扇状态有误!")
                                elif str_sp_rcv_excpt_crc[14: 16] == "72":
                                    if str_sp_rcv_excpt_crc[18: 20] == "30":
                                        obj_mqtt_pblsh = {"Protocol21": {"By_WIFI": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_WIFI"]["2101090057XXXX72YY30"]}}
                                        if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                            print("obj_mqtt_pblsh:针对21协议:Wifi模块:上传继电器状态失败!")
                                    elif str_sp_rcv_excpt_crc[18: 20] == "31":
                                        obj_mqtt_pblsh = {"Protocol21": {"By_WIFI": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_WIFI"]["2101090057XXXX72YY31"]}}
                                        if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                            print("obj_mqtt_pblsh:针对21协议:Wifi模块:上传继电器状态失败!")
                                    else:
                                        print("str_sp_rcv_excpt_crc:针对21协议:Wifi模块:继电器状态有误!")
                                else:
                                    print("str_sp_rcv_excpt_crc:针对21协议:Wifi模块:可控类设备的设备类型无效!")
                            elif not str_sp_rcv_excpt_crc.find("2102090057"):
                                if str_sp_rcv_excpt_crc[14: 16] == "4C":
                                    print("&&&&&&&&&&&&&")
                                    obj_mqtt_pblsh = {"Protocol21": {"By_WIFI": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_WIFI"]["2102090057XXXX4C"]}}
                                    data_photoresistor = int(str_sp_rcv_excpt_crc[18: 22], 16)
                                    obj_mqtt_pblsh["Protocol21"]["By_WIFI"]["Photoresistor"] = data_photoresistor
                                    if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                        print("obj_mqtt_pblsh:针对21协议:Wifi模块:上传光敏传感器数据失败!")
                                elif str_sp_rcv_excpt_crc[14: 16] == "54":
                                    obj_mqtt_pblsh = {"Protocol21": {"By_WIFI": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_WIFI"]["2102090057XXXX54"]}}
                                    data_temperature = int(str_sp_rcv_excpt_crc[18: 20], 16)
                                    data_humidity = int(str_sp_rcv_excpt_crc[20: 22], 16)
                                    obj_mqtt_pblsh["Protocol21"]["By_WIFI"]["DHT11"]["Temperature"] = data_temperature
                                    obj_mqtt_pblsh["Protocol21"]["By_WIFI"]["DHT11"]["Humidity"] = data_humidity
                                    if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                        print("obj_mqtt_pblsh:针对21协议:Wifi模块:上传温湿度传感器数据失败!")
                                else:
                                    print("str_sp_rcv_excpt_crc:针对21协议:Wifi模块:上传类设备的设备类型无效!")
                            else:
                                print("str_sp_rcv_excpt_crc:针对21协议:Wifi模块:传感器数据有误!")
                        elif str_sp_rcv_excpt_crc[8: 10] == "5A":
                            if not str_sp_rcv_excpt_crc.find("210109005A"):
                                if str_sp_rcv_excpt_crc[14: 16] == "66":
                                    if str_sp_rcv_excpt_crc[18: 20] == "30":
                                        obj_mqtt_pblsh = {"Protocol21": {"By_Zigbee": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_Zigbee"]["210109005AXXXX66YY30"]}}
                                        if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                            print("obj_mqtt_pblsh:针对21协议:Zigbee模块:上传风扇状态失败!")
                                    elif str_sp_rcv_excpt_crc[18: 20] == "31":
                                        obj_mqtt_pblsh = {"Protocol21": {"By_Zigbee": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_Zigbee"]["210109005AXXXX66YY31"]}}
                                        if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                            print("obj_mqtt_pblsh:针对21协议:Zigbee模块:上传风扇状态失败!")
                                    else:
                                        print("str_sp_rcv_excpt_crc:针对21协议:Zigbee模块:风扇状态有误!")
                                elif str_sp_rcv_excpt_crc[14: 16] == "72":
                                    if str_sp_rcv_excpt_crc[18: 20] == "30":
                                        obj_mqtt_pblsh = {"Protocol21": {"By_Zigbee": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_Zigbee"]["210109005AXXXX72YY30"]}}
                                        if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                            print("obj_mqtt_pblsh:针对21协议:Wifi模块:上传继电器状态失败!")
                                    elif str_sp_rcv_excpt_crc[18: 20] == "31":
                                        obj_mqtt_pblsh = {"Protocol21": {"By_Zigbee": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_Zigbee"]["210109005AXXXX72YY31"]}}
                                        if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                            print("obj_mqtt_pblsh:针对21协议:Wifi模块:上传继电器状态失败!")
                                    else:
                                        print("str_sp_rcv_excpt_crc:针对21协议:Zigbee模块:继电器状态有误!")
                                else:
                                    print("str_sp_rcv_excpt_crc:针对21协议:Zigbee模块:可控类设备的设备类型无效!")
                            elif not str_sp_rcv_excpt_crc.find("210209005A"):
                                if str_sp_rcv_excpt_crc[14: 16] == "4C":
                                    obj_mqtt_pblsh = {"Protocol21": {"By_Zigbee": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_Zigbee"]["210209005AXXXX4C"]}}
                                    data_photoresistor = int(str_sp_rcv_excpt_crc[18: 22], 16)
                                    obj_mqtt_pblsh["Protocol21"]["By_Zigbee"]["Photoresistor"] = data_photoresistor
                                    if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                        print("obj_mqtt_pblsh:针对21协议:Zigbee模块:上传光敏传感器数据失败!")
                                elif str_sp_rcv_excpt_crc[14: 16] == "54":
                                    obj_mqtt_pblsh = {"Protocol21": {"By_Zigbee": self.obj_cfg_sp2mqtt["Gateway_HQYJ_MCU2MPU"]["Dictionaries"]["Protocol21"]["By_Zigbee"]["210209005AXXXX54"]}}
                                    data_temperature = int(str_sp_rcv_excpt_crc[18: 20], 16)
                                    data_humidity = int(str_sp_rcv_excpt_crc[20: 22], 16)
                                    obj_mqtt_pblsh["Protocol21"]["By_Zigbee"]["DHT11"]["Temperature"] = data_temperature
                                    obj_mqtt_pblsh["Protocol21"]["By_Zigbee"]["DHT11"]["Humidity"] = data_humidity
                                    if not self.obj_mqtt_clt.upload_mcu_json_data(obj_mqtt_pblsh):
                                        print("obj_mqtt_pblsh:针对21协议:Zigbee模块:上传温湿度传感器数据失败!")
                                else:
                                    print("str_sp_rcv_excpt_crc:针对21协议:Zigbee模块:上传类设备的设备类型无效!")
                            else:
                                print("str_sp_rcv_excpt_crc:针对21协议:Zigbee模块:传感器数据有误!")
                        else:
                            print("str_sp_rcv_excpt_crc:传输类型有误!")
                    else:
                        print("str_sp_rcv_excpt_crc:包头错误!")
                else:
                    print("str_sp_rcv_excpt_crc:长度校验不通过!")

if __name__ == "__main__":
    obj_fs_aiarm_gtw = FS_AIARM_Gateway("/dev/ttyS4", 115200, "crc-8", 50, 25, "config/cfg_serial2mqtt.yml",
                                        "config/cfg_mqtt2serial.yml", "127.0.0.1", 1883, 30, 25)
    obj_fs_aiarm_gtw.sp2mqtt()
