from typing import Callable, List, Tuple
from CarSpeedConfig import CarSpeedConfig
# import the necessary packages
from picamera2 import Picamera2
from libcamera import Transform
from enum import IntEnum
import time
import math
import datetime
import cv2
import numpy as np
import json
import os
from pathlib import Path

# Current detection state
class DetectionState(IntEnum):
    WAITING=0
    TRACKING=1

# Current detection direction
class DetectionDirection(IntEnum):
    UNKNOWN = 0
    LEFT_TO_RIGHT = 1
    RIGHT_TO_LEFT = 2

class TrackingData(object):
    def __init__(self,abs_chg: int,secs: float,mph: float,x: int,biggest_area: int,direction: DetectionDirection):
        self.abs_chg = abs_chg
        self.secs = secs
        self.mph = mph
        self.x = x
        self.biggest_area = biggest_area
        self.direction = direction
    
    def toJson(self)->str:
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)   

class DetectionResult(object):
    def __init__(self,cap_time: datetime.datetime, mean_speed: float,direction: DetectionDirection,sd: float,tracking_data: List[TrackingData]):
        # need this to get it to serialize to json
        self.posix_time = time.mktime(cap_time.timetuple())
        self.mean_speed = mean_speed
        self.direction = direction
        self.sd = sd
        self.tracking_data=tracking_data
    
    def toJson(self)->str:
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)    
    
    def getCaptureTime(self)->datetime.datetime:
        return datetime.datetime.fromtimestamp(self.posix_time)

class ObjectDetector(object):
    
    BLURSIZE = (15,15)
    THRESHOLD = 25
    MIN_SAVE_BUFFER = 2

    def __init__(self)->None:
        self._base_image = []
        self._lightlevel=0
        self._last_lightlevel=0
        self._adjusted_min_area=0
        self._adjusted_threshold=0
        self._adjusted_savebuffer=0
        
    
    def update_base_image(self,image)->None:
        # convert the frame to grayscale, and blur it
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, ObjectDetector.BLURSIZE, 0)
    
        # if the base image has not been defined, initialize it
        self._base_image = gray.copy().astype("float")    

    def update_lightlevel(self,image)->None:
        def get_save_buffer(light: float):
            save_buffer = int((100/(light - 0.5)) + ObjectDetector.MIN_SAVE_BUFFER)    
            print(" save buffer " + str(save_buffer))
            return save_buffer
        
        def get_threshold(light: float)->int:
            #Threshold for dark needs to be high so only pick up lights on vehicle
            if (light <= 1):
                threshold = 130
            elif(light <= 2):
                threshold = 100
            elif(light <= 3):
                threshold = 60
            else:
                threshold = ObjectDetector.THRESHOLD
            print("threshold= " + str(threshold))
            return threshold
        
        def get_min_area(light: float)->int:
            if (light > 10):
                light = 10;
            area =int((1000 * math.sqrt(light - 1)) + 100)
            print("min area= " + str(area)) 
            return area
        
        def measure_light(hsvImg)->int:
            #Determine luminance level of monitored area 
            #returns the median from the histogram which contains 0 - 255 levels
            hist = cv2.calcHist([hsvImg], [2], None, [256],[0,255])
            windowsize = (hsvImg.size)/3   #There are 3 pixels per HSV value 
            count = 0
            sum = 0
            print (windowsize)
            for value in hist:
                sum = sum + value
                count +=1    
                if (sum > windowsize/2):   #test for median
                    break
            return count 

        def my_map(x: int, in_min:int , in_max: int, out_min: int, out_max: int)->int:
            return int((x-in_min) * (out_max-out_min) / (in_max-in_min) + out_min)
        
        # capture colour for later when measuring light levels
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        #Set threshold and min area and save_buffer based on light readings
        self._last_lightlevel = self._lightlevel
        self._lightlevel = my_map(measure_light(hsv),0,256,1,10)
        print("light level = " + str(self._lightlevel))
        self._adjusted_min_area = get_min_area(self._lightlevel)
        self._adjusted_threshold = get_threshold(self._lightlevel)
        self._adjusted_save_buffer = get_save_buffer(self._lightlevel)
        if ( self._last_lightlevel!=self._lightlevel):
            self.update_base_image(image)

    def detectObject(self,image)->Tuple[bool,Tuple[int,int,int,int]]:                 
        # convert the frame to grayscale, and blur it
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, ObjectDetector.BLURSIZE, 0)
    
        # if the base image has not been defined, initialize it
        if self._base_image is None:
            self._base_image = gray.copy().astype("float")    

        if self._lightlevel == 0:   #First pass through only
            self.update_lightlevel(image)

        # compute the absolute difference between the current image and
        # base image and then turn eveything lighter gray than THRESHOLD into
        # white
        frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(self._base_image))
        thresh = cv2.threshold(frameDelta, self._adjusted_threshold, 255, cv2.THRESH_BINARY)[1]
        
        # dilate the thresholded image to fill in any holes, then find contours
        # on thresholded image
        thresh = cv2.dilate(thresh, None, iterations=2)
        (cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

        # look for bounding rect of object
        found_object:bool=False
        biggest_area:int = 0
        rect: Tuple[int,int,int,int] = (0,0,0,0)
        # examine the contours, looking for the largest one
        for c in cnts:
            rect = cv2.boundingRect(c)
            (x, y, w, h) = rect
            # get an approximate area of the contour
            found_area = w*h
            # find the largest bounding rectangle
            if (found_area > self._adjusted_min_area) and (found_area > biggest_area):  
                biggest_area = found_area
                found_object = True
        #
        if found_object:
            cv2.accumulateWeighted(gray, self._base_image, 0.25)
        #            
        return (found_object,rect)


class CarSpeedCamera(object):
    def __init__(self,h_flip: bool,v_flip: bool):
        # same aspect ratio as sensor but heavily reduced for speed of processing
        self.image_width=640
        self.image_height=380
        self.h_flip = h_flip
        self.v_flip = v_flip
        self.picam = Picamera2()
        # sensor_mode[1] is the full-frame fast frame rate camera of the pi camera 3
        self.config = self.picam.create_preview_configuration(main={"size": (self.image_width, self.image_height),"format": "RGB888"},
                                                              transform = Transform(hflip=self.h_flip,vflip=self.v_flip),
                                                              queue=False,
                                                              raw=self.picam.sensor_modes[1])
        #
        self.picam.configure(self.config)

    def start(self):
        self.picam.start()

    def update_h_flip(self, h_flip):
        self.h_flip = self.config['transform'].hflip = h_flip
        self.picam.stop()
        self.picam.configure(self.config)
        self.picam.start()

    def update_v_flip(self, v_flip):
        self.v_flip = self.config['transform'].vflip = v_flip
        self.picam.stop()
        self.picam.configure(self.config)
        self.picam.start()
        
class ObjectTracking(object):

    TOO_CLOSE=0.4

    def __init__(self,config: CarSpeedConfig,image_width: int,object_detector: ObjectDetector,moving_object_detected: Callable[[DetectionResult],None])->None:
        #
        self.state = DetectionState.WAITING
        self.direction=DetectionDirection.UNKNOWN
        self.raw_tracking_data=[]
        self.speeds:List[float]=list()
        self.sd=0
        self._object_detector = object_detector
        self._initial_x=0
        self._initial_w=0
        self._initial_time:datetime.datetime
        self._cap_time:datetime.datetime
        self._last_x=0
        self._counter=0
        self._moving_object_detected=moving_object_detected
        ma = config.monitor_area
        self._monitored_width = ma.lower_right_x - ma.upper_left_x

        fov = config.field_of_view
        l2r_distance = config.l2r_distance
        r2l_distance = config.l2r_distance
        l2r_frame_width_ft = 2*(math.tan(math.radians(fov*0.5))*l2r_distance)
        r2l_frame_width_ft = 2*(math.tan(math.radians(fov*0.5))*r2l_distance)
        self._l2r_ftperpixel = l2r_frame_width_ft / float(image_width)
        self._r2l_ftperpixel = r2l_frame_width_ft / float(image_width)

    # calculate elapsed seconds
    @staticmethod
    def secs_diff(endTime: datetime.datetime, begTime:datetime.datetime)->float:
        diff = (endTime - begTime).total_seconds()
        return diff
    
    # calculate speed from pixels and time
    @staticmethod
    def get_speed(pixels, ftperpixel, secs)->float:
        if secs > 0.0:
            return ((pixels * ftperpixel)/ secs) * 0.681818    # Magic number to convert fps to mph
        else:
            return 0.0
        
    def start_tracking(self, rect:Tuple[int,int,int,int], frame_timestamp: datetime.datetime)->None:
        # intialize tracking
        (x,y,w,h) = rect
        self.state = DetectionState.TRACKING
        self.raw_tracking_data=[]
        self._initial_x = x
        self._last_x = x
        self._counter = 0
        #if initial capture straddles start line then the
        # front of vehicle is at position w when clock started
        self._initial_w = w
        self._initial_time = frame_timestamp

        #Initialise array for storing speeds
        self.speeds = np.array([])
        self.sd=0  #Initialise standard deviation
        
        text_on_image = 'Tracking'
        self._counter = 0   # use to test later if saving with too few data points    
        car_gap = ObjectTracking.secs_diff(self._initial_time, self._cap_time) 
        print("initial time = "+str(self._initial_time) + " " + "cap_time =" + str(self._cap_time) + " gap= " +\
            str(car_gap) + " initial x= " + str(self._initial_x) + " initial_w= " + str(self._initial_w))
        print(text_on_image)
        print("x-chg    Secs      MPH  x-pos width     BA  DIR Count time")
        # if gap between cars too low then probably seeing tail lights of current car
        #but I might need to tweek this if find I'm not catching fast cars
        if (car_gap<ObjectTracking.TOO_CLOSE):   
            self.state = DetectionState.WAITING
            print("too close")

    def update_tracking(self,rect:Tuple[int,int,int,int],frame_timestamp:datetime.datetime)->None:
        # compute the elapsed time
        secs = ObjectTracking.secs_diff(frame_timestamp,self._initial_time)
        if secs >= 3: # Object taking too long to move across
            self.reset_tracking()
            return
        
        (x,y,w,h) = rect
        area=w*h

        if x >= self._last_x:
            direction = DetectionDirection.LEFT_TO_RIGHT
            abs_chg = (x + w) - (self._initial_x + self._initial_w)
            mph = ObjectTracking.get_speed(abs_chg,self._l2r_ftperpixel,secs)
        else:
            direction = DetectionDirection.RIGHT_TO_LEFT
            abs_chg = self._initial_x - x     
            mph = ObjectTracking.get_speed(abs_chg,self._r2l_ftperpixel,secs)           

        self._counter+=1   #Increment counter

        self.speeds = np.append(self.speeds, mph)   #Append speed to array

        if mph < 0:
            print("negative speed - stopping tracking"+ "{0:7.2f}".format(secs))
            if direction == DetectionDirection.LEFT_TO_RIGHT:
                direction = DetectionDirection.RIGHT_TO_LEFT  #Reset correct direction
                x=1  #Force save
            else:
                direction = DetectionDirection.LEFT_TO_RIGHT  #Reset correct direction
                x=self._monitored_width + ObjectDetector.MIN_SAVE_BUFFER  #Force save
        else:
            print(f"{abs_chg:4d}  {secs:7.2f}  {mph:7.0f}   {x:4d}  {w:4d} {area:6d} {int(direction):4d} {self._counter:5d} {frame_timestamp:%H:%M:%S.%f}")
            self.raw_tracking_data.append(TrackingData(abs_chg=abs_chg,secs=secs,mph=mph,x=x,biggest_area=area,direction=direction))
        
        # is front of object close to the exit of the monitored boundary? Then write date, time and speed on image
        # and save it 
        if ((x <= self._object_detector._adjusted_save_buffer) and (direction == DetectionDirection.RIGHT_TO_LEFT)) \
                or ((x+w >= self._monitored_width - self._object_detector._adjusted_save_buffer) \
                and (direction == DetectionDirection.LEFT_TO_RIGHT)):
            self.finish_tracking(frame_timestamp)

        else:
            # if the object hasn't reached the end of the monitored area, just 
            self._last_x = x

    def finish_tracking(self, frame_timestamp:datetime.datetime)->None:
        #Last frame has skipped the buffer zone    
        if (self._counter > 2): 
            mean_speed = np.mean(self.speeds[:-1])   #Mean of all items except the last one
            sd = np.std(self.speeds[:-1])  #SD of all items except the last one
            print("missed but saving")
        elif (self._counter > 1):
            mean_speed = self.speeds[-1] # use the last element in the array
            sd = 99 # Set it to a very high value to highlight it's not to be trusted.
            print("missed but saving")
        else:
            mean_speed = 0 #ignore it 
            sd = 0
                
        cap_time = frame_timestamp
        data = DetectionResult(cap_time = cap_time, mean_speed = mean_speed, direction = self.direction, sd = sd, tracking_data=self.raw_tracking_data)
        # run callback
        self._moving_object_detected(data)
        #
        self.reset_tracking()

    def reset_tracking(self):
        self.state = DetectionState.WAITING
        self.direction = DetectionDirection.UNKNOWN        
        print('Resetting tracking')


    def update_state(self,object_detection: Tuple[bool,Tuple[int,int,int,int]],frame_timestamp: datetime.datetime):
        (object_found,object_rect) = object_detection
        if object_found:
            if self.state==DetectionState.WAITING:
                self.start_tracking(object_rect,frame_timestamp)
            elif self.state == DetectionState.TRACKING:
                self.update_tracking(object_rect,frame_timestamp)
            else:
                raise ValueError(f"Unexpected tracking state [{self.state}] found")
        else:
            if self.state==DetectionState.TRACKING:
                self.finish_tracking(frame_timestamp)
                self.reset_tracking()
            elif self.state==DetectionState.WAITING:
                pass
            else:
                raise ValueError(f"Unexpected tracking state [{self.state}] found")
    
class CarSpeedMonitor(object):
    
    def __init__(self, config: CarSpeedConfig) -> None:
        self.config = config
    
    def start(self, detection_hook, show_preview=False):
                
        def store_image(result: DetectionResult):
            # timestamp the image - 
            cap_time = result.getCaptureTime()
            mean_speed = result.mean_speed
            # add text to image
            cv2.putText(image, cap_time.strftime("%A %d %B %Y %I:%M:%S%p"),
            (10, image.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 1)
            # write the speed: first get the size of the text
            size, base = cv2.getTextSize( "%.0f mph" % mean_speed, cv2.FONT_HERSHEY_SIMPLEX, 2, 3)
            # then center it horizontally on the image
            cntr_x = int((image_width - size[0]) / 2) 
            cv2.putText(image, "%.0f mph" % mean_speed,
            (cntr_x , int(image_height * 0.2)), cv2.FONT_HERSHEY_SIMPLEX, 2.00, (0, 255, 0), 3)

            # and save the image to disk
            folder = f'images/{cap_time.year:04}-{cap_time.month:02}-{cap_time.day:02}'
            folderPath = Path(folder)
            if not folderPath.is_dir():
                os.makedirs(folder)                
            imageFilename = folder + "/car_at_" + cap_time.strftime("%Y-%m-%d_%H-%M-%S") + ".jpg"
            jsonFilename=folder + "/car_at_" + cap_time.strftime("%Y-%m-%d_%H-%M-%S") + ".json"

            cv2.imwrite(imageFilename,image)
            # write out json to config file
            with open(jsonFilename, 'w') as f:
                f.write(result.toJson())

        def moving_object_detected(result: DetectionResult):
            if (result.mean_speed > min_speed_save and result.mean_speed < max_speed_save):    
                store_image(result)
                if detection_hook:
                    detection_hook(result)
                # print json version to std out
                print(f'CAR_DETECTED: ({result.mean_speed:.1f} mph) (sd={result.sd:.2f})')
            else:
                print(f"Ignoring detection - speed [{result.mean_speed:.2f}] out of range [{min_speed_save}-{max_speed_save}]")

            

        def annotate_image(object_detection: Tuple[bool,Tuple[int,int,int,int]]): 
            
            # draw the timestamp and tracking state
            cv2.putText(image, frame_timestamp.strftime("%A %d %B %Y %I:%M:%S%p"),
                (10, image.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 1)
            cv2.putText(image, f"Tracking state: {object_tracking.state}", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX,0.35, (0, 0, 255), 1)
        
            # draw monitored area
            green = (0, 255, 0)
            cv2.rectangle(image,(upper_left_x,upper_left_y),(lower_right_x,lower_right_y),green)
            # add last found object
            (object_found, object_rect) = object_detection
            if object_found:
                red = (255, 0, 0)
                (x1,y1,w,h)=object_rect
                x2=x1+w
                y2=y1+h
                cv2.rectangle(image,(x1,y1),(x2,y2),red)

        def process_image():

            object_detection = object_detector.detectObject(image)
            object_tracking.update_state(object_detection,frame_timestamp)                    
            annotate_image(object_detection)
            # show the frame
            if show_preview:
                cv2.imshow("Speed Camera", image)                

        # store local variables from config
        ma = self.config.monitor_area
        upper_left_x = ma.upper_left_x
        upper_left_y = ma.upper_left_y
        lower_right_x = ma.lower_right_x
        lower_right_y = ma.lower_right_y
        min_speed_save = self.config.min_speed_image
        max_speed_save = self.config.max_speed_save

        # initialize the camera. Adjust vflip and hflip to reflect your camera's orientation
        # allow the camera to warm up
        camera = CarSpeedCamera(self.config.h_flip,self.config.v_flip)
        image_width = camera.image_width
        image_height = camera.image_height
        camera.start()
        time.sleep(0.9)

        # create an image window and place it in the upper left corner of the screen
        cv2.namedWindow("Speed Camera")
        cv2.moveWindow("Speed Camera", 10, 40)
                    
        # this gets called after frame captured but before call capture_array
        frame_timestamp = datetime.datetime.now()
        def pre_capture_callback(request):
            nonlocal frame_timestamp
            frame_timestamp = datetime.datetime.now()
        
        camera.picam.pre_callback = pre_capture_callback
        object_detector = ObjectDetector()
        object_tracking = ObjectTracking(self.config,camera.image_width,object_detector,moving_object_detected)
        #
        while True:
            st = time.time()
            # grab the raw NumPy array representing the image 
            image = camera.picam.capture_array('main')
            lap1=time.time()
            # crop area defined by [y1:y2,x1:x2]
            cropped_image = image[upper_left_y:lower_right_y,upper_left_x:lower_right_x]
            process_image()
            lap2=time.time()
            if object_tracking.state == DetectionState.WAITING:
                key = cv2.waitKey(1) & 0xFF
                # if the `q` key is pressed, break from the loop and terminate processing
                if key == ord("q"):
                    break; 
            #
            ft = time.time()
            #print(f'Loop capture_array=[{lap1-st:.3f}] process_image=[{lap2-lap1:.3f}] [{ft-lap2:.3f}]')
            #time.sleep(0.5)
        
        # cleanup the camera and close any open windows
        cv2.destroyAllWindows()



    

    