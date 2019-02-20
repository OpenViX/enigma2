from Converter import Converter
from Components.Element import cached
from pprint import pprint

# the protocol works as the following:

# lines starting with '-' are fatal errors (no recovery possible),
# lines starting with '=' are progress notices,
# lines starting with '+' are PIDs to record:
# 	"+d:[p:t[,p:t...]]" with d=demux nr, p: pid, t: type

class Streaming2(Converter):
	@cached
	def getText(self):
		service = self.source.service
		if service is None:
			return _("-NO SERVICE\n")

		streaming = service.stream()
		s = streaming and streaming.getStreamingData()

		if s is None or not any(s):
			err = hasattr(service, 'getError') and service.getError()
			if err:
				return _("-SERVICE ERROR:%d\n") % err
			else:
				return _("=NO STREAM\n")

                retval = "+%d:%s" % (s["demux"], ','.join(["%x:%s" % (x[0], x[1]) for x in s["pids"]]))

                if "default_audio_pid" in s and s["default_audio_pid"] >= 0:
                        retval += ",%x:%s" % (s["default_audio_pid"], "default_audio_pid")

                retval += "\n"

                return(retval);

	text = property(getText)
