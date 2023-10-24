import json
import pathlib
import math
from typing import Union

class MonitorArea(object):
    def __init__(self,data=None):
        self.class_name = self.__class__.__name__
        self.upper_left_x:int = 0
        self.upper_left_y:int = 0
        self.lower_right_x:int = 0
        self.lower_right_y:int = 0
        if data:
            self.__dict__ = data

class CarSpeedConfig(object):
    DEF_CONFIG_FILE = "CarSpeed.json"
    def __init__(self,data=None):
        self.class_name = self.__class__.__name__
        self.l2r_distance:float = 47
        self.r2l_distance:float = 37
        self.min_speed_image:int = 0
        self.min_speed_save:int = 10
        self.max_speed_save:int = 80
        self.field_of_view:float = 75 # 75 is standard pi camera module 3, 120 for wide angle
        self.h_flip = False
        self.v_flip = False
        self.monitor_area = MonitorArea()
        if data:
            self.__dict__ = data   
            
    def getL2RFrameWidthFt(self)->float:
        frame_width_ft = 2*(math.tan(math.radians(self.field_of_view*0.5))*self.l2r_distance)
        return frame_width_ft
    
    def getR2LFrameWidthFt(self)->float:
        frame_width_ft = 2*(math.tan(math.radians(self.field_of_view*0.5))*self.r2l_distance)
        return frame_width_ft

    def toJson(self)->str:
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)
    @staticmethod
    def fromJsonFile(file:str):
        with open(file,"r") as f:
            return json.load(f, object_hook=CarSpeedConfig._objectHook)
    @staticmethod
    def fromJsonStr(str:str):
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
        if ( 'class_name' in dict):
            class_name = dict['class_name']
            if (class_name=='CarSpeedConfig'):                
                return CarSpeedConfig(dict)
            elif (class_name=='MonitorArea'):            
                return MonitorArea(dict)
    
    def shortDict(self):
        config={'l2r_distance': self.l2r_distance,\
                'r2l_distance': self.r2l_distance,\
                'min_speed_image': self.min_speed_image,\
                'min_speed_save': self.min_speed_save,\
                'max_speed_save': self.max_speed_save,\
                'field_of_view': self.field_of_view,\
                'h_flip': self.h_flip,\
                'v_flip': self.v_flip}
        return config
    
    def isMonitorAreaDefined(self)->bool:
        if not self.monitor_area:
            return False
        elif self.monitor_area.upper_left_x==0 and self.monitor_area.upper_left_y==0\
                and self.monitor_area.lower_right_x==0 and self.monitor_area.lower_right_y==0:
            return False
        else:
            return True
