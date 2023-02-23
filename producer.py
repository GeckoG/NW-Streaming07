"""
This program logs into Garmin Connect and checks the most recent activity uploaded.
If the activity is new, the program will create a message alert and send it to a queue.
The program will check for new activities every 5 minutes.

Author: Matt Goeckel
Date:   22 February 2023

init_api & get_credentials methods from 'Garmin Connect API Demo' by cyberjunky
"""

import json
import logging
import os
import sys
import pika
import time

import requests
import pwinput

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

# Configure debug logging - uncomment if something breaks to see where errors are
#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup Variables
email = os.getenv("EMAIL")
password = os.getenv("PASSWORD")
api = None

activityId = 1
previous_activityId = 0

def get_credentials():
    # Ask user to input their Garmin Connect login credentials
    email = input("Login e-mail: ")
    password = pwinput.pwinput(prompt='Password: ')

    return email, password


def init_api(email, password):
    """Initialize Garmin API with your credentials."""

    try:
        ## Try to load the previous session
        with open("session.json") as f:
            saved_session = json.load(f)

            print(
                "Login to Garmin Connect using session loaded from 'session.json'...\n"
            )

            # Use the loaded session for initializing the API (without need for credentials)
            api = Garmin(session_data=saved_session)
            api.login()

    except (FileNotFoundError, GarminConnectAuthenticationError):
        # Login to Garmin Connect portal with credentials since session is invalid or not present.
        print(
            "Session file not present or turned invalid, login with your Garmin Connect credentials.\n"
            "NOTE: Credentials will not be stored, the session cookies will be stored in 'session.json' for future use.\n"
        )
        try:
            # Ask for credentials if not set as environment variables
            if not email or not password:
                email, password = get_credentials()

            api = Garmin(email, password)
            api.login()

            # Save session dictionary to json file for future use
            with open("session.json", "w", encoding="utf-8") as f:
                json.dump(api.session_data, f, ensure_ascii=False, indent=4)
        except (
            GarminConnectConnectionError,
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
            requests.exceptions.HTTPError,
        ) as err:
            logger.error("Error occurred during Garmin Connect communication: %s", err)
            return None

    return api

def send_message(host: str, queue_name: str, message: str):
    try:
        # create a blocking connection to the RabbitMQ server
        conn = pika.BlockingConnection(pika.ConnectionParameters(host))
        # use the connection to create a communication channel
        ch = conn.channel()
        # use the channel to declare a durable queue
        # a durable queue will survive a RabbitMQ server restart
        # and help ensure messages are processed in order
        # messages will not be deleted until the consumer acknowledges
        ch.queue_declare(queue=queue_name, durable=True)
        # use the channel to publish a message to the queue
        # every message passes through an exchange
        ch.basic_publish(exchange="", routing_key=queue_name, body=message)
        # print a message to the console for the user
        print(f" [x] Sent {message}")
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error: Connection to RabbitMQ server failed: {e}")
        sys.exit(1)

# Main program loop
while True:
    # Initialize API on first loop
    if not api:
        api = init_api(email, password)
    
    # Get the most recently recorded activity, store the ID as a variable
    activity = api.get_last_activity()
    activityId = activity["activityId"]

    # If the ID is the same as the previous loop, no new activity has been recorded
    # If the ID is different, it is a new activity and an alert should be sent, so execute this loop
    if activityId != previous_activityId:
        # Get some info from the activity json for our message.
        user = api.get_full_name()                          #Username
        activityType = activity["activityType"]             
        typeKey = activityType["typeKey"]                   #Activity Type
        distance = round((activity["distance"] / 1609), 2)  #Distance in Miles
        duration = round(activity["elapsedDuration"] / 60)  #Time in Minutes
        # Build our message
        message = (f'{user} just completed a {typeKey} activity. They went {distance} miles in {duration} minutes.')
        # Send the message on the queue
        send_message('localhost', 'garmin', message)
        # Now that we're done with this activity, we set it to our previous_activityId
        previous_activityId = activityId
        # Garmin has strict rate limiting, so we set the sleep timer to 5 minutes or else Garmin will return a 'Forbidden url' error.
        # Also, we don't need the notification IMMEDIATELY after finishing, within 5 minutes will be fine.
        time.sleep(300)