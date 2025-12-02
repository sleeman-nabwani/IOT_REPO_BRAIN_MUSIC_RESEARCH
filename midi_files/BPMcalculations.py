import collections
import time


class BpmCalculator:

    """
        this class receives footsteps happened now and calculates the BPM of the last step the esp sent
        also smoothing the BPM (average of last 3 intervals) "in other words the last four steps"
    """

    def __init__(self, size=3):        # size = how many past intervals we want to average.
        self.size = size
        self.LastStepTime = None # The last time a footstep happened (None until first step arrives)
        self.intervalsQueue = collections.deque(maxlen=size) # deque that stores the last 4 intervals, maxlen=size makes it automatically remove the oldest interval
        #in the dequeue we got 3 intervals but they are for the last 4 steps , interval between 1 and 2, 2 and 3, 3 and 4

    def add_step(self): # This function must be called everytime the ESP detects a step.
       # in this function we : 1) timestamps the step , 2) computes interval & instant BPM & smoothed BPM

        step_time = time.time() #timestamp when step arrives
        if self.LastStepTime is None: # first step = no interval yet
            self.LastStepTime = step_time
            return None

        interval = step_time - self.LastStepTime #time between two steps
        self.LastStepTime = step_time

        if interval <= 0:
            print("error the interval isn't correct")
            return None

        self.intervalsQueue.append(interval)
        instantBPM = 60/interval
        avgInterval = sum(self.intervalsQueue)/len(self.intervalsQueue)
        smoothedBPM = 60/avgInterval
        return instantBPM, smoothedBPM
