import functools
import traceback
import sys

def safe_execute(func):
    """
    Decorator to wrap functions in a try-except block.
    If an exception occurs, it logs it and returns None, keeping the thread alive.
    Attempts to find a 'logger' instance in args or self.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # 1. Try to find logger in self (args[0])
            logger = None
            if args and hasattr(args[0], 'logger'):
                logger = args[0].logger
            
            # 2. Try to find logger in args/kwargs by Duck Typing
            # We check for a .log method instead of importing Logger class
            # to avoid circular imports.
            if not logger:
                for arg in args:
                    if hasattr(arg, 'log') and callable(arg.log):
                        logger = arg
                        break
                if not logger and 'logger' in kwargs:
                    logger = kwargs['logger']
            
            error_msg = f"SAFETY CATCH: Error in {func.__name__}: {e}"
            detailed_trace = traceback.format_exc()
            
            if logger:
                logger.log(error_msg)
                # logger.log(detailed_trace) # Optional: generic log might be too noisy
            else:
                print(error_msg, file=sys.stderr)
                print(detailed_trace, file=sys.stderr)
            
            return None # Swallow error and continue
    return wrapper
