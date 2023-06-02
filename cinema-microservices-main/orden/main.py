from fastapi import FastAPI
import uvicorn
import psycopg2
import requests
import pika
import os
import threading
import json

app = FastAPI()

@app.get("/order")
async def order(client_id, n_seats):

   print(client_id, n_seats)

   conn = psycopg2.connect(
        os.getenv('DATABASE_URL')
   )
   
   cur = conn.cursor()

   cur.execute("INSERT INTO public.\"Order\" (\"NumberOfSeats\", \"ClientID\", \"Status\") VALUES (%s, %s, %s)", (n_seats, client_id, "SUCCESS"))

   conn.commit()

   cur.execute("SELECT MAX(\"ID\") FROM public.\"Order\";")
   order_id = cur.fetchone()

   cur.close()
   conn.close()

   # DO NOT CHANGE THIS: Lets assume that this send to a kafka and we dont know if fails or not
   try:
      send_order(client_id, n_seats, order_id)
   except Exception as e:
      print(e)
      send_rabbitmq_event('orden', 'failed', order_id)


   return {"Result": "Success"}

def send_order(client_id, n_seats, order_id):
   print(client_id, n_seats, order_id[0])
   url = "http://pago:8004/payment?order_id={}&n_seats={}".format(order_id[0], n_seats)

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
      rollback_changes(message['order_id'])

    channel.basic_consume(queue='rollback', on_message_callback=callback, auto_ack=True)

    channel.start_consuming()

def rollback_changes(order_id):
    conn = psycopg2.connect(
        os.getenv('DATABASE_URL')
    )
   
    cur = conn.cursor()

    cur.execute("DELETE FROM public.\"Order\" WHERE \"OrderID\" = %s", (order_id,))

    conn.commit()

    cur.close()
    conn.close()

if __name__ == "__main__":
    rollback_thread = threading.Thread(target=listen_for_rollback)
    rollback_thread.start()

    uvicorn.run(app, host="0.0.0.0", port=8003)


# To excecute: python3 -m uvicorn main:app --reload --port 7000