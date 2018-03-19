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
        self.cyclesCount = 1 
        self.ckpt = {}
        self.history = deque(maxlen=self.maxlen)
        # We add a first pseudo-cycle in case of a modification before the first cycle
        self.history.append({k:{} for k in self.members})
        self.ckpt = {k:{} for k in self.members}

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

    def restartCycle(self):
        """
        Remove the last cycle info without applying any changes to the components.
        Useful for breakpoints, where we actually want to resume the execution
        at the same instruction it was stopped.
        """
        self.history.pop()
        self.cyclesCount -= 1

    def signalChange(self, obj, change):
        """
        Called by a component to signal a change. The name identifier must be
        the same as the one used with `registerObject`.
        """
        for name, val in change.items():
            previousVal = self.history[-1][obj.__class__].get(name)
            if previousVal:
                # If we already set a value for this key in the current cycle,
                # we want to keep the original old value. In other terms, if
                # the first change was (oldval, newval) and there is another change
                # (newval, newnewval), we want to keep (oldval, newnewval) as the
                # change, so that a step back will revert everything.
                newVal = (previousVal[0], val[1])
                self.history[-1][obj.__class__][name] = newVal
            else:
                self.history[-1][obj.__class__].update(change)
            # We always want to update the checkpoint (so that the interface
            # is always up to date)
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

        for name,obj in self.members.items():
            obj.stepBack(hist[name])
        
        self.cyclesCount -= 1
        if self.cyclesCount == 0:
            # We ensure that we always have at least one history struct in our deque
            self.clear()

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