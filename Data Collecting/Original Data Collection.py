import paho.mqtt.client as mqtt
import json
from datetime import datetime, timedelta
import time
import os
import requests
import json


# Configuration
broker = "eu1.cloud.thethings.network"  #The MQTT Broker URL
port = 1883 # Use 1883 for unencrypted, 8883 for TLS
username = "bd-test-app2@ttn" # The TTN application ID
password = "NNSXS.NGFSXX4UXDX55XRIDQZS6LPR4OJXKIIGSZS56CQ.6O4WUAUHFUAHSTEYRWJX6DDO7TL2IBLC7EV2LS4EHWZOOEPCEUOA" # The TTN API key
device_id = "lht65n-01-temp-humidity-sensor" #The sensor

#Fetch Historical Data 
def get_historical_sensor_data():
    app_id = "bd-test-app2"
    
    api_key = "NNSXS.NGFSXX4UXDX55XRIDQZS6LPR4OJXKIIGSZS56CQ.6O4WUAUHFUAHSTEYRWJX6DDO7TL2IBLC7EV2LS4EHWZOOEPCEUOA"
    url = f"https://{broker}/api/v3/as/applications/{app_id}/devices/{device_id}/packages/storage/uplink_message"

    # Set authorization header
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {
        "last": "12h"  # get messages from last 12 hours. Max 48 hours. Possible values: 12m (12 minutes)
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        response_text = response.text 
        #response_text is a json file containing historical sensor readings. Each top-level 'result' key is a sensor reading
        #parse the json text to extract the following Fields of interest and use them to build your Dashboard
        # Key_Name          Meaning
        # field1            Battery Voltage
        # field3            Humidity
        # field4            Motion Counts
        # field5            Temperature (in Celcius)
        # received_at       UTC (Coordinated Universal Time), Uganda is UTC+3
        
        with open("message_history.json", "w") as f: #optionally write data to file
            f.write(response.text.strip())
        # use the response.text to save data in persistent storage and use it to build your dashboard
    else:
        print("Error:", response.status_code, response.text)

get_historical_sensor_data()



#listen for instant notifications
topic = f"v3/{username}/devices/{device_id}/up"  # Topic for uplink messages automatically create by TTN for each sensor/device in your app

# Callback: When connected to broker
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to TTN MQTT broker!")
        client.subscribe(topic)  # Subscribe to uplink topic
    else:
        print(f"Failed to connect, return code {rc}")
        print("Reconnect failed, retrying in 5 minutes...")
        time.sleep(5*60)


# Callback: When a message is received
def on_message(client, userdata, msg):
    # print(f"Message received on topic {msg.topic}")
    
    payload = json.loads(msg.payload.decode())
    #payload contains sensor data with fields 1 to 5 as described before in get_historical_sensor_data() function
    with open("message.json", "w") as f: #optionally save data to a file
            f.write(json.dumps(payload, indent=4))
    
    # Extract the sensor data from the payload and use it for realtime notifications and building your dashboard
    
          
   
    

# Set up MQTT client
client = mqtt.Client()
client.username_pw_set(username, password)
# client.tls_set()  # Use TLS for secure connection
client.on_connect = on_connect
client.on_message = on_message

# Connect to broker and start loop
client.connect(broker, port, 60)
client.loop_forever()





