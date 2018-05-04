import requests

RANCHER_HOST = ""
RANCHER_PORT = 
RANCHER_API_VERSION = "v1"

response = requests.get("http://%s:%s/%s/containers" %
                        (RANCHER_HOST, RANCHER_PORT, RANCHER_API_VERSION))

for datapoint in response.json()["data"]:
    print("Container ID     : %s" % datapoint["data"]["dockerContainer"]["Id"])
    print("Image            : %s" % datapoint["data"]["dockerContainer"]["Image"])
    print
