from picamera2 import Picamera2
from libcamera import Transform, controls
import time
from pprint import *

from picamera2 import Picamera2, MappedArray
import cv2

picam2 = Picamera2()
index=0
max_index=0
max_fps=0
for sm in picam2.sensor_modes:
    (xc,yc,wc,hc)=sm['crop_limits']
    if sm['fps']>max_fps and xc==0 and yc==0:
        max_fps = sm['fps']
        max_index=index
    index=index+1

print(f'max_index={max_index}, max_fps={max_fps} size={picam2.sensor_modes[max_index]["size"]}')
(width,height)=picam2.sensor_modes[max_index]['size']
if width>1024:
    height=int(1024*(height/width))
    width=1024
    
print(f'width={width}, height={height}')
input('press any key to continue')
config = picam2.create_preview_configuration(main={"size": (width, height)},raw=picam2.sensor_modes[1])
pprint(config)
picam2.configure(config)
(w0, h0) = picam2.stream_configuration("main")["size"]
#(w1, h1) = picam2.stream_configuration("lores")["size"]
faces = []
picam2.start(show_preview=False)
frame_count = 0
st = time.time()
while True:
    array = picam2.capture_array("main")
    #grey = array[h1,:]
    frame_count=frame_count+1
    if (frame_count % 100) == 0:
        ft = time.time()
        frame_rate = 100/(ft-st)
        print(f'Time for buffer=[{frame_rate:4f}]')
        st = time.time()
    #faces = face_detector.detectMultiScale(grey, 1.1, 3)



camera = Picamera2()
#config = camera.create_still_configuration({"format": "RGB888"})
#camera.align_configuration(config)
#(width,height)=config['main']['size']
index=0
min_width=0
for sm in camera.sensor_modes:
    (width,height)=sm['size']
    if width<min_width or min_width==0:
        min_width=width
        min_height=height
    index=index+1

print(f"min_width={min_width}, min_height={min_height}")
image_width = min_width
image_height = min_height
ctrls={'NoiseReductionMode': 1, 'FrameDurationLimits': (33333, 33333), 'AfMode': controls.AfModeEnum.Manual}
config = camera.create_still_configuration({"size": (image_width, image_height),"format": "RGB888"},transform = Transform(hflip=True,vflip=True))
config['controls']=ctrls
print(config)
camera.configure(config)
pprint(camera.sensor_modes)

## 
camera.start()

#rawCapture = PiRGBArray(camera, size=camera.resolution)
# allow the camera to warm up
time.sleep(0.9)

count=0
st = time.time()
print("Capturing frames ...")
while True:
    # grab the raw NumPy array representing the image 
    image = camera.capture_array()
    count=count+1
    if count % 100 == 0:
        ft = time.time()
        frame_rate=100/(ft-st);
        print(f'Frame rate after 100 frames=[{frame_rate:.3f}]')
        st=time.time()
        break



