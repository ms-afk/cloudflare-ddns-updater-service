#!/usr/bin/python3

#Cloudflare dns record updater

from cloudflare_api_interface import * #module in this folder

import dns.resolver
import ipaddress
import socket
import logging
import requests
import time
import configparser
from pathlib import Path
import sys
from datetime import datetime as dt
from datetime import timedelta as timedelta

class QueryFailedException(Exception):
  """Wan ip source has returned an invalid response"""
	pass
def getWanIp(recordType="A"):
  """Returns the external net ip. Launches an exception if it fails."""
  #Getting external ip address using the opendns service
	resolver = dns.resolver.Resolver()
	resolver.nameservers=[socket.gethostbyname("resolver4.opendns.com")] #DNS Server
	wan_ip = resolver.resolve("myip.opendns.com", recordType)[0]
	#Verify it is a valid ip address
	try:
		ipaddress.ip_address(wan_ip) #fails if the ip address is invalid
		return str(wan_ip)
	except ValueError:
		logging.error("Error while recovering the "+recordType+" wan ip address: "+str(wan_ip))
		raise QueryFailedException()

def handle_exception(exc_type, exc_value, exc_traceback):
	"""Manages exceptions logging them"""
	if issubclass(exc_type, KeyboardInterrupt): #don't log KeyboardInterrupt...
		sys.__excepthook__(exc_type, exc_value, exc_traceback)
		return
	logging.error("Uncaught exception: ", exc_info=(exc_type, exc_value, exc_traceback))

def getFirstExpiringZoneId(zoneIdDict):
  """Returns the zone identifier with the nearest expiration time, if given a zoneIdDict type list (see below code)."""
	now = dt.now()
	maxTimeDelta = timedelta.min #start from the lowest value
	maxZI = None
	for zI in zoneIdDict:
		curTimeDelta = now - zoneIdDict[zI]["expireDate"]
		if curTimeDelta > maxTimeDelta:
			maxTimeDelta = curTimeDelta
			maxZI = zI
	return maxZI

def dtSecondsFromNow(seconds):
	"""Returns a datetime object containing now time + seconds"""
	return dt.now()+timedelta(seconds=seconds)

def positiveSecUntilExpire(expireDate):
  """Returns the difference in seconds between expireDate and now, only if it is positive. If negative it returns zero."""
	timeDiff = (expireDate - dt.now())
	return timeDiff.total_seconds()*(timeDiff>timedelta(seconds=0))

if __name__ == "__main__":
	configurationFilePath = "cloudflare-ddns-updater.ini"
	loggingFilePath = "cloudflare-ddns-updater.log"
	sys.excepthook = handle_exception #Log exceptions even if not caught
	logging.basicConfig(filename=loggingFilePath, encoding='utf-8', level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
	if not Path(configurationFilePath).exists():
		logging.error("Configuration file "+configurationFilePath+" not found! Creating an empty one...")
		try:
			with open(configurationFilePath, "w") as configFile:
				config = configparser.ConfigParser()
				config["CONFIGURATION"] = {"DebugMode":"False"}
				config["zone_identifier_here"] = {"ApiToken":"", "DNSRecordName":"", "DNSRecordType":"",
								"SecondsToSleepWhenFail": "5", "SecondsToSleepWhenSuccess": "30" }
				config.write(configFile)
		except IOError:
			logging.error("Failed while trying to create the empty configuration file! (Maybe check program permissions?) Exiting!")
			sys.exit(0) #sys.exit to return 0 in this case, so that systemctl won't try to restart the service (in this case it makes no sense to restart it). Indeed systemctl
                  #should be set with Restart=on-failure
	zIDict = {} #dictionary with every zoneIdentifier and its properties
	config = configparser.ConfigParser()
	config.read(configurationFilePath)
	if len(config.sections())==0:
		logging.error("Empty configuration file found! Exiting!")
		sys.exit(0)
	for section in config.sections():
		if section == "CONFIGURATION":
			configValues = config[section]
			if "DebugMode" in configValues:
				if configValues["DebugMode"]=="True":
					logging.getLogger().setLevel(logging.DEBUG)
			continue
		#if it isn't CONFIGURATION, it is a zone identifier
		zoneIdentifier = section
		try:
			zIValues = config[zoneIdentifier]
			apiToken = zIValues["ApiToken"]
			recordName = zIValues["DNSRecordName"]
			recordType = zIValues["DNSRecordType"]
			secToSleepFail = int(zIValues["SecondsToSleepWhenFail"]) #how long to sleep for when failing
			secToSleepSuccess = int(zIValues["SecondsToSleepWhenSuccess"]) #how long to sleep for if the ip was successfully changed or if it was already correct
		except KeyError:
			logging.error("Invalid configuration file! Delete the current one so this program will create a valid empty one. Exiting!")
			sys.exit(0)
		zIDict[zoneIdentifier] = {'apiToken':apiToken, 'recordName':recordName, 'recordType':recordType, 'secToSleepFail':secToSleepFail,
								'secToSleepSuccess':secToSleepSuccess, 'expireDate':dt.now()}
		#expireDate is the expire date/time to update this zone's fields. Here 'now' is used because the zone hasn't been updated yet.
	
	logging.info("Starting service...")
	while True:
		zoneIdentifier = getFirstExpiringZoneId(zIDict) #take the first zone id to expire based on its expireDate field
		curDict=zIDict[zoneIdentifier]

		cfActions = CloudflareApiActions(CloudflareApi(curDict["apiToken"]), zoneIdentifier)
		secToSleep = positiveSecUntilExpire(curDict["expireDate"]) #how long it will sleep
		logging.debug("Sleeping for "+str(secToSleep)+" seconds")
		time.sleep(secToSleep)
		logging.info("Updating "+zoneIdentifier+", record name "+curDict["recordName"]+", record type "+curDict["recordType"])
		try:
			currentWanIp = getWanIp()
			logging.debug("Got current Wan ip: "+currentWanIp)
		except QueryFailedException:
			curDict["expireDate"] = dtSecondsFromNow(curDict["secToSleepFail"]) #am I disconnected? Retry more often, the ip address may have changed!
			continue #Restart the loop because there is no IP address to be used
		except dns.exception.DNSException as e:
			curDict["expireDate"] = dtSecondsFromNow(curDict["secToSleepFail"])
			logging.error("DNS error: "+str(e))
			continue
		except socket.gaierror as e:
			curDict["expireDate"] = dtSecondsFromNow(curDict["secToSleepFail"])
			logging.error("Trying to access the ip finder service failed: "+str(e))
			continue
		try:
			dnsRecords = cfActions.listDNSRecords()
			dnsRecord = None
			for i in range(0,len(dnsRecords)):
				if dnsRecords[i]["name"]==curDict["recordName"] and dnsRecords[i]["type"]==curDict["recordType"]:
					dnsRecord = dnsRecords[i]
					break
			if dnsRecord == None:
				logging.error("Error while retrieving the dns record: no dns record found!")
				curDict["expireDate"] = dtSecondsFromNow(curDict["secToSleepFail"])
				continue
			dnsRecord = dnsRecords[i]
		except cfActions.ResponseError:
			curDict["expireDate"] = dtSecondsFromNow(curDict["secToSleepFail"]) #not able to update the dns record... something strange happened
			continue
		except requests.exceptions.RequestException as e:
			logging.error("Requests error: "+str(e))
			curDict["expireDate"] = dtSecondsFromNow(curDict["secToSleepFail"])
			continue
		dnsRecordTtl = dnsRecord["ttl"]
		dnsRecordName = dnsRecord["name"]
		dnsRecordId = dnsRecord["id"]
		dnsRecordAddress = dnsRecord["content"]
		dnsRecordProxied = dnsRecord["proxied"]
		logging.debug("Cloudflare dns info: "+str(dnsRecord))
		if dnsRecordAddress!=currentWanIp:
			try:
				cfActions.patchDNSRecord(dnsRecordId, curDict["recordType"], dnsRecordName, currentWanIp, dnsRecordTtl, dnsRecordProxied)
				logging.info("Success updating ip address from "+dnsRecordAddress+" to "+currentWanIp)
			except cfActions.ResponseError:
				curDict["expireDate"] = dtSecondsFromNow(curDict["secToSleepFail"])
				continue
			except requests.exceptions.RequestException as e:
				logging.error("Requests error: "+str(e))
				curDict["expireDate"] = dtSecondsFromNow(curDict["secToSleepFail"])
				continue
		curDict["expireDate"] = dtSecondsFromNow(curDict["secToSleepSuccess"]) #if the dns was successfully updated or if it is already correct, sleep
