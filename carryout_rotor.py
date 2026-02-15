#Python program to control Winegard Carryout as an AZ/EL Rotor from Gpredict
#Version 1.1
#Gabe Emerson / Saveitforparts 2024, Email: gabe@saveitforparts.com
#Edits by Michael Langan 2026

import serial
import socket 
import regex as re

#initialize some variables
current_az = 0.0  
current_el = 0.0
index = 0

#define "carryout" as the serial port device to interface with
carryout = serial.Serial(
	port='/dev/ttyUSB0',             #pass this from command line in future?
	baudrate = 115200,
	parity=serial.PARITY_NONE,
	stopbits=serial.STOPBITS_ONE,
	bytesize=serial.EIGHTBITS,
	timeout=1)
	
print ('Carryout antenna connected on ', carryout.port)

carryout.write(bytes(b'q\r')) #go back to root menu in case firmware was left in a submenu
carryout.write(bytes(b'\r')) #clear firmware prompt to avoid unknown command errors

def wait_for_angle(motor_id, angle):
	if motor_id not in (0, 1):
		raise ValueError("motor_id must be 0 or 1")
	if motor_id == 0 and not (0 <= angle <= 360):
		raise ValueError("motor 0 angle must be 0-360")
	if motor_id == 1 and not (18 <= angle <= 65):
		raise ValueError("motor 1 angle must be 18-65")

	expected = float(angle)
	while True:
		line = carryout.readline()
		if not line:
			continue
		text = line.decode('utf-8', errors='ignore').strip()
		if not text:
			continue
		match = re.search(r"Angle\s*=\s*([-+]?\d+(?:\.\d+)?)", text)
		if not match:
			continue
		try:
			value = float(match.group(1))
		except ValueError:
			continue
		if abs(value - expected) < 0.01:
			return


def home_motors(debug=False):
	carryout.write(bytes(b'mot\r'))
	carryout.write(bytes(b'h *\r'))
	while True:
		line = carryout.readline()
		if not line:
			continue
		text = line.decode('utf-8', errors='ignore').strip()
		if not text:
			continue
		if debug:
			print('Carryout:', text)
		if re.search(r"AZ\s*-\s*Angle:\s*1\s*Wrap:\s*0", text):
			return


#listen to local port for rotctld commands
listen_ip = '127.0.0.1'  #listen on localhost
listen_port = 4533     #pass this from command line in future?
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.bind((listen_ip, listen_port))
client_socket.listen(1)

print ('Homing motors before accepting connections...')
home_motors(debug=True)
#my particular G2+ seems to home to this
current_az = 0.0
current_el = 65.0

print ('Listening for rotor commands on', listen_ip, ':', listen_port)
conn, addr = client_socket.accept()
print ('Connection from ',addr)


#Would be nice to get initial / resting position from Carryout firmware
#I have not found a way to do this, just live position while motors are running


#pass rotor commands to Carryout
while 1:
	data = conn.recv(100)  #get Gpredict's message
	if not data:
		break
		
	cmd = data.decode("utf-8").strip().split(" ")   #grab the incoming command
	
	#print("Received: ",cmd)    #debugging, what did Gpredict send?
	
	if cmd[0] == "p":   #Gpredict is requesting current position
		response = "{}\n{}\n".format(current_az, current_el)
		conn.send(response.encode('utf-8'))
		
	elif cmd[0] == "P":   #Gpredict is sending desired position
		target_az = float(cmd[1])
		target_el = float(cmd[2])
		print(' Move antenna to:', target_az, ' ', target_el, end="\r")

		#open the Carryout's MOT menu
		carryout.write(bytes(b'mot\r'))
		
		
		#tell Carryout to move to target azimuth
		command = ('a 0 ' + str(target_az) + '\r').encode('ascii')
		print('Sending:', command)
		carryout.write(command)
		wait_for_angle(0, target_az)

		#tell Carryout to move to target elevation
		command = ('a 1 ' + str(target_el) + '\r').encode('ascii')
		print('Sending:', command)
		carryout.write(command)
		wait_for_angle(1, target_el)

		current_az = target_az
		current_el = target_el
			
		#Tell Gpredict things went correctly
		response="RPRT 0\n "  #Everything's under control, situation normal
		conn.send(response.encode('utf-8'))
					
		carryout.write(bytes(b'q\r')) #go back to Carryout's root menu
		
		
	elif cmd[0] == "S": #Gpredict says to stop
		print('Gpredict disconnected, exiting') #Do we want to do something else with this?
		conn.close()
		carryout.close()
		exit()
	else:
		print('Exiting')
		conn.close()
		carryout.close()
		exit()
