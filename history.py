from collections import deque

class History:

    def __init__(self, historyMaxLength=100):
        """
        Initialize the history manager.
        historyMaxLength indicates how many step back we should allow at most
        """
        self.maxlen = historyMaxLength
        self.members = {}
        self.clear()

    def clear(self):
        """
        Reset the history (but do not unregister the components)
        """
        self.cyclesCount = 0
        self.ckpt = {}
        self.history = deque(maxlen=self.maxlen)

    def registerObject(self, obj):
        """
        Must be called by a component to register itself before starting
        the simulation.
        """
        self.members[obj.__class__] = obj

    def newCycle(self):
        """
        Tell the history manager that we are starting another step
        (all the changes within one step are aggregated).
        Must be called at the _beginning_ of each step (before any changes).
        """
        self.history.append({k:{} for k in self.members})
        self.cyclesCount += 1

    def signalChange(self, obj, change):
        """
        Called by a component to signal a change. The name identifier must be
        the same as the one used with `registerObject`.
        """
        for name, val in change.items():
            previousVal = self.history[-1][obj.__class__].get(name)
            if previousVal:
                # If the object is present in the same cycle, we keep the first value
                newVal = (previousVal[0], val[1])
                self.history[-1][obj.__class__][name] = newVal
            else:
                self.history[-1][obj.__class__].update(change)
                self.ckpt[obj.__class__].update(change)

    def stepBack(self):
        """
        Called by the simulator to operate a step back over all components.
        Each registered object (component) must also have a stepBack method.
        """
        try:
            hist = self.history.pop()
        except IndexError:
            # We reached the end of the history
            raise RuntimeError("Fin de l'historique atteinte, impossible de remonter plus haut!")

        print("Members : {}".format(self.members))
        for name,obj in self.members.items():
            print("Name : {}".format(name))
            print("Obj : {}".format(obj))
            obj.stepBack(hist[name])
        
        self.cyclesCount -= 1

    def setCheckpoint(self):
        """
        Reset the checkpoint so that we aggregate the changes from this point.
        """
        self.ckpt = {k:{} for k in self.members}
    
    def getDiffFromCheckpoint(self):
        """
        Return all the aggregated changes since the last checkpoint
        """
        return self.ckpt