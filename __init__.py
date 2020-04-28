#! /usr/bin/env python3

import random
import time

class remote:
	_remote_type_alias_map = {
		'fut089': 'rgb+cct'
	}
	_remote_type_parameters_map = {
		'rgbw': {
			'retries':  5,
			'delay':    0.02,
			'channels': [9, 40, 71],
			'syncword': [0x258B, 0x147A],
			'features': [
				'can_set_brightness',
				'has_brightness',
				'has_white',
				'has_color'
			],
			'brightness_range': [0, 25],
			'button_map': {
				'slider':     0x00,
				'on':         0x01,
				'white':      0x11,
				'off':        0x02,
				'night':      0x12,
				'zone_on:1':  0x03,
				'zone_on:2':  0x05,
				'zone_on:3':  0x07,
				'zone_on:4':  0x09,
				'zone_white:1': 0x13,
				'zone_white:2': 0x15,
				'zone_white:3': 0x17,
				'zone_white:4': 0x19,
				'zone_off:1': 0x04,
				'zone_off:2': 0x06,
				'zone_off:3': 0x08,
				'zone_off:4': 0x0A,
				'zone_night:1': 0x14,
				'zone_night:2': 0x16,
				'zone_night:3': 0x18,
				'zone_night:4': 0x1A,
				'speed_up':   0x0B,
				'speed_down': 0x0C,
				'change_color_mode': 0x0D,
				'zone_set_brightness': 0x0E,
				'set_color':  0x0F
			}
		},
		'cct': {
			'retries':  10,
			'delay':    0.5,
			'channels': [4, 39, 74],
			'syncword': [0x55AA, 0x050A],
			'brightness_range': [0, 9],
			'temperature_output_range': [0, 9],
			'temperature_input_range':  [3000, 9000],
			'features': [
				'has_max_brightness',
				'has_brightness',
				'has_temperature',
				'is_white'
			],
			'button_map': {
				'on':         0x05,
				'off':        0x09,
				'max':        0x15,
				'night':      0x19,
				'zone_on:1':  0x08,
				'zone_on:2':  0x0D,
				'zone_on:3':  0x07,
				'zone_on:4':  0x02,
				'zone_max:1': 0x18,
				'zone_max:2': 0x1D,
				'zone_max:3': 0x17,
				'zone_max:4': 0x12,
				'zone_off:1': 0x0B,
				'zone_off:2': 0x03,
				'zone_off:3': 0x0A,
				'zone_off:4': 0x06,
				'zone_night:1': 0x1B,
				'zone_night:2': 0x13,
				'zone_night:3': 0x1A,
				'zone_night:4': 0x16,
				'brightness_up':    0x0C,
				'brightness_down':  0x04,
				'temperature_up':   0x0E,
				'temperature_down': 0x0F
			}
		},
		'rgb+cct': {
			'channels': [8, 39, 70],
			'syncword': [0x1809, 0x7236]
		},
		'rgb': {
			'channels': [3, 38, 73],
			'syncword': [0xBCCD, 0x9AAB]
		},
		'fut020': {
			'channels': [6, 41, 76],
			'syncword': [0xAA55, 0x50A0]
		}
	}

	def __init__(self, radio, remote_type, remote_id, message_id = None, config = None):
		# Pull in the config for this remote type
		self._config = self._get_type_parameters(remote_type)

		# Allow the user to specify some more parameters
		if config is not None:
			self._config.update(config)

		# Store parameters
		self._radio = radio
		self._type = remote_type
		self._id = remote_id

		# Initialize the message ID for this remote
		if message_id is None:
			self._message_id = random.randint(0, 255)
		else:
			self._message_id = message_id

		return None

	def _scale_int(self, input_value, input_range_low, input_range_high, output_range_low, output_range_high):
		input_range = input_range_high - input_range_low
		output_range = output_range_high - output_range_low

		input_value = input_value - input_range_low

		output = input_value * (output_range / input_range)

		output = output + output_range_low

		output = int(output + 0.5)
		return output

	def _debug(self, message):
		print("MILITE DEBUG: " + message)
		return None

	def _get_type_parameters(self, remote_type):
		config = self._remote_type_parameters_map[remote_type]

		# Supply default config values
		if 'retries' not in config:
			config['retries'] = 3
		if 'delay' not in config:
			config['delay'] = 0.1

		setattr(self, '_compute_button_message', getattr(self, '_compute_button_message_' + remote_type))
		setattr(self, '_parse_button_message', getattr(self, '_parse_button_message_' + remote_type))
		setattr(self, 'pair', getattr(self, '_pair_' + remote_type))
		setattr(self, 'unpair', getattr(self, '_unpair_' + remote_type))

		return config

	def _compute_button_and_zone_from_button_id(self, button_id):
		button_info = {}
		button_info['button'] = 'unknown=' + str(button_id)
		for button_name, button_value in self._config['button_map'].items():
			if button_value == button_id:
				button_info['button'] = button_name
				break

		# If the button name has a zone, split it out into its own parameter
		if button_info['button'].find(':') != -1:
			button_name_zone = button_info['button'].split(':')
			button_info['button'] = button_name_zone[0]
			button_info['zone']   = int(button_name_zone[1])

		return button_info

	def _compute_button_message_cct(self, button_info):
		remote_id = button_info['remote_id']
		message_id = button_info['message_id']

		# Header consists of magic (0x5A), follow by 16-bit remote ID
		header = [0x5A, (remote_id >> 8) & 0xff, remote_id & 0xff]

		# Determine zone, default to all
		zone = button_info.get('zone', 0)

		# Some buttons need to be converted to zones
		button_name = button_info['button']
		if button_name in ['zone_on', 'zone_off', 'zone_max', 'zone_night']:
			button_name = button_name + ':' + str(zone)

		# Look up the button
		button_id = self._config['button_map'][button_name]

		# Compute message body
		body = [zone, button_id, message_id]

		# Compute message trailer
		## Include a CRC, for good measure ?
		crc = 0
		for byte in header + body:
			crc = crc + byte
		crc = crc & 0xff
		trailer = [crc]

		message = header + body + trailer

		return message

	def _parse_button_message_cct(self, button_message):
		button_info = {}

		# Verify the header -- if it is not valid, return None
		if button_message[0] != 0x5A:
			return None

		# Parse out common parts of the message
		button_info['remote_id'] = (button_message[1] << 8) | button_message[2]
		button_info['zone'] = button_message[3]
		button_info['message_id'] = button_message[5]

		# Remove the all zone
		if button_info['zone'] == 0:
			del button_info['zone']

		# Map the button ID to a button name
		button_id = button_message[4]
		button_info.update(self._compute_button_and_zone_from_button_id(button_id))

		return button_info

	def _pair_cct(self, zone):
		self._send_button({
			'button': 'zone_on',
			'zone': zone
		})

		# Ensure that the "on" button cannot be hit soon after
		# because it might trigger the unpair flow
		time.sleep(5)
		return True

	def _unpair_cct(self, zone):
		for retry in range(7):
			self._send_button({
				'button': 'zone_on',
				'zone': zone
			})
		return True

	def _compute_button_message_rgbw(self, button_info):
		remote_id = button_info['remote_id']
		message_id = button_info['message_id']

		# Allow setting brightness for all zones
		if button_info['button'] == 'set_brightness':
			button_info['button'] = 'zone_set_brightness'
			if 'zone' in button_info:
				del button_info['zone']

		# Header consists of magic (0xB0), follow by 16-bit remote ID
		header = [0xB0, (remote_id >> 8) & 0xff, remote_id & 0xff]

		# Default value for most buttons, since they do not need it
		brightness = 0
		color = 0

		# Some buttons need to be converted to zones
		button_name = button_info['button']
		if button_name in ['zone_on', 'zone_off', 'zone_white', 'zone_night']:
			button_name = button_name + ':' + str(button_info['zone'])

		button_id = self._config['button_map'][button_name]

		# Brightness and Color buttons should also set the appropriate
		# parameters
		if button_info['button'] == 'zone_set_brightness':
			## Brightness is a range of [0..25] (26 steps)
			## Shifted 3 bitsleft
			brightness = button_info['brightness']
			if brightness < 0:
				brightness = 0
			elif brightness > 25:
				brightness = 25

			brightness = 31 - ((brightness + 15) % 32)

			brightness = brightness << 3

			if 'zone' in button_info:
				brightness = brightness | button_info['zone']

		elif button_info['button'] == 'set_color':
			color = button_info['color']

		# Compute message
		body = [color, brightness, button_id, message_id]

		# Compute whole message
		message = header + body

		return message

	def _parse_button_message_rgbw(self, button_message):
		button_info = {}

		# Verify the header -- if it is not valid, return None
		if button_message[0] != 0xB0:
			return None

		# Parse out common parts of the message
		button_info['remote_id'] = (button_message[1] << 8) | button_message[2]
		button_info['color'] = button_message[3]
		button_info['brightness'] = button_message[4]
		button_info['message_id'] = button_message[6]

		# Map the button ID to a button name
		button_id = button_message[5]

		button_info.update(self._compute_button_and_zone_from_button_id(button_id))

		if button_info['button'] == 'zone_set_brightness':
			brightness = button_info['brightness']
			zone = brightness & 0b111
			if zone != 0:
				button_info['zone'] = zone
			else:
				button_info['button'] = 'set_brightness'

			# Compute brightness value, there are 26 brightness steps, [16, 0][31, 23]
			brightness = brightness >> 3
			brightness = 31 - ((brightness + 15) % 32)
			button_info['brightness'] = brightness

		return button_info

	def _pair_rgbw(self, zone):
		self._send_button({
			'button': 'zone_on',
			'zone': zone
		})
		return False

	def _unpair_rgbw(self, zone):
		self._send_button({
			'button': 'zone_white',
			'zone': zone
		})
		return False

	def _get_next_message_id(self):
		# Determine next message ID
		self._message_id = (self._message_id + 1) & 0xff
		return self._message_id

	def _send_button(self, button_info):
		# Configure radio parameters
		self._radio.set_syncword(self._config['syncword'])

		# Include the remote ID unless one was supplied
		if 'remote_id' not in button_info:
			button_info['remote_id'] = self._id

			# Get the next message ID for this remote
			if 'message_id' not in button_info:
				message_id = self._get_next_message_id()
				button_info['message_id'] = message_id
			else:
				self._message_id = button_info['message_id']

		# Compute message
		message = self._compute_button_message(button_info)

		# Transmit
		if 'delay' in button_info:
			delay = button_info['delay']
		else:
			delay = self._config['delay']
		if 'retries' in button_info:
			retries = button_info['retries']
		else:
			retries = self._config['retries']

		self._debug("Sending {}={} n={} times with a {}s delay".format(button_info, message, retries, delay))
		self._radio.multi_transmit(message, self._config['channels'], retries, delay)

		return True

	def _set_brightness(self, brightness, zone = None):
		if zone is None:
			message = {'button': 'set_brightness'}
		else:
			message = {
				'button': 'zone_set_brightness',
				'zone': zone
			}

		message['brightness'] = brightness

		return self._send_button(message)

	def _step_value(self, target_value, target_range_min, target_range_max, button_prefix, zone):
		# Step all the way to the nearest extreme before moving it to
		# where it should be
		target_range = target_range_max - target_range_min + 1
		midpoint = (target_range / 2) + target_range_min

		# Move to the "initial" value where we force the value
		# to the extreme, then move it to its final value
		initial_steps = target_range
		if target_value < midpoint:
			initial_direction = 'down'
			final_direction = 'up'
			initial_value = target_range_min
		else:
			initial_direction = 'up'
			final_direction = 'down'
			initial_value = target_range_max

		# If this remote has a "max" feature, use that instead of stepping
		use_max_button = False
		if initial_value == target_range_max:
			if 'has_max_{}'.format(button_prefix) in self._config['features']:
				use_max_button = True

		if use_max_button:
			self._debug("[INITIAL] Going to max {}".format(button_prefix))
			getattr(self, "max_{}".format(button_prefix))(zone)
		else:
			# Otherwise, step it
			for step in range(initial_steps):
				self._debug("[INITIAL] Stepping {} {}".format(button_prefix, initial_direction))
				self._send_button({'button': "{}_{}".format(button_prefix, initial_direction)})

		# Now that we have forced the value to the extreme, move in
		# steps from that value to the desired value
		if initial_value < target_value:
			final_steps = target_value - initial_value
		else:
			final_steps = initial_value - target_value

		for step in range(final_steps):
			self._debug("[FINAL] Stepping {} {}".format(button_prefix, final_direction))
			self._send_button({'button': "{}_{}".format(button_prefix, final_direction)})

		return True

	def _step_brightness(self, brightness, brightness_min, brightness_max, zone = None):
		# Select the appropriate zone before sending the steps
		# to ensure they reach the correct bulbs
		self.on(zone)
		return self._step_value(brightness, brightness_min, brightness_max, 'brightness', zone)

	def _step_temperature(self, temperature, temperature_min, temperature_max, zone = None):
		# Select the appropriate zone before sending the steps
		# to ensure they reach the correct bulbs
		self.on(zone)
		return self._step_value(temperature, temperature_min, temperature_max, 'temperature', zone)

	def _rgb_to_hue(self, r, g, b):
		r = r / 255.0
		g = g / 255.0
		b = b / 255.0

		cmax = max(r, max(g, b))
		cmin = min(r, min(g, b))
		diff = cmax - cmin

		if cmax == cmin:
			h = 0
		elif cmax == r:
			h = (60 * ((g - b) / diff) + 360) % 360
		elif cmax == g:
			h = (60 * ((b - r) / diff) + 120) % 360
		elif cmax == b:
			h = (60 * ((r - g) / diff) + 240) % 360

		return h

	def _rgb_to_color(self, rgb):
		r = (rgb >> 16) & 0xff
		g = (rgb >>  8) & 0xff
		b =  rgb        & 0xff

		# If the value is really a shade of white
		# encode the brightness as a negative value
		# where 0 is -1, 1 is -2, etc
		if r == g and g == b:
			return (r * -1) - 1

		# Compute the hue of the RGB value (ignore
		# luminance and saturation)
		h = self._rgb_to_hue(r, g, b)

		# Convert the hue into a LimitlessLED value
		# which is really just the position along the
		# color strip, offset
		color = ((h / 360.0) * 255.0) + 26
		color = color % 256

		color = int(color + 0.5)

		self._debug("RGB = \x1b[38;2;%i;%i;%im%06x\x1b[0m; Hue = %s; Color = %i" % (r, g, b, rgb, str(h * 360), color))

		return color

	def raw_send_button(self, button_info):
		return self._send_button(button_info)

	def raw_read_button(self):
		channel = self._config['channels'][0]
		self._radio.set_syncword(self._config['syncword'])
		data = self._radio.receive(channel = channel, wait = True, wait_time = 1)
		message = self._parse_button_message(data)
		return message

	def set_brightness(self, brightness, zone = None):
		if 'has_brightness' not in self._config['features']:
			return False

		if brightness < 0 or brightness > 255:
			return False

		self._debug("Setting brightness to {}".format(brightness))
		if brightness == 0:
			self._debug("Really setting to off")
			return self.off(zone)

		if brightness == 255:
			if 'has_max_brightness' in self._config['features']:
				return self.max_brightness(zone)

		brightness_min = self._config['brightness_range'][0]
		brightness_max = self._config['brightness_range'][1]

		brightness = self._scale_int(brightness, 1, 255, self._config['brightness_range'][0], self._config['brightness_range'][1])

		if 'can_set_brightness' in self._config['features']:
			return self._set_brightness(brightness, zone)
		else:
			return self._step_brightness(brightness, brightness_min, brightness_max, zone)

	def set_color(self, rgb, zone = None):
		# Compute the color value from the RGB value
		value = self._rgb_to_color(rgb)

		# If the color selected is really a shade of grey, turn the
		# bulbs white at that brightness
		if value < 0:
			brightness = (value + 1) * -1
			self._debug("Brightness = {}".format(brightness))
			if self.white(zone):
				return self.set_brightness(brightness, zone)
			else:
				return False

		# If the bulbs do not support color, nothing needs to be done
		if 'has_color' not in self._config['features']:
			return False

		# Turn on the appropriate zone to select it
		self.on(zone)

		# Press the button
		return self._send_button({'button': 'set_color', 'color': value})

	def set_temperature(self, kelvins, zone = None):
		if 'has_temperature' not in self._config['features']:
			return False

		temperature_input_low = self._config['temperature_input_range'][0]
		temperature_input_high = self._config['temperature_input_range'][1]
		temperature_output_low = self._config['temperature_output_range'][0]
		temperature_output_high = self._config['temperature_output_range'][1]

		# Clamp the color temperature to something this remote supports
		if kelvins < temperature_input_low:
			kelvins = temperature_input_low
		elif kelvins > temperature_input_high:
			kelvins = temperature_input_high

		temperature = self._scale_int(kelvins, temperature_input_low, temperature_input_high, temperature_output_low, temperature_output_high)

		if 'can_set_temperature' in self._config['features']:
			return self._set_temperature(temperature, zone)
		else:
			return self._step_temperature(temperature, temperature_output_low, temperature_output_high, zone)

	def on(self, zone = None):
		if zone is None:
			message = {'button': 'on'}
		else:
			message = {
				'button': 'zone_on',
				'zone': zone
			}

		# Increase retries and delay for on/off to ensure
		# that these important messages are delivered
		message['retries'] = self._config['retries'] * 2
		message['delay'] = self._config['delay'] * 2

		return self._send_button(message)

	def off(self, zone = None, dim = True):
		# Dim the bulbs so that when turned on they are not bright
		if dim:
			self.set_brightness(1, zone)

		if zone is None:
			message = {
				'button': 'off',
			}
		else:
			message = {
				'button': 'zone_off',
				'zone': zone
			}

		# Increase retries and delay for on/off to ensure
		# that these important messages are delivered
		message['retries'] = self._config['retries'] * 2
		message['delay'] = self._config['delay'] * 2

		return self._send_button(message)

	def max_brightness(self, zone = None):
		if 'has_max_brightness' not in self._config['features']:
			return self.set_brightness(255, zone)
			
		if zone is None:
			message = {'button': 'max'}
		else:
			message = {
				'button': 'zone_max',
				'zone': zone
			}
		return self._send_button(message)

	def white(self, zone = None):
		# If the bulbs are already white, nothing needs to be done
		if 'is_white' in self._config['features']:
			return True

		# If the bulbs do not support white, nothing needs to be done
		if 'has_white' not in self._config['features']:
			return False

		if zone is None:
			message = {'button': 'white'}
		else:
			message = {
				'button': 'zone_white',
				'zone': zone
			}
		return self._send_button(message)
