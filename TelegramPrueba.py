import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import time
import random
from fpdf import FPDF
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import re
import smtplib
import tkinter as tk
from tkinter import messagebox
from queue import Queue
from threading import Thread
import logging
from tkinter import Scrollbar
import telegram
import asyncio
from telegram import Bot

# Obtén tu token de bot y el ID de chat
bot_token = '7212716298:AAGo5mpzPAwSWjlDtpfIAnM-l5UC6wFRcPM'

async def enviar_mensaje(mensaje):
    bot = Bot(bot_token)
    grupo_id = '-4223057714'
    await bot.send_message(chat_id=grupo_id, text=mensaje)

# Configuración del registro
logging.basicConfig(filename='reddit_scraper.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Variable global para mantener el recuento de procesos finalizados
procesos_finalizados = 0
# Diccionario para almacenar el estado de cada palabra clave
estados_palabras_clave = {}


# Función para actualizar el estado de una palabra clave
def actualizar_estado_palabra_clave(keyword, nuevo_estado):
    estados_palabras_clave[keyword] = nuevo_estado

def remove_non_ascii(text):
    # Eliminar caracteres no ASCII
    return re.sub(r'[^\x00-\x7F]+', '', text)


def generate_pdf(posts, keyword):
    logging.info(f"Generando PDF para '{keyword}'...")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Reporte de Reddit para la palabra clave: {keyword}", ln=True, align='C')
    pdf.ln(10)

    for i, (title, comments) in enumerate(posts, start=1):
        pdf.cell(0, 10, txt=f"{i}. {title} - {comments} comentarios", ln=True)

    pdf_filename = "reporte_reddit.pdf"
    pdf.output(pdf_filename)
    return pdf_filename


def scrape_reddit(keyword):
    logging.info(f"Scraping iniciado para '{keyword}'...")
    base_url = 'https://www.reddit.com/search/?q={}&type=link'.format(keyword)

    headers = {
        'User-Agent': UserAgent().random,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Connection': 'keep-alive'
    }

    # Inicializar variables
    posts = []
    offset = 0
    post_limit = 300

    while len(posts) < post_limit:
        url = f"{base_url}&count={offset}"

        # Añadir un retraso aleatorio entre 1 y 5 segundos antes de hacer la solicitud
        # time.sleep(random.uniform(1, 5))

        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to fetch page, status code: {response.status_code}")

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extraer títulos de las publicaciones
        titles = soup.find_all("a", class_="text-16 xs:text-18 line-clamp-3 text-ellipsis text-neutral-content-strong font-semibold mb-xs no-underline hover:no-underline visited:text-neutral-content-weak")
        # Extraer número de comentarios
        comments = soup.find_all('faceplate-number')

        for title, comment in zip(titles, comments):
            post_title = title.get_text().strip()
            post_title = remove_non_ascii(post_title)
            comment_count = comment.get('number')
            if comment_count is not None:
                posts.append((post_title, comment_count))

        # Actualizar el offset para obtener más resultados en la siguiente iteración
        offset += 25  # Reddit muestra 25 resultados por página

        if len(titles) == 0:
            # No hay más resultados
            break

    return posts[:post_limit]


def send_email(recipient_email, subject, body, attachment):
    global procesos_finalizados
    sender_email = "santiagonueveuno@gmail.com"
    sender_password = "qfwy etqf ieib erdj"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    with open(attachment, "rb") as attach_file:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attach_file.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename= {attachment}")
        msg.attach(part)

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
    procesos_finalizados += 1
    print("Finalizados " + procesos_finalizados)


def process_queue(queue):
    instances = []
    while True:
        if not instances:
            # If no instances running, create one for processing queue
            t = Thread(target=process_queue_instance, args=(queue,))
            t.daemon = True
            t.start()
            instances.append(t)
        if queue.qsize() > 5:
            # Create a new instance if queue size exceeds 5
            t = Thread(target=process_queue_instance, args=(queue,))
            t.daemon = True
            t.start()
            instances.append(t)
        time.sleep(10)  # Check queue size every 10 seconds


def process_queue_instance(queue):
    while not queue.empty():
        keyword = queue.get()
        asyncio.run(main(keyword))
        queue.task_done()


# Proceso principal
async def main(keyword):
    try:
        await enviar_mensaje("Se ha ingresado la palabra " + keyword)
        actualizar_estado_palabra_clave(keyword, "Scraping")
        posts = scrape_reddit(keyword)
        actualizar_estado_palabra_clave(keyword, "PDF generado")
        generate_pdf(posts, keyword)
        pdf_filename = generate_pdf(posts, keyword)
        actualizar_estado_palabra_clave(keyword, "Correo enviado")
        send_email("david.rivera04@uptc.edu.co", f"Reporte de Reddit para {keyword}", "Adjunto el reporte de Reddit.",
                   pdf_filename)
    except Exception as e:
        logging.error(f"Error al procesar '{keyword}': {e}")


def add_to_queue(keyword):
    queue.put(keyword)
    messagebox.showinfo("Added", f"'{keyword}' added to queue.")


def create_gui(queue):
    root = tk.Tk()
    root.title("Reddit Web Scraping Queue")

    def add_keyword():
        keyword = keyword_entry.get()
        add_to_queue(keyword)
        keyword_entry.delete(0, tk.END)

    # Modificación de la función de actualización de registros para mostrar información de la cola
    def update_logs():
        logs_text.delete(1.0, tk.END)
        logs_text.insert(tk.END, f"Queue Size: {queue.qsize()}\n")
        logs_text.insert(tk.END, f"Procesos en cola: {queue.queue}\n")  # Mostrar procesos en la cola
        logs_text.insert(tk.END, f"Procesos pendientes: {queue.unfinished_tasks}\n")  # Mostrar procesos pendientes
        # Mostrar el proceso actual de cada palabra clave en la cola
        for keyword, estado in estados_palabras_clave.items():
                logs_text.insert(tk.END, f"{keyword}: {estado}\n")
        # Calcular la cantidad de procesos finalizados
        logs_text.insert(tk.END, f"Procesos finalizados: {procesos_finalizados}\n")  # Mostrar procesos finalizados
        root.after(1000, update_logs)  # Llamar a la función nuevamente después de 1 segundo


    keyword_label = tk.Label(root, text="Keyword:")
    keyword_label.grid(row=0, column=0, padx=10, pady=10)

    keyword_entry = tk.Entry(root, width=30)
    keyword_entry.grid(row=0, column=1, padx=10, pady=10)

    add_button = tk.Button(root, text="Add to Queue", command=add_keyword)
    add_button.grid(row=0, column=2, padx=10, pady=10)

    # Crear un widget Scrollbar vertical
    scrollbar = Scrollbar(root, orient="vertical")

    # Crear un widget de texto para mostrar los logs y asociarlo con el scrollbar
    logs_text = tk.Text(root, height=100, width=50, yscrollcommand=scrollbar.set)
    logs_text.grid(row=1, columnspan=3, padx=10, pady=10)

    # Configurar el scrollbar para desplazar el widget de texto
    scrollbar.config(command=logs_text.yview)
    scrollbar.grid(row=1, column=3, sticky="ns")

    update_logs()
    root.after(1000, update_logs)  # Update logs every second

    root.geometry("400x200")
    root.mainloop() 
if __name__ == "__main__":
    queue = Queue()
    instances = []
    t = Thread(target=process_queue, args=(queue,))
    t.daemon = True
    t.start()

    create_gui(queue)
