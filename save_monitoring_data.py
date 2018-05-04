import json
import requests
from websocket import create_connection

RANCHER_HOST = ""
RANCHER_PORT = 
RANCHER_API_VERSION = "v1"

response = requests.get("http://%s:%s/%s/containers" %
                        (RANCHER_HOST, RANCHER_PORT, RANCHER_API_VERSION))

# Get the Rancher IDs of currently running and recently exited containers.
rancher_id_list = []
for datapoint in response.json()["data"]:
    # Each datapoint contains all the information Rancher can provide for a
    # single container.
    # Store the Rancher ID of the container for future API calls
    rancher_id_list.append(datapoint["id"])

for rancher_id in rancher_id_list:
    # Get the container stats page
    response = requests.get("http://%s:%s/%s/containers/%s/containerstats" %
                            (RANCHER_HOST, RANCHER_PORT, RANCHER_API_VERSION,
                             rancher_id))

    container_stats = response.json()
    # Work out the websocket link and token to access it
    token = container_stats["token"]
    monitoring_url = container_stats["url"]

    # Get the latest monitoring data
    web_socket = create_connection("%s?token=%s" % (monitoring_url, token))
    # web_socket.recv() returns a list. I am assuming that the list is always
    # size 1. If that is a false assumption, this will fail loudly.
    [monitoring_data] = json.loads(web_socket.recv())
    # close the connection
    web_socket.close()

    # Print metrics
    print("Time             : %s" % monitoring_data["timestamp"])
    print("Container ID     : %s" % monitoring_data["id"])
    print("CPU Usage        : %i Seconds" % (int(monitoring_data["cpu"]["usage"]["total"]) * 0.000000001))
    print("Storage Usage    : %s Bytes" % monitoring_data["memory"]["usage"])

    # There seems to be a nice way to get the total rx and tx bytes, but it
    # doesn't seem to be set properly in the JSON returned by the API.
    # So I am summing all the individual interfaces.
    rx_bytes = 0
    tx_bytes = 0
    for interface in monitoring_data["network"]["interfaces"]:
        rx_bytes = rx_bytes + interface["rx_bytes"]
        tx_bytes = tx_bytes + interface["tx_bytes"]

    print("Network Inbound  : %s Bytes" % rx_bytes)
    print("Network Outbound : %s Bytes" % tx_bytes)
    print("")
