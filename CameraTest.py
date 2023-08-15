from picamera2 import Picamera2
from libcamera import Transform, Size
import time
from pprint import *

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
config = camera.create_still_configuration({"size": (image_width, image_height),"format": "RGB888"},transform = Transform(hflip=True,vflip=True))
camera.configure(config)
print(config)
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



