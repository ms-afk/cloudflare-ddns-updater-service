#!/usr/bin/python3

#Cloudflare api interface. For now limited to the functions i need

import requests
import logging

class CloudflareApi:
  """Class used to make HTTP level requests to Cloudflare's api"""
	def __init__(self, token):
		self.api_url = "https://api.cloudflare.com/client/v4/"
		self.token = token
		self.headers = {"Authorization":"Bearer "+self.token,
				"Content-Type":"application/json"}
	def request(self, method, req_path, parameters={}):
		return requests.request(method, self.api_url+req_path, json=parameters, headers=self.headers)
class CloudflareApiActions:
  """Class containing various actions from Cloudflare's api. It makes app level (json) requests to the api through a CloudflareApi object"""
	def __init__(self, cloudflareApi_object, zone_identifier):
		self.api = cloudflareApi_object
		self.zone_identifier = zone_identifier
	class ResponseError(Exception):
		"""The response has the success flag set as False, so the request didn't work."""
		pass
	@classmethod
	def _analyzeResponse(cls, json_response):
    """Takes a json response and returns the "result" part if the request was successful, otherwise it launches an exception.
		In order to understand the status of the response it looks at the "success" flag."""
		if json_response["success"] == True:
			return json_response["result"]
		logging.error("Api request error: "+str(json_response["errors"]))
		raise cls.ResponseError()
	@staticmethod
	def _createDictionary(**parameters):
    """Creates a dictionary from the given parameters, but removing all the parameters containing a "None" value.
		It is used to take a function's parameters and then to create a dictionary containing the parameters for the api request."""
		return {key:parameters[key] for key in parameters if parameters[key]!=None}
	def listDNSRecords(self):
    """Api's function which returns the DNS records of the zone"""
		path = "zones/"+self.zone_identifier+"/dns_records"
		response = self.api.request("GET", path)
		dnsRecords = self._analyzeResponse(response.json()) #lista di dizionari, ogniuno dei quali rappresenta una voce dns
		return dnsRecords
	def patchDNSRecord(self, dnsIdentifier, type, name, content, ttl, proxied=None):
    """Api's function which updates a given DNS record"""
		path = "zones/"+self.zone_identifier+"/dns_records/"+dnsIdentifier
		parameters = self._createDictionary(type=type, name=name, content=content, ttl=ttl, proxied=proxied)
		response = self.api.request("PATCH", path, parameters)
		updatedDnsRecord = self._analyzeResponse(response.json())
		return updatedDnsRecord
