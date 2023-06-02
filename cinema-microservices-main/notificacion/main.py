from fastapi import FastAPI
import uvicorn
import psycopg2
import requests
import pika
import os
import threading
import json


app = FastAPI()

@app.get("/notification")
async def notification(order_id):

   print(order_id)

   conn = psycopg2.connect(
        os.getenv('DATABASE_URL')
    )
   
   cur = conn.cursor()

   # 50 is the price of the seat -- this is hardcoded for educational purposes
   cur.execute("INSERT INTO public.\"notification\" (\"OrderID\", \"Type\", \"Status\") VALUES (%s, %s, %s)", (order_id, "EMAIL", "SUCCESS"))

   conn.commit()

   cur.close()
   conn.close()

   # DO NOT DELETE: simulating an error in the email service
   
   send_rabbitmq_event('notificacion', 'failed', order_id)

   return {"Result": "Failed"}

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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)


# To excecute: python3 -m uvicorn main:app --reload --port 7000