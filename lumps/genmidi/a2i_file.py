#!/usr/bin/env python
#
# Copyright (c) 2011, 2012
# Contributors to the Freedoom project.  All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of the freedoom project nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER
# OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# ----------------------------------------------------------------------
#
# Module to load A2I (AdlibTracker 2) instrument files.
#

import sys
import struct

HEADER_STRING = "_A2ins_"

class BitReader:
	def __init__(self, data):
		self.data = data
		self.index = 0
		self.byte = 0
		self.byte_bit = 0

	def read_byte(self):
		if self.index >= len(self.data):
			raise IndexError("Reached end of decompress stream " +
			                 "(%i bytes)" % len(self.data))
		result, = struct.unpack("B", self.data[self.index:self.index+1])
		self.index += 1
		return result

	def read_bit(self):
		if self.byte_bit <= 0:
			self.byte = self.read_byte()
			self.byte_bit = 7
		else:
			self.byte_bit -= 1

		if (self.byte & (1 << self.byte_bit)) != 0:
			result = 1
		else:
			result = 0

		return result

	def read_bits(self, n):
		result = 0

		for i in range(n):
			result = (result << 1) + self.read_bit()

		return result

def read_gamma(reader):
	result = 1

	while True:
		result = (result << 1) | reader.read_bit()

		if reader.read_bit() == 0:
			break

	return result

def decompress(data, data_len):
	reader = BitReader(data)
	result = []
	lwm = 0
	last_offset = 0

	# First byte is an implied straight copy.
	result.append(reader.read_byte())

	while True:
		if reader.read_bit():
			if reader.read_bit():
				if reader.read_bit():
					# 111 = Copy byte from history,
					# up to 15 bytes back.
					#print "111 copy"

					offset = reader.read_bits(4)

					if offset == 0:
						result.append(0)
					else:
						b = result[len(result) - offset]
						result.append(b)

					lwm = 0
				else:
					#print "110 copy"
					# 110 = Copy 2-3 bytes from
					# further back in history

					offset = reader.read_byte()
					count = 2 + (offset & 0x01)
					offset = offset >> 1

					if offset == 0:
						break

					index = len(result) - offset
					for i in range(count):
						result += result[index:index+1]
						index += 1

					last_offset = offset
					lwm = 1
			else:
				# 10 = Copy from further away...

				offset = read_gamma(reader)

				if lwm == 0 and offset == 2:
					#print "10 copy type 1"
					count = read_gamma(reader)
					index = len(result) - last_offset
					for i in range(count):
						result += result[index:index+1]
						index += 1
				else:
					#print "10 copy type 2"
					if lwm == 0:
						offset -= 3
					else:
						offset -= 2

					offset = offset * 256 \
					       + reader.read_byte()

					count = read_gamma(reader)

					if offset >= 32000:
						count += 1
					if offset >= 1280:
						count += 1
					if offset < 128:
						count += 2

					index = len(result) - offset
					for i in range(count):
						result += result[index:index+1]
						index += 1

					last_offset = offset

				lwm = 1

		else:
			#print "Single byte output"

			# 0 = Straight-through byte copy.
			result.append(reader.read_byte())
			lwm = 0

		#print "len: %i" % len(result)

	return struct.pack("%iB" % len(result), *result)

FIELDS = [
	"m_am_vibrato_eg",
	"c_am_vibrato_eg",
	"m_ksl_volume",
	"c_ksl_volume",
	"m_attack_decay",
	"c_attack_decay",
	"m_sustain_release",
	"c_sustain_release",
	"m_waveform",
	"c_waveform",
	"feedback_fm",
	"panning",
	"finetune",
	"voice_type",
]

def decode_type_9(data):
	compressed_len, = struct.unpack("<H", data[0:2])
	compressed_data = data[2:2+compressed_len]
	decompressed_data = decompress(compressed_data, compressed_len)

	instr_data = {}

	# Decode main fields:

	for i in range(len(FIELDS)):
		instr_data[FIELDS[i]], = \
		    struct.unpack("B", decompressed_data[i:i+1])

	# Decode instrument name

	ps = decompressed_data[14:]
	instr_data["name"], = struct.unpack("%ip" % len(ps), ps)

	return instr_data

def read(filename):
	f = open(filename)
	data = f.read()
	f.close()

	hdrstr, crc, filever = struct.unpack("<7sHB", data[0:10])

	if hdrstr.lower() != HEADER_STRING.lower():
		raise Exception("Wrong file header ID string")

	# TODO: CRC?

	if filever == 9:
		return decode_type_9(data[10:])
	else:
		raise Exception("Unsupported file version: %i" % filever)

if __name__ == "__main__":
	for filename in sys.argv[1:]:
		print filename
		print read(filename)

