from time import localtime, time, strftime
import functools
import traceback
import sys

indent = 0

# To output call stack and call duration for a function, decorate like this:
# from Tools.Trace import trace
# @trace
# def myFunction()
#


def trace(func):
	funcName = func.__name__

	def func_wrapper(*args, **kwargs):
		global indent
		cls = args[0].__class__ if len(args) > 0 else None
		className = "[Trace:" + cls.__name__ + "]" if cls is not None else "[Trace]"
		print "%s%s %s Starting" % (("| " * indent)[:indent], className, funcName)
		indent += 2
		initTime = time()
		try:
			result = func(*args, **kwargs)
		finally:
			indent -= 2
		print "%s%s %s Finished in %.2fms" % (("| " * indent)[:indent], className, funcName, (time() - initTime) * 1000.0)
		return result

	return func_wrapper


# To output call duration for a function, decorate like this:
# from Tools.Trace import profile
# @profile
# def mySlowFunction()
#
def profile(func):
	funcName = func.__name__

	def func_wrapper(*args, **kwargs):
		global indent
		cls = args[0].__class__ if len(args) > 0 else None
		className = "[Trace:" + cls.__name__ + "]" if cls is not None else "[Trace]"
		initTime = time()
		result = func(*args, **kwargs)
		print "%s%s %s took %.2fms" % (("| " * indent)[:indent], className, funcName, (time() - initTime) * 1000.0)
		return result

	return func_wrapper


def logcaller(func):
	funcName = func.__name__

	def func_wrapper(*args, **kwargs):
		global indent
		cls = args[0].__class__ if len(args) > 0 else None
		className = "[Trace:" + cls.__name__ + "]" if cls is not None else "[Trace]"
		result = func(*args, **kwargs)
		callstack = '\n'.join([("| " * indent)[:indent] + line.strip() for line in traceback.format_stack()][-3:-2])
		print "%s%s %s called. %s" % (("| " * indent)[:indent], className, funcName, callstack)
		return result

	return func_wrapper


def getCallstack():
	# Get all but last line returned by traceback.format_stack()
	# which is the line below.
	return '\n'.join([("| " * indent)[:indent] + line.strip() for line in traceback.format_stack()][-6:-1])
