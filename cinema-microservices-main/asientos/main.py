from fastapi import FastAPI
import uvicorn
import psycopg2
import requests
import pika
import os
import threading
import json

app = FastAPI()

@app.get("/seats")
async def seats(order_id, n_seats):

   print(order_id, n_seats)

   conn = psycopg2.connect(
        os.getenv('DATABASE_URL')
   )
   
   cur = conn.cursor()

   # 50 is the price of the seat -- this is hardcoded for educational purposes
   cur.execute("INSERT INTO public.\"Seat\" (\"OrderID\", \"Total\", \"Status\") VALUES (%s, %s, %s)", (order_id, n_seats, "SUCCESS"))

   conn.commit()

   cur.close()
   conn.close()

   try:
      send_notification(order_id)
   except Exception as e:
      print(e)
      send_rabbitmq_event('asientos', 'failed', order_id)

   return {"Result": "Success"}

def send_notification(order_id):
   print(order_id)
   url = "http://notificacion:8002/notification?order_id={}".format(order_id)

   response = requests.get(url)
   data = response.json()
   print(data)


def send_rabbitmq_event(service, status, order_id):
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()

    channel.queue_declare(queue='rollback')

    message = {
        'service': service,
        'status': status,
        'order_id': order_id
    }

    channel.basic_publish(exchange='', routing_key='rollback', body=json.dumps(message))

    connection.close()

def listen_for_rollback():
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()

    channel.queue_declare(queue='rollback')

    def callback(ch, method, properties, body):
        message = json.loads(body)
        if message['service'] == 'notification' and message['status'] == 'failed':
            rollback_changes(message['order_id'])

    channel.basic_consume(queue='rollback', on_message_callback=callback, auto_ack=True)

    channel.start_consuming()

def rollback_changes(order_id):
    conn = psycopg2.connect(
        os.getenv('DATABASE_URL')
    )
   
    cur = conn.cursor()

    cur.execute("DELETE FROM public.\"Seat\" WHERE \"OrderID\" = %s", (order_id,))

    conn.commit()

    cur.close()
    conn.close()

if __name__ == "__main__":
    rollback_thread = threading.Thread(target=listen_for_rollback)
    rollback_thread.start()

    uvicorn.run(app, host="0.0.0.0", port=8001)
