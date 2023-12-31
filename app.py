from flask import Flask, render_template, jsonify, request
import paho.mqtt.client as mqtt
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
import threading
import time
import statistics
from bson.json_util import dumps
#from flask_mail import Mail, Message
app = Flask(__name__)

notification_sent = False

# Reemplaza con tus credenciales de MongoDB Atlas
mongo_client = MongoClient("mongodb+srv://alejo:123@cluster0.6lushwm.mongodb.net/")
db = mongo_client["iot"]
collection = db["data_gas"]
collection2 = db["data_temp"]

# Configuración de Flask-Mail
# app.config['MAIL_SERVER'] = 'smtp.gmail.com'
# app.config['MAIL_PORT'] = 587
# app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USERNAME'] = 'alejotrujillo11@gmail.com'
# app.config['MAIL_PASSWORD'] = 'ecrb rmlt sqji lrji'
# app.config['MAIL_DEFAULT_SENDER'] = ('Alejandro T.', 'alejotrujillo11@gmail.com')
# mail = Mail(app)

# Crear el DataFrame de Pandas para almacenar los datos
df = pd.DataFrame(columns=["Timestamp", "Data"])

# Configurar el cliente MQTT
mqtt_client = mqtt.Client()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conectado al broker MQTT")
        mqtt_client.subscribe("IOT/GAS")
        mqtt_client.subscribe("IOT/TEMP")
    else:
        print("Error de conexión: ", rc)


# ...

def on_message(client, userdata, msg):
    data = msg.payload.decode("utf-8")
    timestamp = datetime.now()
    topic = msg.topic

    print(data, ' ', topic)

    # Validar que el dato recibido sea numérico
    try:
        float_data = float(data)
    except ValueError:
        print(f"Error: El valor recibido ({data}) en el tópico {topic} no es numérico.")
        return

    # Guardar en MongoDB
    if topic == "IOT/GAS":
        document = {"timestamp": timestamp, "data": float_data}
        collection.insert_one(document)

    elif topic == "IOT/TEMP":
        document = {"timestamp": timestamp, "data": float_data}
        collection2.insert_one(document)

    # Actualizar el DataFrame
    df.loc[len(df)] = [timestamp, float_data]

# ...



# def send_email(subject, body):
#     msg = Message(subject, recipients=['alejandro.1701520969@ucaldas.edu.co'])
#     msg.body = body
#     mail.send(msg)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/stream')
def stream():
    def event_stream():
        while True:
            # Obtener el último dato de la base de datos
            latest_data = collection.find_one(sort=[("timestamp", -1)])

            if latest_data:
                yield f"data: {latest_data['data']}\n\n"
            time.sleep(1)

    return app.response_class(event_stream(), mimetype="text/event-stream")

@app.route('/streamTemp')
def streamTemp():
    def event_stream_temp():
        while True:
            # Obtener el último dato de la base de datos
            latest_data = collection2.find_one(sort=[("timestamp", -1)])

            if latest_data:
                # Enviar el evento con el tipo de evento "message"
                yield f"data: {latest_data['data']}\n\n"
            time.sleep(1)

    # Establecer el tipo de contenido correctamente a "text/event-stream"
    return app.response_class(event_stream_temp(), mimetype="text/event-stream")

@app.route('/stats')
def stats():
    global notification_sent
    # Calcular estadísticas directamente desde MongoDB Atlas
    cursor = collection.find()
    data_values = [doc['data'] for doc in cursor]

    if data_values:
        latest_data = data_values[-1]
        mean_value = statistics.mean(data_values)
        max_value = max(data_values)
        min_value = min(data_values)

        # if latest_data > 30 and not notification_sent:
        #     send_email('Alerta de Umbral', f'El último dato es {latest_data}, ¡se ha superado el umbral!')
        #     notification_sent = True
        # elif latest_data <= 30:
        #     notification_sent = False

        return jsonify({
            'latest_data': latest_data,
            'mean_value': mean_value,
            'max_value': max_value,
            'min_value': min_value
        })
    else:
        return jsonify({})

@app.route('/send_message')
def send_message():
        message = request.args.get('message')
        print(f"Recibido mensaje: {message}")

        # Verificar si el cliente MQTT está conectado antes de publicar
        if mqtt_client.is_connected():
            # Cambia el tópico a "ALERT"
            mqtt_client.publish("IOT/ALERT", message)
            return jsonify({'status': 'success', 'message': f'Mensaje {message} enviado al tópico ALERT'})
        else:
            return jsonify({'status': 'error', 'message': 'Cliente MQTT no está conectado'})
        


@app.route('/collection_data')
def collection_data():
    # Obtener datos de la colección y devolver como JSON
    cursor = collection.find().sort('timestamp', -1).limit(10)  # Ajusta según tus necesidades
    data = [{'timestamp': doc['timestamp'].strftime('%Y-%m-%d %H:%M:%S'), 'data': doc['data']} for doc in cursor]
    data.reverse()  # Invertir el orden para mostrar los datos más recientes primero
    return jsonify(data)


if __name__ == '__main__':
    # Configuración del cliente MQTT
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    # Conexión al servidor MQTT
    mqtt_client.connect("91.121.93.94", 1883, 60)

    # Iniciar hilo MQTT
    mqtt_thread = threading.Thread(target=mqtt_client.loop_forever)
    mqtt_thread.start()

    # Iniciar la aplicación Flask
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
