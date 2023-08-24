class MonitorArea(object):
    def __init__(self,ulx,uly,lrx,lry):
        self.upper_left_x = ulx
        self.upper_left_y = uly
        self.lower_right_x = lrx
        self.lower_right_y = lry

class ConfigureMonitorArea(object):
    def __init__(self, h_flip:bool,v_flip: bool):
        self.area = MonitorArea(1,2,3,4)
        self.h_flip=h_flip
        self.v_flip=v_flip
    def start(self):
        pass