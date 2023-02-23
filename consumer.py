'''
This program receives messages from a queue, and sends them as text messages to a number.
To use, input your Twilio credentials for 'account_sid' and 'auth_token', along with the desired phone number in the 'send_text()' method

Author: Matt Goeckel
Date:   22 February 2023
'''
import pika
import sys
from twilio.rest import Client

def send_text(text):
    # Set up variables for Twilio account - these should be unique to you
    account_sid = 'xxxxxx'
    auth_token = 'xxxxxx'

    # Set up Twilio client
    client = Client(account_sid, auth_token)

    # Define the phone number you want to send the message to and the message itself
    to_phone_number = '+17857090504'
    message = text

    # Send the message using the Twilio API
    message = client.messages.create(
        body=message,
        from_='+14793832936',  # This is the Twilio phone number you've purchased or obtained
        to=to_phone_number
    )

    # Print the message SID to confirm that it was sent successfully
    print(f'Message Sent: {message.sid}')


# define a callback function to be called when a message is received
def callback(ch, method, properties, body):
    # decode the binary message body to a string
    textmessage = body.decode()
    print(f" [x] Received: {textmessage}")
    # acknowledge the message was received and processed 
    # (now it can be deleted from the queue)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    # Use the send_text method to send the text alert
    send_text(textmessage)


def receive_message(hn: str = "localhost", qn: str = "task_queue"):
    """ Continuously listen for task messages on a named queue."""

    # when a statement can go wrong, use a try-except block
    try:
        # try this code, if it works, keep going
        # create a blocking connection to the RabbitMQ server
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=hn))

    # except, if there's an error, do this
    except Exception as e:
        print()
        print("ERROR: connection to RabbitMQ server failed.")
        print(f"Verify the server is running on host={hn}.")
        print(f"The error says: {e}")
        print()
        sys.exit(1)

    try:
        # use the connection to create a communication channel
        channel = connection.channel()

        # use the channel to declare a durable queue
        # a durable queue will survive a RabbitMQ server restart
        # and help ensure messages are processed in order
        # messages will not be deleted until the consumer acknowledges
        channel.queue_declare(queue=qn, durable=True)

        # configure the channel to listen on a specific queue,  
        # use the callback function named callback,
        # and do not auto-acknowledge the message (let the callback handle it)
        channel.basic_consume( queue=qn, on_message_callback=callback)

        # print a message to the console for the user
        print(" [*] Ready to receive messages. To exit press CTRL+C")

        # start consuming messages via the communication channel
        channel.start_consuming()

    # except, in the event of an error OR user stops the process, do this
    except Exception as e:
        print()
        print("ERROR: something went wrong.")
        print(f"The error says: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print(" User interrupted continuous listening process.")
        sys.exit(0)
    finally:
        print("\nClosing connection. Goodbye.\n")
        connection.close()


# If this is the program being run, then execute the code below
if __name__ == "__main__":
    # call the main function with the information needed
    receive_message("localhost", "garmin")