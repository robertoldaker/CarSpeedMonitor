from typing import Callable, List, Tuple, Union

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
try:
    from pynput import keyboard
    keyboard_avalable = True
except:
    keyboard_avalable = False
    print("keyboard ignored")


# Current detection state
class DetectionState(IntEnum):
    WAITING=0
    TRACKING=1
    SAVING=2

class Commands(IntEnum):
    CONTINUE=0
    EXIT=1
    TOGGLE_DETECTION=2
    RESET_TRACKING=3

# Current detection direction
class DetectionDirection(IntEnum):
    UNKNOWN = 0
    LEFT_TO_RIGHT = 1
    RIGHT_TO_LEFT = 2

class Logger:
    def __init__(self,logger_hook) -> None:
        self.logger_hook = logger_hook
    
    def logMessage(self,mess:str):
        if self.logger_hook!=None:
            self.logger_hook(mess)
        else:
            print(mess)

class TrackingData(object):
    def __init__(self,abs_chg: int,secs: float,mph: float,x: int,width: int,image):
        self.abs_chg = abs_chg
        self.secs = secs
        self.mph = mph
        self.x = x
        self.width = width
        self.image=image.copy()

    @staticmethod    
    def _jsonDict(o: object)->dict:
        d = dict(o.__dict__)
        # remove fields not for serialization
        del d['image']
        return d

    def toJson(self)->str:
        return json.dumps(self, default=TrackingData._jsonDict, indent=4)  


class DetectionResult(object):
    def __init__(self,cap_time: datetime.datetime, mean_speed: float,direction: DetectionDirection,sd: float,inExitZone: bool, tracking_data: List[TrackingData]):
        # need this to get it to serialize to json
        self.posix_time = time.mktime(cap_time.timetuple())
        self.mean_speed = mean_speed
        self.direction = direction
        self.sd = sd
        self.inExitZone=inExitZone
        self.tracking_data=tracking_data
        self.image=None
        self.configId=0
    
    @staticmethod    
    def _jsonDict(o: object)->dict:
        d = dict(o.__dict__)
        # remove fields not for serialization
        del d['image']
        return d

    def toJson(self)->str:
        return json.dumps(self, default=DetectionResult._jsonDict, indent=4)  

    
    def getCaptureTime(self)->datetime.datetime:
        return datetime.datetime.fromtimestamp(self.posix_time)

class ObjectDetector(object):
    
    BLURSIZE = (15,15)
    THRESHOLD = 25
    MIN_SAVE_BUFFER = 2

    def __init__(self, logger:Logger, min_area:int)->None:
        self.rect=(0,0,0,0)
        self.ncontours=0
        self._base_image = None
        self._lightlevel=-1
        self._last_lightlevel=0
        self._adjusted_min_area=min_area
        self._adjusted_threshold=0
        self._adjusted_save_buffer=0
        self._lightlevel_time:Union[None,datetime.datetime]=None
        self._first_pass=True
        self.logger=logger
            
    def update_base_image(self,gray)->None:
        # if the base image has not been defined, initialize it
        self._base_image = gray.copy().astype("float")    

    def update_lightlevel(self,image,gray)->None:
        def get_save_buffer(light: float):
            save_buffer = int((100/(light - 0.5)) + ObjectDetector.MIN_SAVE_BUFFER)    
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
            return threshold
        
        def get_min_area(light: float)->int:
            if (light > 10):
                light = 10;
            area =int((1000 * math.sqrt(light - 1)) + 100)
            #return area
            return 10000
        
        def measure_light(hsvImg)->int:
            #Determine luminance level of monitored area 
            #returns the median from the histogram which contains 0 - 255 levels
            hist = cv2.calcHist([hsvImg], [2], None, [256],[0,255])
            windowsize = (hsvImg.size)/3   #There are 3 pixels per HSV value 
            count = 0
            sum = 0
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
        ### now fixed
        #self._adjusted_min_area = get_min_area(self._lightlevel)
        self._adjusted_threshold = get_threshold(self._lightlevel)
        self._adjusted_save_buffer = get_save_buffer(self._lightlevel)
        print(f"LIGHT_LEVEL_UPDATE: (level={self._lightlevel}) (min_area={self._adjusted_min_area}) (threshold={self._adjusted_threshold}) (save_buffer={self._adjusted_save_buffer}))")
        self._lightlevel_time=datetime.datetime.now()
        ###if ( self._last_lightlevel!=self._lightlevel):
        ###    self.update_base_image(gray)
        ### since I can;t get accumulateWeithed to work always refresh the base_image when the lightlevel taken
        self.update_base_image(gray)

    def reset(self):
        self._first_pass=True
    
    def needs_lightlevel_update(self)->bool:
        return not self._lightlevel_time is None and (datetime.datetime.now()-self._lightlevel_time).total_seconds() > 60

    def detectObject(self,image)->bool:
        # convert the frame to grayscale, and blur it
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, ObjectDetector.BLURSIZE, 0)
    
        # if the base image has not been defined, initialize it
        #if self._base_image is None:
        #    self.update_base_image(image)

        if self._first_pass:  #First pass through only get light level and define base_image
            self.update_lightlevel(image,gray)
            self._first_pass = False

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
        self.rect: Tuple[int,int,int,int] = (0,0,0,0)
        self.ncontours = len(cnts)
        # examine the contours, looking for the largest one
        for c in cnts:
            (x, y, w, h) = cv2.boundingRect(c)
            # get an approximate area of the contour
            found_area = w*h
            # find the largest bounding rectangle
            if (found_area > self._adjusted_min_area) and (found_area > biggest_area):  
                biggest_area = found_area
                found_object = True
                self.rect = (x,y, w, h)
        #
        if not found_object:
            ### can't get this to work so commented out
            ### and re-do base_image when lightlevel taken
            ###cv2.accumulateWeighted(gray, self._base_image, 0.25)
            # update light level every 60secs assuming no car detected
            if self.needs_lightlevel_update():
                self.update_lightlevel(image,gray)                

        #            
        return found_object


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
    
    def set_flip(self,h_flip: bool, v_flip: bool):
        self.h_flip = self.config['transform'].hflip = h_flip
        self.v_flip = self.config['transform'].vflip = v_flip
        self.picam.configure(self.config)

    def stop(self):
        self.picam.stop()
        
class ObjectTracking(object):

    TOO_CLOSE=0.4
    DETECTION_STATE_TEXT={ DetectionState.WAITING: 'WAITING', DetectionState.TRACKING: 'TRACKING', DetectionState.SAVING: 'SAVING'}
    def __init__(self,logger: Logger, config: CarSpeedConfig,image_width: int,object_detector: ObjectDetector,moving_object_detected: Callable[[DetectionResult],None])->None:
        #
        self.state = DetectionState.WAITING
        self.direction = DetectionDirection.UNKNOWN
        self.raw_tracking_data=[]
        self.speeds:List[float]=list()
        self.sd=0
        self._object_detector = object_detector
        self._initial_x=0
        self._initial_w=0
        self._initial_time:datetime.datetime
        self._cap_time:Union[datetime.datetime,None] = None
        self._last_x=0
        self._counter=0
        self._moving_object_detected=moving_object_detected
        ma = config.monitor_area
        self._monitored_width = ma.lower_right_x - ma.upper_left_x
        # work out ft per pixel in both directions
        self._l2r_ftperpixel = config.getL2RFrameWidthFt() / float(image_width)
        self._r2l_ftperpixel = config.getL2RFrameWidthFt() / float(image_width)
        #
        self.logger = logger

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
        
        self._counter = 0   # use to test later if saving with too few data points    
        self.logger.logMessage("x-chg    Secs      MPH  x-pos width     BA  DIR Count")
        if not self._cap_time == None:
            car_gap = ObjectTracking.secs_diff(self._initial_time, self._cap_time) 
            self.logger.logMessage("initial time = "+str(self._initial_time) + " " + "cap_time =" + str(self._cap_time) + " gap= " +\
                str(car_gap) + " initial x= " + str(self._initial_x) + " initial_w= " + str(self._initial_w))
            # if gap between cars too low then probably seeing tail lights of current car
            #but I might need to tweek this if find I'm not catching fast cars
            if (car_gap<ObjectTracking.TOO_CLOSE):   
                self.state = DetectionState.WAITING
                self.logger.logMessage("too close")
    
    def check_tracking(self,frame_timestamp:datetime.datetime):
        # compute the elapsed time
        secs = ObjectTracking.secs_diff(frame_timestamp,self._initial_time)
        if secs >= 10: # Object taking too long to move across
            self.reset()
            return False
        return True
    
    def reset(self):
        self.reset_tracking(False)
        # this forces a light level re-calc and base image refresh
        self._object_detector.reset()      
        self.logger.logMessage('Resetting tracking and detector')
        return False


    def update_tracking(self,rect:Tuple[int,int,int,int],image,frame_timestamp:datetime.datetime)->None:
        
        secs = ObjectTracking.secs_diff(frame_timestamp,self._initial_time)
        (x,y,w,h) = rect
        area=w*h

        if x >= self._last_x:
            self.direction = DetectionDirection.LEFT_TO_RIGHT
            abs_chg = (x + w) - (self._initial_x + self._initial_w)
            mph = ObjectTracking.get_speed(abs_chg,self._l2r_ftperpixel,secs)
        else:
            self.direction = DetectionDirection.RIGHT_TO_LEFT
            abs_chg = self._initial_x - x     
            mph = ObjectTracking.get_speed(abs_chg,self._r2l_ftperpixel,secs)           

        self._counter+=1   #Increment counter

        self.speeds = np.append(self.speeds, mph)   #Append speed to array

        if mph < 0:
            self.logger.logMessage("negative speed - stopping tracking"+ "{0:7.2f}".format(secs))
            if self.direction == DetectionDirection.LEFT_TO_RIGHT:
                self.direction = DetectionDirection.RIGHT_TO_LEFT  #Reset correct direction
                x=1  #Force save
            else:
                self.direction = DetectionDirection.LEFT_TO_RIGHT  #Reset correct direction
                x=self._monitored_width + ObjectDetector.MIN_SAVE_BUFFER  #Force save
        else:
            self.logger.logMessage(f"{abs_chg:4d}  {secs:7.2f}  {mph:7.0f}   {x:4d}  {w:4d} {area:6d} {int(self.direction):4d} {self._counter:5d}")
            self.raw_tracking_data.append(TrackingData(abs_chg=abs_chg,secs=secs,mph=mph,x=x,width=w,image=image))
        
        # is front of object close to the exit of the monitored boundary? Then write date, time and speed on image
        # and save it 
        if ((x <= self._object_detector._adjusted_save_buffer) and (self.direction == DetectionDirection.RIGHT_TO_LEFT)) \
                or ((x+w >= self._monitored_width - self._object_detector._adjusted_save_buffer) \
                and (self.direction == DetectionDirection.LEFT_TO_RIGHT)):
            self.finish_tracking(frame_timestamp, True)
        else:
            # if the object hasn't reached the end of the monitored area, just store last_x 
            self._last_x = x

    def finish_tracking(self, frame_timestamp:datetime.datetime, inExitZone: bool,)->None:
        #Last frame has skipped the buffer zone    
        if (self._counter > 2): 
            mean_speed = np.mean(self.speeds[:-1])   #Mean of all items except the last one
            sd = np.std(self.speeds[:-1])  #SD of all items except the last one
        elif (self._counter > 1):
            mean_speed = self.speeds[-1] # use the last element in the array
            sd = 99 # Set it to a very high value to highlight it's not to be trusted.
        else:
            mean_speed = 0 #ignore it 
            sd = 0
                
        cap_time = frame_timestamp
        result = DetectionResult(cap_time = cap_time, mean_speed = mean_speed, direction = self.direction, sd = sd, inExitZone=inExitZone, tracking_data=self.raw_tracking_data)
        # run callback
        self._moving_object_detected(result)
        #
        self.reset_tracking(inExitZone)

    def reset_tracking(self, inExitZone):
        # SAVING is used to wait until we get to state WAITING
        self.state = DetectionState.SAVING if inExitZone else DetectionState.WAITING
        self._last_x=0


    def update_state(self,found_object: bool, object_rect: Tuple[int,int,int,int],image,frame_timestamp: datetime.datetime):
        if found_object:
            if self.state==DetectionState.WAITING:
                # start off tracking
                self.start_tracking(object_rect,frame_timestamp)
            elif self.state == DetectionState.TRACKING:
                # update tracking state
                if self.check_tracking(frame_timestamp):
                    self.update_tracking(object_rect,image,frame_timestamp)
            elif self.state == DetectionState.SAVING:
                # ensure we haven;t timedout waiting for a no detection
                self.check_tracking(frame_timestamp)
            else:
                raise ValueError(f"Unexpected tracking state [{self.state}] found")
        else:
            if self.state==DetectionState.TRACKING:
                # stop tracking since no vehicle is now detected
                self.finish_tracking(frame_timestamp,False)
            elif self.state==DetectionState.SAVING:
                # means vehicle has passed out of view so reset back to waiting
                self.reset_tracking(False)
            elif self.state==DetectionState.WAITING:
                # just wait!
                pass
            else:
                raise ValueError(f"Unexpected tracking state [{self.state}] found")
    
    def getStateStr(self):
        return ObjectTracking.DETECTION_STATE_TEXT[self.state]
    
class CarSpeedMonitorState:
    def __init__(self,image,state:str, frameRate:float, detectionEnabled: bool, avgContours: int, lightLevel: float) -> None:
        self.image=image.copy()
        self.state=state
        self.frameRate=frameRate
        self.detectionEnabled=detectionEnabled
        self.avgContours=avgContours
        self.lightLevel=lightLevel
  
    def generateJpg(self):
        (result,jpg) = cv2.imencode('.jpg', self.image)
        self.jpg = jpg.data
        del(self.image)

class CarSpeedMonitor(object):
    
    WINDOW_NAME="Car Speed Monitor"
    def __init__(self, config: CarSpeedConfig) -> None:
        self.config = config
        self.camera = CarSpeedCamera(self.config.h_flip,self.config.v_flip)
    
    def start(self, detection_hook:Callable, preview_hook=None, logger_hook=None, command_hook=None, show_preview=False):

        def annotate_main_image(result: DetectionResult):
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

        def moving_object_detected(result: DetectionResult):
            if (result.mean_speed > min_speed_save and result.mean_speed < max_speed_save):                
                annotate_main_image(result)
                result.image = image.copy()
                if detection_hook:
                    detection_hook(result)
                # print json version to std out
                logger.logMessage(f'CAR_DETECTED: ({result.mean_speed:.1f} mph) (sd={result.sd:.2f})')
            else:
                logger.logMessage(f"Ignoring detection - speed [{result.mean_speed:.2f}] out of range [{min_speed_save}-{max_speed_save}]")

            

        def annotate_image_for_storage(found_object: bool,object_rect:Tuple[int,int,int,int]): 
            
            # draw the timestamp and tracking state
            cv2.putText(image, frame_timestamp.strftime("%A %d %B %Y %I:%M:%S%p"),
                (10, image.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 1)
            # draw monitored area
            green = (0, 255, 0)
            cv2.rectangle(image,(upper_left_x,upper_left_y),(lower_right_x,lower_right_y),green)
            # add last found object
            if found_object:
                blue = (255, 0, 0)
                (x1,y1,w,h)=object_rect
                x1+=upper_left_x
                y1+=upper_left_y
                x2=x1+w
                y2=y1+h
                cv2.rectangle(image,(x1,y1),(x2,y2),blue)

        def annotate_image_for_preview(): 
            
            # draw the timestamp and tracking state
            cv2.putText(image, f"Tracking state: {object_tracking.getStateStr()}", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX,0.35, (0, 0, 255), 1)
            cv2.putText(image, f"Detection enabled: {detection_enabled}", (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX,0.35, (0, 0, 255), 1)
            cv2.putText(image, f"Frame rate: {frame_rate:3.0f} fps, avg contours: {num_contours:3.0f}", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX,0.35, (0, 0, 255), 1)        
            cv2.putText(image, f"Enter 'q' to quit, 'd' to toggle detection", (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX,0.35, (0, 0, 255), 1)

        def process_image():
            found_object = object_detector.detectObject(cropped_image)
            annotate_image_for_storage(found_object,object_detector.rect)
            if detection_enabled:
                object_tracking.update_state(found_object,object_detector.rect,image,frame_timestamp)
            # show the frame
            if show_preview:
                annotate_image_for_preview()
                cv2.imshow(CarSpeedMonitor.WINDOW_NAME, image)

            run_preview_hook()

        def run_preview_hook():
            if preview_hook!=None:
                stateStr = object_tracking.getStateStr() if cont else "IDLE"
                state=CarSpeedMonitorState(image, stateStr ,frame_rate,detection_enabled,int(num_contours),object_detector._lightlevel)
                preview_hook(state)

        def on_key_press(key):
            nonlocal cont, detection_enabled 
            if hasattr(key,'char'):
                char = key.char
                # quit
                if char == "q":
                    cont = False
                # toggle detection
                if char == "d":
                    detection_enabled = not detection_enabled
                # reset 
                if char == "r":
                    object_tracking.reset()

        #
        logger = Logger(logger_hook)

        # store local variables from config
        ma = self.config.monitor_area
        upper_left_x = ma.upper_left_x
        upper_left_y = ma.upper_left_y
        lower_right_x = ma.lower_right_x
        lower_right_y = ma.lower_right_y
        min_speed_save = self.config.min_speed_save
        max_speed_save = self.config.max_speed_save

        # initialize the camera. Adjust vflip and hflip to reflect your camera's orientation
        # allow the camera to warm up
        image_width = self.camera.image_width
        image_height = self.camera.image_height
        self.camera.start()
        time.sleep(0.9)

        # create an image window and place it in the upper left corner of the screen
        if show_preview:
            cv2.namedWindow(CarSpeedMonitor.WINDOW_NAME)
            cv2.moveWindow(CarSpeedMonitor.WINDOW_NAME, 10, 40)
        
        cont = True
        if keyboard_avalable:
            listener = keyboard.Listener(
                on_press=on_key_press)
            listener.start()

                    
        # this gets called after frame captured but before call capture_array
        frame_timestamp = datetime.datetime.now()
        def pre_capture_callback(request):
            nonlocal frame_timestamp
            frame_timestamp = datetime.datetime.now()
        
        self.camera.picam.pre_callback = pre_capture_callback
        # min width in pixels of a car
        min_width=5/(self.config.getL2RFrameWidthFt())*self.camera.image_width
        min_area=min_width*min_width

        object_detector = ObjectDetector(logger,int(min_area))
        object_tracking = ObjectTracking(logger,self.config,self.camera.image_width,object_detector,moving_object_detected)
        
        frame_rate:float=0
        detection_enabled:bool = True
        frame_count:int=0
        total_contours:int=0
        num_contours:float=0
        st:float = time.monotonic()
        #
        logger.logMessage("Monitor started")
        while cont:
            # grab the raw NumPy array representing the image 
            image = self.camera.picam.capture_array('main')
            # crop area defined by detection areat defined in the config
            cropped_image = image[upper_left_y:lower_right_y,upper_left_x:lower_right_x]
            process_image()

            frame_count+=1
            total_contours+=object_detector.ncontours
            if frame_count % 50 == 0:
                ft = time.monotonic()
                frame_rate=50/(ft-st)
                num_contours=total_contours/50
                total_contours=0
                st=time.monotonic()
                #if not show_preview:
                #    print(f'Frame rate={frame_rate:3.0f}, avg. contours={num_contours:3.0f}      ',end="\r")

            # needed to ensure the images in the preview window get updated
            if show_preview:
                key = cv2.waitKey(1) & 0xFF
            # process commands from the command hook
            if command_hook:
                command = command_hook()
                if command == Commands.EXIT:
                    cont=False
                elif command == Commands.RESET_TRACKING:
                    object_tracking.reset()
                elif command == Commands.TOGGLE_DETECTION:
                    detection_enabled = not detection_enabled

        run_preview_hook()            
        self.camera.stop()
        # cleanup the camera and close any open windows
        cv2.destroyAllWindows()
        logger.logMessage("Monitor stopped")
    
    def setConfig(self, config: CarSpeedConfig):
        self.config = config
        self.camera.set_flip(config.h_flip,config.v_flip)


    