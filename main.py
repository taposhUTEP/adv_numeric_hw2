import wave
import time
import sys
import pyaudio
import array
import math
import sine

# Sampling frequency
fsampling = 8000

# Frequency to send a zero, in Hertz
fzero = 1850

# Frequency to send a one, in Hertz
fone = 1650

# Number of bits per second
baud = 50

# Time in ms to wait before sending anything
# Ones are sent during that initial wait
tstart = 1000

# Time in ms to wait after sending the text
# Ones are sent during that final wait
tstop = 1000


# This is a function that returns the k-th bit
# There are (2 + 8) bits per byte
#
# The text argument is a bytes object (see below)
#
# The k argument is an index to the k-th bit,
# including the start and stop bits.
#
# The bytes need to be framed with start and
# stop bits (see below).
#
# The bytes are to be sent LSB first
#
# For example, this means, if k = 17,
# the 6-th bit (17 % 10 - 1) of the 1-th byte (17 // 10)
# is to be returned.
#
# For example, this also means, if k = 29,
# the stop bit (9-th bit), set to 1, after the 2-th byte
# needs to be returned.
#
# The function returns True for a one, False for a zero.
#
def get_actual_bit(text, k):
    start_bit = 0
    stop_bit = len(text) * 10 + 1 # because each byte is 10 bits
    if (k == start_bit) or (k == stop_bit):
        return True
    else:
        byte_idx = k // 10
        bit_idx = (k % 10) - 1
        byte = text[byte_idx]
        bit = (byte >> bit_idx) & 1
        if bit==1:
            return True
        else:
            return False


# This is a function that returns the bit for the i-th sample
# and states if we are done or not
#
# Returns a 2-tuple of two boolean values: bit, done
#
# If the bit value is True, a one is to be sent for sample #i
# If the bit value is False, a zero is to be sent for sample #i
#
# If the done value is False, the transmission continues
# If the done value is True, the transmission is done
#
# The text argument is a bytes object. You can pull the
# k-th byte (k=0...len(text)-1) with text[k].
#
# The i argument is an integer indicating the i-th sample
# that needs to be produced.
#
# The function gets called in real time. It should
# avoid doing expensive operations.
#
# This function gets called for the ones bits in the
# initial, tstart ms long, start phase and
# for the final, tstop ms long, stop phase.
#
def get_bit(text, i):
    start_bits = tstart * baud // 1000
    stop_bits = tstop * baud // 1000
    if i < start_bits:
        return True, True
    elif i >= (len(text) * 10 + stop_bits):
        return False, True
    else:
        idx = i - start_bits
        actual_bit = get_actual_bit(text, idx + 1)
        return actual_bit, False


# This is a generator that produces samples
#
# Uses the sine.sine table
#
# That table contains
#
# sine[k] = nearestint((2^15 - 1) * sin(2 * pi * k / 2^16))
#
# The generator needs to output the samples for the
# FSK modulation of the text in text
#
# For a zero bit, a sine wave of fzero Hz is to be sent
# For a one bit, a sine wave of fone Hz is to be sent
#
# There are baud bits per second that are sent
#
# Every 8 bit byte is framed with one start bit, which is
# always zero, and one stop bit, which is always one.
#
# In the beginning, for tstart ms, ones are sent.
#
# Then the text is sent in FSK.
#
# After the text is sent, for tstop ms, ones are sent.
#
# The generator yields samples until is done
#
# The sine wave that is produced need to be free of
# phase jumps, even when switching from fone to fzero
# or vice versa.
#
# This latter point is IMPORTANT. If you do not
# understand what it means, ask your instructor!
#
# This generator runs in real time. So it should not
# do expensive things like len(sine.sine) at each call
#
def get_sample(text):
    # Number of sample
    i = 0

    # Current index in table, times 2**16
    idx = 0

    # Table size
    tbl = len(sine.sine)

    # Compute modulo for table index
    m = tbl * 2 ** 16

    # Compute table offsets for both frequencies
    off_zero = int(fzero * tbl * 2 ** 16 / fsampling)
    off_one = int(fone * tbl * 2 ** 16 / fsampling)

    # Set sentinel
    done = False
    while not done:
        # Get bit and sentinel
        bit, done = get_bit(text, i)

        # Increase sample number
        i = i + 1

        # Get table offset for bit
        if bit:
            off_bit = off_one
        else:
            off_bit = off_zero

        # Add bit offset to table index
        idx = (idx + off_bit) % m

        # Get real index into the table
        k = (idx // 2 ** 16) % tbl

        # Get sample
        s = sine.sine[k]

        # Yield the sample
        yield s


if __name__ == "__main__":
    # Check if we got some text to send
    if len(sys.argv) < 2:
        print("Need to have a text message to send.")
        sys.exit(-1)

    # Get text as byte object
    text = bytes(sys.argv[1] + '\0', "utf-8")

    # Initialize sample generator
    gen = get_sample(text)


    # Define callback function
    def audio_callback(in_data, frame_count, time_info, status):
        samples = []
        for i in range(frame_count):
            n = next(gen, None)
            if n is None:
                break
            sample = int(n + 0.5)
            if sample > (2 ** 15 - 1):
                sample = 2 ** 15 - 1
            if sample < -2 ** 15:
                sample = -2 ** 15
            samples.append(sample)
        data = array.array('h', samples).tobytes()
        return (data, pyaudio.paContinue)


    # Initialize audio environment
    p = pyaudio.PyAudio()

    # Initialize an audio stream
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=8000,
                    output=True,
                    stream_callback=audio_callback)

    # Run the stream
    while stream.is_active():
        time.sleep(0.1)

    # Close the stream
    stream.close()

    # Close the audio environment
    p.terminate()

