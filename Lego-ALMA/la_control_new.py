import pickle
import numpy as np
import operator
import os
import glob

class Control:
	def __init__(self,ctrl_id = 'USB1',but_dict_file = None,separating_bit = 35,swi_bit_list = [],rot_bit_list = [],button_ids = ["R0","R1","R2","S0","S1","S2"]):
		self.ctrl_id = ctrl_id
		self.separating_bit = separating_bit
		self.but_dict_file = but_dict_file
		self.button_dict = dict()
		self.swi_bit_list = swi_bit_list
		self.rot_bit_list = rot_bit_list
		self.button_ids = button_ids
		self.all_button_bits = [0]#tuple(rot_bits, swi_bits)
		self.rot_switch_pos =  [0]#tuple(rot_pos),tuple(swi_pos)
		if self.rot_bit_list == []:
			self.rot_bit_list = np.array([[5,13,21,29], [6,14,22,30], [7,15,23,31]])
	def set_rot_bits_from_file(self, filename):
		try:
			self.rot_bit_list = np.loadtxt(filename, delimiter = ",")
			return 1
		except Exception as e:
			print(e,"unable to load rot but bit list")
			return 0
	def set_swi_bits_from_file(self, filename):
		try:
			self.swi_bit_list = np.loadtxt(filename, delimiter = ",")
			return 1
		except Exception as e:
			print(e,"unable to load swi but bit list")
			return 0

		
	def add_button(self, button_id):
		self.button_dict[button_id] = Button(identifier = button_id)
	def add_buttons(self,button_ids = None):
		if button_ids is None:
			button_ids = self.button_ids
		for _bid in self.button_ids:
			self.add_button(_bid)
		return 1
	def set_button(self,button_id,state):
		if button_id in self.button_dict:
			self.button_dict[button_id].set_state(state)
			return 1
		else:
			print("error",button_id," not in button dict")
			return 0
	def set_buttons(self,button_ids = None,button_states=None):
		if button_ids is None:
			button_ids = self.button_ids
		if button_states is None:
			button_states = [0] * len(button_ids)
		if len(button_ids) != len(button_states):
			print("error, number button ids {} must equal number of button states {}".format(button_ids,button_states))
			return 0
		for _bid,_bst in zip(button_ids,button_states):
			self.set_button(_bid,_bst)	
		return 1
	def remove_button(self,button_id):
		try:
			del self.button_dict[button_id]
		except Exception as e:
			print("error",button_id," not in button dict")
			return 0

	def _read_button_bits(self,last_measurements):
		#print(last_measurements[self.ctrl_id])
		rot_bits =tuple(last_measurements[self.ctrl_id][last_measurements[self.ctrl_id] < self.separating_bit])
		#print(rot_bits)
		swi_bits = tuple((last_measurements[self.ctrl_id][last_measurements[self.ctrl_id] > self.separating_bit])[:-1])
		return tuple(rot_bits),tuple(swi_bits)

	def get_all_pos(self,last_measurements,use_dict = False):
		rot_bits, swi_bits = self._read_button_bits(last_measurements)
		if use_dict == True:
			rot_pos = self.but_bit_dict[rot_bits]
		else:
			button_bits = self.rot_bit_list#np.array([[5,13,21,29],[6,14,22,30],[7,15,23,31]])
			rot_pos = [0,0,0]
			for _b in rot_bits:
				i,ans = np.where(button_bits == _b)
				rot_pos[i[0]] = ans[0]
			
		swi_pos = list(np.array([_b in swi_bits for _b in self.swi_bit_list])*1)
		self.all_button_bits = tuple(rot_bits), tuple(swi_bits)
		self.rot_switch_pos =  tuple(rot_pos),tuple(swi_pos)
		#print(self.swi_bit_list,swi_bits,swi_pos)
		#print(rot_pos,swi_pos,"POS")
		return tuple(rot_pos),tuple(swi_pos)
		
	def set_all_buttons(self,last_measurements):
		all_states = operator.add(*self.get_all_pos(last_measurements))
		#print("setting all states",all_states)
		self.set_buttons(button_states = all_states)
		
	def get_state(self,last_measurements):
		try:
			self.set_all_buttons(last_measurements)
		except Exception:
			# If control data is not present in last_measurements (single-device setup),
			# keep existing button states and continue.
			pass
		return self.button_dict

		
		
	
	def _read_switch_part(self,last_measuerements):
		swi_part = tuple((last_measurements[self.ctrl_id][last_measurements[self.ctrl_id] > self.separating_bit])[:-1])
		return swi_part
	def set_swi_bit_list(self,swi_bit_list):
		self.swi_bit_list = swi_bit_list

	def set_but_bit_dict_file(self,fname):
		self.but_dict_file = fname
	
	def load_but_bit_dict(self,fname = None):
		if fname is None:
			fname = self.but_dict_file

		with open(fname,'rb') as fin:
			self.but_bit_dict = pickle.load(fin)


class Button:
	def __init__(self,identifier = "",init_state = 0):
		self.indentifier = identifier
		self.state = init_state
	def get_state(self):
		return self.state
	def set_state(self,state):
		self.state = state
	def get_id(self):
		return self.identifier
	def set_id(self,identifier):
		self.identifier = identifier


def id_usb_conn(last_measurements, use_last_bit = True, discriminant = 6):
	"""
	Simplified device selection for a Pi setup with a single antenna USB device.
	Prefer `/dev/ttyACM1` (user Arduino) as antenna source. If it is present in
	`last_measurements` keys, return it and no control device. Otherwise,
	fall back to the first `ttyACM*` or `ttyUSB*` key if available.
	"""

	preferred = '/dev/ttyACM1'
	keys = list(last_measurements.keys())
	# If the shared measurements dict already contains the preferred device, use it
	if preferred in keys:
		return preferred, None
	# fallback: any ACM
	for k in keys:
		if 'ACM' in k:
			return k, None
	# fallback: any USB
	for k in keys:
		if 'USB' in k:
			return k, None


	# If last_measurements did not contain any keys, fall back to filesystem
	if len(keys) == 0:
		# direct check for preferred device
		if os.path.exists(preferred):
			return preferred, None
		# any ACM
		acm = glob.glob('/dev/ttyACM*')
		if len(acm) > 0:
			return acm[0], None
		# any USB
		usb = glob.glob('/dev/ttyUSB*')
		if len(usb) > 0:
			return usb[0], None

	raise RuntimeError('no serial devices found')
