from abc import ABC, abstractmethod

class BaseMode(ABC):
    def __init__(self, context):
        """
        :param context: The BPM_estimation instance (provides access to player, logger, state).
        """
        self.context = context
        self.logger = context.logger

    @abstractmethod
    def handle_step(self, now_ts, current_bpm):
        """
        Called on every step computation.
        Should return the target BPM to set, or None if no change.
        """
        pass

    def activate(self):
        """Called when switching to this mode."""
        self.logger.log(f"Mode Activated: {self.__class__.__name__}")

    def deactivate(self):
        """Called when leaving this mode."""
        pass

    def on_step(self, bpm):
        """Called when a step is detected."""
        pass
