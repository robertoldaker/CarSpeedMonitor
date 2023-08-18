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
from pprint import *

class DetectionResult(object):
    def __init__(self,cap_time,mean_speed,direction,counter,sd,tracking_data):
        # need this to get it to serialize to json
        self.posix_time = time.mktime(cap_time.timetuple())
        self.mean_speed = mean_speed
        self.direction = direction
        self.counter = counter
        self.sd = sd
        self.tracking_data=tracking_data
    
    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)    

class TrackingData(object):
    def __init__(self,abs_chg,secs,mph,x,biggest_area,direction):
        self.abs_chg = abs_chg
        self.secs = secs
        self.mph = mph
        self.x = x
        self.biggest_area = biggest_area
        self.direction = direction
    
    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__, indent=4)    

class CarSpeedCamera(object):
    def __init__(self,h_flip,v_flip):
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
        
class CarSpeedMonitor(object):
    
    def __init__(self, config) -> None:
        if config is None:
            raise Exception(f'Configuration object is None')                    
        elif not isinstance(config,CarSpeedConfig):
            raise Exception(f'First parameter should be of type [{CarSpeedConfig.__class__.__name__}]')        
        self.config = config
    
    def start(self, detection_hook, show_preview=False):

        def my_map(x, in_min, in_max, out_min, out_max):
            return int((x-in_min) * (out_max-out_min) / (in_max-in_min) + out_min)

        def measure_light(hsvImg):
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

        def get_min_area(light):
            if (light > 10):
                light = 10;
            area =int((1000 * math.sqrt(light - 1)) + 100)
            print("min area= " + str(area)) 
            return area

        def get_threshold(light):
            #Threshold for dark needs to be high so only pick up lights on vehicle
            if (light <= 1):
                threshold = 130
            elif(light <= 2):
                threshold = 100
            elif(light <= 3):
                threshold = 60
            else:
                threshold = THRESHOLD
            print("threshold= " + str(threshold))
            return threshold
        
        def get_save_buffer(light):
            save_buffer = int((100/(light - 0.5)) + MIN_SAVE_BUFFER)    
            print(" save buffer " + str(save_buffer))
            return save_buffer
        
        # calculate elapsed seconds
        def secs_diff(endTime, begTime):
            diff = (endTime - begTime).total_seconds()
            return diff
        
        # calculate speed from pixels and time
        def get_speed(pixels, ftperpixel, secs):
            if secs > 0.0:
                return ((pixels * ftperpixel)/ secs) * 0.681818    # Magic number to convert fps to mph
            else:
                return 0.0
        
        def store_image(data):
            # timestamp the image - 
            nonlocal cap_time, image, mean_speed

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
                f.write(data.toJson())

        # place a prompt on the displayed image
        def prompt_on_image(txt):
            nonlocal image
            cv2.putText(image, txt, (10, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        def raise_detection_result(data):

            # raise event if hook set
            if detection_hook:
                detection_hook(data)

            # print json version to std out
            #jsonStr = data.toJson()
            print(f'CAR_DETECTED: ({data.mean_speed:.1f} mph) (sd={data.sd:.2f})')

        def process_image():
            nonlocal base_image, initial_x, initial_w, initial_time, last_x, state, abs_chg, mph, text_on_image, secs, t1, t2
            nonlocal lightlevel, last_lightlevel, adjusted_threshold, adjusted_min_area, adjusted_save_buffer, counter, speeds, cap_time
            nonlocal direction, mean_speed, image, frame_timestamp, raw_tracking_data

            # crop area defined by [y1:y2,x1:x2]
            gray = image[upper_left_y:lower_right_y,upper_left_x:lower_right_x]
            # capture colour for later when measuring light levels
            hsv = cv2.cvtColor(gray, cv2.COLOR_BGR2HSV)
            # convert the frame to grayscale, and blur it
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, BLURSIZE, 0)
        
            # if the base image has not been defined, initialize it
            if base_image is None:
                base_image = gray.copy().astype("float")
                if SHOW_IMAGE:
                    cv2.imshow("Speed Camera", image)
        

            if lightlevel == 0:   #First pass through only
                #Set threshold and min area and save_buffer based on light readings
                lightlevel = my_map(measure_light(hsv),0,256,1,10)
                print("light level = " + str(lightlevel))
                adjusted_min_area = get_min_area(lightlevel)
                adjusted_threshold = get_threshold(lightlevel)
                adjusted_save_buffer = get_save_buffer(lightlevel)
                last_lightlevel = lightlevel

            # compute the absolute difference between the current image and
            # base image and then turn eveything lighter gray than THRESHOLD into
            # white
            frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(base_image))
            thresh = cv2.threshold(frameDelta, adjusted_threshold, 255, cv2.THRESH_BINARY)[1]
            
            # dilate the thresholded image to fill in any holes, then find contours
            # on thresholded image
            thresh = cv2.dilate(thresh, None, iterations=2)
            (cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

            # look for motion 
            motion_found = False
            biggest_area = 0
            # examine the contours, looking for the largest one
            for c in cnts:
                (x1, y1, w1, h1) = cv2.boundingRect(c)
                # get an approximate area of the contour
                found_area = w1*h1 
                # find the largest bounding rectangle
                if (found_area > adjusted_min_area) and (found_area > biggest_area):  
                    biggest_area = found_area
                    motion_found = True
                    x = x1
                    y = y1
                    w = w1
                    #record the timestamp at the point in code where motion found
                    #timestamp = datetime.datetime.now()
                    timestamp = frame_timestamp

            if motion_found:
                if state == DetectionState.WAITING:
                    # intialize tracking
                    state = DetectionState.TRACKING
                    raw_tracking_data=[]
                    initial_x = x
                    last_x = x
                    #if initial capture straddles start line then the
                    # front of vehicle is at position w when clock started
                    initial_w = w
                    initial_time = timestamp
                
                    #Initialise array for storing speeds
                    speeds = np.array([])
                    sd=0  #Initialise standard deviation
                    
                    text_on_image = 'Tracking'
                    counter = 0   # use to test later if saving with too few data points    
                    car_gap = secs_diff(initial_time, cap_time) 
                    print("initial time = "+str(initial_time) + " " + "cap_time =" + str(cap_time) + " gap= " +\
                        str(car_gap) + " initial x= " + str(initial_x) + " initial_w= " + str(initial_w))
                    print(text_on_image)
                    print("x-chg    Secs      MPH  x-pos width     BA  DIR Count time")
                    # if gap between cars too low then probably seeing tail lights of current car
                    #but I might need to tweek this if find I'm not catching fast cars
                    if (car_gap<TOO_CLOSE):   
                        state = DetectionState.WAITING
                        print("too close")
                else:  #state != WAITING
                    # compute the lapsed time
                    secs = secs_diff(timestamp,initial_time)
                    if secs >= 3: # Object taking too long to move across
                        state = DetectionState.WAITING
                        direction = DetectionDirection.UNKNOWN
                        text_on_image = 'No Car Detected'
                        motion_found = False
                        biggest_area = 0
                        base_image = None
                        print('Resetting')
                        return           

                    if state == DetectionState.TRACKING:       
                        if x >= last_x:
                            direction = DetectionDirection.LEFT_TO_RIGHT
                            abs_chg = (x + w) - (initial_x + initial_w)
                            mph = get_speed(abs_chg,l2r_ftperpixel,secs)
                        else:
                            direction = DetectionDirection.RIGHT_TO_LEFT
                            abs_chg = initial_x - x     
                            mph = get_speed(abs_chg,r2l_ftperpixel,secs)           

                        counter+=1   #Increment counter

                        speeds = np.append(speeds, mph)   #Append speed to array

                        if mph < 0:
                            print("negative speed - stopping tracking"+ "{0:7.2f}".format(secs))
                            if direction == DetectionDirection.LEFT_TO_RIGHT:
                                direction = DetectionDirection.RIGHT_TO_LEFT  #Reset correct direction
                                x=1  #Force save
                            else:
                                direction = DetectionDirection.LEFT_TO_RIGHT  #Reset correct direction
                                x=monitored_width + MIN_SAVE_BUFFER  #Force save
                        else:
                            print(f"{abs_chg:4d}  {secs:7.2f}  {mph:7.0f}   {x:4d}  {w:4d} {biggest_area:6d} {int(direction):4d} {counter:5d} {timestamp:%H:%M:%S.%f}")
                            raw_tracking_data.append(TrackingData(abs_chg=abs_chg,secs=secs,mph=mph,x=x,biggest_area=biggest_area,direction=direction))
                        
                        # is front of object outside the monitired boundary? Then write date, time and speed on image
                        # and save it 
                        if ((x <= adjusted_save_buffer) and (direction == DetectionDirection.RIGHT_TO_LEFT)) \
                                or ((x+w >= monitored_width - adjusted_save_buffer) \
                                and (direction == DetectionDirection.LEFT_TO_RIGHT)):
                            
                            #you need at least 2 data points to calculate a mean and we're deleting one on line below
                            if (counter > 2): 
                                mean_speed = np.mean(speeds[:-1])   #Mean of all items except the last one
                                sd = np.std(speeds[:-1])  #SD of all items except the last one
                            elif (counter > 1):
                                mean_speed = speeds[-1] # use the last element in the array
                                sd = 99 # Set it to a very high value to highlight it's not to be trusted.
                            else:
                                mean_speed = 0 #ignore it 
                                sd = 0
                            
                            #cap_time = datetime.datetime.now()   
                            cap_time = frame_timestamp

                            # save the image but only if there is light and above the min speed for images 
                            data = DetectionResult(cap_time = cap_time, mean_speed = mean_speed, direction = direction, counter = counter, sd = sd, tracking_data=raw_tracking_data)
                            if (mean_speed > min_speed_image) and (lightlevel > 1) :    
                                store_image(data)
                            
                            # save the data if required and above min speed for data
                            if mean_speed > min_speed_save and mean_speed < max_speed_save:
                                raise_detection_result(data)
                            
                            counter = 0
                            state = DetectionState.SAVING
                        # if the object hasn't reached the end of the monitored area, just remember the speed 
                        # and its last position
                        last_mph = mph
                        last_x = x
            else:
                # No motion detected
                if state == DetectionState.TRACKING:
                    #Last frame has skipped the buffer zone    
                    if (counter > 2): 
                        mean_speed = np.mean(speeds[:-1])   #Mean of all items except the last one
                        sd = np.std(speeds[:-1])  #SD of all items except the last one
                        print("missed but saving")
                    elif (counter > 1):
                        mean_speed = speeds[-1] # use the last element in the array
                        sd = 99 # Set it to a very high value to highlight it's not to be trusted.
                        print("missed but saving")
                    else:
                        mean_speed = 0 #ignore it 
                        sd = 0
                            
                    #cap_time = datetime.datetime.now()
                    cap_time = frame_timestamp

                    data = DetectionResult(cap_time = cap_time, mean_speed = mean_speed, direction = direction, counter = counter, sd = sd, tracking_data=raw_tracking_data)
                    if (mean_speed > min_speed_image) and (lightlevel > 1) :    
                        store_image(data)
                    if mean_speed > min_speed_save:
                        raise_detection_result(data)

                if state != DetectionState.WAITING:
                    state = DetectionState.WAITING
                    direction = DetectionDirection.UNKNOWN
                    text_on_image = 'Waiting'
                    counter = 0
                    print(text_on_image)
                    
            # only update image and wait for a keypress when waiting for a car
            # This is required since waitkey slows processing.
            if (state == DetectionState.WAITING):    
        
                # draw the text and timestamp on the frame
                cv2.putText(image, frame_timestamp.strftime("%A %d %B %Y %I:%M:%S%p"),
                    (10, image.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 1)
                cv2.putText(image, "Road Status: {}".format(text_on_image), (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX,0.35, (0, 0, 255), 1)
            
                if SHOW_BOUNDS:
                    #define the monitored area right and left boundary
                    cv2.line(image,(upper_left_x,upper_left_y),(upper_left_x,lower_right_y),(0, 255, 0))
                    cv2.line(image,(lower_right_x,upper_left_y),(lower_right_x,lower_right_y),(0, 255, 0))
            
                # show the frame and check for a keypress
                if SHOW_IMAGE:
                    prompt_on_image(prompt)
                    cv2.imshow("Speed Camera", image)
                    
                # Adjust the base_image as lighting changes through the day
                if state == DetectionState.WAITING:
                    last_x = 0
                    cv2.accumulateWeighted(gray, base_image, 0.25)
                    t2 = time.process_time()
                    if (t2 - t1) > 60:   # We need to measure light level every so often
                        t1 = time.process_time()
                        lightlevel = my_map(measure_light(hsv),0,256,1,10)
                        print("light level = " + str(lightlevel))
                        adjusted_min_area = get_min_area(lightlevel)
                        adjusted_threshold = get_threshold(lightlevel)
                        adjusted_save_buffer = get_save_buffer(lightlevel)
                        if lightlevel != last_lightlevel:
                            base_image = None
                        last_lightlevel = lightlevel
                state=DetectionState.WAITING

        # Current detection state
        class DetectionState(IntEnum):
            WAITING=0
            TRACKING=1
            SAVING=2
        
        # Current detection direction
        class DetectionDirection(IntEnum):
            UNKNOWN = 0
            LEFT_TO_RIGHT = 1
            RIGHT_TO_LEFT = 2

        THRESHOLD = 25
        MIN_AREA = 175
        BLURSIZE = (15,15)
        SHOW_BOUNDS = True
        SHOW_IMAGE = show_preview

        TOO_CLOSE = 0.4
        MIN_SAVE_BUFFER = 2


        # store local variables from config
        ma = self.config.monitor_area
        upper_left_x = ma.upper_left_x
        upper_left_y = ma.upper_left_y
        lower_right_x = ma.lower_right_x
        lower_right_y = ma.lower_right_y
        fov = self.config.field_of_view
        l2r_distance = self.config.l2r_distance
        r2l_distance = self.config.l2r_distance
        min_speed_image = self.config.min_speed_image
        min_speed_save = self.config.min_speed_save
        max_speed_save = self.config.max_speed_save

        # initialize the camera. Adjust vflip and hflip to reflect your camera's orientation
        # allow the camera to warm up
        camera = CarSpeedCamera(self.config.h_flip,self.config.v_flip)
        image_width = camera.image_width
        image_height = camera.image_height
        camera.start()
        time.sleep(0.9)

        # calculate the the width of the image at the distance specified
        #frame_width_ft = 2*(math.tan(math.radians(FOV*0.5))*DISTANCE)
        l2r_frame_width_ft = 2*(math.tan(math.radians(fov*0.5))*l2r_distance)
        r2l_frame_width_ft = 2*(math.tan(math.radians(fov*0.5))*r2l_distance)
        l2r_ftperpixel = l2r_frame_width_ft / float(image_width)
        r2l_ftperpixel = r2l_frame_width_ft / float(image_width)
        print("L2R Image width in feet {} at {} from camera".format("%.0f" % l2r_frame_width_ft,"%.0f" % l2r_distance))
        print("R2L Image width in feet {} at {} from camera".format("%.0f" % r2l_frame_width_ft,"%.0f" % r2l_distance))


        # state maintains the state of the speed computation process
        # if starts as WAITING
        # the first motion detected sets it to TRACKING
        
        # if it is tracking and no motion is found or the x value moves
        # out of bounds, state is set to SAVING and the speed of the object
        # is calculated
        # initial_x holds the x value when motion was first detected
        # last_x holds the last x value before tracking was was halted
        # depending upon the direction of travel, the front of the
        # vehicle is either at x, or at x+w 
        # (tracking_end_time - tracking_start_time) is the elapsed time
        # from these the speed is calculated and displayed 
        
        #Initialisation
        state = DetectionState.WAITING
        raw_tracking_data=[]
        direction = DetectionDirection.UNKNOWN
        initial_x = 0
        last_x = 0
        initial_w = 0
        initial_time=None
        cap_time = datetime.datetime.now()   
        counter = 0
        speeds = None
        
        #-- other values used in program
        base_image = None
        abs_chg = 0
        mph = 0
        secs = 0.0
        text_on_image = 'No cars'
        prompt = ''
        t1 = 0.0  #timer
        t2 = 0.0  #timer
        lightlevel = 0
        last_lightlevel = 0
        adjusted_threshold = THRESHOLD
        adjusted_min_area = MIN_AREA
        adjusted_save_buffer = 0
        base_image=None
        mean_speed = 0.0
        sd = 0.0

        # create an image window and place it in the upper left corner of the screen
        if SHOW_IMAGE:
            cv2.namedWindow("Speed Camera")
            cv2.moveWindow("Speed Camera", 10, 40)
                    
        monitored_width = lower_right_x - upper_left_x
        monitored_height = lower_right_y - upper_left_y
        
        print("Monitored area:")
        print(" upper_left_x {}".format(upper_left_x))
        print(" upper_left_y {}".format(upper_left_y))
        print(" lower_right_x {}".format(lower_right_x))
        print(" lower_right_y {}".format(lower_right_y))
        print(" monitored_width {}".format(monitored_width))
        print(" monitored_height {}".format(monitored_height))
        print(" monitored_area {}".format(monitored_width * monitored_height))

        frame_timestamp=datetime.datetime.now()
        def pre_capture_callback(request):
            nonlocal frame_timestamp
            frame_timestamp = datetime.datetime.now()
        
        camera.picam.pre_callback = pre_capture_callback
        while True:
            st = time.time()
            # grab the raw NumPy array representing the image 
            image = camera.picam.capture_array('main')
            lap1=time.time()
            process_image()
            lap2=time.time()
            if state == DetectionState.WAITING:
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

    
    

    