from CarSpeedProcessor import CarSpeedProcessor
from CarSpeedConfig import CarSpeedConfig

def car_detected(data):
    print('car_detected')
    print(data)

print('CarSpeed!!')
config = CarSpeedConfig.fromDefJsonFile()
proc = CarSpeedProcessor(config)
proc.start(detection_hook=car_detected)

