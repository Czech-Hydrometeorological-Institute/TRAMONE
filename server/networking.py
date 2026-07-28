import serial
import time 
import os
from gpiozero import DigitalOutputDevice
import threading
import subprocess
from datetime import datetime
import pytz
import psutil
import fcntl
from systemd.daemon import notify


def subscribe(command):
	ser.write((command + '\r').encode())	
	time.sleep(0.5)
	response = ser.read(ser.in_waiting).decode()
	print(response)
	print("-------------")
	if "ERR" in response or "+SMSTATE: 0" in response or "+SMSTATE: 2" in response:
		return False

def close_all():		
	global ser
	ser = serial.Serial(SERIAL_PORT, baudrate=115200, timeout=3)
	print("---------------------")
	print("Closing everything...")
	if os.path.exists("/home/pi/TRAMONE/networking_on"):
		os.remove("/home/pi/TRAMONE/networking_on")
#		subprocess.run(["sudo","pkill","-f","gprs"],check=True)
#		print("PPP killed.")
	ser.write(('AT+FTPQUIT' + '\r').encode())
	time.sleep(1)
	response=ser.read(ser.in_waiting).decode()
	print(response)	
	response=ser.read(ser.in_waiting).decode()
	print(response)
	subscribe_to_log(response)
	ser.write(('AT+SMDISC' + '\r').encode())
	time.sleep(1)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	ser.write(('AT+CNACT=0,0' + '\r').encode())
	time.sleep(0.2)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	ser.write(('AT+CGACT=0,1' + '\r').encode())
	time.sleep(0.2)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	ser.write(('AT+CGATT=0' + '\r').encode())
	time.sleep(0.2)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	time.sleep(1)
	ser.close()	


def init_GSM():
	
	err=True
	while err == True:
		err=False
		close_all()
		print("------------")
		print("Init GSM...")
		gsm_pwr.on()
		time.sleep(2)
		gsm_pwr.off()
		time.sleep(1)
		global ser
		ser = serial.Serial(SERIAL_PORT, baudrate=115200, timeout=1)
		time.sleep(2)
		ser.write(('AT' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		if not 'OK' in response:
			print("GSM module off. Starting up...")
			gsm_pwr.on()
			time.sleep(2)
			gsm_pwr.off()
			time.sleep(1)
			ser.write(('AT' + '\r').encode())
			time.sleep(0.1)
			response=ser.read(ser.in_waiting).decode()
			print(response)
		else:
			print("GSM module started.")
		ser.write(('AT+IPR=115200' + '\r').encode())
		time.sleep(1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		if not 'OK' in response:
			err=True
		ser.write(('AT+CMNB=1' + '\r').encode())
		time.sleep(1)
		response=ser.read(ser.in_waiting).decode()
		print(response)	
		ser.write(('AT+CNMP=38' + '\r').encode())
		time.sleep(0.5)
		response=ser.read(ser.in_waiting).decode()
		print(response)	
		if not 'OK' in response:
			err=True
		ser.write(('AT+CGATT=1' + '\r').encode())
		time.sleep(1)	
		response=ser.read(ser.in_waiting).decode()
		print(response)
		if not 'OK' in response:
			err=True
		ser.write(('AT+CGDCONT=1,"IP","internet.t-mobile.cz"' + '\r').encode())
		time.sleep(0.1)	
		response=ser.read(ser.in_waiting).decode()
		print(response)
		if not 'OK' in response:
			err=True
		ser.write(('AT+CGACT=1,1' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		if not 'OK' in response:
			err=True	
		ser.write(('AT+CNACT=0,2' + '\r').encode())
		time.sleep(2)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		if not 'ACTIVE' in response:
			#err=True
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|NET|INIT|GSM|ERR\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)
		else:
			print("------------")
			print("Init GSM OK.")
			print("------------")
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|NET|INIT|GSM|OK\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)
		#set ntp time
		ser.write(('AT+CNTP' + '\r').encode())
		time.sleep(2)
		response=ser.read(ser.in_waiting).decode()
		print(response)	
		if 'OK' in response:
			lines=response.splitlines()
			for line in lines:
				if "+CNTP:" in line:
					line=line.replace('"','')
					parts=line.split(',')
					parse_datetime=datetime.strptime(f"{parts[1]} {parts[2]}","%Y/%m/%d %H:%M:%S")
					with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
						fcntl.flock(log_lock, fcntl.LOCK_EX)
						file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|NET|NTP|{parse_datetime}|OK\n")
						file.flush()
						fcntl.flock(log_lock, fcntl.LOCK_UN)
					formatted_datetime=parse_datetime.strftime("%m%d%H%M%Y.%S")
					subprocess.run(["sudo","date",formatted_datetime])
					break
	return err

def init_MQTT():
	err=False	
	#init MQTT
	ser.write((f'AT+SMCONF="URL",{MQTT_BROKER},{MQTT_PORT}' + '\r').encode())
	time.sleep(0.1)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	if not 'OK' in response:
		err=True
	ser.write(('AT+SMCONF="KEEPTIME",600' + '\r').encode())
	time.sleep(0.1)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	if not 'OK' in response:
		err=True
	ser.write(('AT+SMCONF="CLEANSS",1' + '\r').encode())
	time.sleep(0.1)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	if not 'OK' in response:
		err=True
	ser.write(('AT+SMCONF="CLIENTID","TRAMONE_SERVER"' + '\r').encode())
	time.sleep(0.1)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	if not 'OK' in response:
		err=True
	ser.write(('AT+SMCONN' + '\r').encode())
	time.sleep(5)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	if not 'OK' in response or 'ERR' in response:
		err=True
		print("MQTT reconnection error!!!")
	if err==False:
		#set subscribe responses
		ser.write((f'AT+SMSUB="TRAMONE/#",0' + '\r').encode())
		time.sleep(0.2)
		#create topics for publishing
		for sampling_region in sampling_regions:
			for site in sampling_sites:
				#create topic of request
				ser.write((f'AT+SMPUB=TRAMONE/{sampling_region}{site}/request,2,0,1' + '\r').encode())
				time.sleep(0.1)
				ser.write((f'99' + '\r').encode())
				time.sleep(0.1)
		time.sleep(5)
		response = ser.read(ser.in_waiting).decode()
		print(response)
		if '+SMSUB:' in response and "99" in response and not "ERR" in response:
			subscribe_to_log(response)
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|{sampling_region}{site}|NET|INIT|MQTT_REQUEST|OK\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)			
		else:
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|{sampling_region}{site}|NET|INIT|MQTT_REQUEST|ERR\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)			
			err=True
	print("-------------")
	print("End init MQTT")
	print("-------------")
	return err

def init_FTP():
	err=True
	while err == True:
		err=False	
		#init FTP
		ser.write(('AT+FTPCID?' + '\r').encode())
		time.sleep(1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)	
		if not 'OK' in response:
			err=True
		else:
			if not '+FTPCID: 0' in response:
				ser.write(('AT+FTPCID=0' + '\r').encode())
				time.sleep(0.1)
				response=ser.read(ser.in_waiting).decode()
				print(response)
				subscribe_to_log(response)
		ser.write((f'AT+FTPSERV="{FTP_SERV}"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)
		if not 'OK' in response:
			err=True
		ser.write((f'AT+FTPUN="{FTP_USER}"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)
		if not 'OK' in response:
			err=True
		ser.write((f'AT+FTPPW="{FTP_PASS}"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)
		if not 'OK' in response:
			err=True	
		ser.write(('AT+FTPGETNAME="autovzorsta.txt"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)
		if not 'OK' in response:
			err=True	
		ser.write(('AT+FTPGETPATH="/OCO/vzorsta/"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)	
		if not 'OK' in response:
			err=True
		ser.write(('AT+FTPMODE=1' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)	
		if not 'OK' in response:
			err=True
		ser.write(('AT+FTPTYPE="I"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)	
		if not 'OK' in response:
			err=True	
		if err==True:
			print("FTP init error!")
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|NET|CONN|FTP|ERR\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)
		else:
			print("FTP connected.")
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|NET|CONN|FTP|OK\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)
	return err					


def init_FTP_AIM(max_attempts=3):
	err=True
	attempt=0
	while err == True and attempt < max_attempts:
		attempt+=1
		err=False
		#init FTP
		ser.write(('AT+FTPCID?' + '\r').encode())
		time.sleep(1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)	
		if not 'OK' in response:
			err=True
		else:
			if not '+FTPCID: 0' in response:
				ser.write(('AT+FTPCID=0' + '\r').encode())
				time.sleep(0.1)
				response=ser.read(ser.in_waiting).decode()
				print(response)
				subscribe_to_log(response)
		ser.write((f'AT+FTPSERV="{FTP_AIM_SERV}"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)
		if not 'OK' in response:
			err=True
		ser.write((f'AT+FTPUN="{FTP_AIM_USER}"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)
		if not 'OK' in response:
			err=True
		ser.write((f'AT+FTPPW="{FTP_AIM_PASS}"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)
		if not 'OK' in response:
			err=True	
		ser.write(('AT+FTPGETNAME="tramone.txt"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)
		if not 'OK' in response:
			err=True	
		ser.write(('AT+FTPGETPATH="/"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)	
		if not 'OK' in response:
			err=True
		ser.write(('AT+FTPMODE=1' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)	
		if not 'OK' in response:
			err=True
		ser.write(('AT+FTPTYPE="I"' + '\r').encode())
		time.sleep(0.1)
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)	
		if not 'OK' in response:
			err=True	
		if err==True:
			print(f"FTP AIM init error! (attempt {attempt}/{max_attempts})")
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|NET|CONN|AIM_FTP|ERR\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)
			if attempt < max_attempts:
				time.sleep(1)
		else:
			print("FTP AIM connected.")
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|NET|CONN|AIM_FTP|OK\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)
	return err

	
def wind_download():
	err=False
	response=ser.read(ser.in_waiting).decode()
	print(response)
	subscribe_to_log(response)
	ser.write(('AT+FTPSIZE' + '\r').encode())
	time.sleep(2)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	subscribe_to_log(response)
	lines = response.splitlines()
	file_size=None
	for line in lines:
		if "+FTPSIZE:" in line:
			parts=line.split(',')
			file_size=int(parts[-1])
			break
	#download to memory
	ser.write(('AT+FTPEXTGET=1' + '\r').encode())
	time.sleep(2)
	time_start=time.time()
	while True:
		print("Downloading to memory...")
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)
		lines = response.splitlines()
		if time.time()-time_start>60:
			print("FTP download timeout!")
			err=True
			break
		if '+FTPEXTGET:' in response:
			for line in lines:
				if '+FTPEXTGET:' in line:
					FTPEXTGET_state=int(line.split(',')[-1])
					if FTPEXTGET_state==0:
						print("Wind file downloaded successfully.")
					elif FTPEXTGET_state<file_size:
						print("Wind file corrupted or other FTP error.")
						err=True
			break
		time.sleep(3)		
	#print/save from memory
	if err==False:
		with threading.Lock():
			ser.write((f'AT+FTPEXTGET=3,0,{file_size}' + '\r').encode())
		response=''
		while True:
			if ser.in_waiting:
				line=ser.readline().decode("utf-8",errors="replace").strip()
				response += line + '\n'
				if line == 'OK':
					break
		print("---------------------")
		print(response)	
		subscribe_to_log(response)
		lines = response.splitlines()
		#filter out MQTT and FTP messages from the windfile (less columns than has the first column)
		filtered_lines=[
			line for line in lines
			if '+FTPEXTGET' not in line and 'OK' not in line and '+SMSUB:' not in line and '"' not in line and line.strip()
		]
		
		with open('/home/pi/TRAMONE/wind.tmp', "w") as f:
		    f.write("\n".join(filtered_lines) + "\n")
		    f.flush()
		    os.fsync(f.fileno())
		os.replace('/home/pi/TRAMONE/wind.tmp', '/home/pi/TRAMONE/wind.txt')
		if err==False:
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|WIND_DOWNLOAD|OK\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)			
		else:
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|WIND_DOWNLOAD|ERR\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)			
	return err




def wind_download_AIM():
	err=False
	response=ser.read(ser.in_waiting).decode()
	print(response)
	subscribe_to_log(response)
	ser.write(('AT+FTPSIZE' + '\r').encode())
	time.sleep(2)
	response=ser.read(ser.in_waiting).decode()
	print(response)
	subscribe_to_log(response)
	lines = response.splitlines()
	file_size=None
	for line in lines:
		if "+FTPSIZE:" in line:
			parts=line.split(',')
			file_size=int(parts[-1])
			break
	#download to memory
	ser.write(('AT+FTPEXTGET=1' + '\r').encode())
	time.sleep(2)
	time_start=time.time()
	while True:
		print("Downloading AIM wind to memory...")
		response=ser.read(ser.in_waiting).decode()
		print(response)
		subscribe_to_log(response)
		lines = response.splitlines()
		if time.time()-time_start>60:
			print("FTP AIM wind download timeout!")
			err=True
			break
		if '+FTPEXTGET:' in response:
			for line in lines:
				if '+FTPEXTGET:' in line:
					if '+FTPEXTGET: 1,77' in line:
						print("AIM wind file does not exist!")
						err=True
					else:
						FTPEXTGET_state=int(line.split(',')[-1])	
						if FTPEXTGET_state==0:
							print("AIM wind file downloaded successfully.")
						elif FTPEXTGET_state<file_size:
							print("AIM wind file corrupted or other FTP error.")
							err=True
					break
			break
		time.sleep(3)		
	#print/save from memory
	if err==False:
		with threading.Lock():
			ser.write((f'AT+FTPEXTGET=3,0,{file_size}' + '\r').encode())
		response=''
		while True:
			if ser.in_waiting:
				line=ser.readline().decode("utf-8",errors="replace").strip()
				response += line + '\n'
				if line == 'OK':
					break
		print("---------------------")
		print(response)	
		subscribe_to_log(response)
		lines = response.splitlines()
		#filter out MQTT and FTP messages from the windfile (less columns than has the first column)
		filtered_lines=[
			line for line in lines
			if '+FTPEXTGET' not in line and 'OK' not in line and '+SMSUB:' not in line and line.strip()
		]
		with open('/home/pi/TRAMONE/wind_AIM.txt','w') as file:
			file.write('\n'.join(filtered_lines)+'\n')
		if err==False:
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|AIM_WIND_DOWNLOAD|OK\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)			
		else:
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|AIM_WIND_DOWNLOAD|ERR\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)			
	return err







def subscribe_to_log(resp: str):
    if not isinstance(resp, str) or not resp:
        return
    lines = resp.splitlines()
    for raw_line in lines:
        if '+SMSUB:' not in raw_line:
            continue
        line = raw_line.replace('"', '').strip()
        if line.count('/') < 2:
            log_text = f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|SUBSCRIBE|LINE|{line}|ERR\n"
            with open("/home/pi/TRAMONE/.log_lock", "w") as log_lock, open(LOG, "a") as file:
                fcntl.flock(log_lock, fcntl.LOCK_EX)
                file.write(log_text)
                file.flush()
                fcntl.flock(log_lock, fcntl.LOCK_UN)
            continue
        if ',' not in line:
            log_text = f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|SUBSCRIBE|LINE|{line}|ERR\n"
            with open("/home/pi/TRAMONE/.log_lock", "w") as log_lock, open(LOG, "a") as file:
                fcntl.flock(log_lock, fcntl.LOCK_EX)
                file.write(log_text)
                file.flush()
                fcntl.flock(log_lock, fcntl.LOCK_UN)
            continue

        left, payload = line.rsplit(',', 1)
        payload = payload.strip()
        try:
            topic_path = left.split(':', 1)[1].strip()
        except Exception:
            log_text = f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|SUBSCRIBE|LINE|{line}|ERR\n"
            with open("/home/pi/TRAMONE/.log_lock", "w") as log_lock, open(LOG, "a") as file:
                fcntl.flock(log_lock, fcntl.LOCK_EX)
                file.write(log_text)
                file.flush()
                fcntl.flock(log_lock, fcntl.LOCK_UN)
            continue

        parts = topic_path.split('/')
        if len(parts) < 3:
            log_text = f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|SUBSCRIBE|LINE|{line}|ERR\n"
            with open("/home/pi/TRAMONE/.log_lock", "w") as log_lock, open(LOG, "a") as file:
                fcntl.flock(log_lock, fcntl.LOCK_EX)
                file.write(log_text)
                file.flush()
                fcntl.flock(log_lock, fcntl.LOCK_UN)
            continue

        region_site = parts[-2].strip()
        topic = parts[-1].strip()
        # ----------------------------
        # response
        # ----------------------------
        if topic == 'response':
            log_text = f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|{region_site}|{topic}|{payload}\n"
            with open("/home/pi/TRAMONE/.log_lock", "w") as log_lock, open(LOG, "a") as file:
                fcntl.flock(log_lock, fcntl.LOCK_EX)
                file.write(log_text)
                file.flush()
                fcntl.flock(log_lock, fcntl.LOCK_UN)
        # -----------------------------------------
        # filter
        # -----------------------------------------
        if topic == 'filter' and '99' not in payload:
            sampler = payload
            log_text = f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|{region_site}|{topic}|{sampler}|REPLACED|OK\n"
            with open("/home/pi/TRAMONE/.log_lock", "w") as log_lock, open(LOG, "a") as file:
                fcntl.flock(log_lock, fcntl.LOCK_EX)
                file.write(log_text)
                file.flush()
                fcntl.flock(log_lock, fcntl.LOCK_UN)
            with open(f"/home/pi/TRAMONE/sampling_{region_site}{sampler}", "w") as file:
                file.write("0")
                file.flush()
                os.fsync(file.fileno())
            sampling_time()
        # ----------------------------
        # override
        # ----------------------------
        if topic == 'override':
            message = payload
            log_text = f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|{region_site}|{topic}|STATE|{message}|WR\n"
            with open("/home/pi/TRAMONE/.log_lock", "w") as log_lock, open(LOG, "a") as file:
                fcntl.flock(log_lock, fcntl.LOCK_EX)
                file.write(log_text)
                file.flush()
                fcntl.flock(log_lock, fcntl.LOCK_UN)
            override_path = f"/home/pi/TRAMONE/override_{region_site}"
            with open(override_path, "w") as file:
                file.write(message)
                file.flush()
                os.fsync(file.fileno())
        # -----------------------------------------
        # ping
        # -----------------------------------------
        with open("/home/pi/TRAMONE/networking_on", "w") as file:
            pass
    return response









def sampling_time():
	for region in sampling_regions:
		for site in sampling_sites:
			for sampler in [0, 1]:
			
				#find the last sampling time reset
				with open(LOG,'r',encoding='utf-8') as file:
					lines=file.readlines()
					reverse_num_line=-1
					for line in reversed(lines):
						reverse_num_line=reverse_num_line+1
						if f"|{region}{site}|filter|{sampler}|" in line:
							break
				start_line=len(lines)-reverse_num_line
				
				tot_sampling_time=0
				line=start_line
				sampling=False
				while line<len(lines):
					if f"|{region}{site}|response|STATE|" in lines[line]:
						if lines[line].split("|STATE|")[1][sampler]=="1":
							start_time=str(lines[line].split('|')[0])
							start_time=int(datetime.strptime(start_time,"%Y-%m-%d %H:%M:%S").timestamp())
							current_sampling_time=0
							sampling=True
							while line<len(lines):
								if f"|{region}{site}|response|STATE|" in lines[line]:
									if lines[line].split("|STATE|")[1][sampler]=="0":
										end_time=str(lines[line].split('|')[0])
										end_time=int(datetime.strptime(end_time,"%Y-%m-%d %H:%M:%S").timestamp())		
										current_sampling_time=end_time-start_time
										sampling=False
										break
								line=line+1
							tot_sampling_time=tot_sampling_time+current_sampling_time
					line=line+1
				#calculate the total time including a last unfinished period 
				if sampling==True:
					log_sampling_time=tot_sampling_time+(int(time.time())-start_time)
				else:
					log_sampling_time=tot_sampling_time
				#if filter replacement not present in the log (start_line==0), the log backup was done => add a previous sampling times from the temp files
				#if start_line==0:
				with open(LOG,'r',encoding='utf-8') as file:
					log_lines=file.readlines()
				if f"|{region}{site}|filter|{sampler}|" not in log_lines:
					with open(f"/home/pi/TRAMONE/sampling_{region}{site}{sampler}","r") as file:
						temp_sampling_time=float(file.readline().strip())*3600
						log_sampling_time=temp_sampling_time+log_sampling_time
				#sampling time to MQTT
				sampling_value = f"{log_sampling_time/3600.0:.3f}"
				payload_len = len(sampling_value)
				ser.write((f'AT+SMPUB=TRAMONE/{region}{site}{sampler}/sampling,{payload_len},0,1\r').encode())
				time.sleep(0.1)
				ser.write((sampling_value + '\r').encode())
				time.sleep(2)
				resp = ser.read(ser.in_waiting).decode(errors="replace")
				print(resp)
				subscribe_to_log(resp)
				#sampling time to log
				ok = (log_sampling_time / 3600.0) < 72.0
				with open("/home/pi/TRAMONE/.log_lock", "w") as log_lock, open(LOG, "a") as f:
					fcntl.flock(log_lock, fcntl.LOCK_EX)
					f.write(
						f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|{region}{site}|{sampler}|SAMPLING|{sampling_value}|{'OK' if ok else 'ERR'}\n"
					)
					f.flush()
					fcntl.flock(log_lock, fcntl.LOCK_UN)
					










def load_shell_cfg(path):
    cfg = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue

            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()

            # odstranění uvozovek "..." nebo '...'
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]

            cfg[k] = v
    return cfg



		
if __name__=="__main__":
	###################
	#start main loop
	cfg = load_shell_cfg(os.path.join(os.environ["HOME"], "TRAMONE", "tramone.cfg"))
	SERIAL_PORT = cfg["SERIAL_PORT"]
	MQTT_BROKER = cfg["MQTT_BROKER"]
	MQTT_PORT = int(cfg["MQTT_PORT"])
	MQTT_TOPICS_DIR = os.path.join(os.environ["HOME"], "TRAMONE", "MQTT")
	LOG = cfg["LOG"]
	FTP_SERV = cfg["FTP_SERV"]
	FTP_USER = cfg["FTP_USER"]
	FTP_PASS = cfg["FTP_PASS"]
	FTP_AIM_SERV = cfg["FTP_AIM_SERV"]
	FTP_AIM_USER = cfg["FTP_AIM_USER"]
	FTP_AIM_PASS = cfg["FTP_AIM_PASS"]
	sampling_regions = os.environ.get("SAMPLING_REGIONS")
	sampling_sites = os.environ.get("SAMPLING_SITES")
	sampling_regions=sampling_regions.split(",")
	sampling_sites=sampling_sites.split(",")

	print(SERIAL_PORT)
	print(MQTT_BROKER)
	print(MQTT_PORT)
	print(MQTT_TOPICS_DIR)
	print(LOG)
	print(sampling_regions)
	print(sampling_sites)

	gsm_pwr=DigitalOutputDevice(4,active_high=True,initial_value=False)
	last_request_time=[sampling_regions,sampling_sites]
	notify("READY=1")

	last_subscribe=time.time()
	
	#os.system('x-terminal-emulator')
	with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
		fcntl.flock(log_lock, fcntl.LOCK_EX)
		file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|NET|NETWORKING|START|OK\n")
		file.flush()
		fcntl.flock(log_lock, fcntl.LOCK_UN)			
	
	response=""
	last_request_time = {}
	#set last request time
	for sampling_region in sampling_regions:
		for site in sampling_sites:
			if not os.path.exists(f'{MQTT_TOPICS_DIR}/TRAMONE/{sampling_region}{site}/request'):
				os.makedirs(os.path.dirname(f'{MQTT_TOPICS_DIR}/TRAMONE/{sampling_region}{site}/request'),exist_ok=True)
				with open(f'{MQTT_TOPICS_DIR}/TRAMONE/{sampling_region}{site}/request', 'w') as f:
					f.write('')
			last_request_time[(sampling_region,site)] = os.path.getmtime(f'{MQTT_TOPICS_DIR}/TRAMONE/{sampling_region}{site}/request')
	#wind file creation time set to zero
	FTPMDTM_prev=0
	FTPMDTM_AIM_prev=0
	err_count=0
	err_count_aim=0
	err=True
	while err==True:
		err=init_GSM()
		if err==False:
			err=init_MQTT()
		if err==True:
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|INIT|MQTT|ERR\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)			
		else:
			with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
				fcntl.flock(log_lock, fcntl.LOCK_EX)
				file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|INIT|MQTT|OK\n")
				file.flush()
				fcntl.flock(log_lock, fcntl.LOCK_UN)			
	#info on succesfull connection for bash
	with open ("/home/pi/TRAMONE/networking_on","w") as file:
		pass	
	hour_prev=0
	minute_prev=0
	
	sampling_time()
	
	#main loop			
	try:
		while True:
			
			notify("WATCHDOG=1")
			
			#check MQTT connection
			ser.write(('AT+SMSTATE?' + '\r').encode())
			time.sleep(1)
			response=ser.read(ser.in_waiting).decode()
			print(response)
			subscribe_to_log(response)
			if '+SMSUB:' in response:
				err_count=0
				err=False
			if not 'SMPUB' in response:
				if '+SMSTATE: 0' in response:
					err=True
					with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
						fcntl.flock(log_lock, fcntl.LOCK_EX)
						file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|MQTT|CONN|ERR\n")
						file.flush()
						fcntl.flock(log_lock, fcntl.LOCK_UN)			
					#if MQTT connection error, try to restart only MQTT and if not success, restart GSM and MQTT
					while err == True:
						print("New init...")
						err=init_MQTT()
						while err==True:
							err=init_GSM()
							if err==False:
								err=init_MQTT()
							if err==True:
								with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
									fcntl.flock(log_lock, fcntl.LOCK_EX)
									file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|INIT|MQTT|ERR\n")
									file.flush()
									fcntl.flock(log_lock, fcntl.LOCK_UN)			
							else:
								with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
									fcntl.flock(log_lock, fcntl.LOCK_EX)
									file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|INIT|MQTT|OK\n")
									file.flush()
									fcntl.flock(log_lock, fcntl.LOCK_UN)			

			#refresh subscribe for sparsely used topics
			now=time.time()
			if now - last_subscribe > 300:
				print("Refreshing subscription for override and filter topics...")
				for region in sampling_regions:
					for site in sampling_sites:
						ser.write((f'AT+SMUNSUB=TRAMONE/{region}{site}/override' + '\r').encode())
						time.sleep(0.2)
						ser.write((f'AT+SMUNSUB=TRAMONE/{region}{site}/filter' + '\r').encode())
						time.sleep(0.2)
				time.sleep(0.5)
				response=ser.read(ser.in_waiting).decode()
				print(response)			
				subscribe_to_log(response)
				for region in sampling_regions:
					for site in sampling_sites:
						ser.write((f'AT+SMSUB="TRAMONE/{region}{site}/override",0\r').encode())
						time.sleep(0.2)
						ser.write((f'AT+SMSUB="TRAMONE/{region}{site}/filter",0\r').encode())
						time.sleep(0.2)
				time.sleep(0.5)
				print("...OK")
				response=ser.read(ser.in_waiting).decode()
				print(response)			
				subscribe_to_log(response)			
				last_subscribe=now
			
			#check if new wind file present on the server every 1 minute
			minute_now = int(time.time() // 60)  # počet minut od epochy
			if minute_now != minute_prev and minute_now % 1 == 0:
				err=init_FTP()
				ser.write(('AT+FTPMDTM' + '\r').encode())
				time.sleep(2)
				response=ser.read(ser.in_waiting).decode()
				print(response)
				subscribe_to_log(response)
				if 'OK' in response and ',63' in response:
					print("FTP server error!!!")
					with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
						fcntl.flock(log_lock, fcntl.LOCK_EX)
						file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|SERVER|ERR\n")	
						file.flush()
						fcntl.flock(log_lock, fcntl.LOCK_UN)			
					err=True
				if 'OK' in response and not ',66' in response:
					err_count=0
					err=False
					lines=response.splitlines()
					for line in lines:
						if "+FTPMDTM:" in line:
							#if not server error code in response
							if "+FTPMDTM: 1,0" in response:
								parts=line.split(',')
								FTPMDTM=int(datetime.strptime(parts[2],"%Y%m%d%H%M%S").timestamp())
								print("-------------------------------------------------------------------------")
								print(f"FTP server wind file is {int(datetime.now(pytz.utc).timestamp())-FTPMDTM}s old.")
								print("-------------------------------------------------------------------------")
								if int(datetime.now(pytz.utc).timestamp())-FTPMDTM > 15*60:
									with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
										fcntl.flock(log_lock, fcntl.LOCK_EX)
										file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|WIND_ON_SERVER_OLD|ERR\n")	
										file.flush()
										fcntl.flock(log_lock, fcntl.LOCK_UN)			
									err=True
									break
								if FTPMDTM>FTPMDTM_prev:
									err=True
									while err==True:
										err=wind_download()
									FTPMDTM_prev=FTPMDTM
							else:
								FTPMDTM=FTPMDTM_prev
								with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
									fcntl.flock(log_lock, fcntl.LOCK_EX)
									file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|SERVER|ERR\n")	
									file.flush()
									fcntl.flock(log_lock, fcntl.LOCK_UN)			
								err=True
								break
				else:
					FTPMDTM=FTPMDTM_prev
					#count failed connections and restart if they are >3 (approx. three minutes)
					err_count=err_count+1
					if err_count>3:
						err=True
						with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
							fcntl.flock(log_lock, fcntl.LOCK_EX)
							file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|CONN|ERR\n")
							file.flush()
							fcntl.flock(log_lock, fcntl.LOCK_UN)			
						#if FTP connection error, try to restart only FTP and if not success, restart GSM and FTP
						while err == True:
							print("New FTP init...")
							err=init_FTP()
							while err==True:
								err=init_GSM()
								if err==False:
									err=init_MQTT()
									if err==False:
										err=init_FTP()
								if err==True:
									with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
										fcntl.flock(log_lock, fcntl.LOCK_EX)
										file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|INIT|CONN|ERR\n")
										file.flush()
										fcntl.flock(log_lock, fcntl.LOCK_UN)			
								else:
									with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
										fcntl.flock(log_lock, fcntl.LOCK_EX)
										file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|INIT|CONN|OK\n")
										file.flush()
										fcntl.flock(log_lock, fcntl.LOCK_UN)			
				
				
				# AIM is an optional secondary wind data source. A failure here must
				# never restart GSM/MQTT (that would disrupt client-station
				# communication) - it is only logged and retried next minute.
				# When AIM stays unavailable, wind_preparation.R falls back to
				# ChHMU-only data automatically (file.exists() check on its side).
				aim_err=init_FTP_AIM()
				if aim_err==True:
					err_count_aim=err_count_aim+1
					with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
						fcntl.flock(log_lock, fcntl.LOCK_EX)
						file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|AIM_UNAVAILABLE|ERR\n")
						file.flush()
						fcntl.flock(log_lock, fcntl.LOCK_UN)
				else:
					err_count_aim=0
					ser.write(('AT+FTPMDTM' + '\r').encode())
					time.sleep(2)
					response=ser.read(ser.in_waiting).decode()
					print(response)
					subscribe_to_log(response)
					if 'OK' in response and ',63' in response:
						print("FTP server error!!!")
						with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
							fcntl.flock(log_lock, fcntl.LOCK_EX)
							file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|AIM_SERVER|ERR\n")
							file.flush()
							fcntl.flock(log_lock, fcntl.LOCK_UN)
						aim_err=True
					elif 'OK' in response and not ',66' in response:
						lines=response.splitlines()
						for line in lines:
							if "+FTPMDTM:" in line:
								#if not server error code in response
								if "+FTPMDTM: 1,0" in response:
									parts=line.split(',')
									FTPMDTM_AIM=int(datetime.strptime(parts[2],"%Y%m%d%H%M%S").timestamp())
									print("-------------------------------------------------------------------------")
									print(f"FTP server AIM wind file is {int(datetime.now(pytz.utc).timestamp())-FTPMDTM_AIM}s old.")
									print("-------------------------------------------------------------------------")
									if int(datetime.now(pytz.utc).timestamp())-FTPMDTM_AIM > 15*60:
										with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
											fcntl.flock(log_lock, fcntl.LOCK_EX)
											file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|AIM_WIND_ON_SERVER_OLD|ERR\n")
											file.flush()
											fcntl.flock(log_lock, fcntl.LOCK_UN)
										break
									if FTPMDTM_AIM>FTPMDTM_AIM_prev:
										for dl_attempt in range(3):
											if wind_download_AIM()==False:
												FTPMDTM_AIM_prev=FTPMDTM_AIM
												break
								else:
									with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
										fcntl.flock(log_lock, fcntl.LOCK_EX)
										file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|AIM_SERVER|ERR\n")
										file.flush()
										fcntl.flock(log_lock, fcntl.LOCK_UN)
									break
					else:
						err_count_aim=err_count_aim+1
						with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
							fcntl.flock(log_lock, fcntl.LOCK_EX)
							file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|ALL|MAIN|FTP|AIM_UNAVAILABLE|ERR\n")
							file.flush()
							fcntl.flock(log_lock, fcntl.LOCK_UN)

				minute_prev=minute_now
																				
			#check a new request and publish
			for sampling_region in sampling_regions:
				for site in sampling_sites:
					current_modification_time_request = os.path.getmtime(f'{MQTT_TOPICS_DIR}/TRAMONE/{sampling_region}{site}/request')
					if current_modification_time_request != last_request_time[(sampling_region,site)]:
						print("New request for "+sampling_region+site)
						if os.path.exists(f'{MQTT_TOPICS_DIR}/TRAMONE/{sampling_region}{site}/request'):
							with open(f'{MQTT_TOPICS_DIR}/TRAMONE/{sampling_region}{site}/request', 'r') as f:
								lines = f.readlines()
								lines = [line.strip() for line in lines]
							if lines:
								for line in lines:
									ser.write((f'AT+SMPUB=TRAMONE/{sampling_region}{site}/request,2,0,1' + '\r').encode())
									time.sleep(0.1)
									#set sampler to idle state if the wind file is old
									with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
										fcntl.flock(log_lock, fcntl.LOCK_EX)
										file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|{sampling_region}{site}|request|{line}|REQUESTED|OK\n")
										file.flush()
										fcntl.flock(log_lock, fcntl.LOCK_UN)			
									if int(datetime.now(pytz.utc).timestamp())-FTPMDTM > 15*60:
										line="00"
										print(f"ERROR: wind files old !!! Samplers set to idle state !!!")
										with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
											fcntl.flock(log_lock, fcntl.LOCK_EX)
											file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|{sampling_region}{site}|request|00|WIND_OLD|ERR\n")
											file.flush()
											fcntl.flock(log_lock, fcntl.LOCK_UN)			
									# manually overiding sampler state
									if os.path.exists(f'/home/pi/TRAMONE/override_{sampling_region}{site}'):
										with open(f'/home/pi/TRAMONE/override_{sampling_region}{site}', 'r') as f:
											override = f.readline().strip()
										if override != "99":
											print(f"WARNING: request for {sampling_region}{site} overrided from {line} to {override} !!!")
											with open ("/home/pi/TRAMONE/.log_lock","w") as log_lock, open(LOG, "a") as file:
												fcntl.flock(log_lock, fcntl.LOCK_EX)
												file.write(f"{datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')}|{sampling_region}{site}|request|OVERRIDED|FROM {line} TO {override}|WRN\n")
												file.flush()
												fcntl.flock(log_lock, fcntl.LOCK_UN)			
											line=override
									ser.write((f'{line}' + '\r').encode())
									time.sleep(3)
									response = ser.read(ser.in_waiting).decode()
									print(response)
									subscribe_to_log(response)				
									
						last_request_time[(sampling_region,site)] = current_modification_time_request
						
						
			#log messages arrived during main loop
			response=ser.read(ser.in_waiting).decode()
			subscribe_to_log(response)
			
			#hourly logging sampling time since filter replacement
			hour_now=int(datetime.now(pytz.utc).strftime("%Y%m%d%H"))
			if hour_now!=hour_prev:
				sampling_time()
				hour_prev=hour_now
			
			#log backup
			with open(LOG, "r") as log_active:
				lines=log_active.readlines()
			line_count=len(lines)
			if line_count>500000:
				sampling_time()
				#write recent sampling times from the log to the temp files
				for sampling_region in sampling_regions:
					for site in sampling_sites:
						for sampler in [0, 1]:
							#find the last sampling time in log
							with open(LOG,'r',encoding='utf-8') as file:
								lines=file.readlines()
								reverse_num_line=-1
								for line in reversed(lines):
									reverse_num_line=reverse_num_line+1
									if f"|{sampling_region}{site}|{sampler}|SAMPLING" in line:
										sampler_time=line.split('|')[-2]
										with open(f"/home/pi/TRAMONE/sampling_{sampling_region}{site}{sampler}", "w") as file:
											file.write(f"{round(float(sampler_time),3)}")	
										break
				with open(LOG, "r") as log_active:
					content=log_active.read()
				timestamp=datetime.now(pytz.utc).strftime("%Y%m%d_%H%M%S")
				base,ext=os.path.splitext(LOG)
				with open(f"{base}_{timestamp}{ext}", "w") as log_backup:
					log_backup.write(content)
				with open(LOG, "w") as log_active:
					pass
											
			#longer loop time to limit FTP server load
			time.sleep(3)
			
	except KeyboardInterrupt:
	    pass
	    
	ser.close()


