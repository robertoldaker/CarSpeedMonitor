import json
import pathlib

class MonitorArea(object):
    def __init__(self,data=None):
        self.class_name = self.__class__.__name__
        self.upper_left_x = 0
        self.upper_left_y = 0
        self.lower_right_x = 0
        self.lower_right_y = 0
        if data:
            self.__dict__ = data

class CarSpeedConfig(object):
    DEF_CONFIG_FILE = "CarSpeed.json"
    def __init__(self,data=None):
        self.class_name = self.__class__.__name__
        self.l2r_distance = 47
        self.r2l_distance = 37
        self.min_speed_image = 0
        self.min_speed_save = 10
        self.max_speed_save = 80
        self.field_of_view = 75 # 75 is standard pi camera module 3, 120 for wide angle
        self.h_flip = False
        self.v_flip = False
        self.monitor_area = MonitorArea()
        if  data:
            self.__dict__ = data
            
    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)
    @staticmethod
    def fromJsonFile(file):
        with open(file,"r") as f:
            return json.load(f, object_hook=CarSpeedConfig._objectHook)
    @staticmethod
    def fromJsonStr(str):
        return json.loads(str, object_hook=CarSpeedConfig._objectHook)
    @staticmethod
    def fromDefJsonFile():
        config = None
        configPath = pathlib.Path(CarSpeedConfig.DEF_CONFIG_FILE)
        if ( configPath.exists()):
            print(f"Loading config from [{CarSpeedConfig.DEF_CONFIG_FILE}]")
            config = CarSpeedConfig.fromJsonFile(CarSpeedConfig.DEF_CONFIG_FILE)
        return config
        
    @staticmethod
    def _objectHook(dict):
        print("ObjectHook")
        print(dict)
        if ( 'class_name' in dict):
            class_name = dict['class_name']
            if (class_name=='CarSpeedConfig'):                
                return CarSpeedConfig(dict)
            elif (class_name=='MonitorArea'):            
                return MonitorArea(dict)
