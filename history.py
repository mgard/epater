from collections import deque

class History:

    def __init__(self, historyMaxLength=100):
        """
        Initialize the history manager.
        historyMaxLength indicates how many step back we should allow at most
        """
        self.maxlen = historyMaxLength
        self.members = {}
        self.ckpt = {}
        self.history = deque(maxlen=self.maxlen)

    def registerObject(self, obj):
        """
        Must be called by a component to register itself before starting
        the simulation.
        """
        self.members[obj.__class__] = obj

    def newStep(self):
        """
        Tell the history manager that we are starting another step
        (all the changes within one step are aggregated).
        Must be called at the _beginning_ of each step (before any changes).
        """
        self.history.append({k:{} for k in self.members})

    def signalChange(self, obj, change):
        """
        Called by a component to signal a change. The name identifier must be
        the same as the one used with `registerObject`.
        """
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

        for name,obj in self.members.values():
            obj.stepBack(hist[name])

    def setCheckpoint(self):
        """
        Reset the checkpoint so that we aggregate the changes from this point.
        """
        self.ckpt = {k:{} for k in self.members}
    
    def getDiffFromCheckpoint(self):
        """
        Return all the aggregated changes since the last checkpoint
        """
        return self.ckpt        # TODO : format for the UI