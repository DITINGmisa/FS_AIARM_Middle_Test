import re
import serial
import binascii
import crcmod.predefined
from queue import Queue
from enum import Enum

class CRC_Generator(object):

    def __init__(self, str_mode: str):
        self.mode = str_mode

    def crc_calculate(self, str_hex_data: str):
        hex_data = binascii.unhexlify(str_hex_data)
        crc_check_object = crcmod.predefined.Crc(self.mode)
        crc_check_object.update(hex_data)
        result_crc_check_original = hex(crc_check_object.crcValue)
        result_crc_check_final = re.sub("0x", "", result_crc_check_original)
        if len(result_crc_check_final) < 2:
            result_crc_check_final = '0' + result_crc_check_final
        return result_crc_check_final.upper()

class StatusReadSerialPortProtocol3021(Enum):
    header = 0
    data_length = 1
    data_offset = 2
    data_type = 3
    transfer_type = 4
    difference_field = 5
    data_field = 6
    crc_8 = 7

class Protocol(Enum):
    protocol_30 = 0
    protocol_21 = 1

class ProtocolVersion(Enum):
    XArm_RFID = 0x30
    WSN = 0x21

class Protocol30DataType(Enum):
    mpu_receive_XArm = 0x00
    mpu_receive_RFID = 0x02

class Protocol21DataType(Enum):
    mpu_receive_WSN = 0x00

Protocol30TransferType = 0x55

class Protocol21TransferType(Enum):
    Zigbee = 0x5A
    WIFI = 0x57

class Protocol30DifferenceField(Enum):
    node_id_low = 0
    node_id_high = 1

Protocol30NodeIdLow = 0xA1

class Protocol30NodeIdHigh(Enum):
    servos_pose_upload = 0x92
    XArm_pose_upload = 0x21
    XArm_grab_finished = 0x41
    RFID_data_get = 0xD2

class Protocol21DifferenceField(Enum):
    device_address_low = 0
    device_address_high = 1
    device_type = 2
    battery_level = 3

class HQYJ_Serial:

    def __init__(self, port_name: str, baud_rate: int, check_mode: str, max_size_rcv_data: int, max_size_rcv_msg: int):
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.serial_port = None
        self.check_mode = check_mode
        self.crc_check = None
        self.max_size_rcv_data = max_size_rcv_data
        self.queue_rcv_data = None
        self.max_size_rcv_msg = max_size_rcv_msg
        self.queue_rcv_msg = None
        self.loop_run = True

    def open_serial_port(self) -> bool:
        self.serial_port = serial.Serial(self.port_name, self.baud_rate)
        if self.serial_port.is_open:
            self.crc_check = CRC_Generator(self.check_mode)
            self.queue_rcv_data = Queue(self.max_size_rcv_data)
            self.queue_rcv_msg = Queue(self.max_size_rcv_msg)
            return True
        else:
            return False

    def close_serial_port(self):
        self.serial_port.flush()
        self.queue_rcv_data.queue.clear()
        self.queue_rcv_msg.queue.clear()
        self.loop_run = False
        self.serial_port.close()

    @staticmethod
    def int2hexstr(hex_data: int) -> str:
        str_hex_data = "%02X" % int(hex(hex_data), 16)
        return str_hex_data

    @staticmethod
    def str2hex(str_data: str) -> bytes:
        hex_data = bytes.fromhex(str_data)
        return hex_data

    def receive_data(self):
        # bytes_rcv_data = bytes()
        while self.loop_run:
            data_size = self.serial_port.in_waiting
            if data_size:
                bytes_rcv_data = self.serial_port.read_all()
                # print("bytes_rcv_data:", bytes_rcv_data)
                if len(bytes_rcv_data):
                    if not self.queue_rcv_data.full():
                        self.queue_rcv_data.put(bytes_rcv_data)
                    else:
                        print("serial_hqyj:queue_rcv_data:full!")
                        # self.queue_rcv_data.queue.clear()
                else:
                    print("length of bytes_rcv_data:0!")

    def receive_msg(self):
        status_read_serial_port: StatusReadSerialPortProtocol3021 = StatusReadSerialPortProtocol3021.header
        length_data: int = 0
        offset_data: int = 0
        mode_protocol: Protocol = Protocol.protocol_30
        status_difference_field_protocol30: Protocol30DifferenceField = Protocol30DifferenceField.node_id_low
        status_difference_field_protocol21: Protocol21DifferenceField = Protocol21DifferenceField.device_address_low
        count_bytes_data_field: int = 0
        msg_rcv: str = ""
        bytes_dt_rcv: bytes
        while self.loop_run:
            try:
                if not self.queue_rcv_data.empty():
                    bytes_dt_rcv = self.queue_rcv_data.get()
                    l_bytes_dt_rcv = len(bytes_dt_rcv)
                    for i in range(l_bytes_dt_rcv):
                        # print("bytes_dt_rcv[{}]:0x{:02X}".format(i, bytes_dt_rcv[i]))
                        if status_read_serial_port == StatusReadSerialPortProtocol3021.header:
                            if bytes_dt_rcv[i] == ProtocolVersion.XArm_RFID.value:
                                print("XArm_RFID++++++")
                                mode_protocol = Protocol.protocol_30
                                msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                status_read_serial_port = StatusReadSerialPortProtocol3021.data_length
                            elif bytes_dt_rcv[i] == ProtocolVersion.WSN.value:
                                mode_protocol = Protocol.protocol_21
                                msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                status_read_serial_port = StatusReadSerialPortProtocol3021.data_length
                            else:
                                if length_data:
                                    length_data = 0
                                if offset_data:
                                    offset_data = 0
                                if msg_rcv != '':
                                    msg_rcv = ''
                        elif status_read_serial_port == StatusReadSerialPortProtocol3021.data_length:
                            length_data = bytes_dt_rcv[i]
                            # print("length_data:", length_data)
                            msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                            status_read_serial_port = StatusReadSerialPortProtocol3021.data_offset
                        elif status_read_serial_port == StatusReadSerialPortProtocol3021.data_offset:
                            offset_data = bytes_dt_rcv[i]
                            # print("offset_data:", offset_data)
                            msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                            status_read_serial_port = StatusReadSerialPortProtocol3021.data_type
                        elif status_read_serial_port == StatusReadSerialPortProtocol3021.data_type:
                            if mode_protocol == Protocol.protocol_30:
                                if bytes_dt_rcv[i] == Protocol30DataType.mpu_receive_XArm.value:
                                    msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.transfer_type
                                elif bytes_dt_rcv[i] == Protocol30DataType.mpu_receive_RFID.value:
                                    msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.transfer_type
                                else:
                                    if length_data:
                                        length_data = 0
                                    if offset_data:
                                        offset_data = 0
                                    if msg_rcv != '':
                                        msg_rcv = ''
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.header
                            else:
                                if bytes_dt_rcv[i] == Protocol21DataType.mpu_receive_WSN.value:
                                    msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.transfer_type
                                else:
                                    if length_data:
                                        length_data = 0
                                    if offset_data:
                                        offset_data = 0
                                    if msg_rcv != '':
                                        msg_rcv = ''
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.header
                        elif status_read_serial_port == StatusReadSerialPortProtocol3021.transfer_type:
                            if mode_protocol == Protocol.protocol_30:
                                if bytes_dt_rcv[i] == Protocol30TransferType:
                                    msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.difference_field
                                else:
                                    if length_data:
                                        length_data = 0
                                    if offset_data:
                                        offset_data = 0
                                    if msg_rcv != '':
                                        msg_rcv = ''
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.header
                            else:
                                if bytes_dt_rcv[i] == Protocol21TransferType.Zigbee.value:
                                    msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.difference_field
                                elif bytes_dt_rcv[i] == Protocol21TransferType.WIFI.value:
                                    msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.difference_field
                                else:
                                    if length_data:
                                        length_data = 0
                                    if offset_data:
                                        offset_data = 0
                                    if msg_rcv != '':
                                        msg_rcv = ''
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.header
                        elif status_read_serial_port == StatusReadSerialPortProtocol3021.difference_field:
                            if mode_protocol == Protocol.protocol_30:
                                if status_difference_field_protocol30 == Protocol30DifferenceField.node_id_low:
                                    if bytes_dt_rcv[i] == Protocol30NodeIdLow:
                                        # print("Protocol30NodeIdLow+++")
                                        msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                        status_difference_field_protocol30 = Protocol30DifferenceField.node_id_high
                                    else:
                                        if length_data:
                                            length_data = 0
                                        if offset_data:
                                            offset_data = 0
                                        if msg_rcv != '':
                                            msg_rcv = ''
                                        status_read_serial_port = StatusReadSerialPortProtocol3021.header
                                else:
                                    if bytes_dt_rcv[i] in [Protocol30NodeIdHigh.servos_pose_upload.value,
                                                           Protocol30NodeIdHigh.XArm_pose_upload.value,
                                                           Protocol30NodeIdHigh.XArm_grab_finished.value,
                                                           Protocol30NodeIdHigh.RFID_data_get.value]:
                                        # print("Protocol30NodeIdHigh+++")
                                        msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                        status_read_serial_port = StatusReadSerialPortProtocol3021.data_field
                                    else:
                                        if length_data:
                                            length_data = 0
                                        if offset_data:
                                            offset_data = 0
                                        if msg_rcv != '':
                                            msg_rcv = ''
                                        status_read_serial_port = StatusReadSerialPortProtocol3021.header
                                    status_difference_field_protocol30 = Protocol30DifferenceField.node_id_low
                            else:
                                if status_difference_field_protocol21 == Protocol21DifferenceField.device_address_low:
                                    msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                    status_difference_field_protocol21 = Protocol21DifferenceField.device_address_high
                                elif status_difference_field_protocol21 == Protocol21DifferenceField.device_address_high:
                                    msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                    status_difference_field_protocol21 = Protocol21DifferenceField.device_type
                                elif status_difference_field_protocol21 == Protocol21DifferenceField.device_type:
                                    msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                    status_difference_field_protocol21 = Protocol21DifferenceField.battery_level
                                else:
                                    msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                                    status_read_serial_port = StatusReadSerialPortProtocol3021.data_field
                                    status_difference_field_protocol21 = Protocol21DifferenceField.device_address_low
                        elif status_read_serial_port == StatusReadSerialPortProtocol3021.data_field:
                            msg_rcv += self.int2hexstr(bytes_dt_rcv[i])
                            count_bytes_data_field += 1
                            # print("count_bytes_data_field:", count_bytes_data_field)
                            if count_bytes_data_field == length_data:
                                status_read_serial_port = StatusReadSerialPortProtocol3021.crc_8
                                count_bytes_data_field = 0
                        else:
                            print("msg_rcv(except crc_8):", msg_rcv)
                            result_crc_8_ccl = self.crc_check.crc_calculate(msg_rcv)
                            result_crc_8_rcv = self.int2hexstr(bytes_dt_rcv[i])
                            if result_crc_8_ccl == result_crc_8_rcv:
                                msg_rcv += result_crc_8_rcv
                                if not self.queue_rcv_msg.full():
                                    self.queue_rcv_msg.put(msg_rcv.upper())
                                    print("msg_rcv:", msg_rcv.upper())
                                else:
                                    print("serial_hqyj:queue_rcv_msg:full")
                            else:
                                print("crc_8 error:ccl:{},rcv:{}".format(result_crc_8_ccl, result_crc_8_rcv))
                            if length_data:
                                length_data = 0
                            if offset_data:
                                offset_data = 0
                            if msg_rcv != '':
                                msg_rcv = ''
                            status_read_serial_port = StatusReadSerialPortProtocol3021.header
            except Exception as e:
                print("receive_msg:error:{}".format(str(e)))
                status_read_serial_port = StatusReadSerialPortProtocol3021.header
                length_data = 0
                offset_data = 0
                mode_protocol = Protocol.protocol_30
                status_difference_field_protocol30 = Protocol30DifferenceField.node_id_low
                status_difference_field_protocol21 = Protocol21DifferenceField.device_address_low
                count_bytes_data_field = 0
                msg_rcv = ""
                bytes_dt_rcv = bytes()

    def send_str_data(self, str_data: str) -> bool:
        str_data_frame = str_data + self.crc_check.crc_calculate(str_data)
        print("str_data_frame:", str_data_frame)
        bytes_data_frame = self.str2hex(str_data_frame)
        result_write_serial_port = self.serial_port.write(bytes_data_frame)
        # print("result_write_serial_port:", result_write_serial_port)
        # print("length bytes_data_frame:", len(bytes_data_frame))
        return result_write_serial_port == len(bytes_data_frame)
